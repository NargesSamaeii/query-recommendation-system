"""
Pipeline Orchestrator

Orchestrates the complete NL2SPARQL pipeline.
"""

import os
import json
import logging
import re
import importlib.util
from pathlib import Path
from datetime import datetime

from .schema_parser import SHACLSchemaParser
from .schema_formatter import SchemaFormatter
from .toon_formatter import TOONFormatter
from .class_evaluator import ClassRelevanceEvaluator
from .results_manager import ResultsManager
from .evaluator import PipelineEvaluator
from .ground_truth_manager import GroundTruthManager, EvaluationResultsManager
from .property_evaluator import PropertyEvaluator
from .sparql_generator import SPARQLGenerator
from .sparql_executor import SPARQLExecutor
from .llm_interface import create_llm, MistralLLMWrapper
from .config import Config
from .query_router import QueryRouter

# For results organization
try:
    from .results_organizer import ResultsOrganizer
except ImportError:
    ResultsOrganizer = None


class NL2SPARQLPipeline:
    """Complete pipeline for natural language to SPARQL translation."""
    
    def __init__(self, config_path=None):
        """
        Initialize pipeline with configuration.
        
        Args:
            config_path: Path to config.yaml file
        """
        self.config = Config(config_path)
        self._setup_logging()
        self._setup_directories()
        
        # Initialize components
        self.llm_reasoning = None  # For class/property extraction (Mistral)
        self.llm_generation = None  # For query generation (Gemini)
        self.llm_reasoning_info = {}
        self.llm_generation_info = {}
        self.parser = None
        self.executor = None
        
        self.logger.info("NL2SPARQL Pipeline initialized")
    
    def _setup_logging(self):
        """Setup logging configuration."""
        log_level = self.config.get("pipeline.log_level", "INFO")
        log_file = self.config.get("pipeline.log_file", "logs/nl2sparql.log")
        
        # Create logs directory
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
    
    def _setup_directories(self):
        """Create necessary directories."""
        dirs = [
            self.config.get("schema.input_dir", "data/input"),
            self.config.get("schema.output_dir", "data/output"),
            self.config.get("output.results_dir", "tests/results"),
            self.config.get("output.extractions_dir", "tests/extractions"),
            self.config.get("output.prompts_dir", "tests/prompts"),
            self.config.get("output.evaluation_results_dir", "tests/evaluation_results"),
            self.config.get("output.ground_truth_dir", "tests/ground_truth")
        ]
        
        for directory in dirs:
            os.makedirs(directory, exist_ok=True)

    def _sanitize_name(self, value, default="default"):
        raw = str(value or default).strip()
        safe = raw.replace("/", "_").replace("\\", "_").replace(":", "_").replace(" ", "_")
        return safe or default

    def _normalize_entity_text(self, text):
        value = (text or "").strip().lower()
        value = re.sub(r"[^a-z0-9\s_-]", " ", value)
        value = re.sub(r"[_-]", " ", value)
        value = re.sub(r"\s+", " ", value).strip()
        return value

    def _canonical_entity_token(self, token):
        """Return a conservative canonical form for lexical token matching.

        This handles common singular/plural surface variants without applying
        aggressive stemming that could increase false positives.
        """
        token = (token or "").strip().lower()
        if len(token) <= 3:
            return token

        # countries -> country
        if token.endswith("ies") and len(token) > 4:
            return token[:-3] + "y"

        # switches -> switch, boxes -> box, classes -> class
        if token.endswith("es") and len(token) > 4:
            es_suffixes = ("ses", "xes", "zes", "ches", "shes")
            if any(token.endswith(suffix) for suffix in es_suffixes):
                return token[:-2]

        # states -> state, components -> component
        if token.endswith("s") and len(token) > 4 and not token.endswith("ss"):
            return token[:-1]

        return token

    def _extract_partial_match_from_query(self, query_text):
        if not query_text:
            return ""
        match = re.search(r'VALUES\s+\?partialMatch\s*\{\s*"([^"]+)"\s*\}', query_text, flags=re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else ""

    def _extract_missing_id_class_from_query(self, query_text):
        if not query_text:
            return ""

        class_match = re.search(
            r'\?[A-Za-z_][A-Za-z0-9_]*\s+a\s+([A-Za-z_][A-Za-z0-9_\-]*:[A-Za-z_][A-Za-z0-9_\-]*|<[^>]+>)\s*[;.]',
            query_text,
            flags=re.IGNORECASE,
        )
        if not class_match:
            return ""

        class_token = class_match.group(1).strip()
        if class_token.startswith("<") and class_token.endswith(">"):
            class_token = class_token[1:-1]
        return class_token

    def _add_missing_iri_class_mapping(self, missing_iris_by_class, class_name, label, iri):
        if not class_name or not iri:
            return

        class_entities = missing_iris_by_class.setdefault(class_name, [])
        for item in class_entities:
            if item.get("label") == label and item.get("iri") == iri:
                return
        class_entities.append({"label": label, "iri": iri})

    def _is_equivalent_entity_match(self, mention, label, class_name=None):
        mention_norm = self._normalize_entity_text(mention)
        label_norm = self._normalize_entity_text(label)
        if not mention_norm or not label_norm:
            return False

        mention_tokens = [token for token in mention_norm.split() if token]
        label_tokens = [token for token in label_norm.split() if token]
        label_token_set = set(label_tokens)
        mention_tokens_canon = [self._canonical_entity_token(token) for token in mention_tokens]
        label_tokens_canon = [self._canonical_entity_token(token) for token in label_tokens]
        label_token_set_canon = set(label_tokens_canon)
        if not mention_tokens or not label_token_set:
            return False

        def is_id_like(token):
            return bool(re.search(r'\d', token))

        mention_id_tokens = [token for token in mention_tokens if is_id_like(token)]
        mention_text_tokens = [token for token in mention_tokens if not is_id_like(token)]
        mention_text_tokens_canon = [self._canonical_entity_token(token) for token in mention_text_tokens]

        # For non-ID mentions, ignore leading ID-like tokens in labels
        # (e.g., "m558 2275045 sensor switch" -> "sensor switch").
        label_tokens_core = list(label_tokens)
        while label_tokens_core and is_id_like(label_tokens_core[0]):
            label_tokens_core.pop(0)
        if not label_tokens_core:
            label_tokens_core = label_tokens
        label_tokens_canon_core = [self._canonical_entity_token(token) for token in label_tokens_core]

        # ID-like mentions: keep all labels containing all mention ID tokens.
        if mention_id_tokens:
            if not all(token in label_token_set for token in mention_id_tokens):
                return False
            if mention_text_tokens and not any(token in label_token_set or canon in label_token_set_canon for token, canon in zip(mention_text_tokens, mention_text_tokens_canon)):
                return False
            return True

        # Unigram mention: only exact single-token labels (no extra words).
        token = mention_tokens[0]
        token_canon = mention_tokens_canon[0]
        if len(mention_tokens) == 1:
            return len(label_tokens_core) == 1 and (
                label_tokens_core[0] == token or label_tokens_canon_core[0] == token_canon
            )

        # N-gram mention: label must be exactly one of mention's contiguous n-grams.
        # Example mention "sensor switch" allows labels: "sensor", "switch", "sensor switch"
        # but disallows "sensor compensator" (contains token outside mention n-grams).
        mention_ngrams = set()
        mention_ngrams_canon = set()
        token_count = len(mention_tokens)
        for start_idx in range(token_count):
            for end_idx in range(start_idx + 1, token_count + 1):
                mention_ngrams.add(" ".join(mention_tokens[start_idx:end_idx]))
            mention_ngrams_canon.add(" ".join(mention_tokens_canon[start_idx:end_idx]))

        label_phrase = " ".join(label_tokens_core)
        label_phrase_canon = " ".join(label_tokens_canon_core)
        return label_phrase in mention_ngrams or label_phrase_canon in mention_ngrams_canon

    def _resolve_stage_llm(self, stage_name):
        llm_config = self.config.config.get("llm", {})
        stage_config = llm_config.get("stages", {}).get(stage_name, {})
        provider = stage_config.get("provider") or llm_config.get("provider")
        model_name = stage_config.get("model_name") or llm_config.get("model_name")

        if not provider:
            raise ValueError(f"LLM provider not configured for stage '{stage_name}'. Set llm.provider or llm.stages.{stage_name}.provider")

        if provider == "powerful_local":
            raise ValueError(
                "Provider 'powerful_local' is no longer supported. "
                f"Update llm.stages.{stage_name}.provider to one of: mistral, gemini, openai"
            )

        return provider, model_name

    def _init_stage_llm(self, stage_name, purpose_label):
        provider, model_name = self._resolve_stage_llm(stage_name)
        llm_config = self.config.config.get("llm", {})
        stage_config = llm_config.get("stages", {}).get(stage_name, {})

        effective_temperature = stage_config.get("temperature", llm_config.get("temperature", 0.0))
        effective_seed = stage_config.get("seed", llm_config.get("seed", None))

        parsed_seed = None
        if effective_seed is not None and str(effective_seed).strip() != "":
            try:
                parsed_seed = int(effective_seed)
            except (TypeError, ValueError):
                self.logger.warning(
                    "Invalid seed configured for stage '%s': %r. Ignoring seed.",
                    stage_name,
                    effective_seed,
                )

        self.logger.info(
            "Initializing %s LLM: provider=%s, model=%s, temperature=%s, seed=%s",
            purpose_label,
            provider,
            model_name or "<not set>",
            effective_temperature,
            parsed_seed,
        )

        if provider == "mistral":
            mistral_config = llm_config.get("mistral", {})
            model_path = mistral_config.get("model_path")
            if not model_path:
                raise ValueError("llm.mistral.model_path is required when provider is 'mistral'")
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Mistral model not found at configured path: {model_path}")

            from llama_cpp import Llama

            llm_instance = Llama(
                model_path=model_path,
                n_ctx=mistral_config.get("n_ctx", 4096),
                n_threads=mistral_config.get("n_threads", 4),
                seed=parsed_seed if parsed_seed is not None else -1,
            )
            runtime_info = {
                "stage": stage_name,
                "provider": provider,
                "model_path": model_path,
                "temperature": effective_temperature,
                "seed": parsed_seed,
            }
            return llm_instance, runtime_info

        if not model_name:
            raise ValueError(
                f"Model name missing for provider '{provider}' on stage '{stage_name}'. "
                f"Set llm.model_name or llm.stages.{stage_name}.model_name in config.yaml"
            )

        init_kwargs = {"model_name": model_name}
        if provider == "gemini":
            init_kwargs["api_key"] = llm_config.get("api_key", "")
            init_kwargs["temperature"] = effective_temperature
            if parsed_seed is not None:
                init_kwargs["seed"] = parsed_seed
        elif provider == "openai":
            init_kwargs["api_key"] = llm_config.get("api_key", "")
            init_kwargs["temperature"] = effective_temperature
            if parsed_seed is not None:
                init_kwargs["seed"] = parsed_seed

        llm_instance = create_llm(provider, **init_kwargs)
        runtime_info = {
            "stage": stage_name,
            "provider": provider,
            "model_name": model_name,
            "temperature": effective_temperature,
            "seed": parsed_seed,
        }
        return llm_instance, runtime_info

    def _get_kg_model(self):
        kg_name = self._sanitize_name(self.config.get("kg.name", "default"), "default")
        stage_model = self.config.get("llm.stages.query_generation.model_name", None)
        configured_model = stage_model or self.config.get("llm.model_name", None)
        if configured_model:
            model_name = self._sanitize_name(configured_model, "default")
        else:
            stage_provider = self.config.get("llm.stages.query_generation.provider", None)
            model_name = self._sanitize_name(stage_provider or self.config.get("llm.provider", "default"), "default")
        return kg_name, model_name

    def _get_output_dirs(self):
        kg_name, model_name = self._get_kg_model()
        # Determine if current run used TOON input (set in answer_question)
        use_toon = bool(getattr(self, "_use_toon_input", False))

        base_results = self.config.get("output.results_dir", "tests/results")
        base_extractions = self.config.get("output.extractions_dir", "tests/extractions")
        base_prompts = self.config.get("output.prompts_dir", "tests/prompts")
        base_evaluation = self.config.get("output.evaluation_results_dir", "tests/evaluation_results")

        if use_toon:
            base_results = self.config.get("output.toon_results_dir", f"{base_results}_toon")
            base_extractions = self.config.get("output.toon_extractions_dir", f"{base_extractions}_toon")
            base_prompts = self.config.get("output.toon_prompts_dir", f"{base_prompts}_toon")
            base_evaluation = self.config.get("output.toon_evaluation_results_dir", f"{base_evaluation}_toon")

        dirs = {
            "kg": kg_name,
            "model": model_name,
            "results": os.path.join(base_results, kg_name, model_name),
            "extractions": os.path.join(base_extractions, kg_name, model_name),
            "prompts": os.path.join(base_prompts, kg_name, model_name),
            "evaluation": os.path.join(base_evaluation, f"{kg_name}_{model_name}", "evaluation"),
        }
        for key in ["results", "extractions", "prompts", "evaluation"]:
            os.makedirs(dirs[key], exist_ok=True)
        return dirs
    
    def _save_prompt_immediately(self, prompt_type, prompt_content, question):
        """Save a single prompt immediately (for debugging even on failures)."""
        prompts_dir = self._get_output_dirs()["prompts"]
        os.makedirs(prompts_dir, exist_ok=True)
        
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"prompt_{timestamp}_{prompt_type}.txt"
        filepath = os.path.join(prompts_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"Question: {question}\n")
                f.write(f"=== {prompt_type.upper()} PROMPT ===\n\n")
                f.write(prompt_content)
            self.logger.debug(f"Saved {prompt_type} prompt to {filepath}")
        except Exception as e:
            self.logger.warning(f"Failed to save prompt: {e}")
    
    def _save_extractions(self, question, relevant_classes, property_selection):
        """Save extracted classes and properties to separate files.
        
        Args:
            question: The user's natural language question
            relevant_classes: List of extracted classes
            property_selection: List of extracted properties per class
        """
        dirs = self._get_output_dirs()
        extractions_dir = dirs["extractions"]
        os.makedirs(extractions_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save classes
        classes_file = os.path.join(extractions_dir, f"classes_{timestamp}.json")
        classes_data = {
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "kg": dirs["kg"],
            "model": dirs["model"],
            "extracted_classes": relevant_classes,
            "total_classes": len(relevant_classes)
        }
        try:
            with open(classes_file, 'w', encoding='utf-8') as f:
                json.dump(classes_data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Saved extracted classes to {classes_file}")
        except Exception as e:
            self.logger.warning(f"Failed to save extracted classes: {e}")
        
        # Save properties
        properties_file = os.path.join(extractions_dir, f"properties_{timestamp}.json")
        properties_data = {
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "kg": dirs["kg"],
            "model": dirs["model"],
            "property_selection": property_selection,
            "total_classes_with_properties": len(property_selection)
        }
        try:
            with open(properties_file, 'w', encoding='utf-8') as f:
                json.dump(properties_data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Saved extracted properties to {properties_file}")
        except Exception as e:
            self.logger.warning(f"Failed to save extracted properties: {e}")
        
        # Save combined extraction summary
        summary_file = os.path.join(extractions_dir, f"extraction_summary_{timestamp}.json")
        summary_data = {
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "kg": dirs["kg"],
            "model": dirs["model"],
            "extracted_classes": relevant_classes,
            "property_selection": property_selection,
            "statistics": {
                "total_classes": len(relevant_classes),
                "total_classes_with_properties": len(property_selection),
                "total_properties": sum(len(p.get("relevant_properties", [])) for p in property_selection)
            }
        }
        try:
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Saved extraction summary to {summary_file}")
        except Exception as e:
            self.logger.warning(f"Failed to save extraction summary: {e}")
    
    
    def _init_llm(self):
        """Initialize LLMs if not already initialized."""
        if self.llm_reasoning is None:
            self.llm_reasoning, self.llm_reasoning_info = self._init_stage_llm(
                "class_extraction",
                "Reasoning (class/property extraction)",
            )
        
        if self.llm_generation is None:
            self.llm_generation, self.llm_generation_info = self._init_stage_llm(
                "query_generation",
                "Generation (missing-id/query generation)",
            )
    
    def _init_parser(self):
        """Initialize schema parser if not already initialized."""
        if self.parser is None:
            fix_syntax = self.config.get("schema.fix_syntax", True)
            self.parser = SHACLSchemaParser(fix_syntax=fix_syntax)
    
    def _init_executor(self):
        """Initialize SPARQL executor if not already initialized."""
        if self.executor is None:
            sparql_config = self.config.get_sparql_config()
            self.executor = SPARQLExecutor(
                endpoint_url=sparql_config.get("endpoint_url"),
                timeout=sparql_config.get("timeout", 30),
                default_graph=sparql_config.get("default_graph")
            )
    
    def extract_schema(self, ttl_path, output_name=None):
        """
        Extract schema from SHACL TTL file.
        
        Args:
            ttl_path: Path to SHACL Turtle file
            output_name: Name for output JSON file (auto-generated if None)
            
        Returns:
            Parsed schema dictionary
        """
        self.logger.info(f"Starting schema extraction from {ttl_path}")
        
        self._init_parser()
        
        # Generate output path
        if output_name is None:
            output_name = Path(ttl_path).stem + "_mschema.json"
        
        output_dir = self.config.get("schema.output_dir", "data/output")
        output_path = os.path.join(output_dir, output_name)
        
        # Parse schema
        schema = self.parser.parse(ttl_path, save_json_path=output_path)
        
        self.logger.info(f"Schema extracted successfully to {output_path}")
        return schema
    
    def _create_filtered_schema(self, schema, property_selection):
        """
        Create a filtered schema containing only classes selected in property_selection.
        
        Args:
            schema: Full schema dictionary
            property_selection: List of selected classes and their properties
            
        Returns:
            Filtered schema dictionary with only relevant classes
        """
        prefixes = schema.get("prefixes", {})
        all_classes = schema.get("classes", {})
        filtered_classes = {}
        
        # Filter classes based on property_selection
        for item in property_selection:
            class_name_input = item.get("class_name", "")
            relevant_props = item.get("relevant_properties", [])
            
            # Match the correct class key (prefixed or not)
            matched_class_key = None
            for k in all_classes.keys():
                if k == class_name_input or k.split(":")[-1] == class_name_input:
                    matched_class_key = k
                    break
            
            if not matched_class_key:
                continue
            
            class_data = all_classes[matched_class_key]
            class_copy = {
                "class_label": class_data.get("class_label", ""),
                "class_examples": class_data.get("class_examples", []),
                "properties": []
            }
            
            # Filter only relevant properties
            for prop in class_data.get("properties", []):
                prop_name = prop.get("property_name", "")
                prop_label = prop.get("property_label", "")
                if any(
                    rp == prop_label or rp == prop_name.split(":")[-1] or rp in prop_name
                    for rp in relevant_props
                ):
                    class_copy["properties"].append(prop)
            
            if class_copy["properties"]:
                filtered_classes[matched_class_key] = class_copy
        
        filtered_schema = {
            "prefixes": prefixes,
            "classes": filtered_classes
        }
        
        return filtered_schema
    
    def schema_to_toon(self, json_schema_path, output_path=None):
        """
        Convert a JSON mschema to TOON (Token-Oriented Object Notation) format.
        TOON dramatically reduces tokens for LLM prompts, especially for uniform arrays.
        
        Args:
            json_schema_path: Path to JSON mschema file
            output_path: Path for TOON output file (auto-generated if None)
            
        Returns:
            Path to generated TOON file
        """
        self.logger.info(f"Converting schema to TOON format: {json_schema_path}")
        
        # Load JSON schema
        with open(json_schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
        
        # Encode to TOON with config settings
        include_examples = self.config.get("toon.formatting.include_examples", True)
        include_descriptions = self.config.get("toon.formatting.include_descriptions", True)
        max_examples = self.config.get("toon.formatting.max_examples", 2)
        toon_content = TOONFormatter.encode(
            schema,
            include_examples=include_examples,
            include_descriptions=include_descriptions,
            max_examples=max_examples,
        )
        
        # Generate output path if not provided
        if output_path is None:
            base_path = json_schema_path.rsplit('.', 1)[0]
            output_path = f"{base_path}.toon"
        
        # Create output directory if needed
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        
        # Write TOON file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(toon_content)
        
        # Log token savings (rough estimate)
        json_tokens = len(schema) * 3  # Very rough estimate
        toon_tokens = len(toon_content.split()) * 1.3  # Rough token count
        savings_percent = (1 - toon_tokens / json_tokens) * 100 if json_tokens > 0 else 0
        
        self.logger.info(
            f"Schema converted to TOON successfully. "
            f"Output: {output_path} (estimated token savings: ~{savings_percent:.0f}%)"
        )
        
        return output_path
    
    def schema_from_toon(self, toon_schema_path):
        """
        Load and decode a TOON schema file to JSON format.
        
        Args:
            toon_schema_path: Path to TOON schema file
            
        Returns:
            Decoded schema dictionary
        """
        self.logger.info(f"Loading TOON schema: {toon_schema_path}")
        
        with open(toon_schema_path, 'r', encoding='utf-8') as f:
            toon_content = f.read()
        
        schema = TOONFormatter.decode(toon_content)
        self.logger.info(f"TOON schema decoded successfully")
        
        return schema
    
    def answer_question(self, question, schema_path):
        """
        Answer a natural language question using the pipeline.
        
        Args:
            question: Natural language question
            schema_path: Path to m_schema JSON file
            
        Returns:
            Dictionary containing results and intermediate outputs
        """
        self.logger.info(f"Processing question: {question}")

        self._init_executor()
        
        output_dirs = self._get_output_dirs()
        kg_name = output_dirs["kg"]
        model_name = output_dirs["model"]

        # Initialize new comprehensive results manager in per-KG/model directory
        rm = ResultsManager(output_dirs["results"])
        result = rm.create_result_entry(question)
        result.setdefault("metadata", {})["kg"] = kg_name
        result.setdefault("metadata", {})["model"] = model_name
        result.setdefault("metadata", {})["llm_runtime"] = {
            "reasoning": self.llm_reasoning_info,
            "generation": self.llm_generation_info,
        }
        
        results = {
            "question": question,
            "timestamp": datetime.now().isoformat(),
            "intermediate": {}
        }

        def refresh_llm_runtime_metadata():
            runtime_payload = {
                "reasoning": self.llm_reasoning_info,
                "generation": self.llm_generation_info,
            }
            result.setdefault("metadata", {})["llm_runtime"] = runtime_payload
            results["intermediate"]["llm_runtime"] = runtime_payload

        refresh_llm_runtime_metadata()
        
        # Load schema (support both JSON and TOON formats)
        self.logger.info(f"Loading schema from {schema_path}")
        with open(schema_path, 'r', encoding='utf-8') as f:
            if schema_path.lower().endswith('.toon'):
                self.logger.info("Schema detected as TOON format, decoding...")
                toon_content = f.read()
                schema = TOONFormatter.decode(toon_content)
            else:
                schema = json.load(f)
        routing_enabled = self.config.get("pipeline.stages.query_routing", True)
        route_decision = {
            "route": "sparql",
            "confidence": 0.0,
            "reason": "Routing disabled; defaulting to SPARQL.",
        }

        schema_summary = ""
        try:
            class_names = list((schema or {}).get("classes", {}).keys())
            sample_classes = ", ".join(class_names[:8]) if class_names else "(none)"
            schema_summary = f"Classes: {len(class_names)} | Samples: {sample_classes}"
        except Exception:
            schema_summary = "(schema summary unavailable)"

        if routing_enabled:
            if self.llm_reasoning is None:
                self.llm_reasoning, self.llm_reasoning_info = self._init_stage_llm(
                    "query_routing",
                    "Routing (query type decision)",
                )
                refresh_llm_runtime_metadata()

            router_llm = MistralLLMWrapper(self.llm_reasoning) if hasattr(self.llm_reasoning, '__call__') else self.llm_reasoning
            router = QueryRouter(router_llm)
            route_decision = router.route(question, schema_summary=schema_summary)
            results["intermediate"]["query_routing"] = route_decision
            results["intermediate"]["query_routing_prompt"] = router.last_prompt
            self.logger.info(
                "[ROUTING] route=%s confidence=%.2f reason=%s",
                route_decision.get("route"),
                float(route_decision.get("confidence") or 0.0),
                route_decision.get("reason"),
            )
            rm.update_query_routing(
                result,
                route=route_decision.get("route"),
                confidence=route_decision.get("confidence"),
                reason=route_decision.get("reason"),
                config={"enabled": routing_enabled},
                schema_summary=schema_summary,
                prompt=router.last_prompt,
            )

            if route_decision.get("route") != "sparql":
                friendly_route = route_decision.get("route") or "non-sparql"
                message = (
                    f"Routed to {friendly_route} workflow. This pipeline currently executes SPARQL only. "
                    f"Reason: {route_decision.get('reason', '')}"
                )
                results["routing"] = route_decision
                results["message"] = message
                result["pipeline"]["query_execution"]["formatted_results"] = message
                rm.update_query_execution(
                    result,
                    executed_query=None,
                    query_type=friendly_route.upper(),
                    raw_results=None,
                    formatted_results=message,
                    error=None,
                )
                rm.save_result(result)
                return results
        
        # Format base schema (without examples, will be customized per step)
        formatter = SchemaFormatter(schema)
        # Detect whether the input schema was provided as TOON (user switched to .toon file)
        use_toon_input = str(schema_path).lower().endswith('.toon')
        # Expose flag to other helpers so output dirs route correctly
        self._use_toon_input = use_toon_input
        if use_toon_input:
            # Store TOON-encoded schema for prompts instead of formatted mschema text
            include_examples = self.config.get("toon.formatting.include_examples", True)
            include_descriptions = self.config.get("toon.formatting.include_descriptions", True)
            max_examples = self.config.get("toon.formatting.max_examples", 2)
            results["intermediate"]["formatted_schema"] = TOONFormatter.encode(
                schema,
                include_examples=include_examples,
                include_descriptions=include_descriptions,
                max_examples=max_examples,
            )
        else:
            results["intermediate"]["formatted_schema"] = formatter.format_clean(include_examples=True)  # Store full version
        # Note: formatted_schema_missing will be computed later when property_selection is available
        # so we can use filtered schema for TOON
        formatted_schema_missing = None  # Will be computed per-step based on property_selection
        
        # Initialize shared embedding evaluator if using embedding method (to avoid loading model twice)
        extraction_method = self.config.get("pipeline.extraction.method", "llm")
        embedding_config = self.config.get("pipeline.extraction.embedding", {})
        toon_direct_mode_requested = bool(embedding_config.get("toon_direct_mode", False))
        if extraction_method == "embedding":
            embedding_mode = "direct_toon" if (use_toon_input and toon_direct_mode_requested) else "decoded_json"
        else:
            embedding_mode = "llm"
        shared_embedding_evaluator = None

        class_extraction_enabled = self.config.get("pipeline.stages.class_extraction", True)
        property_extraction_enabled = self.config.get("pipeline.stages.property_extraction", True)
        missing_id_enabled = self.config.get("pipeline.stages.missing_id_extraction", True)
        query_generation_enabled = self.config.get("pipeline.stages.query_generation", True)

        results["intermediate"]["extraction_method"] = extraction_method
        results["intermediate"]["embedding_mode"] = embedding_mode
        result.setdefault("metadata", {})["extraction_method"] = extraction_method
        result.setdefault("metadata", {})["embedding_mode"] = embedding_mode
        result.setdefault("metadata", {})["toon_direct_mode"] = toon_direct_mode_requested

        needs_reasoning_llm = extraction_method == "llm" and (class_extraction_enabled or property_extraction_enabled)
        if needs_reasoning_llm and self.llm_reasoning is None:
            reasoning_stage = "class_extraction" if class_extraction_enabled else "property_extraction"
            self.llm_reasoning, self.llm_reasoning_info = self._init_stage_llm(
                reasoning_stage,
                "Reasoning (class/property extraction)",
            )
            refresh_llm_runtime_metadata()
        
        if extraction_method == "embedding":
            EmbeddingEvaluator = None
            try:
                from .embedding_evaluator_v2 import EmbeddingEvaluator as _EmbeddingEvaluator
                EmbeddingEvaluator = _EmbeddingEvaluator
            except (ImportError, KeyError) as import_error:
                self.logger.warning(
                    "Relative import for EmbeddingEvaluator failed (%s). Trying file-based fallback import.",
                    import_error,
                )
                try:
                    module_path = Path(__file__).with_name("embedding_evaluator_v2.py")
                    spec = importlib.util.spec_from_file_location(
                        "nl2sparql.embedding_evaluator_v2",
                        str(module_path),
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        EmbeddingEvaluator = getattr(module, "EmbeddingEvaluator", None)
                except Exception as fallback_error:
                    self.logger.error(
                        "Fallback import for EmbeddingEvaluator also failed: %s",
                        fallback_error,
                    )

            if EmbeddingEvaluator is None:
                self.logger.error("Embedding method selected, but EmbeddingEvaluator could not be imported.")

            try:
                embedding_model_name = embedding_config.get("model", "all-mpnet-base-v2")
                include_descriptions = embedding_config.get("include_descriptions", True)
                include_examples = embedding_config.get("include_examples", True)
                cache_config = embedding_config.get("cache", {})
                use_cache = cache_config.get("enabled", True)
                cache_dir = cache_config.get("cache_dir", "cache/embeddings")

                if EmbeddingEvaluator is not None:
                    shared_embedding_evaluator = EmbeddingEvaluator(
                        embedding_model_name,
                        include_descriptions=include_descriptions,
                        include_examples=include_examples,
                        use_cache=use_cache,
                        cache_dir=cache_dir
                    )
                    self.logger.info(f"[SHARED] Embedding evaluator initialized (will be used for both classes and properties)")
            except Exception as e:
                self.logger.error(f"Failed to initialize shared embedding evaluator: {e}")
        
        # Evaluate class relevance (Use Mistral for reasoning)
        if class_extraction_enabled:
            # Get class extraction examples config
            include_examples_class = self.config.get("pipeline.schema.class_extraction.include_examples", True)
            # For smaller token usage, allow TOON encoding when requested
            if use_toon_input:
                # Encode the full schema (or class-focused subset) as TOON
                include_examples = self.config.get("toon.formatting.include_examples", True)
                include_descriptions = self.config.get("toon.formatting.include_descriptions", True)
                max_examples = self.config.get("toon.formatting.max_examples", 2)
                formatted_schema_class = TOONFormatter.encode(
                    schema,
                    include_examples=include_examples,
                    include_descriptions=include_descriptions,
                    max_examples=max_examples,
                )
            else:
                formatted_schema_class = formatter.format_clean(include_examples=include_examples_class)
            # Debug preview for class extraction schema
            try:
                preview = str(formatted_schema_class)[:200]
                self.logger.info(
                    f"[TOON DEBUG] use_toon_input={use_toon_input} | class preview={preview!r} | contains_Class_Name={'Class Name:' in str(formatted_schema_class)}"
                )
            except Exception:
                pass
            
            self.logger.info(f"Evaluating class relevance with {extraction_method} method (examples={include_examples_class})...")
            llm_for_class = MistralLLMWrapper(self.llm_reasoning) if hasattr(self.llm_reasoning, '__call__') else self.llm_reasoning
            evaluator = ClassRelevanceEvaluator(
                llm_for_class, 
                method=extraction_method,
                embedding_config=embedding_config,
                embedding_evaluator=shared_embedding_evaluator
            )
            relevant_classes = evaluator.evaluate(question, formatted_schema_class, schema_json=schema)
            results["intermediate"]["relevant_classes"] = relevant_classes
            results["intermediate"]["class_prompts"] = evaluator.prompts
            results["intermediate"]["extraction_method"] = extraction_method
            results["intermediate"]["embedding_mode"] = embedding_mode
            results["intermediate"]["class_extraction_config"] = {"include_examples": include_examples_class}
            result.setdefault("metadata", {})["extraction_method"] = extraction_method
            result.setdefault("metadata", {})["embedding_mode"] = embedding_mode
            result.setdefault("metadata", {})["toon_direct_mode"] = toon_direct_mode_requested
            self.logger.info(f"Found {len(relevant_classes)} relevant classes")
            
            # Generate schema without examples for reference
            if use_toon_input:
                include_examples = self.config.get("toon.formatting.include_examples", True)
                include_descriptions = self.config.get("toon.formatting.include_descriptions", True)
                max_examples = self.config.get("toon.formatting.max_examples", 2)
                formatted_schema_class_no_examples = TOONFormatter.encode(
                    schema,
                    include_examples=False,
                    include_descriptions=include_descriptions,
                    max_examples=max_examples,
                )
            else:
                formatted_schema_class_no_examples = formatter.format_clean(include_examples=False)
            
            # Update results manager with class extraction
            rm.update_class_extraction(
                result,
                extracted_classes=relevant_classes,
                config={"include_examples": include_examples_class},
                schema_with=formatted_schema_class,
                schema_without=formatted_schema_class_no_examples,
                prompts=evaluator.prompts
            )
            
            # Save extracted classes immediately (if property extraction is disabled, this will be the final save)
            if not property_extraction_enabled:
                self._save_extractions(question, relevant_classes, [])
        else:
            relevant_classes = []
        
        # Evaluate property relevance (Use Mistral for reasoning)
        if property_extraction_enabled and relevant_classes:
            # Get property extraction examples config
            include_examples_prop = self.config.get("pipeline.schema.property_extraction.include_examples", True)
            if use_toon_input:
                include_examples = self.config.get("toon.formatting.include_examples", True)
                include_descriptions = self.config.get("toon.formatting.include_descriptions", True)
                max_examples = self.config.get("toon.formatting.max_examples", 2)
                formatted_schema_prop = TOONFormatter.encode(
                    schema,
                    include_examples=include_examples,
                    include_descriptions=include_descriptions,
                    max_examples=max_examples,
                )
            else:
                formatted_schema_prop = formatter.format_clean(include_examples=include_examples_prop)
            # Debug preview for property extraction schema
            try:
                preview = str(formatted_schema_prop)[:200]
                self.logger.info(
                    f"[TOON DEBUG] use_toon_input={use_toon_input} | prop preview={preview!r} | contains_Class_Name={'Class Name:' in str(formatted_schema_prop)}"
                )
            except Exception:
                pass
            
            self.logger.info(f"Evaluating property relevance with {extraction_method} method (examples={include_examples_prop})...")
            llm_for_props = MistralLLMWrapper(self.llm_reasoning) if hasattr(self.llm_reasoning, '__call__') else self.llm_reasoning
            prop_evaluator = PropertyEvaluator(
                llm_for_props,
                method=extraction_method,
                embedding_config=embedding_config,
                embedding_evaluator=shared_embedding_evaluator  # Reuse the same evaluator instance
            )
            property_selection = prop_evaluator.evaluate(question, relevant_classes, formatted_schema_prop, schema_json=schema)
            results["intermediate"]["property_selection"] = property_selection
            results["intermediate"]["property_prompts"] = prop_evaluator.prompts
            results["intermediate"]["property_extraction_config"] = {"include_examples": include_examples_prop}
            self.logger.info(f"Property selection completed")
            
            # Generate schema without examples for reference
            if use_toon_input:
                include_examples = self.config.get("toon.formatting.include_examples", True)
                include_descriptions = self.config.get("toon.formatting.include_descriptions", True)
                max_examples = self.config.get("toon.formatting.max_examples", 2)
                formatted_schema_prop_no_examples = TOONFormatter.encode(
                    schema,
                    include_examples=False,
                    include_descriptions=include_descriptions,
                    max_examples=max_examples,
                )
            else:
                formatted_schema_prop_no_examples = formatter.format_clean(include_examples=False)
            
            # Update results manager with property extraction
            rm.update_property_extraction(
                result,
                property_selection=property_selection,
                config={"include_examples": include_examples_prop},
                schema_with=formatted_schema_prop,
                schema_without=formatted_schema_prop_no_examples,
                prompts=prop_evaluator.prompts
            )
            
            # Save extracted classes and properties to separate folder
            self._save_extractions(question, relevant_classes, property_selection)
        else:
            property_selection = []
        
        # Check for missing IDs (Use Gemini for generation)
        missing_iris = {}
        missing_iris_by_class = {}
        self.logger.info(f"Missing ID Extraction enabled: {missing_id_enabled}")
        
        if missing_id_enabled and property_selection:
            if self.llm_generation is None:
                self.llm_generation, self.llm_generation_info = self._init_stage_llm(
                    "query_generation",
                    "Generation (missing-id/query generation)",
                )
                refresh_llm_runtime_metadata()
            self.logger.info("Checking for missing entity IDs with generation LLM...")
            llm_for_gen = MistralLLMWrapper(self.llm_generation) if hasattr(self.llm_generation, '__call__') else self.llm_generation
            generator = SPARQLGenerator(llm_for_gen)
            include_descriptions_missing = self.config.get("pipeline.schema.missing_id_extraction.include_descriptions", False)
            missing_id_property_selection = property_selection
            self.logger.info(
                "Missing-ID pre-step rerank disabled: using original property selection (%s classes).",
                len(missing_id_property_selection),
            )
            results["intermediate"]["missing_id_property_selection"] = missing_id_property_selection
            
            # Compute formatted schema for missing ID (using filtered schema for TOON)
            if use_toon_input:
                # For TOON, use filtered schema (only relevant classes and properties)
                filtered_schema_for_missing_id = self._create_filtered_schema(schema, missing_id_property_selection)
                include_examples = self.config.get("toon.formatting.include_examples", True)
                include_descriptions = self.config.get("toon.formatting.include_descriptions", True)
                max_examples = self.config.get("toon.formatting.max_examples", 2)
                formatted_schema_missing = TOONFormatter.encode(
                    filtered_schema_for_missing_id,
                    include_examples=include_examples,
                    include_descriptions=include_descriptions,
                    max_examples=max_examples,
                )
                self.logger.info(
                    f"[TOON] Encoded filtered schema with {len(filtered_schema_for_missing_id.get('classes', {}))} classes for missing ID extraction"
                )
            else:
                # For non-TOON, use full schema with examples
                formatted_schema_missing = formatter.format_clean(include_examples=True)
            
            # Generate query (this sets generator.missing_id_prompt)
            missing_id_query = generator.generate_missing_id_query(
                question,
                missing_id_property_selection,
                schema,
                include_descriptions=include_descriptions_missing,
                schema_text_override=(formatted_schema_missing if use_toon_input else None),
            )
            
            # Save prompt immediately after it's ready (before LLM execution completes)
            results["intermediate"]["missing_id_prompt"] = generator.missing_id_prompt
            results["intermediate"]["entity_extraction_prompt"] = getattr(generator, "entity_extraction_prompt", None)
            results["intermediate"]["entity_extraction_response"] = getattr(generator, "entity_extraction_response", None)
            results["intermediate"]["entity_extraction_mentions"] = getattr(generator, "entity_extraction_mentions", [])
            if getattr(generator, "entity_extraction_prompt", None):
                self._save_prompt_immediately("entity_extraction", generator.entity_extraction_prompt, question)
            if generator.missing_id_prompt:
                self._save_prompt_immediately("missing_id", generator.missing_id_prompt, question)
            
            results["intermediate"]["missing_id_query"] = missing_id_query
            
            # Execute missing ID query to get actual IRIs
            if missing_id_query and missing_id_query.strip():
                self.logger.info("Executing missing ID query to retrieve entity IRIs...")
                try:
                    # Split queries by PREFIX boundaries to execute UNION queries separately
                    # This handles cases where multiple UNION queries are generated
                    queries_to_execute = []
                    current_query = []
                    prefixes = []
                    
                    lines = missing_id_query.split('\n')
                    for line in lines:
                        if line.strip().startswith('PREFIX'):
                            if not prefixes or line not in prefixes:
                                prefixes.append(line)
                                if current_query and any(kw in '\n'.join(current_query).upper() for kw in ['SELECT', 'WHERE']):
                                    queries_to_execute.append('\n'.join(prefixes + current_query))
                                    current_query = []
                        elif line.strip().startswith('SELECT'):
                            if current_query and any(kw in '\n'.join(current_query).upper() for kw in ['SELECT', 'WHERE']):
                                queries_to_execute.append('\n'.join(prefixes + current_query))
                            current_query = [line]
                        elif current_query or any(kw in line.upper() for kw in ['WHERE', 'VALUES', 'FILTER', '}']):
                            current_query.append(line)
                    
                    if current_query:
                        queries_to_execute.append('\n'.join(prefixes + current_query))
                    
                    # If no split was successful, use original query
                    if not queries_to_execute:
                        queries_to_execute = [missing_id_query]
                    
                    self.logger.info(f"Executing {len(queries_to_execute)} missing ID query/queries separately...")

                    missing_id_llm_repair_enabled = self.config.get("pipeline.stages.missing_id.enable_llm_repair", True)
                    missing_id_repair_generator = None
                    if missing_id_llm_repair_enabled:
                        llm_for_missing_id_repair = MistralLLMWrapper(self.llm_generation) if hasattr(self.llm_generation, '__call__') else self.llm_generation
                        missing_id_repair_generator = SPARQLGenerator(llm_for_missing_id_repair)
                        results["intermediate"].setdefault("missing_id_query_repairs", [])

                    # Optional cap for results taken from each missing-ID query (post-execution, no LIMIT injection)
                    max_results_per_query = self.config.get("pipeline.stages.missing_id.max_results_per_query", None)
                    if max_results_per_query is not None:
                        try:
                            max_results_per_query = int(max_results_per_query)
                            if max_results_per_query <= 0:
                                max_results_per_query = None
                        except (ValueError, TypeError):
                            self.logger.warning(f"Invalid pipeline.stages.missing_id.max_results_per_query: {max_results_per_query}")
                            max_results_per_query = None
                    
                    # Execute each query separately and accumulate results
                    per_query_label_keys = []
                    collected_partial_matches = []
                    for q_idx, query_to_exec in enumerate(queries_to_execute, 1):
                        if query_to_exec.strip():
                            try:
                                self.logger.debug(f"Executing query {q_idx}/{len(queries_to_execute)}")
                                query_partial_match = self._extract_partial_match_from_query(query_to_exec)
                                if query_partial_match:
                                    collected_partial_matches.append(query_partial_match)
                                query_class = self._extract_missing_id_class_from_query(query_to_exec)
                                missing_id_results = self.executor.execute(query_to_exec)
                                if isinstance(missing_id_results, dict) and missing_id_results.get("error"):
                                    raise RuntimeError(str(missing_id_results.get("error")))
                                query_label_keys = []

                                if max_results_per_query is not None:
                                    bindings = missing_id_results.get("results", {}).get("bindings", [])
                                    if isinstance(bindings, list) and len(bindings) > max_results_per_query:
                                        self.logger.info(
                                            f"Trimming missing-ID query {q_idx} results from {len(bindings)} to {max_results_per_query} (config: max_results_per_query)"
                                        )
                                        missing_id_results["results"]["bindings"] = bindings[:max_results_per_query]

                                results["intermediate"][f"missing_id_results_{q_idx}"] = missing_id_results
                                
                                # Extract IRIs from results
                                if missing_id_results.get("results", {}).get("bindings"):
                                    for binding in missing_id_results["results"]["bindings"]:
                                        if "IRI" in binding:
                                            iri = binding["IRI"].get("value")
                                            label = binding.get("fullValue", {}).get("value", "")
                                            if not iri:
                                                continue
                                            base_label = (label or "").strip() or iri
                                            existing_iri = missing_iris.get(base_label)
                                            if existing_iri is None:
                                                missing_iris[base_label] = iri
                                                query_label_keys.append(base_label)
                                                self._add_missing_iri_class_mapping(missing_iris_by_class, query_class, base_label, iri)
                                            elif existing_iri == iri:
                                                self._add_missing_iri_class_mapping(missing_iris_by_class, query_class, base_label, iri)
                                                continue
                                            else:
                                                # Preserve distinct IRIs even when labels collide (e.g., "Sensor")
                                                iri_tail = iri.rsplit('/', 1)[-1]
                                                unique_label = f"{base_label} ({iri_tail})"
                                                suffix = 2
                                                while unique_label in missing_iris and missing_iris[unique_label] != iri:
                                                    unique_label = f"{base_label} ({iri_tail}) [{suffix}]"
                                                    suffix += 1
                                                missing_iris[unique_label] = iri
                                                query_label_keys.append(unique_label)
                                                self._add_missing_iri_class_mapping(missing_iris_by_class, query_class, unique_label, iri)
                                per_query_label_keys.append(query_label_keys)
                            except Exception as e:
                                self.logger.debug(f"Query {q_idx} failed: {e}")

                                if not missing_id_llm_repair_enabled or missing_id_repair_generator is None:
                                    continue

                                try:
                                    self.logger.warning(
                                        "Missing-ID query %s failed. Attempting LLM-based repair and retry once.",
                                        q_idx,
                                    )
                                    corrected_missing_id_query = missing_id_repair_generator.correct_query_from_error(
                                        original_query=query_to_exec,
                                        error_message=str(e),
                                        question=question,
                                        schema=schema,
                                    )

                                    if (
                                        not corrected_missing_id_query
                                        or not corrected_missing_id_query.strip()
                                        or corrected_missing_id_query.strip() == query_to_exec.strip()
                                    ):
                                        self.logger.debug(
                                            "Missing-ID query %s repair skipped (empty or unchanged correction).",
                                            q_idx,
                                        )
                                        continue

                                    repaired_results = self.executor.execute(corrected_missing_id_query)
                                    if isinstance(repaired_results, dict) and repaired_results.get("error"):
                                        raise RuntimeError(str(repaired_results.get("error")))
                                    query_partial_match = self._extract_partial_match_from_query(corrected_missing_id_query) or self._extract_partial_match_from_query(query_to_exec)
                                    if query_partial_match:
                                        collected_partial_matches.append(query_partial_match)
                                    query_class = self._extract_missing_id_class_from_query(corrected_missing_id_query) or self._extract_missing_id_class_from_query(query_to_exec)
                                    query_label_keys = []

                                    if max_results_per_query is not None:
                                        bindings = repaired_results.get("results", {}).get("bindings", [])
                                        if isinstance(bindings, list) and len(bindings) > max_results_per_query:
                                            self.logger.info(
                                                f"Trimming repaired missing-ID query {q_idx} results from {len(bindings)} to {max_results_per_query} (config: max_results_per_query)"
                                            )
                                            repaired_results["results"]["bindings"] = bindings[:max_results_per_query]

                                    results["intermediate"][f"missing_id_results_{q_idx}"] = repaired_results
                                    results["intermediate"][f"missing_id_query_repair_{q_idx}"] = corrected_missing_id_query

                                    repair_prompt = missing_id_repair_generator.query_repair_prompt
                                    if repair_prompt:
                                        results["intermediate"][f"missing_id_query_repair_prompt_{q_idx}"] = repair_prompt
                                        self._save_prompt_immediately("missing_id_query_repair", repair_prompt, question)

                                    if repaired_results.get("results", {}).get("bindings"):
                                        for binding in repaired_results["results"]["bindings"]:
                                            if "IRI" in binding:
                                                iri = binding["IRI"].get("value")
                                                label = binding.get("fullValue", {}).get("value", "")
                                                if not iri:
                                                    continue

                                                base_label = (label or "").strip() or iri
                                                existing_iri = missing_iris.get(base_label)
                                                if existing_iri is None:
                                                    missing_iris[base_label] = iri
                                                    query_label_keys.append(base_label)
                                                    self._add_missing_iri_class_mapping(missing_iris_by_class, query_class, base_label, iri)
                                                elif existing_iri == iri:
                                                    self._add_missing_iri_class_mapping(missing_iris_by_class, query_class, base_label, iri)
                                                    continue
                                                else:
                                                    iri_tail = iri.rsplit('/', 1)[-1]
                                                    unique_label = f"{base_label} ({iri_tail})"
                                                    suffix = 2
                                                    while unique_label in missing_iris and missing_iris[unique_label] != iri:
                                                        unique_label = f"{base_label} ({iri_tail}) [{suffix}]"
                                                        suffix += 1
                                                    missing_iris[unique_label] = iri
                                                    query_label_keys.append(unique_label)
                                                    self._add_missing_iri_class_mapping(missing_iris_by_class, query_class, unique_label, iri)

                                    per_query_label_keys.append(query_label_keys)
                                    results["intermediate"]["missing_id_query_repairs"].append(
                                        {
                                            "query_index": q_idx,
                                            "applied": True,
                                            "reason": str(e),
                                        }
                                    )
                                    self.logger.info("Missing-ID repaired query %s executed successfully.", q_idx)
                                except Exception as repair_error:
                                    self.logger.warning(
                                        "Missing-ID query %s repair failed: %s",
                                        q_idx,
                                        repair_error,
                                    )
                                    results["intermediate"]["missing_id_query_repairs"].append(
                                        {
                                            "query_index": q_idx,
                                            "applied": False,
                                            "reason": str(repair_error),
                                        }
                                    )
                                    continue

                    # Final explicit filtering on resolved IRIs (post-collection), based on extracted partial matches.
                    if missing_iris and collected_partial_matches:
                        unique_mentions = []
                        seen_mentions = set()
                        for mention in collected_partial_matches:
                            normalized_mention = self._normalize_entity_text(mention)
                            if normalized_mention and normalized_mention not in seen_mentions:
                                unique_mentions.append(mention)
                                seen_mentions.add(normalized_mention)

                        mention_profiles = []
                        for mention in unique_mentions:
                            mention_norm = self._normalize_entity_text(mention)
                            mention_tokens = [token for token in mention_norm.split() if token]
                            if not mention_tokens:
                                continue
                            mention_profiles.append(
                                {
                                    "mention": mention,
                                    "tokens": mention_tokens,
                                    "has_id": any(bool(re.search(r'\d', token)) for token in mention_tokens),
                                }
                            )

                        filtered_missing_iris = {}
                        for label, iri in missing_iris.items():
                            class_hints = []
                            if missing_iris_by_class:
                                for class_name, entities in missing_iris_by_class.items():
                                    for item in entities:
                                        if item.get("label") == label and item.get("iri") == iri:
                                            class_hints.append(class_name)
                                            break

                            matching_profiles = [
                                profile
                                for profile in mention_profiles
                                if any(
                                    self._is_equivalent_entity_match(profile["mention"], label, class_hint)
                                    for class_hint in (class_hints or [None])
                                )
                            ]
                            if not matching_profiles:
                                continue

                            filtered_missing_iris[label] = iri

                        # Zero-only fallback: if strict equivalence keeps nothing,
                        # allow mention substring containment in label text.
                        if not filtered_missing_iris and mention_profiles:
                            for label, iri in missing_iris.items():
                                label_norm = self._normalize_entity_text(label)
                                if any(
                                    (self._normalize_entity_text(profile.get("mention", "")) in label_norm)
                                    and len(self._normalize_entity_text(profile.get("mention", ""))) >= 3
                                    for profile in mention_profiles
                                ):
                                    filtered_missing_iris[label] = iri

                            if filtered_missing_iris:
                                self.logger.info(
                                    "Equivalence filter yielded zero IRIs; containment fallback recovered %s IRI(s).",
                                    len(filtered_missing_iris),
                                )

                        if len(filtered_missing_iris) != len(missing_iris):
                            self.logger.info(
                                "Post-filtered resolved IRIs by equivalence from %s to %s.",
                                len(missing_iris),
                                len(filtered_missing_iris),
                            )
                        missing_iris = filtered_missing_iris

                        if missing_iris_by_class:
                            allowed_items = set((label, iri) for label, iri in missing_iris.items())
                            trimmed_by_class = {}
                            for class_name, entities in missing_iris_by_class.items():
                                kept = []
                                seen_pairs = set()
                                for item in entities:
                                    pair = (item.get("label", ""), item.get("iri", ""))
                                    if pair in allowed_items and pair not in seen_pairs:
                                        kept.append(item)
                                        seen_pairs.add(pair)
                                if kept:
                                    trimmed_by_class[class_name] = kept
                            missing_iris_by_class = trimmed_by_class
                    
                    # Apply IRI limit if configured
                    max_iris = self.config.get("pipeline.stages.missing_id.max_iris", None)
                    if max_iris is not None:
                        # Ensure max_iris is an integer (in case it's read as string from YAML)
                        try:
                            max_iris = int(max_iris)
                        except (ValueError, TypeError) as e:
                            self.logger.warning(f"Failed to convert max_iris to int: {e}")
                            max_iris = None
                        
                        if max_iris is not None and len(missing_iris) > max_iris:
                            self.logger.info(f"Limiting resolved IRIs from {len(missing_iris)} to {max_iris} (configured max, fair round-robin across queries)")

                            selected_keys = []
                            if per_query_label_keys:
                                max_len = max((len(lst) for lst in per_query_label_keys), default=0)
                                for i in range(max_len):
                                    for lst in per_query_label_keys:
                                        if len(selected_keys) >= max_iris:
                                            break
                                        if i < len(lst):
                                            key = lst[i]
                                            if key in missing_iris and key not in selected_keys:
                                                selected_keys.append(key)
                                    if len(selected_keys) >= max_iris:
                                        break

                            # Fallback: preserve insertion order if round-robin couldn't fill target
                            if len(selected_keys) < max_iris:
                                for key in missing_iris.keys():
                                    if key not in selected_keys:
                                        selected_keys.append(key)
                                    if len(selected_keys) >= max_iris:
                                        break

                            missing_iris = {k: missing_iris[k] for k in selected_keys if k in missing_iris}

                            if missing_iris_by_class:
                                allowed_items = set((label, iri) for label, iri in missing_iris.items())
                                trimmed_by_class = {}
                                for class_name, entities in missing_iris_by_class.items():
                                    kept = []
                                    seen_pairs = set()
                                    for item in entities:
                                        pair = (item.get("label", ""), item.get("iri", ""))
                                        if pair in allowed_items and pair not in seen_pairs:
                                            kept.append(item)
                                            seen_pairs.add(pair)
                                    if kept:
                                        trimmed_by_class[class_name] = kept
                                missing_iris_by_class = trimmed_by_class
                    
                    if missing_iris:
                        self.logger.info(f"Found {len(missing_iris)} entity IRI(s): {list(missing_iris.keys())}")
                except Exception as e:
                    self.logger.warning(f"Error processing missing ID queries: {e}")
                
                # Store missing IRIs in results for GUI (outside try/except so it always saves)
                results["intermediate"]["missing_iris"] = missing_iris
                results["intermediate"]["missing_iris_by_class"] = missing_iris_by_class
                
                # Update results manager with missing ID extraction (use precomputed value)
                rm.update_missing_id(
                    result,
                    query=missing_id_query,
                    resolved_entities=missing_iris,
                    config={
                        "enabled": True,
                        "class_keyword_rerank": self.config.get("pipeline.stages.missing_id.class_keyword_rerank", True),
                        "mention_class_weight": self.config.get("pipeline.stages.missing_id.mention_class_weight", 0.55),
                        "value_match_weight": self.config.get("pipeline.stages.missing_id.value_match_weight", 1.0),
                        "heuristics": {
                            "weight": self.config.get("pipeline.stages.missing_id.heuristics.weight", 0.20),
                            "id_boost": self.config.get("pipeline.stages.missing_id.heuristics.id_boost", 1.0),
                            "plural_category_boost": self.config.get("pipeline.stages.missing_id.heuristics.plural_category_boost", 0.8),
                            "transfer_object_category_boost": self.config.get("pipeline.stages.missing_id.heuristics.transfer_object_category_boost", 0.8),
                            "transfer_object_instance_penalty": self.config.get("pipeline.stages.missing_id.heuristics.transfer_object_instance_penalty", 0.3),
                        },
                        "connectivity": {
                            "enabled": self.config.get("pipeline.stages.missing_id.connectivity.enabled", True),
                            "weight": self.config.get("pipeline.stages.missing_id.connectivity.weight", 0.15),
                            "max_hops": self.config.get("pipeline.stages.missing_id.connectivity.max_hops", 3),
                        },
                        "include_class_examples_in_index": self.config.get("pipeline.stages.missing_id.include_class_examples_in_index", False),
                        "use_descriptions_in_rerank": self.config.get("pipeline.stages.missing_id.use_descriptions_in_rerank", self.config.get("pipeline.schema.missing_id_extraction.include_descriptions", False)),
                        "dynamic_selection": {
                            "enabled": self.config.get("pipeline.stages.missing_id.dynamic_selection.enabled", True),
                            "coverage": self.config.get("pipeline.stages.missing_id.dynamic_selection.coverage", 0.85),
                            "zscore_factor": self.config.get("pipeline.stages.missing_id.dynamic_selection.zscore_factor", -0.25),
                            "ambiguity_gap_threshold": self.config.get("pipeline.stages.missing_id.dynamic_selection.ambiguity_gap_threshold", None),
                            "ambiguity_ratio_threshold": self.config.get("pipeline.stages.missing_id.dynamic_selection.ambiguity_ratio_threshold", 1.4),
                            "ambiguity_min_top_score": self.config.get("pipeline.stages.missing_id.dynamic_selection.ambiguity_min_top_score", 0.55),
                            "ambiguity_min_candidates": self.config.get("pipeline.stages.missing_id.dynamic_selection.ambiguity_min_candidates", 3),
                            "ambiguity_collapse_to": self.config.get("pipeline.stages.missing_id.dynamic_selection.ambiguity_collapse_to", 2),
                            "max_classes": self.config.get("pipeline.stages.missing_id.dynamic_selection.max_classes", None),
                        },
                        "entity_mention_max_ngram": self.config.get("pipeline.stages.missing_id.entity_mention_max_ngram", 3),
                        "entity_mention_max_count": self.config.get("pipeline.stages.missing_id.entity_mention_max_count", 12),
                        "extra_stopwords": self.config.get("pipeline.stages.missing_id.extra_stopwords", []),
                        "auto_stopword_min_len": self.config.get("pipeline.stages.missing_id.auto_stopword_min_len", 2),
                        "auto_stopword_min_df": self.config.get("pipeline.stages.missing_id.auto_stopword_min_df", 0.65),
                        "max_candidate_classes": self.config.get("pipeline.stages.missing_id.max_candidate_classes", None),
                        "min_class_score": self.config.get("pipeline.stages.missing_id.min_class_score", 0.05),
                        "relative_score_threshold": self.config.get("pipeline.stages.missing_id.relative_score_threshold", 0.4),
                        "low_confidence_best_score": self.config.get("pipeline.stages.missing_id.low_confidence_best_score", 0.12),
                        "min_selected_classes": self.config.get("pipeline.stages.missing_id.min_selected_classes", 2),
                        "no_signal_fallback_classes": self.config.get("pipeline.stages.missing_id.no_signal_fallback_classes", None),
                        "enable_schema_augmentation": self.config.get("pipeline.stages.missing_id.enable_schema_augmentation", True),
                        "max_augmented_classes": self.config.get("pipeline.stages.missing_id.max_augmented_classes", 3),
                        "min_augmented_similarity": self.config.get("pipeline.stages.missing_id.min_augmented_similarity", 0.45),
                        "augmented_class_max_properties": self.config.get("pipeline.stages.missing_id.augmented_class_max_properties", 5),
                        "include_meta_classes": self.config.get("pipeline.stages.missing_id.include_meta_classes", False),
                        "exclude_meta_class_prefixes": self.config.get("pipeline.stages.missing_id.exclude_meta_class_prefixes", ["owl", "rdf", "rdfs", "void"]),
                        "exclude_meta_class_local_names": self.config.get("pipeline.stages.missing_id.exclude_meta_class_local_names", ["Class", "ObjectProperty", "DatatypeProperty", "Ontology", "Dataset", "Property", "Agent"]),
                        "top_k_classes_legacy": self.config.get("pipeline.stages.missing_id.top_k_classes", None),
                        "include_descriptions": include_descriptions_missing,
                        "max_iris": self.config.get("pipeline.stages.missing_id.max_iris", None),
                        "max_results_per_query": self.config.get("pipeline.stages.missing_id.max_results_per_query", None)
                    },
                    schema_passed=formatted_schema_missing,
                    prompt=generator.missing_id_prompt if hasattr(generator, 'missing_id_prompt') else None
                )
        
        # Generate SPARQL query (Use Gemini for generation, pass found IRIs)
        if query_generation_enabled and property_selection:
            if self.llm_generation is None:
                self.llm_generation, self.llm_generation_info = self._init_stage_llm(
                    "query_generation",
                    "Generation (missing-id/query generation)",
                )
                refresh_llm_runtime_metadata()
            # Get query generation examples config (for tracking purposes)
            include_examples_query = self.config.get("pipeline.schema.query_generation.include_examples", True)
            include_descriptions_query = self.config.get("pipeline.schema.query_generation.include_descriptions", False)
            force_text_filter_matching = self.config.get("pipeline.schema.query_generation.force_text_filter_matching", True)
            include_resolved_entity_labels_query = self.config.get(
                "pipeline.schema.query_generation.include_resolved_entity_labels",
                True,
            )
            
            self.logger.info(f"Generating SPARQL query with generation LLM (examples={include_examples_query})...")
            
            # Log what IRIs are available for the LLM
            if missing_iris:
                self.logger.info(f"[IRI CONTEXT] Passing {len(missing_iris)} resolved entity IRI(s) to query generator:")
                for label, iri in missing_iris.items():
                    self.logger.info(f"  - {label} -> {iri}")
            else:
                self.logger.info("[IRI CONTEXT] No resolved entity IRIs available (or no entities mentioned in question)")
            
            llm_for_gen = MistralLLMWrapper(self.llm_generation) if hasattr(self.llm_generation, '__call__') else self.llm_generation
            generator = SPARQLGenerator(llm_for_gen)
            
            # Generate query (this sets generator.last_prompt)
            _ent_mentions_for_gen = results.get("intermediate", {}).get("entity_extraction_mentions", [])
            self.logger.info(
                "[IRI GROUPING] entity_extraction_mentions passed to generate_query: %s",
                _ent_mentions_for_gen,
            )
            # Precompute formatted schema variants to pass as overrides into generator
            if use_toon_input:
                # For TOON, use filtered schema (only relevant classes and properties)
                filtered_schema_for_toon = self._create_filtered_schema(schema, property_selection)
                include_examples = self.config.get("toon.formatting.include_examples", True)
                include_descriptions = self.config.get("toon.formatting.include_descriptions", True)
                max_examples = self.config.get("toon.formatting.max_examples", 2)
                formatted_schema_query_with = TOONFormatter.encode(
                    filtered_schema_for_toon,
                    include_examples=include_examples,
                    include_descriptions=include_descriptions,
                    max_examples=max_examples,
                )
                formatted_schema_query_without = TOONFormatter.encode(
                    filtered_schema_for_toon,
                    include_examples=False,
                    include_descriptions=include_descriptions,
                    max_examples=max_examples,
                )
                self.logger.info(
                    f"[TOON] Encoded filtered schema with {len(filtered_schema_for_toon.get('classes', {}))} classes for query generation"
                )
            else:
                # For non-TOON, use full schema (generator will filter internally)
                formatted_schema_query_with = formatter.format_clean(
                    include_examples=include_examples_query,
                    include_descriptions=include_descriptions_query,
                )
                formatted_schema_query_without = formatter.format_clean(
                    include_examples=False,
                    include_descriptions=include_descriptions_query,
                )
            # Debug preview for query generation schema
            try:
                preview_with = str(formatted_schema_query_with)[:200]
                preview_without = str(formatted_schema_query_without)[:200]
                self.logger.info(
                    f"[TOON DEBUG] use_toon_input={use_toon_input} | query_with_preview={preview_with!r} | query_without_preview={preview_without!r} | contains_Class_Name_with={'Class Name:' in str(formatted_schema_query_with)}"
                )
            except Exception:
                pass

            sparql_query = generator.generate_query(
                question,
                property_selection,
                schema,
                missing_iris,
                missing_iris_by_class=missing_iris_by_class,
                entity_mentions=_ent_mentions_for_gen,
                include_examples=include_examples_query,
                include_descriptions=include_descriptions_query,
                force_text_filter_matching=force_text_filter_matching,
                include_resolved_entity_labels=include_resolved_entity_labels_query,
                schema_text_override=(formatted_schema_query_with if use_toon_input else None),
            )
            
            # Save prompt immediately after it's ready (before LLM execution completes)
            results["intermediate"]["final_query_prompt"] = generator.last_prompt
            if generator.last_prompt:
                self._save_prompt_immediately("final_query", generator.last_prompt, question)
            
            results["sparql_query"] = sparql_query
            self.logger.info("SPARQL query generated")
            results["intermediate"]["final_query"] = sparql_query
            results["intermediate"]["query_generation_config"] = {
                "include_examples": include_examples_query,
                "include_descriptions": include_descriptions_query,
                "force_text_filter_matching": force_text_filter_matching,
                "include_resolved_entity_labels": include_resolved_entity_labels_query,
            }
            
            # Update results manager with query generation (already computed above)
            rm.update_query_generation(
                result,
                generated_query=sparql_query,
                config={
                    "include_examples": include_examples_query,
                    "include_descriptions": include_descriptions_query,
                    "force_text_filter_matching": force_text_filter_matching,
                    "include_resolved_entity_labels": include_resolved_entity_labels_query,
                },
                schema_with=formatted_schema_query_with,
                schema_without=formatted_schema_query_without,
                prompt=generator.last_prompt
            )
        else:
            sparql_query = None
        
        # Execute query
        if self.config.get("pipeline.stages.query_execution", True) and sparql_query:
            self.logger.info("Executing SPARQL query...")
            limit = self.config.get("sparql.default_limit")
            query_results = self.executor.execute(sparql_query, limit=limit)

            # If syntax/compiler error, ask LLM to repair query and retry once
            syntax_markers = [
                "QueryBadFormed",
                "SPARQL compiler",
                "syntax error",
                "bad request has been sent",
                "parse",
                "SP03",
            ]
            error_text = query_results.get("error") if isinstance(query_results, dict) else None
            if error_text and any(marker.lower() in str(error_text).lower() for marker in syntax_markers):
                self.logger.warning("Detected SPARQL syntax/compiler error. Attempting LLM-based query repair and retry...")
                llm_for_repair = MistralLLMWrapper(self.llm_generation) if hasattr(self.llm_generation, '__call__') else self.llm_generation
                repair_generator = SPARQLGenerator(llm_for_repair)
                corrected_query = repair_generator.correct_query_from_error(
                    original_query=sparql_query,
                    error_message=error_text,
                    question=question,
                    schema=schema,
                )

                if corrected_query and corrected_query.strip() and corrected_query.strip() != sparql_query.strip():
                    results["intermediate"]["query_repair_prompt"] = repair_generator.query_repair_prompt
                    results["intermediate"]["query_repair_candidate"] = corrected_query
                    if repair_generator.query_repair_prompt:
                        self._save_prompt_immediately("query_repair", repair_generator.query_repair_prompt, question)

                    retried_results = self.executor.execute(corrected_query, limit=limit)
                    if not (isinstance(retried_results, dict) and retried_results.get("error")):
                        self.logger.info("LLM-repaired query executed successfully.")
                        sparql_query = corrected_query
                        results["intermediate"]["final_query"] = corrected_query
                        results["sparql_query"] = corrected_query
                        query_results = retried_results
                        results["intermediate"]["query_repair_applied"] = True
                    else:
                        self.logger.warning("LLM-repaired query still failed; returning original execution error.")
                        results["intermediate"]["query_repair_applied"] = False

            results["query_results"] = query_results
            results["intermediate"]["results"] = query_results
            
            # Format results
            output_format = self.config.get("output.format", "json")
            formatted_results = self.executor.format_results(query_results, output_format)
            results["formatted_results"] = formatted_results
            
            # Detect query type for results
            query_type = "UNKNOWN"
            if "ASK" in sparql_query.upper():
                query_type = "ASK"
            elif "SELECT" in sparql_query.upper():
                query_type = "SELECT"
            elif "CONSTRUCT" in sparql_query.upper():
                query_type = "CONSTRUCT"
            elif "DESCRIBE" in sparql_query.upper():
                query_type = "DESCRIBE"
            
            # Update results manager with execution
            rm.update_query_execution(
                result,
                executed_query=sparql_query,
                query_type=query_type,
                raw_results=query_results,
                formatted_results=formatted_results,
                error=None
            )
            
            self.logger.info("Query executed successfully")
        
        # Save comprehensive results and optionally perform evaluation (only when recording enabled)
        record_flag = self.config.get("pipeline.record_and_evaluate", False)
        if record_flag and self.config.get("output.save_intermediate", True):
            # Save old-style results (for backward compatibility)
            self._save_results(results)

            # Save new comprehensive results
            # Mark whether this run used schema examples for query generation
            # (used by GUI filters for final query execution comparisons).
            try:
                ce = result.get("pipeline", {}).get("class_extraction", {}).get("config", {}).get("include_examples")
                pe = result.get("pipeline", {}).get("property_extraction", {}).get("config", {}).get("include_examples")
                qg = result.get("pipeline", {}).get("query_generation", {}).get("config", {}).get("include_examples")
                if qg is not None:
                    with_examples = bool(qg)
                else:
                    with_examples = any(bool(x) for x in [ce, pe])
            except Exception:
                with_examples = False

            # attach flag to metadata for easier filtering later
            if "metadata" not in result:
                result["metadata"] = {}
            result["metadata"]["with_examples"] = with_examples

            result_filepath = rm.save_result(result)
            self.logger.info(f"Comprehensive results saved to {result_filepath}")

            # Perform evaluation if recording enabled and ground truth exists
            ground_truth_manager = GroundTruthManager()
            ground_truth = ground_truth_manager.load_ground_truth_by_question(question, kg_name=kg_name, model_name=model_name)

            if ground_truth:
                self.logger.info("Ground truth found. Performing evaluation...")
                try:
                    evaluation_method = self.config.get(
                        "pipeline.evaluation.query_execution.method",
                        "row_based"
                    )
                    normalize_query_execution_values = self.config.get(
                        "pipeline.evaluation.query_execution.normalize_values",
                        True
                    )
                    order_matters = self.config.get(
                        "pipeline.evaluation.query_execution.order_matters",
                        False
                    )
                    order_required_questions = self.config.get(
                        "pipeline.evaluation.query_execution.order_required_questions",
                        []
                    )
                    evaluator = PipelineEvaluator(
                        normalize_query_execution_values=normalize_query_execution_values,
                        evaluation_method=evaluation_method,
                        order_matters=order_matters,
                        order_required_questions=order_required_questions,
                    )
                    evaluator.logger = self.logger
                    evaluation = evaluator.evaluate_full_pipeline(result, ground_truth)

                    kg_source = self.config.get("kg.source", "unknown")

                    # Add tags for multi-KG multi-model evaluation
                    evaluation["kg"] = kg_name
                    evaluation["kg_source"] = kg_source
                    evaluation["model"] = model_name
                    evaluation["schema_format"] = "toon" if use_toon_input else "mschema"
                    evaluation["extraction_method"] = extraction_method
                    evaluation["embedding_mode"] = embedding_mode
                    # Propagate with_examples flag into evaluation so GUI/aggregator can filter
                    try:
                        evaluation["with_examples"] = result.get("metadata", {}).get("with_examples", False)
                    except Exception:
                        evaluation["with_examples"] = False

                    # Save evaluation results
                    base_eval_dir = self.config.get("output.evaluation_results_dir", "tests/evaluation_results")
                    if use_toon_input:
                        toon_eval_dir = self.config.get("output.toon_evaluation_results_dir", None)
                        eval_output_dir = toon_eval_dir or f"{base_eval_dir}_toon"
                    else:
                        eval_output_dir = base_eval_dir

                    eval_manager = EvaluationResultsManager(eval_dir=eval_output_dir)
                    eval_file_path = eval_manager.save_evaluation(kg_name, model_name, evaluation)

                    # Persist evaluation details back into the comprehensive result JSON
                    # so per-stage precision / recall / F1 remain attached to the run record.
                    result["evaluation"] = evaluation
                    try:
                        result_filepath = rm.save_result_with_custom_name(result, Path(result_filepath).stem)
                    except Exception as save_err:
                        self.logger.debug(f"Could not refresh result file with evaluation data: {save_err}")

                    # Organize results by KG+Model (if organizer available)
                    if ResultsOrganizer:
                        try:
                            organizer = ResultsOrganizer()
                            gt_file_path = ground_truth.get("__source_file") if isinstance(ground_truth, dict) else None
                            organizer.move_evaluation_and_related_files(
                                eval_file_path,
                                gt_file_path,
                                result_filepath,
                                kg_name,
                                model_name
                            )
                            self.logger.info(f"Results organized: {kg_name}/{model_name}")
                        except Exception as e:
                            self.logger.debug(f"Could not organize results: {e}")

                    # Add evaluation to old-style results too
                    results["evaluation"] = evaluation

                    # Log evaluation summary
                    overall = evaluation.get("overall", {})
                    if overall:
                        self.logger.info(f"Evaluation - Average F1: {overall.get('average_f1', 0)}")
                        for stage in overall.get('stages', []):
                            stage_metrics = evaluation['stages'].get(stage, {})
                            f1 = stage_metrics.get('f1')
                            if f1 is None:
                                f1 = stage_metrics.get('set_f1')
                            if f1 is None:
                                f1 = stage_metrics.get('macro_average', {}).get('f1', 0)
                            self.logger.info(f"  {stage}: F1={f1}")
                except Exception as e:
                    self.logger.warning(f"Error during evaluation: {e}")
        
        return results
    
    def _save_results(self, results):
        """Save results to file."""
        results_dir = self._get_output_dirs()["results"]
        os.makedirs(results_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"result_{timestamp}.json"
        filepath = os.path.join(results_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Results saved to {filepath}")
        
        # Also save prompts separately for easy review
        self._save_prompts(results, timestamp)
    
    def _save_prompts(self, results, timestamp):
        """Save all prompts to separate files for analysis."""
        prompts_dir = self._get_output_dirs()["prompts"]
        os.makedirs(prompts_dir, exist_ok=True)
        
        intermediate = results.get("intermediate", {})
        question = results.get("question", "unknown")
        
        # Create a prompt summary file
        prompt_summary = {
            "timestamp": timestamp,
            "question": question,
            "prompts": {}
        }
        
        # Map of prompt names to their locations in results
        prompt_mappings = {
            "class_extraction": "class_prompts",
            "property_extraction": "property_prompts",
            "missing_id": "missing_id_prompt",
            "final_query": "final_query_prompt"
        }
        
        for name, key in prompt_mappings.items():
            if key in intermediate:
                prompt_value = intermediate[key]
                
                # Handle list of prompts (class/property)
                if isinstance(prompt_value, list):
                    prompt_summary["prompts"][name] = f"[{len(prompt_value)} prompts]"
                    for idx, prompt in enumerate(prompt_value):
                        filename = f"prompt_{timestamp}_{name}_{idx}.txt"
                        filepath = os.path.join(prompts_dir, filename)
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(f"Question: {question}\n")
                            f.write(f"=== {name.upper()} PROMPT {idx} ===\n\n")
                            # Convert to string if it's not already
                            prompt_str = str(prompt) if not isinstance(prompt, str) else prompt
                            f.write(prompt_str)
                # Handle single prompts
                elif isinstance(prompt_value, str):
                    prompt_summary["prompts"][name] = "stored"
                    filename = f"prompt_{timestamp}_{name}.txt"
                    filepath = os.path.join(prompts_dir, filename)
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(f"Question: {question}\n")
                        f.write(f"=== {name.upper()} PROMPT ===\n\n")
                        f.write(prompt_value)
                    self.logger.debug(f"Saved {name} prompt to {filepath}")
                # Handle dict/other types (convert to JSON string)
                else:
                    prompt_summary["prompts"][name] = "stored (dict)"
                    filename = f"prompt_{timestamp}_{name}.txt"
                    filepath = os.path.join(prompts_dir, filename)
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(f"Question: {question}\n")
                        f.write(f"=== {name.upper()} PROMPT ===\n\n")
                        f.write(json.dumps(prompt_value, indent=2, ensure_ascii=False))
                    self.logger.debug(f"Saved {name} prompt to {filepath}")
        
        # Save summary
        summary_file = os.path.join(prompts_dir, f"summary_{timestamp}.json")
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(prompt_summary, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Prompts saved to {prompts_dir}/")
