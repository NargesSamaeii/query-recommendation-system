"""
Class Relevance Evaluator

Evaluates which RDF classes are relevant to answering a user question.
"""

import json
import re
import logging


class ClassRelevanceEvaluator:
    """Evaluates relevance of classes for a given question."""
    
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
        """
        Normalize any RDF class identifier to its compact local ID.
        
        Examples:
          'wd:Q515' -> 'Q515'
          'gptkb:James_Bryant_Conant' -> 'James_Bryant_Conant'
          '<http://www.wikidata.org/entity/Q515>' -> 'Q515'
        """
        if not cls:
            return None
        
        # Remove markup <...>
        cls = cls.strip().replace("<", "").replace(">", "")

        # If prefix form, return local part
        if ":" in cls:
            prefix, local = cls.split(":", 1)
            # Prevent false splits like "http://..."
            if not prefix.startswith("http") and local:
                return local

        # If URL form, take last segment
        if "/" in cls:
            return cls.rsplit("/", 1)[-1]

        # Otherwise return raw string
        return cls
    
    def evaluate(self, question, formatted_schema, schema_json=None):
        """
        Evaluate which classes are relevant to the question.
        
        Args:
            question: User's natural language question
            formatted_schema: Formatted schema string
            schema_json: Raw JSON schema dictionary (optional, used by embedding method)
            
        Returns:
            List of relevant class names
        """
        if self.method == "embedding":
            return self._evaluate_with_embedding(question, formatted_schema, schema_json)
        else:
            return self._evaluate_with_llm(question, formatted_schema)
    
    def _evaluate_with_embedding(self, question, formatted_schema, schema_json=None):
        """Evaluate using embedding-based cosine similarity."""
        if not self.embedding_evaluator:
            self.logger.error("Embedding evaluator not initialized, falling back to LLM")
            return self._evaluate_with_llm(question, formatted_schema)

        toon_direct_mode = bool(self.embedding_config.get("toon_direct_mode", False))
        verbose_flag = bool(self.embedding_config.get("verbose_logs", False))
        if toon_direct_mode and isinstance(formatted_schema, str) and "--- " in formatted_schema:
            self.logger.info("Using direct TOON embedding mode for class extraction")
            return self.embedding_evaluator.evaluate_classes_from_toon(question, formatted_schema, verbose=verbose_flag)
        
        return self.embedding_evaluator.evaluate_classes(
            question,
            formatted_schema,
            schema_json,
            verbose=verbose_flag,
        )
    
    def _evaluate_with_llm(self, question, formatted_schema):
        """Evaluate using LLM reasoning (original method)."""
        if not isinstance(formatted_schema, str):
            raise TypeError("formatted_schema must be a string.")

        # Split off the Prefixes section if present
        prefix_section = ""
        split_schema = re.split(r"\nClass Name: ", formatted_schema, maxsplit=1)
        if len(split_schema) > 1:
            prefix_section = split_schema[0].strip()
            class_blocks_text = "Class Name: " + split_schema[1]
        else:
            class_blocks_text = formatted_schema

        # Split schema into class blocks
        class_blocks = re.split(r"\n(?=Class Name: )", class_blocks_text.strip())
        class_blocks = [blk for blk in class_blocks if "Class Name:" in blk]

        if not class_blocks:
            self.logger.warning("No class blocks found in schema. Returning empty relevance list.")
            return []

        def local_name(iri):
            return iri.split(":")[1] if ":" in iri else iri

        relevant_classes = []

        for block in class_blocks:
            block = block.strip()
            m = re.search(r"Class Name:\s*(\S+)", block)
            pref_name = m.group(1) if m else None
            if not pref_name:
                continue

            output_name = local_name(pref_name)

            # Include prefixes from the schema
            class_details_with_prefixes = f"{prefix_section}\n\n{block}" if prefix_section else block
            
            # Limit class details to prevent context overflow
            # Keep first 3000 characters of class details
            if len(class_details_with_prefixes) > 3000:
                class_details_with_prefixes = class_details_with_prefixes[:3000] + "\n... (truncated)"
                self.logger.warning(f"Truncated class details for {pref_name} to fit context window")

            prompt = f"""You are an RDF schema reasoning assistant.

Determine if this RDF class is relevant to answering the user's question.

User Question: {question}

Class Details:
{class_details_with_prefixes}

CRITICAL: Respond with ONLY a JSON array. No explanations.
- If relevant: ["{output_name}"]
- If not relevant: []

Answer:"""

            self.prompts.append({
                "class_name": pref_name,
                "prompt": prompt
            })

            self.logger.info(f"--- Evaluating class: {pref_name} ---")

            # Send prompt to LLM
            try:
                response = self.llm.generate(prompt, max_tokens=400)
                text = response.strip()
                self.logger.info(f"Raw LLM output: {text}")
            except Exception as e:
                self.logger.error(f"Error evaluating class {pref_name}: {e}")
                continue

            # Parse JSON safely - try to extract JSON from response
            try:
                # Try direct parse first
                parsed = json.loads(text)
                if isinstance(parsed, list) and output_name in parsed:
                    relevant_classes.append(output_name)
            except json.JSONDecodeError:
                # Try to extract JSON array from text
                json_match = re.search(r'\[.*?\]', text)
                if json_match:
                    try:
                        parsed = json.loads(json_match.group(0))
                        if isinstance(parsed, list) and output_name in parsed:
                            relevant_classes.append(output_name)
                    except:
                        self.logger.warning(f"Could not parse LLM output for class {pref_name}. Skipping.")
                else:
                    self.logger.warning(f"Could not parse LLM output for class {pref_name}. Skipping.")

        return relevant_classes