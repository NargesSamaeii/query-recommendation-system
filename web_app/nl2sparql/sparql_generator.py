"""
SPARQL Query Generator

Generates SPARQL queries from natural language questions.
"""

import json
import logging
import re
import textwrap
from .schema_formatter import SchemaFormatter


class SPARQLGenerator:
    """Generates SPARQL queries from questions and schema."""
    
    def __init__(self, llm):
        """
        Initialize generator with LLM instance.
        
        Args:
            llm: Language model instance for generation
        """
        self.llm = llm
        self.logger = logging.getLogger("nl2sparql.pipeline")
        self.missing_id_prompt = None
        self.entity_extraction_prompt = None
        self.entity_extraction_response = None
        self.entity_extraction_mentions = []
        self.last_prompt = None
        self.query_repair_prompt = None

    def _normalize_entity_text(self, text):
        value = (text or "").strip().lower()
        value = re.sub(r"[^a-z0-9\s_-]", " ", value)
        value = re.sub(r"[_-]", " ", value)
        value = re.sub(r"\s+", " ", value).strip()
        return value

    def _compact_iri_for_prompt(self, iri, prefixes):
        """Return prefixed form when possible, otherwise wrapped absolute IRI."""
        value = str(iri or "").strip()
        if not value:
            return value

        for prefix, base in (prefixes or {}).items():
            if value.startswith(base):
                return f"{prefix}:{value[len(base):]}"

        return f"<{value}>"

    def _strip_toon_prefix_section(self, formatted_schema_str):
        """Remove the TOON prefix block so the prompt can render PREFIXES separately."""
        if not formatted_schema_str:
            return formatted_schema_str

        lines = formatted_schema_str.splitlines()
        cleaned = []
        skipping_prefix_block = False
        for line in lines:
            stripped = line.strip()
            if stripped == "Prefixes:":
                skipping_prefix_block = True
                continue
            if skipping_prefix_block:
                if stripped.startswith("PREFIX "):
                    continue
                if stripped.startswith("--- "):
                    skipping_prefix_block = False
                    cleaned.append(line)
                continue
            cleaned.append(line)
        return "\n".join(cleaned).strip()

    def _parse_entity_mentions_response(self, response_text, max_mentions=6):
        if not response_text:
            return []

        cleaned = self._clean_sparql_response(response_text)
        if not cleaned:
            cleaned = response_text.strip()

        mentions = []

        # Prefer strict JSON list
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                for item in parsed:
                    text = self._normalize_entity_text(str(item))
                    if text and text not in mentions:
                        mentions.append(text)
        except Exception:
            pass

        # Try extracting first JSON-like list from text
        if not mentions:
            list_match = re.search(r'\[(.*?)\]', cleaned, flags=re.DOTALL)
            if list_match:
                candidate = "[" + list_match.group(1) + "]"
                try:
                    parsed = json.loads(candidate)
                    if isinstance(parsed, list):
                        for item in parsed:
                            text = self._normalize_entity_text(str(item))
                            if text and text not in mentions:
                                mentions.append(text)
                except Exception:
                    pass

        # Fallback: parse lines / comma-separated output
        if not mentions:
            rough_parts = []
            for line in cleaned.splitlines():
                line = line.strip().lstrip("-•*").strip()
                if line:
                    rough_parts.extend([part.strip() for part in line.split(",") if part.strip()])
            for part in rough_parts:
                text = self._normalize_entity_text(part)
                if text and text not in mentions:
                    mentions.append(text)

        return mentions[:max_mentions]

    def _extract_question_entities_via_llm(self, question, class_priority_list, formatted_schema_str):
        class_list_text = "\n".join(f"- {class_name}" for class_name in class_priority_list) if class_priority_list else "- (none)"
        prompt = f"""You are a named-entity extractor specialized in knowledge graph queries. 

TASK:
Given a question and a schema, return ONLY the entity names found in the question that require IRI lookup — i.e., named things that must be matched against instance data.

Rules:
1. Return ONLY a JSON array of strings.
2. Include concrete, named entities: specific domain values like expertise areas, department names, product names, country names, organization names, categories, IDs, etc.
3. Exclude generic functional/helper words: verbs (list, show, apply), question words (what, which), and nouns that are class labels used generically (e.g., "employee", "supplier", "name").
4. Exclude structural/relational words (e.g., "from", "of", "responsible", "expert") even if domain-adjacent.
5. 5. Extract ONLY from the QUESTION text. Ignore any entity names that appear solely in the SCHEMA or instance examples.

SCHEMA:
{formatted_schema_str}

QUESTION:
\"\"\"{question}\"\"\"

OUTPUT FORMAT EXAMPLE:
["u990 lcd inductor", "russia"]
""".strip()

        self.entity_extraction_prompt = prompt
        try:
            response = self.llm.generate(prompt, max_tokens=300)
            self.entity_extraction_response = response
            mentions = self._parse_entity_mentions_response(response, max_mentions=6)
            self.entity_extraction_mentions = list(mentions)
            self.logger.info(
                "Missing-ID entity extraction generated %s mention(s): %s",
                len(mentions),
                mentions,
            )
            return mentions
        except Exception as e:
            self.logger.warning(f"Missing-ID entity extraction via LLM failed: {e}")
            self.entity_extraction_response = ""
            self.entity_extraction_mentions = []
            return []

    def _clean_sparql_response(self, response):
        """
        Clean LLM response to extract pure SPARQL query.
        
        Args:
            response: Raw LLM response string
            
        Returns:
            Cleaned SPARQL query string
        """
        if not response:
            return ""

        # If model returns XML wrapper format, extract query block first.
        # Supports:
        #   <out><query> ...sparql... </query></out>
        xml_query_match = re.search(r'<query>\s*(.*?)\s*</query>', response, flags=re.IGNORECASE | re.DOTALL)
        if xml_query_match:
            response = xml_query_match.group(1).strip()
        
        # Remove markdown code fences globally (including separators between multiple queries)
        response = re.sub(r'```\s*sparql\s*', '', response, flags=re.IGNORECASE)
        response = re.sub(r'```', '', response)
        
        # Remove any text before PREFIX or SELECT
        lines = response.split('\n')
        start_idx = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(('PREFIX', 'SELECT', 'ASK', 'CONSTRUCT', 'DESCRIBE')):
                start_idx = i
                break
        
        response = '\n'.join(lines[start_idx:])

        # Fix PREFIX declarations that are missing angle brackets around the URI.
        # e.g.  PREFIX foo: http://example.org/  →  PREFIX foo: <http://example.org/>
        response = re.sub(
            r'(PREFIX\s+[\w-]*:\s*)(https?://[^\s<>"{}|\\^`]+)',
            r'\1<\2>',
            response,
            flags=re.IGNORECASE,
        )

        return response.strip()

    def _sanitize_malformed_prefixed_iris(self, query):
        """Fix malformed tokens that concatenate full IRI and prefixed name.

        Example malformed token:
            <http://ld.company.org/prod-vocab/>prod_vocab:Supplier
        Rewritten as:
            prod_vocab:Supplier
        """
        if not query:
            return query

        # Replace any <...> immediately followed by a prefixed name token.
        # This pattern is invalid SPARQL and should collapse to the prefixed token.
        pattern = re.compile(r'<[^>]+>\s*([A-Za-z_][A-Za-z0-9_\-]*:[A-Za-z_][A-Za-z0-9_\-]*)')
        return pattern.sub(r'\1', query)

    def _ensure_required_prefixes(self, query, prefixes):
        """Inject missing PREFIX declarations for used prefixed names.

        Adds only prefixes that are both:
        1) used in the query body, and
        2) available in schema prefixes.
        """
        if not query:
            return query

        available_prefixes = prefixes or {}
        if not available_prefixes:
            return query

        lines = query.splitlines()
        declared_prefixes = set()

        prefix_decl_re = re.compile(
            r'^\s*PREFIX\s+([A-Za-z_][A-Za-z0-9_\-]*)\s*:\s*<[^>]+>\s*$',
            flags=re.IGNORECASE,
        )
        used_prefix_re = re.compile(r'\b([A-Za-z_][A-Za-z0-9_\-]*):[A-Za-z0-9_\-.%]+\b')

        for line in lines:
            match = prefix_decl_re.match(line)
            if match:
                declared_prefixes.add(match.group(1))

        used_prefixes = set()
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.upper().startswith("PREFIX "):
                continue
            for prefix_name in used_prefix_re.findall(line):
                used_prefixes.add(prefix_name)

        missing_prefixes = sorted(
            pfx for pfx in used_prefixes
            if pfx not in declared_prefixes and pfx in available_prefixes
        )
        if not missing_prefixes:
            return query

        prefix_lines = [f"PREFIX {pfx}: <{available_prefixes[pfx]}>" for pfx in missing_prefixes]

        # Keep Virtuoso directives/comments at the very top, then inject PREFIX lines.
        insert_at = 0
        while insert_at < len(lines):
            stripped = lines[insert_at].strip()
            if (
                not stripped
                or stripped.lower().startswith("define ")
                or stripped.startswith("#")
                or stripped.upper().startswith("PREFIX ")
            ):
                insert_at += 1
                continue
            break

        updated_lines = lines[:insert_at] + prefix_lines + lines[insert_at:]
        return "\n".join(updated_lines)

    def _retain_complete_query_blocks(self, query):
        """Keep only complete SPARQL query blocks, dropping truncated trailing fragments."""
        if not query:
            return query

        text = query.strip()
        if not text:
            return text

        lines = text.splitlines()
        query_start_re = re.compile(r'^\s*(SELECT|ASK|CONSTRUCT|DESCRIBE)\b', re.IGNORECASE)
        prefix_re = re.compile(r'^\s*PREFIX\b', re.IGNORECASE)

        complete_blocks = []
        i = 0
        total = len(lines)

        while i < total:
            while i < total and not lines[i].strip():
                i += 1

            if i >= total:
                break

            block_prefixes = []
            while i < total and prefix_re.match(lines[i]):
                block_prefixes.append(lines[i])
                i += 1

            while i < total and not query_start_re.match(lines[i]):
                i += 1

            if i >= total:
                break

            query_lines = [lines[i]]
            brace_depth = lines[i].count("{") - lines[i].count("}")
            saw_open_brace = "{" in lines[i]
            i += 1

            while i < total:
                line = lines[i]
                query_lines.append(line)
                brace_depth += line.count("{") - line.count("}")
                if "{" in line:
                    saw_open_brace = True
                i += 1

                if saw_open_brace and brace_depth <= 0:
                    break

            block_text = "\n".join((block_prefixes + query_lines)).strip()
            upper = block_text.upper()
            has_query_shape = ("SELECT" in upper or "ASK" in upper or "CONSTRUCT" in upper or "DESCRIBE" in upper) and "WHERE" in upper
            balanced_braces = block_text.count("{") == block_text.count("}")
            if has_query_shape and balanced_braces:
                complete_blocks.append(block_text)

        if complete_blocks:
            return "\n\n".join(complete_blocks)

        upper = text.upper()
        if "SELECT" in upper and "WHERE" in upper and text.count("{") == text.count("}"):
            return text
        return ""

    def _normalize_partial_match_values(self, query):
        """Normalize simple plural partialMatch tokens to singular (e.g., Transistors -> Transistor)."""
        if not query:
            return query

        def singularize_token(token):
            text = token.strip()
            lower = text.lower()
            if len(text) > 3 and lower.endswith("ies"):
                return text[:-3] + "y"

            # switches -> switch, boxes -> box, classes -> class
            if len(text) > 4 and lower.endswith(("ses", "xes", "zes", "ches", "shes")):
                return text[:-2]

            # states -> state, components -> component
            if len(text) > 4 and lower.endswith("s") and not lower.endswith("ss"):
                return text[:-1]
            return text

        def repl(match):
            inner = match.group(1)
            normalized = re.sub(
                r'"([^"]+)"',
                lambda m: f'"{singularize_token(m.group(1))}"',
                inner
            )
            return f"VALUES ?partialMatch {{ {normalized} }}"

        return re.sub(
            r'VALUES\s+\?partialMatch\s*\{\s*(.*?)\s*\}',
            repl,
            query,
            flags=re.IGNORECASE | re.DOTALL
        )

    def _rewrite_literal_equality_to_filter(self, query):
        """Rewrite string literal equality triples into case-insensitive FILTER matching.

        Example:
            ?employee prod_vocab:name "John" .
        becomes:
            ?employee prod_vocab:name ?_text_match_1 .
            FILTER(CONTAINS(LCASE(STR(?_text_match_1)), LCASE("John")))
        """
        if not query:
            return query

        lines = query.split('\n')
        rewritten = []
        counter = 0

        triple_pattern = re.compile(
            r'^(\s*)(\?[A-Za-z_][A-Za-z0-9_]*)\s+([^\s]+)\s+"([^"\\]*)"(?:\^\^[^\s]+|@[A-Za-z\-]+)?\s*\.\s*$'
        )

        for line in lines:
            match = triple_pattern.match(line)
            if not match:
                rewritten.append(line)
                continue

            indent, subject, predicate, literal_value = match.groups()

            # Keep explicit type assertions untouched
            predicate_lower = predicate.lower()
            if predicate_lower in {"a", "rdf:type"}:
                rewritten.append(line)
                continue

            counter += 1
            var_name = f"?_text_match_{counter}"
            rewritten.append(f"{indent}{subject} {predicate} {var_name} .")
            rewritten.append(
                f'{indent}FILTER(CONTAINS(LCASE(STR({var_name})), LCASE("{literal_value}")))'
            )

        return '\n'.join(rewritten)

    def _resolve_class_key(self, class_name_input, all_classes):
        """Resolve class key from exact/prefixed/local class name."""
        if not class_name_input:
            return None

        if class_name_input in all_classes:
            return class_name_input

        local_name = class_name_input.split(":")[-1]
        for key in all_classes.keys():
            if key.split(":")[-1] == local_name:
                return key

        return None

    def _extract_linked_class_key(self, datatype_value, all_classes):
        """Extract linked class key from property datatype if it points to a known class."""
        if not datatype_value:
            return None

        datatype_text = str(datatype_value).strip()
        if not datatype_text:
            return None

        # Ignore scalar XML schema datatypes
        if "XMLSchema#" in datatype_text:
            return None

        # Direct prefixed class reference (e.g., prod_vocab:ProductCategory)
        if ":" in datatype_text and not datatype_text.startswith("http"):
            return self._resolve_class_key(datatype_text, all_classes)

        # Full IRI - try matching by suffix or exact URI if class keys are URI-like
        candidate_local = datatype_text.rstrip("/>").split("#")[-1].split("/")[-1]
        if candidate_local:
            resolved = self._resolve_class_key(candidate_local, all_classes)
            if resolved:
                return resolved

        return self._resolve_class_key(datatype_text, all_classes)

    def _extract_linked_class_candidates(self, datatype_value, all_classes, prefixes):
        """Return resolved and placeholder linked classes from datatype field."""
        if not datatype_value:
            return []

        values = datatype_value if isinstance(datatype_value, (list, tuple, set)) else [datatype_value]
        candidates = []

        for value in values:
            text = str(value).strip().strip("<>")
            if not text:
                continue

            if "XMLSchema#" in text:
                continue

            resolved = self._extract_linked_class_key(text, all_classes)
            if resolved:
                candidates.append((resolved, False))
                continue

            prefixed_value = None
            if ":" in text and not text.startswith("http"):
                prefix = text.split(":", 1)[0]
                if prefix in prefixes:
                    prefixed_value = text
            elif text.startswith("http"):
                for pfx, uri in prefixes.items():
                    if text.startswith(uri):
                        local = text[len(uri):]
                        if local:
                            prefixed_value = f"{pfx}:{local}"
                        break

            if prefixed_value:
                candidates.append((prefixed_value, True))

        return candidates

    def _canonical_entity_label(self, label):
        """Normalize display labels used in missing_iris to a canonical mention-like key."""
        text = (label or "").strip()
        if not text:
            return ""
        # Remove collision suffixes like "(Q123)" or "[2]" appended during dedupe.
        text = re.sub(r"\s*\[[0-9]+\]\s*$", "", text)
        text = re.sub(r"\s*\([^)]*\)\s*$", "", text)
        return self._normalize_entity_text(text)

    def _mention_matches_label(self, mention, label):
        """Heuristic mention->label matcher for grouping resolved IRIs in prompt context."""
        mention_norm = self._normalize_entity_text(mention)
        label_norm = self._normalize_entity_text(label)
        if not mention_norm or not label_norm:
            return False

        mention_tokens = [token for token in mention_norm.split() if token]
        label_tokens = [token for token in label_norm.split() if token]
        label_set = set(label_tokens)
        if not mention_tokens or not label_set:
            return False

        honorifics = {"mr", "ms", "mrs", "dr", "prof"}
        core_tokens = [token for token in mention_tokens if token not in honorifics]
        if not core_tokens:
            core_tokens = mention_tokens

        id_tokens = [token for token in core_tokens if re.search(r"\d", token)]
        text_tokens = [token for token in core_tokens if not re.search(r"\d", token)]
        if id_tokens:
            if not all(token in label_set for token in id_tokens):
                return False
            if text_tokens and not any(token in label_set for token in text_tokens):
                return False
            return True

        if len(core_tokens) == 1:
            return core_tokens[0] in label_set

        overlap_count = sum(1 for token in core_tokens if token in label_set)
        min_overlap = max(1, len(core_tokens) // 2)
        return overlap_count >= min_overlap

    def _extract_question_mentions_fallback(self, question):
        """Extract mention-like phrases from question when LLM extraction is empty.

        This is a lightweight heuristic to preserve grouping keys such as
        "ms brant" in RESOLVED ENTITIES when the extraction model is unstable.
        """
        q = (question or "").strip().lower()
        if not q:
            return []

        mentions = []
        seen = set()
        # Capture honorific + name patterns (e.g., "ms brant", "dr shah").
        for m in re.finditer(r"\b(mr|ms|mrs|dr|prof)\.?\s+([a-z][a-z0-9_-]{1,})\b", q):
            candidate = self._normalize_entity_text(f"{m.group(1)} {m.group(2)}")
            if candidate and candidate not in seen:
                mentions.append(candidate)
                seen.add(candidate)

        return mentions

    def _build_class_copy(self, class_data, relevant_props=None, max_properties_per_class=5):
        """Build compact class payload for prompt schema."""
        relevant_props = relevant_props or []
        class_copy = {
            "class_label": class_data.get("class_label", ""),
            "class_examples": class_data.get("class_examples", [])[:3],
            "properties": []
        }

        prop_count = 0
        for prop in class_data.get("properties", []):
            if prop_count >= max_properties_per_class:
                break

            if relevant_props:
                prop_name = prop.get("property_name", "")
                prop_label = prop.get("property_label", "")
                matched = False
                for selected_prop in relevant_props:
                    selected_id = selected_prop.split(":")[-1]
                    if selected_id == prop_label or selected_id == prop_name.split(":")[-1]:
                        matched = True
                        break
                if not matched:
                    continue

            prop_copy = dict(prop)
            if "examples" in prop_copy:
                prop_copy["examples"] = prop_copy["examples"][:3]
            class_copy["properties"].append(prop_copy)
            prop_count += 1

        return class_copy
    
    def generate_missing_id_query(self, question, property_selection, full_schema, include_descriptions=False, schema_text_override=None):
        """
        Generate SPARQL query to find missing entity IRIs.
        
        Args:
            question: User's natural language question
            property_selection: List of selected classes and properties
            full_schema: Complete schema dictionary
            
        Returns:
            SPARQL query string for finding missing IDs
        """
        self.logger.info("Generating missing ID query...")
        prefixes = full_schema.get("prefixes", {})
        all_classes = full_schema.get("classes", {})

        filtered_classes = {}
        selected_class_keys = []
        selected_priority_classes = []
        linked_class_candidates = []
        linked_class_seen = set()

        # Filter the schema based on property_selection
        for item in property_selection:
            class_name_input = item["class_name"]
            relevant_props = item.get("relevant_properties", [])

            # Match correct class key (prefixed or not)
            matched_class_key = self._resolve_class_key(class_name_input, all_classes)

            if not matched_class_key:
                self.logger.warning(f"Class '{class_name_input}' not found in schema (missing ID).")
                continue

            if matched_class_key not in selected_priority_classes:
                selected_priority_classes.append(matched_class_key)

            class_data = all_classes[matched_class_key]
            class_copy = self._build_class_copy(
                class_data,
                relevant_props=relevant_props,
                max_properties_per_class=5,
            )

            # Keep class even when relevant properties are empty/missed by evaluator.
            # Fallback to a compact generic property slice so the class still appears
            # in Missing-ID prompt and can be chosen by the LLM.
            if not class_copy["properties"]:
                class_copy = self._build_class_copy(
                    class_data,
                    relevant_props=None,
                    max_properties_per_class=3,
                )
                self.logger.debug(
                    "Missing-ID fallback properties used for class '%s' (no relevant_properties matched)",
                    matched_class_key,
                )

            # Track linked object/datatype classes referenced by ALL class properties,
            # not only relevant ones, so indirect target classes (e.g., ProductCategory,
            # Country) are still discoverable.
            for prop in class_data.get("properties", []):
                linked_candidates = self._extract_linked_class_candidates(
                    prop.get("datatype", ""),
                    all_classes,
                    prefixes,
                )
                for linked_class_key, is_placeholder in linked_candidates:
                    if linked_class_key == matched_class_key:
                        continue
                    dedupe_key = f"{linked_class_key}|{int(is_placeholder)}"
                    if dedupe_key in linked_class_seen:
                        continue
                    linked_class_candidates.append((linked_class_key, is_placeholder))
                    linked_class_seen.add(dedupe_key)

            if class_copy["properties"]:
                filtered_classes[matched_class_key] = class_copy
                if matched_class_key not in selected_class_keys:
                    selected_class_keys.append(matched_class_key)
            else:
                self.logger.debug(
                    "Missing-ID class '%s' skipped because no properties available in schema",
                    matched_class_key,
                )

        # Augment with linked classes (e.g., Hardware.hasCategory -> ProductCategory)
        # so Missing-ID can resolve entities like "Compensator" even if rerank did not
        # directly include the target class.
        max_linked_classes = 3
        added_linked = 0
        for linked_class_key, is_placeholder in linked_class_candidates:
            if added_linked >= max_linked_classes:
                break
            if linked_class_key in filtered_classes:
                continue
            linked_data = all_classes.get(linked_class_key)
            if linked_data:
                linked_class_copy = self._build_class_copy(
                    linked_data,
                    relevant_props=None,
                    max_properties_per_class=3,
                )
            elif is_placeholder:
                linked_class_copy = {
                    "class_label": linked_class_key.split(":")[-1],
                    "class_examples": [],
                    "properties": [],
                }
            else:
                continue

            filtered_classes[linked_class_key] = linked_class_copy
            added_linked += 1

        if added_linked:
            linked_candidate_keys = {class_key for class_key, _ in linked_class_candidates}
            linked_added_keys = sorted(
                [key for key in filtered_classes.keys() if key in linked_candidate_keys]
            )
            self.logger.info(
                "Missing-ID schema augmented with %d linked class(es): %s",
                added_linked,
                linked_added_keys,
            )

        filtered_schema = {
            "prefixes": prefixes,
            "classes": filtered_classes
        }

        class_priority_list = list(selected_priority_classes) if selected_priority_classes else list(filtered_classes.keys())

        # Use formatted schema instead of JSON to fit within context window
        if schema_text_override is not None:
            formatted_schema_str = schema_text_override
        else:
            formatter = SchemaFormatter(filtered_schema, label_source_schema=full_schema)
            formatted_schema_str = formatter.format_clean(
                include_examples=True,
                include_descriptions=include_descriptions,
            )

        # Get prefixes from schema for the template
        prefix_declarations = ""
        if prefixes:
            for pfx, uri in prefixes.items():
                prefix_declarations += f"PREFIX {pfx}: <{uri}>\n"
        # Always include rdfs prefix
        if "rdfs" not in prefixes:
            prefix_declarations = f"PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n{prefix_declarations}"
        
        extracted_mentions = self._extract_question_entities_via_llm(
            question,
            class_priority_list,
            formatted_schema_str,
        )

        expanded_mentions = []
        seen_mentions = set()
        for mention in extracted_mentions or []:
            normalized_mention = self._normalize_entity_text(mention)
            if not normalized_mention:
                continue
            if normalized_mention not in seen_mentions:
                expanded_mentions.append(normalized_mention)
                seen_mentions.add(normalized_mention)
            for token in normalized_mention.split():
                token = token.strip()
                if token and token not in seen_mentions:
                    expanded_mentions.append(token)
                    seen_mentions.add(token)
            if len(expanded_mentions) >= 12:
                break

        mentions = expanded_mentions[:12]
        if not mentions or not class_priority_list:
            self.missing_id_prompt = None
            return ""

        query_blocks = []
        for mention in mentions:
            escaped = mention.replace('"', '\\"')
            for class_name in class_priority_list:
                query_blocks.append(
                    (
                        f"{prefix_declarations}"
                        f"SELECT DISTINCT (?entity AS ?IRI) ?fullValue ?partialMatch WHERE {{\n"
                        f"  VALUES ?partialMatch {{ \"{escaped}\" }}\n"
                        f"  ?entity a {class_name};\n"
                        f"          rdfs:label ?fullValue .\n"
                        f"  FILTER(REGEX(STR(?fullValue), ?partialMatch, \"i\"))\n"
                        f"}}"
                    ).strip()
                )

        cleaned_query = "\n\n".join(query_blocks)
        cleaned_query = self._sanitize_malformed_prefixed_iris(cleaned_query)
        cleaned_query = self._normalize_partial_match_values(cleaned_query)
        cleaned_query = self._retain_complete_query_blocks(cleaned_query)
        self.missing_id_prompt = None
        self.logger.info(
            "Missing-ID template generation created %s query block(s) from %s mention(s) (base mentions=%s) and %s class(es).",
            len(query_blocks),
            len(mentions),
            len(extracted_mentions),
            len(class_priority_list),
        )
        self.logger.debug(f"Cleaned missing ID query: {cleaned_query[:300]}...")
        return cleaned_query
    
    def generate_query(self, question, property_selection, schema, missing_iris=None, missing_iris_by_class=None, entity_mentions=None, include_examples=True, include_descriptions=False, force_text_filter_matching=True, include_resolved_entity_labels=True, schema_text_override=None):
        """
        Generate SPARQL query for answering the question.
        
        Args:
            question: User's natural language question
            property_selection: List of selected classes and properties
            schema: Complete schema dictionary
            missing_iris: Dictionary of entity labels to their IRIs (from missing ID step)
            missing_iris_by_class: Dictionary of class -> list of resolved entities ({label, iri})
            entity_mentions: Extracted mention list from missing-ID entity extraction
            include_examples: Whether to include examples in schema (default: True)
            include_descriptions: Whether to include property descriptions in schema (default: False)
            force_text_filter_matching: Rewrite literal text equality to case-insensitive FILTER matching (default: True)
            include_resolved_entity_labels: Whether to include labels with IRIs in RESOLVED ENTITIES section (default: True)
            
        Returns:
            Generated SPARQL query string
        """
        self.logger.info(f"Generating final SPARQL query (include_examples={include_examples})...")
        if missing_iris:
            self.logger.info(f"Using {len(missing_iris)} resolved entity IRI(s) in query generation")
        
        prefixes = schema.get("prefixes", {})
        all_classes = schema.get("classes", {})

        filtered_classes = {}
        selected_class_keys = []

        # Filter classes and properties based on selection
        for item in property_selection:
            class_name_input = item["class_name"]
            relevant_props = item.get("relevant_properties", [])

            # Match the correct class key (prefixed or not)
            matched_class_key = None
            for k in all_classes.keys():
                if k == class_name_input or k.split(":")[-1] == class_name_input:
                    matched_class_key = k
                    break

            if not matched_class_key:
                self.logger.warning(f"Class '{class_name_input}' not found in schema (query generation).")
                continue

            class_data = all_classes[matched_class_key]

            class_copy = {
                "class_label": class_data.get("class_label", ""),
                "class_examples": class_data.get("class_examples", [])[:2] if include_examples else [],  # Max 2 examples
                "properties": []
            }

            if include_examples and missing_iris_by_class:
                class_resolved_entities = missing_iris_by_class.get(matched_class_key, [])
                if class_resolved_entities:
                    existing_examples_norm = {
                        self._normalize_entity_text(example)
                        for example in class_copy["class_examples"]
                        if isinstance(example, str) and example.strip()
                    }
                    for entity in class_resolved_entities:
                        label = (entity or {}).get("label", "").strip()
                        if not label:
                            continue
                        normalized_label = self._normalize_entity_text(label)
                        if normalized_label and normalized_label not in existing_examples_norm:
                            class_copy["class_examples"].append(label)
                            existing_examples_norm.add(normalized_label)

            # Filter only the relevant properties selected by property evaluation
            for prop in class_data.get("properties", []):
                prop_name = prop.get("property_name", "")
                prop_label = prop.get("property_label", "")
                if any(
                    rp == prop_label or rp == prop_name.split(":")[-1] or rp in prop_name
                    for rp in relevant_props
                ):
                    if include_examples:
                        prop_copy = dict(prop)
                        # Limit examples per property to 1
                        if "examples" in prop_copy:
                            prop_copy["examples"] = prop_copy["examples"][:1]
                        class_copy["properties"].append(prop_copy)
                    else:
                        prop_copy = dict(prop)
                        prop_copy.pop("examples", None)
                        class_copy["properties"].append(prop_copy)

            if class_copy["properties"]:
                filtered_classes[matched_class_key] = class_copy
                if matched_class_key not in selected_class_keys:
                    selected_class_keys.append(matched_class_key)

        # Construct filtered schema
        filtered_schema = {
            "prefixes": prefixes,
            "classes": filtered_classes
        }

        # Use formatted schema instead of JSON to fit within context window
        if schema_text_override is not None:
            formatted_schema_str = schema_text_override
        else:
            formatter = SchemaFormatter(filtered_schema, label_source_schema=schema)
            formatted_schema_str = formatter.format_clean(
                include_examples=include_examples,
                include_descriptions=include_descriptions,
            )

        # Build conditional schema details line based on include_examples
        if include_examples and include_descriptions:
            schema_details_line = "Use the schema details below (class IRIs, property IRIs, property descriptions, and examples)"
            self.logger.debug("Query generation: INCLUDING examples in prompt")
        elif include_examples:
            schema_details_line = "Use the schema details below (class IRIs, property IRIs, and examples)"
            self.logger.debug("Query generation: INCLUDING examples in prompt")
        elif include_descriptions:
            schema_details_line = "Use the schema details below (class IRIs, property IRIs, and property descriptions)"
            self.logger.debug("Query generation: INCLUDING descriptions in prompt")
        else:
            schema_details_line = "Use the schema details below (class IRIs and property IRIs)"
            self.logger.debug("Query generation: EXCLUDING examples from prompt")

        # Build IRI context if missing entities were resolved
        iris_context = ""

        # Build unified resolved entities section grouped by extracted entity name
        # Map each IRI to its class (from missing_iris_by_class)
        iri_to_class = {}
        if missing_iris_by_class:
            for class_name, entities in missing_iris_by_class.items():
                for item in entities or []:
                    iri = (item or {}).get("iri", "")
                    if iri and not iri_to_class.get(iri):
                        iri_to_class[iri] = class_name
        
        # Map each IRI to its label for display
        iri_to_label = {}
        if missing_iris:
            for label, iri in missing_iris.items():
                if iri:
                    iri_to_label[iri] = label
        
        # Map each entity mention to all possible IRIs.
        # Prefer extracted mention keys (e.g., "ms brant") over resolved labels.
        mention_to_iris = {}
        mention_order = []

        effective_mentions = list(entity_mentions or [])
        if not effective_mentions:
            effective_mentions = self._extract_question_mentions_fallback(question)
            if effective_mentions:
                self.logger.info(
                    "[IRI GROUPING] using fallback question mentions: %s",
                    effective_mentions,
                )

        for raw_mention in effective_mentions:
            mention_key = self._normalize_entity_text(raw_mention)
            if not mention_key:
                continue
            if mention_key not in mention_to_iris:
                mention_to_iris[mention_key] = []
                mention_order.append(mention_key)

        self.logger.info("[IRI GROUPING] mention_order from entity_mentions: %s", mention_order)

        if missing_iris:
            for label, iri in missing_iris.items():
                if not iri:
                    continue

                assigned_mention = None
                for mention_key in mention_order:
                    if self._mention_matches_label(mention_key, label):
                        assigned_mention = mention_key
                        break

                self.logger.info(
                    "[IRI GROUPING] label=%r -> assigned_mention=%r",
                    label, assigned_mention,
                )

                if not assigned_mention:
                    canonical = self._canonical_entity_label(label)
                    if not canonical:
                        canonical = self._normalize_entity_text(label)

                    # If we already have extracted mentions, do not create new
                    # mention groups from labels. Instead, map to the best existing
                    # mention by token overlap, falling back to the first mention.
                    if mention_order:
                        canonical_tokens = set(canonical.split()) if canonical else set()
                        best_mention = None
                        best_score = 0
                        for mention_key in mention_order:
                            mention_tokens = set(mention_key.split())
                            score = len(canonical_tokens & mention_tokens)
                            if score > best_score:
                                best_score = score
                                best_mention = mention_key

                        assigned_mention = best_mention if best_score > 0 else mention_order[0]
                    else:
                        assigned_mention = canonical

                if not assigned_mention:
                    continue

                if assigned_mention not in mention_to_iris:
                    mention_to_iris[assigned_mention] = []
                    mention_order.append(assigned_mention)

                if iri not in mention_to_iris[assigned_mention]:
                    mention_to_iris[assigned_mention].append(iri)
        
        # Output resolved entities section grouped by entity mention
        if mention_to_iris:
            iris_context += "\n\n=== RESOLVED ENTITIES ===\n"

            for entity_name in mention_order:
                iri_list = mention_to_iris.get(entity_name, [])
                if not iri_list:
                    continue

                iris_context += f"Entity mention: {entity_name}\n"
                iris_context += "  Possible IRI(s):\n"

                # Group IRIs by class
                class_to_iris = {}
                for iri in iri_list:
                    class_name = iri_to_class.get(iri, "Unknown")
                    class_to_iris.setdefault(class_name, []).append(iri)

                # Output each class with its IRIs and optional labels
                for class_name in sorted(class_to_iris.keys()):
                    iris_context += f"    Instances of Class: {class_name}\n"
                    for iri in class_to_iris[class_name]:
                        iri_display = self._compact_iri_for_prompt(iri, prefixes)
                        label = iri_to_label.get(iri, "")
                        if include_resolved_entity_labels and label:
                            iris_context += f"    • {label} -> {iri_display}\n"
                        else:
                            iris_context += f"    • {iri_display}\n"

                iris_context += "\n"

            iris_context += (
                "Only use resolved IRIs when directly relevant to answer the question. "
                "If not relevant, do NOT use them in the query.\n"
            )

        schema_table_str = self._strip_toon_prefix_section(formatted_schema_str) or formatted_schema_str
        prefix_lines = "\n".join(f"PREFIX {p}: <{u}>" for p, u in (prefixes or {}).items())

        prompt = textwrap.dedent(f"""You are a SPARQL query generator. Produce one correct, complete SPARQL query for the question below.

    ══════════════════════════════════════════
     PREFIXES
    ══════════════════════════════════════════
    {prefix_lines}

    ══════════════════════════════════════════
     SCHEMA  —  scan headers, use only what is relevant
    ══════════════════════════════════════════
    {schema_table_str}

    ══════════════════════════════════════════
     RULES
    ══════════════════════════════════════════

    -- Property use --
R1. Use only the exact property IRIs listed in the schema above. Never derive an IRI from a label.
R2. Apply a property only to the class that declares it. Never cross-apply across classes.

-- Query form --
R3. Yes/no question           → ASK
    Data retrieval             → SELECT
    Count / total / avg / max  → SELECT with the appropriate aggregate

-- SELECT variables --
R4. No specific properties requested  → SELECT the entity IRI only
    Specific properties requested     → SELECT only those properties
    Aggregates                        → all non-aggregate SELECT vars must appear in GROUP BY

-- Entity resolution --
R5. When a resolved entity IRI is provided, bind it directly as a term in the triple pattern.
    Never use FILTER(CONTAINS(?iri, "...")) or FILTER(STRSTARTS(?iri, "...")) on IRIs.

-- Multi-hop joins --
R6. Derive join paths step by step using declared properties only.
    For each hop, verify: does the property's declared range match the next class in the chain?
    Never invent a direct link between two classes — use the intermediate node.

-- Subqueries --
R7. [CRITICAL] All variables inside a subquery must be completely different from outer query
    variables. Add suffix _sub to every variable inside the subquery without exception.
    Every non-aggregate SELECT variable in a subquery must appear in GROUP BY.

-- LIMIT and ORDER BY --
R8. Use LIMIT only when the question explicitly requests a subset (top N, first, highest, lowest).
    Pair LIMIT with ORDER BY when ranking is required.
    Use MAX/MIN aggregates instead of ORDER BY + LIMIT 1.

-- Data types --
R9. Cast strings when needed: xsd:integer(?s), xsd:decimal(?s), xsd:date(?s)

══════════════════════════════════════════
 QUESTION
══════════════════════════════════════════
{question}{iris_context}

══════════════════════════════════════════
 OUTPUT  —  strict format, no deviations
══════════════════════════════════════════
Return ONLY the XML block below. No markdown fences, no explanation outside the block.

<out>
    <question>…restate the question…</question>
    <classes_used>…comma-separated class IRIs used in the WHERE clause…</classes_used>
    <query>
<!-- Use ASK for yes/no, SELECT for data retrieval -->
PREFIX …
WHERE {...}
    </query>
</out>


The final output is:
""").strip()

        # Normalize the major section headings so they start at column 0.
        normalized_lines = []
        for line in prompt.splitlines():
            stripped = line.lstrip()
            if stripped.startswith(("════════", "PREFIXES", "SCHEMA", "RULES", "QUESTION", "OUTPUT", "Cardinality key:")):
                normalized_lines.append(stripped)
            elif stripped.startswith("PREFIX "):
                normalized_lines.append(stripped)
            elif stripped == "<out>" or stripped == "</out>":
                normalized_lines.append(stripped)
            elif stripped.startswith(("<question>", "<classes_used>", "<query>", "</query>")):
                normalized_lines.append(f"  {stripped}")
            elif stripped.startswith(("ASK / SELECT", "WHERE {")):
                normalized_lines.append(stripped)
            else:
                normalized_lines.append(line)
        prompt = "\n".join(normalized_lines)

        self.last_prompt = prompt
        # Save prompt immediately before LLM call
        self.logger.debug("Final query prompt ready (stored in self.last_prompt)")
        raw_response = self.llm.generate(prompt, max_tokens=1000)
        self.logger.debug(f"Raw LLM response for final query: {raw_response[:500]}...")
        cleaned_query = self._clean_sparql_response(raw_response)
        cleaned_query = self._sanitize_malformed_prefixed_iris(cleaned_query)
        cleaned_query = self._ensure_required_prefixes(cleaned_query, prefixes)
        if force_text_filter_matching:
            cleaned_query = self._rewrite_literal_equality_to_filter(cleaned_query)
        self.logger.debug(f"Cleaned final query: {cleaned_query[:300]}...")
        return cleaned_query

    def correct_query_from_error(self, original_query, error_message, question=None, schema=None):
        """Ask the LLM to repair a malformed SPARQL query based on endpoint error details."""
        prompt = f"""You are an expert SPARQL query repair assistant.

TASK:
Repair the SPARQL query so it executes successfully while preserving the original intent.

RULES:
1. Return ONLY the corrected executable SPARQL query.
2. Do NOT include markdown fences, explanations, or extra text.
3. Keep the same prefixes unless a missing prefix is required for syntax validity.
4. Preserve the original semantics (same question intent).
5. Fix syntax/compiler issues indicated by the endpoint error.

QUESTION (for intent reference):
{question or "(not provided)"}

ENDPOINT ERROR:
{error_message}

ORIGINAL QUERY:
{original_query}

CORRECTED QUERY:
""".strip()

        self.query_repair_prompt = prompt
        raw_response = self.llm.generate(prompt, max_tokens=1000)
        cleaned_query = self._clean_sparql_response(raw_response)
        cleaned_query = self._sanitize_malformed_prefixed_iris(cleaned_query)
        cleaned_query = self._ensure_required_prefixes(
            cleaned_query,
            (schema or {}).get("prefixes", {}),
        )
        self.logger.debug(f"Corrected query from error: {cleaned_query[:300]}...")
        return cleaned_query
