"""
Schema Parser Module

Parses SHACL TTL files and generates machine-readable schema (m_schema).
"""

from rdflib import Graph, Namespace, RDF, RDFS, URIRef
from urllib.parse import urlparse
from collections import defaultdict
import json
import re
import tempfile
import os


class SHACLSchemaParser:
    """Parser for SHACL Turtle files."""
    
    def __init__(self, fix_syntax=True):
        """
        Initialize the SHACL parser.
        
        Args:
            fix_syntax: If True, attempts to fix common Turtle syntax errors
        """
        self.fix_syntax = fix_syntax
        self.SH = Namespace("http://www.w3.org/ns/shacl#")
        self.EX = Namespace("http://example.org/")
        self.RDFS_COMMENT = URIRef("https://www.w3.org/TR/rdf-schema/#ch_comment")
        
    def split_namespace_local(self, iri):
        """Split namespace and localname '#' or '/' part from IRI."""
        iri = str(iri).strip()
        if not iri or iri in ("None", "nan"):
            return "", iri
        iri = iri.strip("<>")
        if "#" in iri:
            ns, local = iri.rsplit("#", 1)
            return ns + "#", local
        if "/" in iri:
            ns, local = iri.rsplit("/", 1)
            return ns + "/", local
        return "", iri

    def parse_rdf_list(self, graph, list_node):
        """Convert an RDF list into a Python list."""
        items = []
        while list_node and list_node != RDF.nil:
            first = graph.value(list_node, RDF.first)
            if first is not None:
                items.append(first)
            list_node = graph.value(list_node, RDF.rest)
        return items

    def make_prefix_candidate(self, ns):
        """Get useful prefix names automatically using namespace."""
        # Prefer stable, human-friendly aliases for common namespaces.
        fixed_aliases = {
            "http://www.w3.org/2001/XMLSchema#": "xsd",
            "http://ld.company.org/prod-instances/": "prod_inst",
            "https://ns.eccenca.com/": "ecce",
        }
        if ns in fixed_aliases:
            return fixed_aliases[ns]

        parsed = urlparse(ns)
        path = parsed.path.rstrip("/").split("/")
        candidate = path[-1] if path[-1] else parsed.netloc.split(".")[0]
        candidate = candidate.lower() if candidate else "ns"
        candidate = "".join(c if c.isalnum() else "_" for c in candidate)
        return candidate or "ns"

    def shrink_with_prefix(self, iri, prefix_map):
        """Compact IRI using known prefixes; leave literals unwrapped."""
        if not iri:
            return iri

        if iri.replace('.', '', 1).isdigit() or iri.lower() in ("true", "false", "none", "null"):
            return iri
        if iri.startswith('"') and iri.endswith('"'):
            return iri
        if not (":" in iri or "/" in iri or "#" in iri):
            return iri

        for prefix, base in prefix_map.items():
            if iri.startswith(base):
                return f"{prefix}:{iri[len(base):]}"
        return f"<{iri}>"

    def extract_iri_and_label(self, text):
        """Safely extract IRI/literal and label from example text."""
        if not text:
            return None, None
        text = str(text).strip()

        def clean_label(raw_label):
            label = str(raw_label or "").strip()
            if not label:
                return None
            if label.startswith("(") and label.endswith(")") and len(label) > 2:
                label = label[1:-1].strip()
            # Heal common source artifacts like trailing "(26" -> "(26)".
            open_count = label.count("(")
            close_count = label.count(")")
            if open_count > close_count:
                label = label + (")" * (open_count - close_count))
            label = re.sub(r'\s+', ' ', label).strip()
            return label or None

        # Capture leading IRI token (bracketed or unbracketed), keep full tail intact.
        match = re.match(
            r'^\s*(<[^>]+>|https?://\S+|[A-Za-z_][A-Za-z0-9_\-]*:[^\s]+)\s*(.*)$',
            text,
        )
        if match:
            iri_token, tail = match.groups()
            iri = iri_token.strip("<>").strip()
            tail = (tail or "").strip()

            # Case: examples like "<iri> (Label) ..." -> take first parenthetical as label
            paren_match = re.match(r'^\(\s*([^)]*?)\s*\)\s*(.*)$', tail)
            if paren_match:
                first_paren_value, remainder = paren_match.groups()
                label = clean_label(first_paren_value)
                if label:
                    return iri, label

                # Empty parens ("( ) is a ...") should be treated as no label.
                if remainder.lower().startswith("is a "):
                    return iri, None

                return iri, clean_label(remainder)

            # If tail is ontology boilerplate, ignore as label.
            if tail.lower().startswith("is a "):
                return iri, None

            return iri, clean_label(tail)

        # Pattern 4: plain literal value (not an IRI)
        return None, text

    def compact_example_text(self, example_text, prefix_map):
        """Compact leading IRI in example strings while preserving trailing labels/values."""
        text = str(example_text or "").strip()
        if not text:
            return text

        # Form: <IRI> optional-label
        match = re.match(r'^<([^>]+)>\s*(.*)$', text)
        if match:
            iri = match.group(1).strip()
            suffix = match.group(2).strip()
            compact_iri = self.shrink_with_prefix(iri, prefix_map)
            if suffix:
                suffix = re.sub(r'^-\s*', '', suffix)
                return f"{compact_iri} - {suffix}".strip()
            return compact_iri

        # Form: prefixed_or_full_iri optional-label
        parts = text.split(maxsplit=1)
        head = parts[0]
        tail = parts[1] if len(parts) > 1 else ""
        if head.startswith("http://") or head.startswith("https://") or ":" in head:
            compact_head = self.shrink_with_prefix(head.strip("<>"), prefix_map)
            tail = tail.strip()
            if tail:
                tail = re.sub(r'^-\s*', '', tail)
                return f"{compact_head} - {tail}".strip()
            return compact_head

        return text

    def clean_dict(self, d):
        """Recursively remove keys with empty lists, None, or empty dicts."""
        if isinstance(d, dict):
            return {k: self.clean_dict(v) for k, v in d.items() if v not in (None, [], {})}
        elif isinstance(d, list):
            return [self.clean_dict(v) for v in d if v not in (None, [], {})]
        else:
            return d

    def simplify_comment(self, comment, prefix_map):
        """Simplify verbose SHACL comments into readable natural language."""
        if not comment:
            return None

        for prefix, namespace in prefix_map.items():
            comment = comment.replace(namespace, f"{prefix}:")

        comment = re.sub(r'\s*\(\s*\)', '', comment)
        comment = re.sub(r'<([^>]+)>', r'\1', comment)
        comment = re.sub(r'\s+', ' ', comment)
        comment = comment.strip()

        if 'has at most' in comment or 'has at least' in comment or 'has exactly' in comment:
            comment = re.sub(r'(\w+):(\w+)(?=\s|,|$)', r'\2', comment)

        return comment

    def parse(self, ttl_path, save_json_path=None):
        """
        Parse SHACL TTL file and return structured schema with compact prefixes.
        
        Args:
            ttl_path: Path to SHACL Turtle file
            save_json_path: Optional path to save JSON output
            
        Returns:
            Dictionary containing prefixes and classes
        """
        print(f"Loading graph from {ttl_path}...")
        
        # Fix malformed Turtle files (prefixes after data)
        if self.fix_syntax:
            print("Checking and fixing Turtle syntax...")
            with open(ttl_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract all @prefix declarations
            prefix_lines = []
            other_lines = []
            
            for line in content.split('\n'):
                if line.strip().startswith('@prefix'):
                    prefix_lines.append(line)
                else:
                    other_lines.append(line)
            
            # Reconstruct with prefixes first
            if prefix_lines:
                fixed_content = '\n'.join(prefix_lines) + '\n\n' + '\n'.join(other_lines)
                
                # Write to temporary file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.ttl', delete=False, encoding='utf-8') as tmp:
                    tmp.write(fixed_content)
                    temp_path = tmp.name
                
                try:
                    g = Graph()
                    g.parse(temp_path, format="turtle", encoding="utf-8")
                    print(f"Graph loaded with {len(g)} triples (syntax fixed)")
                finally:
                    os.unlink(temp_path)
            else:
                g = Graph()
                g.parse(ttl_path, format="turtle", encoding="utf-8")
                print(f"Graph loaded with {len(g)} triples")
        else:
            g = Graph()
            g.parse(ttl_path, format="turtle", encoding="utf-8")
            print(f"Graph loaded with {len(g)} triples")

        m_schema = {}
        ns_to_prefix = {}

        # Helper to register namespaces
        def register_ns(ns):
            if not ns or ns in ns_to_prefix:
                return ns_to_prefix.get(ns, "")
            base_guess = self.make_prefix_candidate(ns)
            
            # SPARQL prefixes cannot start with digits - prepend 'ns_' if needed
            if base_guess and base_guess[0].isdigit():
                base_guess = f"ns_{base_guess}"
            
            pref = base_guess
            i = 1
            while pref in ns_to_prefix.values():
                i += 1
                pref = f"{base_guess}{i}"
            ns_to_prefix[ns] = pref
            return pref

        # Pre-compute all NodeShapes and their properties
        print("Pre-computing NodeShapes...")
        node_shapes = list(g.subjects(RDF.type, self.SH.NodeShape))
        print(f"Found {len(node_shapes)} NodeShapes")
        
        # Create lookup tables for faster access
        # NOTE: A NodeShape can have MULTIPLE targetClass values
        node_shape_targets = {}  # {node_shape: [target_class1, target_class2, ...]}
        node_shape_properties = defaultdict(list)
        
        for node_shape in node_shapes:
            targets = list(g.objects(node_shape, self.SH.targetClass))
            if targets:
                node_shape_targets[node_shape] = targets  # Store ALL targets, not just first
                props = list(g.objects(node_shape, self.SH.property))
                node_shape_properties[node_shape] = props

        # Batch extract all labels from examples
        print("Extracting labels from examples...")
        label_map = {}
        
        for node_shape in node_shapes:
            for example_text in g.objects(node_shape, self.EX.example):
                iri, label = self.extract_iri_and_label(example_text)
                if iri:
                    ex_ns, _ = self.split_namespace_local(iri)
                    register_ns(ex_ns)
                    if label:
                        label_map[iri] = label

        # Cache RDFS labels and comments
        print("Caching RDFS labels and comments...")
        rdfs_label_cache = {}
        rdfs_comment_cache = {}
        
        for s, p, o in g.triples((None, RDFS.label, None)):
            rdfs_label_cache[str(s)] = str(o)
        
        for s, p, o in g.triples((None, self.RDFS_COMMENT, None)):
            rdfs_comment_cache[str(s)] = str(o)

        # Infer labels from SHACL comment text, e.g.
        # "http://.../someIri (Human Label) ..." when explicit rdfs:label is missing.
        comment_label_map = {}

        def extract_iri_comment_labels(comment_text):
            pairs = {}
            if not comment_text:
                return pairs

            text = str(comment_text)
            for match in re.finditer(r'https?://[^\s)\"]+', text):
                iri = match.group(0).strip()
                idx = match.end()

                # Skip whitespace between IRI and opening parenthesis.
                while idx < len(text) and text[idx].isspace():
                    idx += 1

                if idx >= len(text) or text[idx] != '(':
                    continue

                depth = 0
                end_idx = None
                for j in range(idx, len(text)):
                    ch = text[j]
                    if ch == '(':
                        depth += 1
                    elif ch == ')':
                        depth -= 1
                        if depth == 0:
                            end_idx = j
                            break

                if end_idx is None:
                    continue

                label = text[idx + 1:end_idx].strip()
                # Ignore empty placeholders like "( )".
                if not label:
                    continue
                if not any(c.isalpha() for c in label):
                    continue

                pairs[iri] = label

            return pairs

        for _, comment in rdfs_comment_cache.items():
            extracted_pairs = extract_iri_comment_labels(comment)
            for iri, label in extracted_pairs.items():
                comment_label_map.setdefault(iri, label)

        # Process NodeShapes with cached data
        print("Processing NodeShapes...")
        rdfs_label_uri = str(RDFS.label)
        
        for node_shape in node_shapes:
            target_classes = node_shape_targets.get(node_shape, [])
            if not target_classes:
                continue

            # Process each target class separately (a NodeShape can have multiple targetClasses)
            for target_class in target_classes:
                class_iri = str(target_class)
                class_ns, class_local = self.split_namespace_local(class_iri)
                register_ns(class_ns)

                # Use cached label or fallback
                class_label = (label_map.get(class_iri) or 
                              rdfs_label_cache.get(class_iri) or 
                              comment_label_map.get(class_iri) or
                              class_local)
                
                # Get class comment
                class_comment = rdfs_comment_cache.get(class_iri)
                
                # Skip if this class was already created (from another NodeShape)
                if class_iri not in m_schema:
                    m_schema[class_iri] = {
                        "class_label": class_label,
                        "class_examples": [],
                        "properties": []
                    }

                # Add examples (from the NodeShape, shared by all target classes)
                for ex in g.objects(node_shape, self.EX.example):
                    iri, label = self.extract_iri_and_label(ex)
                    if iri:
                        ex_ns, _ = self.split_namespace_local(iri)
                        register_ns(ex_ns)
                        # Keep explicit separator so downstream output stays consistent.
                        display_example = f"<{iri}> - {label}" if label else f"<{iri}>"
                        if display_example not in m_schema[class_iri]["class_examples"]:
                            m_schema[class_iri]["class_examples"].append(display_example)

                # Process properties with minimal graph queries (shared by all target classes)
                properties = node_shape_properties.get(node_shape, [])
                
                for prop in properties:
                    prop_dict = {}
                    prop_paths = list(g.objects(prop, self.SH.path))
                    if not prop_paths:
                        continue

                    prop_iri = str(prop_paths[0])

                    # Skip redundant rdfs:label properties
                    if prop_iri in ("rdfs:label", rdfs_label_uri, 
                                   "http://www.w3.org/2000/01/rdf-schema#label"):
                        continue

                    prop_ns, prop_local = self.split_namespace_local(prop_iri)
                    register_ns(prop_ns)

                    # Use cached label
                    prop_label = (label_map.get(prop_iri) or 
                                 rdfs_label_cache.get(prop_iri) or 
                                 comment_label_map.get(prop_iri) or
                                 prop_local)
                    
                    prop_dict["property_name"] = prop_iri
                    prop_dict["property_label"] = prop_label

                    # Batch fetch constraints
                    dtype_classes = (list(g.objects(prop, self.SH.datatype)) + 
                                   list(g.objects(prop, self.SH["class"])))
                    
                    # Only add datatype if present
                    if dtype_classes:
                        prop_dict["datatype"] = [str(d) for d in dtype_classes]

                    maxc = list(g.objects(prop, self.SH.maxCount))
                    minc = list(g.objects(prop, self.SH.minCount))

                    # Only add counts if present
                    if maxc:
                        prop_dict["max_count"] = int(maxc[0])
                    if minc:
                        prop_dict["min_count"] = int(minc[0])

                    # OR classes and NodeKinds
                    or_nodes = list(g.objects(prop, self.SH["or"]))
                    or_classes = []
                    or_node_kinds = []
                    
                    if or_nodes:
                        or_list = self.parse_rdf_list(g, or_nodes[0])
                        for o in or_list:
                            for c in g.objects(o, self.SH["class"]):
                                or_classes.append(str(c))
                                cls_ns, _ = self.split_namespace_local(str(c))
                                register_ns(cls_ns)
                            nk = list(g.objects(o, self.SH.NodeKind))
                            if nk:
                                or_node_kinds.append(str(nk[0]))

                    prop_node_kind = list(g.objects(prop, self.SH.NodeKind))
                    node_kind_value = (str(prop_node_kind[0]) if prop_node_kind 
                                     else (or_node_kinds[0] if or_node_kinds else None))

                    if node_kind_value:
                        prop_dict["node_kind"] = node_kind_value
                    if or_classes:
                        prop_dict["or_classes"] = or_classes

                    # Property examples
                    examples_list = []
                    for example_text in g.objects(prop, self.EX.example):
                        raw = str(example_text).strip()
                        iri, label = self.extract_iri_and_label(raw)
                        
                        if iri and iri.startswith("http"):
                            ex_ns, _ = self.split_namespace_local(iri)
                            register_ns(ex_ns)
                            # Real IRI — keep explicit separator before label.
                            display_example = f"<{iri}> - {label}".strip() if label else f"<{iri}>"
                        elif iri:
                            ex_ns, _ = self.split_namespace_local(iri)
                            register_ns(ex_ns)
                            # Prefixed IRI
                            display_example = f"{iri} - {label}".strip() if label else iri
                        else:
                            # Plain literal value — show as-is
                            display_example = raw
                        
                        if display_example not in examples_list:
                            examples_list.append(display_example)
                    if examples_list:
                        prop_dict["examples"] = examples_list

                    # Description
                    minc_val = int(minc[0]) if minc else None
                    maxc_val = int(maxc[0]) if maxc else None
                    
                    if minc_val == maxc_val and minc_val is not None:
                        qty = f"exactly {minc_val}"
                    elif minc_val and maxc_val:
                        qty = f"at least {minc_val} and at most {maxc_val}"
                    elif maxc_val:
                        qty = f"at most {maxc_val}"
                    elif minc_val:
                        qty = f"at least {minc_val}"
                    else:
                        qty = "typically one, but may vary"

                    prop_dict["description"] = f"{class_label} has {qty} {prop_label}."
                    m_schema[class_iri]["properties"].append(prop_dict)

        # Batch compact all IRIs
        print("Compacting IRIs...")
        prefix_map = {v: k for k, v in ns_to_prefix.items()}
        compact_classes = {}
        
        for class_iri, class_data in m_schema.items():
            compact_class = self.shrink_with_prefix(class_iri, prefix_map)

            if "class_examples" in class_data and class_data["class_examples"]:
                class_data["class_examples"] = [
                    self.compact_example_text(example, prefix_map)
                    for example in class_data["class_examples"]
                ]
            
            # Compact property fields
            for p in class_data["properties"]:
                p["property_name"] = self.shrink_with_prefix(p["property_name"], prefix_map)
                
                # Compact datatype values if present
                if "datatype" in p:
                    p["datatype"] = [
                        self.shrink_with_prefix(dt, prefix_map) for dt in p["datatype"]
                    ]
                
                # Compact or_classes if present
                if "or_classes" in p and p["or_classes"]:
                    p["or_classes"] = [
                        self.shrink_with_prefix(oc, prefix_map) for oc in p["or_classes"]
                    ]

                if "examples" in p and p["examples"]:
                    p["examples"] = [
                        self.compact_example_text(example, prefix_map)
                        for example in p["examples"]
                    ]

            compact_classes[compact_class] = class_data

        # Clean empty values
        print("Cleaning output...")
        cleaned_classes = {cls: self.clean_dict(data) for cls, data in compact_classes.items()}

        result = {"prefixes": prefix_map, "classes": cleaned_classes}
        
        if save_json_path:
            print(f"Saving to {save_json_path}...")
            with open(save_json_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print("Done!")
        
        return result