"""
Property Evaluator Module

Evaluates which properties of relevant classes are needed for a question.
"""

import json
import re
import logging


class PropertyEvaluator:
    """Evaluates relevant properties for classes."""
    
    def __init__(self, llm, method="llm", embedding_config=None, embedding_evaluator=None):
        """
        Initialize evaluator with LLM instance.
        
        Args:
            llm: Language model instance for evaluation (used when method="llm")
            method: Extraction method - "llm" or "embedding"
            embedding_config: Configuration dict for embedding method
            embedding_evaluator: Optional pre-initialized EmbeddingEvaluator instance (to share between evaluators)
        """
        self.llm = llm
        self.method = method
        self.embedding_config = embedding_config or {}
        self.logger = logging.getLogger("nl2sparql.pipeline")
        self.prompts = []
        self.embedding_evaluator = embedding_evaluator  # Use shared instance if provided
        
        # Initialize embedding evaluator if needed and not provided
        if self.method == "embedding" and self.embedding_evaluator is None:
            self._init_embedding_evaluator()
    
    def _init_embedding_evaluator(self):
        """Initialize the embedding evaluator."""
        try:
            from .embedding_evaluator_v2 import EmbeddingEvaluator
            model_name = self.embedding_config.get(
                "model", 
                "all-mpnet-base-v2"
            )
            include_descriptions = self.embedding_config.get(
                "include_descriptions",
                True
            )
            include_examples = self.embedding_config.get(
                "include_examples",
                True
            )
            
            # Cache configuration
            cache_config = self.embedding_config.get("cache", {})
            use_cache = cache_config.get("enabled", True)
            cache_dir = cache_config.get("cache_dir", "cache/embeddings")
            
            self.embedding_evaluator = EmbeddingEvaluator(
                model_name,
                include_descriptions=include_descriptions,
                include_examples=include_examples,
                use_cache=use_cache,
                cache_dir=cache_dir
            )
            self.logger.info(f"Embedding evaluator initialized with model: {model_name}, cache_enabled={use_cache}, cache_dir={cache_dir}")
        except Exception as e:
            self.logger.error(f"Failed to initialize embedding evaluator: {e}")
            self.logger.warning("Falling back to LLM method")
            self.method = "llm"
    
    def normalize_class_id(self, cls):
        """Normalize any RDF class identifier to its compact local ID."""
        if not cls:
            return None
        
        cls = cls.strip().replace("<", "").replace(">", "")

        if ":" in cls:
            prefix, local = cls.split(":", 1)
            if not prefix.startswith("http") and local:
                return local

        if "/" in cls:
            return cls.rsplit("/", 1)[-1]

        return cls
    
    def evaluate(self, question, relevant_classes, formatted_schema, schema_json=None):
        """
        Evaluate relevant properties for the user question.
        
        Args:
            question: User's natural language question
            relevant_classes: List of relevant class names
            formatted_schema: Formatted schema string
            schema_json: Raw JSON schema dictionary (optional, used by embedding method)
            
        Returns:
            List of dictionaries with class_name and relevant_properties
        """
        if self.method == "embedding":
            return self._evaluate_with_embedding(question, relevant_classes, formatted_schema, schema_json)
        else:
            return self._evaluate_with_llm(question, relevant_classes, formatted_schema)
    
    def _evaluate_with_embedding(self, question, relevant_classes, formatted_schema, schema_json=None):
        """Evaluate using embedding-based cosine similarity."""
        if not self.embedding_evaluator:
            self.logger.error("Embedding evaluator not initialized, falling back to LLM")
            return self._evaluate_with_llm(question, relevant_classes, formatted_schema)

        toon_direct_mode = bool(self.embedding_config.get("toon_direct_mode", False))
        verbose_flag = bool(self.embedding_config.get("verbose_logs", False))
        if toon_direct_mode and isinstance(formatted_schema, str) and "--- " in formatted_schema:
            self.logger.info("Using direct TOON embedding mode for property extraction")
            return self.embedding_evaluator.evaluate_properties_from_toon(
                question,
                relevant_classes,
                formatted_schema,
                verbose=verbose_flag,
            )
        
        if not schema_json:
            self.logger.error("schema_json required for embedding-based property evaluation")
            return []
        
        try:
            result = self.embedding_evaluator.evaluate_properties(
                question,
                relevant_classes,
                formatted_schema,
                schema_json,
                verbose=verbose_flag,
            )
            self.logger.info(f"[OK] Property evaluation returned {len(result)} class results")
            for r in result:
                self.logger.info(f"     - {r.get('class_name')}: {len(r.get('relevant_properties', []))} properties")
            return result
        except Exception as e:
            self.logger.error(f"Error during embedding-based property evaluation: {e}", exc_info=True)
            self.logger.warning("Falling back to LLM method")
            return self._evaluate_with_llm(question, relevant_classes, formatted_schema)
    
    def _evaluate_with_llm(self, question, relevant_classes, formatted_schema):
        """Evaluate using LLM reasoning (original method)."""
        if not isinstance(formatted_schema, str):
            raise TypeError("formatted_schema must be a string.")

        if not relevant_classes:
            self.logger.warning("No relevant classes provided. Skipping property evaluation.")
            return []

        # Split schema into prefixes and class blocks
        split_schema = re.split(r"\nClass Name: ", formatted_schema, maxsplit=1)
        if len(split_schema) > 1:
            prefix_section = split_schema[0].strip()
            class_blocks_text = "Class Name: " + split_schema[1]
        else:
            prefix_section = ""
            class_blocks_text = formatted_schema

        # Split into individual class blocks
        class_blocks = re.split(r"\n(?=Class Name: )", class_blocks_text.strip())

        # Normalize relevant_classes
        relevant_classes = set([self.normalize_class_id(c) for c in relevant_classes])

        final_results = []

        for block in class_blocks:
            block = block.strip()
            if not block:
                continue

            # Extract class name and normalize
            match = re.search(r"Class Name:\s*(\S+)", block)
            class_name_raw = match.group(1) if match else None
            class_name = self.normalize_class_id(class_name_raw)
            if not class_name or class_name not in relevant_classes:
                continue

            # Prepend prefix section for the LLM prompt
            block_with_prefixes = f"{prefix_section}\n\n{block}" if prefix_section else block

            # Build the LLM prompt
            # Truncate block to prevent context overflow
            if len(block_with_prefixes) > 2500:
                block_with_prefixes = block_with_prefixes[:2500] + "\n... (truncated)"
            
            prompt = f"""Identify which properties are essential to answer the user's question.

User Question: {question}

Class Details:
{block_with_prefixes}

CRITICAL: Respond with ONLY valid JSON. No explanations.
Format:
{{
  "class_name": "{class_name}",
  "relevant_properties": ["property1", "property2"]
}}

Answer:""".strip()

            self.prompts.append({
                "class_name": class_name,
                "prompt": prompt
            })

            self.logger.info(f"===== Evaluating properties for Class: {class_name} =====")

            # Call the LLM
            try:
                response_text = self.llm.generate(prompt, max_tokens=600)
            except Exception as e:
                self.logger.error(f"Error calling LLM for {class_name}: {e}")
                continue

            self.logger.info(f"Raw LLM Output for {class_name}:\n{response_text}")

            # Parse JSON safely
            try:
                parsed = json.loads(response_text)
                if (
                    isinstance(parsed, dict)
                    and parsed.get("class_name") == class_name
                    and isinstance(parsed.get("relevant_properties"), list)
                ):
                    final_results.append(parsed)
                else:
                    self.logger.warning(f"Invalid JSON structure for {class_name}, skipping.")
            except json.JSONDecodeError:
                # Try to extract JSON object from text
                json_match = re.search(r'\{[^{}]*"class_name"[^{}]*\}', response_text, re.DOTALL)
                if json_match:
                    try:
                        parsed = json.loads(json_match.group(0))
                        if (
                            isinstance(parsed, dict)
                            and parsed.get("class_name") == class_name
                            and isinstance(parsed.get("relevant_properties"), list)
                        ):
                            final_results.append(parsed)
                    except:
                        self.logger.warning(f"JSON parse failed for {class_name}, skipping.")
                else:
                    self.logger.warning(f"JSON parse failed for {class_name}, skipping.")

        self.logger.info("Final relevant properties per class:")
        self.logger.info(json.dumps(final_results, indent=2))
        return final_results
