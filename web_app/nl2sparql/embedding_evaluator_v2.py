"""
Embedding-based Evaluator V2 - Pure cosine similarity approach with caching

Simplified approach from notebook: sbert_similarity_for_property_extraction_NL_to_SPARQL.ipynb
Uses sentence-transformers for embeddings and statistical thresholding for filtering.
Includes persistent caching for fast repeated queries over same schema.
"""

import logging
import re
import hashlib
from pathlib import Path
from typing import List, Dict
from sentence_transformers import SentenceTransformer, util
import torch
import numpy as np


class EmbeddingEvaluator:
    """Evaluates relevance using pure cosine similarity with statistical thresholding and caching."""
    
    def __init__(self, model_name="all-mpnet-base-v2", include_descriptions=True, include_examples=True, use_cache=True, cache_dir="cache/embeddings"):
        """Initialize evaluator with embedding model and cache.
        
        Args:
            model_name: Sentence transformer model name (all-mpnet-base-v2 recommended)
            include_descriptions: Whether to include property descriptions in embeddings
            include_examples: Whether to include property examples in embeddings
            use_cache: Whether to use persistent embedding cache
            cache_dir: Directory for cache storage
        """
        self.logger = logging.getLogger("nl2sparql.pipeline")
        self.model_name = model_name
        self.include_descriptions = include_descriptions
        self.include_examples = include_examples
        self.encode_batch_size = 512
        self.device = "cpu"
        self.model = None
        self.use_cache = use_cache
        self.cache = None
        self._init_model()
        self._init_cache(cache_dir)
    
    def _init_model(self):
        """Initialize the embedding model."""
        try:
            self.logger.info(f"Loading embedding model: {self.model_name}")
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model = SentenceTransformer(self.model_name, device=self.device)
            self.logger.info(f"Using embedding device: {self.device}")
            self.logger.info("[OK] Embedding model loaded successfully")
        except Exception as e:
            self.logger.error(f"Failed to load embedding model: {e}", exc_info=True)
            raise
    
    def _init_cache(self, cache_dir: str):
        """Initialize cache manager."""
        if not self.use_cache:
            self.logger.info("Caching disabled - embeddings computed on-the-fly")
            return
        
        try:
            from .embedding_cache import EmbeddingCache
            self.cache = EmbeddingCache(cache_dir)
            stats = self.cache.get_cache_stats()
            self.logger.info(f"[OK] Cache initialized: {stats['total_size_mb']}MB ({stats['schemas_cached']} schema cached, {sum(stats['cache_files'].values())} files)")
        except Exception as e:
            self.logger.warning(f"Failed to initialize cache: {e}. Continuing without cache.")
            self.use_cache = False
    
    def encode(self, texts, batch_size=None):
        """Encode texts into embeddings.
        
        Args:
            texts: Single text string or list of texts
            
        Returns:
            Embeddings as tensor
        """
        if isinstance(texts, str):
            texts = [texts]

        effective_batch = int(batch_size or self.encode_batch_size)
        min_batch = 8

        while True:
            try:
                return self.model.encode(
                    texts,
                    convert_to_tensor=True,
                    batch_size=effective_batch,
                    show_progress_bar=False,
                    normalize_embeddings=True,
                )
            except RuntimeError as e:
                error_text = str(e).lower()
                is_cuda_oom = "out of memory" in error_text and "cuda" in error_text
                if not is_cuda_oom or effective_batch <= min_batch:
                    raise

                next_batch = max(min_batch, effective_batch // 2)
                self.logger.warning(
                    "CUDA OOM during embedding encode at batch_size=%s. Retrying with batch_size=%s.",
                    effective_batch,
                    next_batch,
                )
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                effective_batch = next_batch
    
    def normalize_class_id(self, cls):
        """Normalize class identifier to simple name."""
        if not cls:
            return None
        cls = str(cls).strip().replace("<", "").replace(">", "")
        if ":" in cls and not cls.startswith("http"):
            return cls.split(":", 1)[1]
        if "/" in cls:
            return cls.rsplit("/", 1)[-1]
        return cls
    
    def build_class_description(self, class_name, class_data):
        """Build rich text representation of a class using examples and properties.
        
                Includes: class_label + property context + examples.
        
                Property context behavior:
                - if include_descriptions=True: prefer property descriptions and only fall back
                    to property labels when description is missing
                - if include_descriptions=False: use property labels
        
        Args:
            class_name: Simple class identifier
            class_data: Class metadata from schema
            
        Returns:
            Combined text description of class
        """
        parts = [
            class_data.get('class_label', ''),
        ]
        
        # Avoid duplicating property label text when descriptions are included.
        for prop in class_data.get('properties', []):
            prop_label = prop.get('property_label', '')
            prop_description = prop.get('description', '')
            if self.include_descriptions and prop_description:
                parts.append(prop_description)
            elif prop_label:
                parts.append(prop_label)
        
        # Add class examples for semantic grounding
        examples = class_data.get('class_examples', [])
        if examples:
            example_labels = []
            for example in examples[:5]:
                if '/' in str(example):
                    label = str(example).rsplit('/', 1)[-1].strip('>')
                    label = label.replace('_', ' ')
                    example_labels.append(label)
            parts.extend(example_labels)
        
        return " ".join(filter(None, parts))
    
    def build_property_description(self, prop_name, prop_label, prop_data):
        """Build rich text representation of a property.
        
        Combines property name, label, (optional) description, and (optional) examples.
        
        Args:
            prop_name: Property identifier
            prop_label: Human-readable property label
            prop_data: Property metadata
            
        Returns:
            Combined text description of property
        """
        parts = [
            prop_label,
        ]
        
        # Include description only if enabled in config
        if self.include_descriptions:
            description = prop_data.get('description', '')
            if description:
                parts.append(description)
        
        # Add examples only if enabled in config
        if self.include_examples:
            examples = prop_data.get('examples', [])
            if examples:
                examples_text = ', '.join(str(e)[:50] for e in examples[:3])
                parts.append(f"Examples of {prop_label} are: {examples_text}.")
        
        return " ".join(filter(None, parts))

    def _parse_toon_blocks(self, toon_text: str) -> Dict[str, Dict]:
        """Parse TOON text into per-class blocks and property row chunks."""
        if not isinstance(toon_text, str) or not toon_text.strip():
            return {}

        lines = toon_text.splitlines()
        class_blocks: Dict[str, Dict] = {}
        current_class = None
        current_lines = []

        def _flush_block(class_iri: str, block_lines: list[str]):
            if not class_iri or not block_lines:
                return
            normalized = self.normalize_class_id(class_iri)
            prop_rows = []
            for line in block_lines:
                stripped = line.strip()
                if not stripped.startswith("|"):
                    continue
                # Skip header row and separator-like lines
                if "Property IRI" in stripped:
                    continue
                cells = [c.strip() for c in stripped.split("|")[1:-1]]
                if not cells:
                    continue
                prop_iri = cells[0]
                if not prop_iri or prop_iri == "(none)":
                    continue
                row_text = " ".join(c for c in cells if c)
                prop_rows.append({"property_name": prop_iri, "row_text": row_text})

            class_blocks[normalized] = {
                "class_iri": class_iri,
                "class_block": "\n".join(block_lines).strip(),
                "property_rows": prop_rows,
            }

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("--- ") and stripped.endswith(" ---"):
                if current_class is not None:
                    _flush_block(current_class, current_lines)
                current_class = stripped[4:-4].strip()
                current_lines = []
                continue

            if current_class is not None:
                current_lines.append(line)

        if current_class is not None:
            _flush_block(current_class, current_lines)

        return class_blocks

    def evaluate_classes_from_toon(self, question: str, toon_text: str, verbose: bool = False):
        """Evaluate relevant classes by embedding TOON class blocks directly."""
        self.logger.info("=" * 80)
        self.logger.info("STEP 1: CLASS RELEVANCE EVALUATION (DIRECT TOON)")
        self.logger.info("=" * 80)

        blocks = self._parse_toon_blocks(toon_text)
        if not blocks:
            self.logger.warning("No TOON class blocks found for direct embedding")
            return []

        class_names = list(blocks.keys())
        class_texts = []
        for name in class_names:
            # Flatten block formatting slightly for cleaner semantic text
            block_text = blocks[name]["class_block"].replace("|", " ")
            class_texts.append(f"{name}: {block_text}")

        self.logger.info(f"[ENCODING] {len(class_texts)} TOON class blocks...")
        class_embeddings = self.encode(class_texts)
        query_embedding = self.encode(question)
        cos_scores = util.cos_sim(query_embedding, class_embeddings)[0]

        scores_mean = cos_scores.mean()
        scores_std = cos_scores.std()
        threshold = scores_mean - scores_std

        sorted_indices = torch.argsort(cos_scores, descending=True)
        relevant_classes = []
        max_classes = 10

        for idx in sorted_indices:
            class_name = class_names[idx.item()]
            score = cos_scores[idx].item()
            if score >= threshold and len(relevant_classes) < max_classes:
                relevant_classes.append(class_name)
                if verbose or score > 0.5:
                    self.logger.info(f"  [OK] {class_name:20s}  similarity={score:.4f}")
            elif len(relevant_classes) >= max_classes:
                break

        self.logger.info(f"[OK] Selected {len(relevant_classes)} relevant classes (direct TOON mode)")
        self.logger.info("=" * 80 + "\n")
        return relevant_classes

    def evaluate_properties_from_toon(
        self,
        question: str,
        relevant_classes: List[str],
        toon_text: str,
        verbose: bool = False,
    ):
        """Evaluate relevant properties by embedding TOON property rows directly."""
        self.logger.info("=" * 80)
        self.logger.info("STEP 2: PROPERTY RELEVANCE EVALUATION (DIRECT TOON)")
        self.logger.info("=" * 80)

        if not relevant_classes:
            return []

        blocks = self._parse_toon_blocks(toon_text)
        if not blocks:
            self.logger.warning("No TOON class blocks found for property evaluation")
            return []

        relevant_set = set(self.normalize_class_id(c) for c in relevant_classes)
        query_embedding = self.encode(question)
        results = []

        for class_name, block_data in blocks.items():
            if class_name not in relevant_set:
                continue

            rows = block_data.get("property_rows", [])
            if not rows:
                results.append({"class_name": class_name, "relevant_properties": []})
                continue

            property_names = [r["property_name"] for r in rows]
            property_texts = [f"{r['property_name']}: {r['row_text']}" for r in rows]
            property_embeddings = self.encode(property_texts)
            cos_scores = util.cos_sim(query_embedding, property_embeddings)[0]

            scores_mean = cos_scores.mean()
            threshold = 0
            if len(cos_scores) > 1:
                scores_std = cos_scores.std()
                threshold = scores_mean - scores_std

            sorted_indices = torch.argsort(cos_scores, descending=True)
            relevant_properties = []
            for idx in sorted_indices:
                prop_name = property_names[idx.item()]
                score = cos_scores[idx].item()
                if score >= threshold:
                    relevant_properties.append(prop_name)
                    if verbose or score > 0.5:
                        self.logger.info(f"    [OK] {prop_name:35s} similarity={score:.4f}")

            results.append({"class_name": class_name, "relevant_properties": relevant_properties})
            if verbose:
                self.logger.info(f"[OK] {class_name}: selected {len(relevant_properties)}/{len(rows)} properties")

        self.logger.info(f"[OK] Property evaluation completed for {len(results)} classes (direct TOON mode)")
        self.logger.info("=" * 80 + "\n")
        return results
    
    def evaluate_classes(self, question, formatted_schema, schema_json, verbose=False):
        """
        Evaluate which classes are relevant using cosine similarity with caching.
        
        Uses statistical thresholding: filters classes where score >= (mean - std)
        
        Args:
            question: User's natural language question
            formatted_schema: Unused (kept for compatibility)
            schema_json: Raw JSON schema dictionary
            verbose: Print debug information
            
        Returns:
            List of relevant class names
        """
        self.logger.info("="*80)
        self.logger.info("STEP 1: CLASS RELEVANCE EVALUATION")
        self.logger.info("="*80)
        
        if not schema_json or 'classes' not in schema_json:
            self.logger.error("Invalid schema_json provided")
            return []
        
        classes_dict = schema_json['classes']
        classes = list(classes_dict.keys())
        
        if not classes:
            return []
        
        # Log schema info
        total_properties = sum(len(c.get('properties', [])) for c in classes_dict.values())
        self.logger.info(f"[DEBUG] Schema has {len(classes)} classes with {total_properties} total properties")
        
        # Check cache first
        class_embeddings = None
        class_descriptions_text = []
        class_descriptions = {}
        
        if self.use_cache and self.cache and self.cache.has_cached_classes(schema_json):
            self.logger.info("[CACHE HIT] Using cached class embeddings...")
            try:
                class_embeddings_array, cached_class_names = self.cache.load_class_cache(schema_json)
                class_embeddings = torch.tensor(class_embeddings_array, dtype=torch.float32)
                class_descriptions_text = [f"{cn}" for cn in cached_class_names]
                # IMPORTANT: Rebuild class_descriptions dict from cached names
                class_descriptions = {cn: "" for cn in cached_class_names}
                self.logger.info(f"[OK] Loaded {len(cached_class_names)} class embeddings from cache")
                
                # Show examples of what was embedded (rebuild descriptions for display)
                self.logger.info("Examples of cached class embeddings:")
                for i, class_name in enumerate(cached_class_names[:2]):
                    # Find the class in schema to rebuild its description
                    class_full_name = None
                    for cls_key in classes_dict.keys():
                        if self.normalize_class_id(cls_key) == class_name:
                            class_full_name = cls_key
                            break
                    
                    if class_full_name:
                        desc = self.build_class_description(class_name, classes_dict[class_full_name])
                        preview = f"{class_name}: {desc[:100]}..." if len(desc) > 100 else f"{class_name}: {desc}"
                        self.logger.info(f"  [{i+1}] {preview}")
                    else:
                        self.logger.info(f"  [{i+1}] {class_name}")
            except Exception as e:
                self.logger.warning(f"Failed to load cache: {e}. Computing fresh embeddings...", exc_info=True)
                class_embeddings = None
        
        # Compute fresh if not cached
        if class_embeddings is None:
            self.logger.info(f"[COMPUTING] Embeddings for {len(classes)} classes (fresh)...")
            
            # Build class descriptions
            for class_name in classes:
                normalized = self.normalize_class_id(class_name)
                class_descriptions[normalized] = self.build_class_description(
                    normalized, classes_dict[class_name]
                )
            
            class_descriptions_text = [
                f"{k}: {v}" for k, v in class_descriptions.items()
            ]
            
            # Show example of what's being embedded
            self.logger.info("Examples of class embeddings:")
            for i, text in enumerate(class_descriptions_text[:2]):
                preview = text[:120] + "..." if len(text) > 120 else text
                self.logger.info(f"  [{i+1}] {preview}")
            
            # Encode classes
            self.logger.info(f"[ENCODING] {len(classes)} class descriptions...")
            class_embeddings = self.encode(class_descriptions_text)
            
            # Save to cache
            if self.use_cache and self.cache:
                try:
                    embeddings_np = class_embeddings.cpu().numpy()
                    self.cache.save_class_cache(schema_json, embeddings_np, list(class_descriptions.keys()))
                    self.logger.info("[OK] Class embeddings saved to cache")
                except Exception as e:
                    self.logger.warning(f"Failed to save cache: {e}", exc_info=True)
        
        # Encode question
        self.logger.info(f"[ENCODING] Question: \"{question[:100]}...\"")
        query_embedding = self.encode(question)
        
        # Compute cosine similarity
        self.logger.info("[COMPUTING] Cosine similarity...")
        cos_scores = util.cos_sim(query_embedding, class_embeddings)[0]
        
        # Statistical thresholding (notebook approach: mean - std)
        scores_mean = cos_scores.mean()
        scores_std = cos_scores.std()
        scores_min_threshold = scores_mean - scores_std
        
        # Sort by score
        sorted_indices = torch.argsort(cos_scores, descending=True)
        
        if verbose:
            self.logger.info(f"Query: {question}")
            self.logger.info(f"Scores mean: {scores_mean:.4f}, std: {scores_std:.4f}")
            self.logger.info(f"Threshold: {scores_min_threshold:.4f}")
            self.logger.info("Most relevant KG classes:")
        
        # Filter relevant classes
        relevant_classes = []
        max_classes =10  # Limit to top 5 classes to prevent context overflow
        for idx in sorted_indices:
            class_name = list(class_descriptions.keys())[idx.item()] if class_descriptions else f"class_{idx.item()}"
            score = cos_scores[idx].item()
            
            if score >= scores_min_threshold and len(relevant_classes) < max_classes:
                relevant_classes.append(class_name)
                if verbose or score > 0.5:
                    self.logger.info(f"  [OK] {class_name:20s}  similarity={score:.4f}")
            elif len(relevant_classes) >= max_classes:
                break
        
        self.logger.info(f"[OK] Selected {len(relevant_classes)} relevant classes (max {max_classes})")
        self.logger.info("="*80 + "\n")
        return relevant_classes
    
    def evaluate_properties(self, question, relevant_classes, formatted_schema, schema_json,
                          verbose=False):
        """
        Evaluate relevant properties using cosine similarity with caching.
        
        For each relevant class, filters properties where score >= (mean - std)
        
        Args:
            question: User's natural language question
            relevant_classes: List of relevant class names
            formatted_schema: Unused (kept for compatibility)
            schema_json: Raw JSON schema dictionary
            verbose: Print debug information
            
        Returns:
            List of dictionaries with class_name and relevant_properties
        """
        self.logger.info("="*80)
        self.logger.info("STEP 2: PROPERTY RELEVANCE EVALUATION")
        self.logger.info("="*80)
        
        if not relevant_classes or not schema_json:
            return []
        
        classes_dict = schema_json['classes']
        
        # Check cache for properties
        cached_properties = {}
        if self.use_cache and self.cache and self.cache.has_cached_properties(schema_json):
            self.logger.info("[CACHE HIT] Using cached property embeddings...")
            try:
                cached_properties = self.cache.load_property_cache(schema_json)
                self.logger.info(f"[OK] Loaded property embeddings from cache")
            except Exception as e:
                self.logger.warning(f"Failed to load property cache: {e}. Computing fresh...", exc_info=True)
                cached_properties = {}
        
        # Encode question once
        query_embedding = self.encode(question)
        
        results = []
        properties_to_cache = {}
        
        # Log schema structure
        if cached_properties:
            self.logger.info(f"[CACHE MODE] Evaluating {len(relevant_classes)} classes using cached embeddings")
        else:
            self.logger.info(f"[FRESH MODE] Computing embeddings for {len(relevant_classes)} relevant classes")
        
        for class_full_name, class_data in classes_dict.items():
            class_name = self.normalize_class_id(class_full_name)
            
            # Skip if not in relevant classes
            if class_name not in relevant_classes:
                continue
            
            properties = class_data.get('properties', [])
            
            # Only log per-class details when computing fresh embeddings
            if not cached_properties:
                self.logger.info(f"[DEBUG] {class_name}: {len(properties)} properties in schema")
            
            if not properties:
                results.append({"class_name": class_name, "relevant_properties": []})
                continue
            
            # Check cache for this class
            property_embeddings = None
            if class_name in cached_properties:
                # Properties already loaded from cache at the start - just access them
                property_embeddings = torch.tensor(cached_properties[class_name], dtype=torch.float32)
                property_names = [p.get('property_name', '') for p in properties]
            else:
                self.logger.info(f"[COMPUTING] Property embeddings for {class_name} (fresh)...")
                
                # Build property descriptions
                property_descriptions = {}
                for prop in properties:
                    prop_name = prop.get('property_name', '')
                    prop_label = prop.get('property_label', '')
                    prop_description = self.build_property_description(prop_name, prop_label, prop)
                    property_descriptions[prop_name] = prop_description
                
                property_texts = [
                    f"{k}: {v}" for k, v in property_descriptions.items()
                ]
                
                # Show example of what's being embedded for this class
                self.logger.info(f"  Examples of {class_name} property embeddings:")
                for i, text in enumerate(property_texts[:2]):
                    preview = text[:110] + "..." if len(text) > 110 else text
                    self.logger.info(f"    [{i+1}] {preview}")
                
                # Encode properties
                self.logger.info(f"  [ENCODING] {len(property_texts)} properties for {class_name}...")
                property_embeddings = self.encode(property_texts)
                property_names = list(property_descriptions.keys())
                
                # Store for caching
                properties_to_cache[class_name] = property_embeddings.cpu().numpy()
            
            # Compute cosine similarity
            cos_scores = util.cos_sim(query_embedding, property_embeddings)[0]
            
            # Statistical thresholding (notebook approach: mean - std)
            scores_mean = cos_scores.mean()
            scores_min_threshold = 0
            
            if len(cos_scores) > 1:
                scores_std = cos_scores.std()
                scores_min_threshold = scores_mean - scores_std
            
            # Sort by score
            sorted_indices = torch.argsort(cos_scores, descending=True)
            
            if verbose:
                self.logger.info(f"  Score threshold for {class_name}: {scores_min_threshold:.4f}")
                self.logger.info(f"  Most relevant properties:")
            
            # Filter relevant properties
            relevant_properties = []
            for idx in sorted_indices:
                prop_name = property_names[idx.item()]
                score = cos_scores[idx].item()
                
                if score >= scores_min_threshold:
                    relevant_properties.append(prop_name)
                    if verbose or score > 0.5:
                        self.logger.info(f"    [OK] {prop_name:20s}  similarity={score:.4f}")
            
            # Only log per-class results when computing fresh or in verbose mode
            if not cached_properties or verbose:
                self.logger.info(f"  [OK] {class_name}: {len(relevant_properties)} relevant properties")
            
            results.append({
                "class_name": class_name,
                "relevant_properties": relevant_properties
            })
        
        # Save properties to cache
        if properties_to_cache and self.use_cache and self.cache:
            try:
                self.cache.save_property_cache(schema_json, properties_to_cache)
                self.logger.info("[OK] Property embeddings saved to cache")
            except Exception as e:
                self.logger.warning(f"Failed to save property cache: {e}", exc_info=True)
        
        self.logger.info(f"[OK] Property evaluation completed for {len(results)} classes")
        self.logger.info("="*80 + "\n")
        return results
    def precompute_embeddings(self, schema_json, progress_callback=None):
        """
        Pre-compute and cache all embeddings for a schema.
        
        This allows the first query to be instant instead of waiting 17+ minutes
        for embedding computation.
        
        Args:
            schema_json: Raw JSON schema dictionary
            progress_callback: Optional callback function to report progress
                              Called as: progress_callback(stage, current, total, label)
            
        Returns:
            Dictionary with statistics about precomputation
        """
        if not self.use_cache or not self.cache:
            self.logger.warning("Caching disabled - cannot precompute embeddings")
            return {"status": "failed", "reason": "caching_disabled"}
        
        self.logger.info("="*80)
        self.logger.info("PRE-COMPUTING AND CACHING EMBEDDINGS FOR SCHEMA")
        self.logger.info("="*80)
        
        if not schema_json or 'classes' not in schema_json:
            self.logger.error("Invalid schema_json provided")
            return {"status": "failed", "reason": "invalid_schema"}
        
        classes_dict = schema_json['classes']
        num_classes = len(classes_dict)
        total_properties = sum(len(c.get('properties', [])) for c in classes_dict.values())
        
        self.logger.info(f"Schema contains {num_classes} classes with {total_properties} total properties")
        
        # Collect all class/property texts first (single-batch encode path)
        self.logger.info("\n[1/2] Collecting class/property texts...")
        classes = list(classes_dict.keys())
        class_names = []
        class_descriptions_text = []
        all_prop_texts = {}

        for i, class_full_name in enumerate(classes):
            normalized = self.normalize_class_id(class_full_name)
            class_data = classes_dict[class_full_name]
            class_names.append(normalized)
            class_descriptions_text.append(self.build_class_description(normalized, class_data))

            props = class_data.get("properties", [])
            if props:
                prop_texts = []
                for prop in props:
                    prop_name = prop.get("property_name", "")
                    prop_label = prop.get("property_label", "")
                    if not prop_name:
                        continue
                    prop_texts.append(self.build_property_description(prop_name, prop_label, prop))
                if prop_texts:
                    all_prop_texts[normalized] = prop_texts

            if progress_callback:
                progress_callback("collecting", i + 1, num_classes, f"Collecting class {i+1}/{num_classes}")

        # Precompute class embeddings in one call
        self.logger.info(f"Encoding {len(class_names)} class descriptions (batched)...")
        if progress_callback:
            progress_callback("classes_encoding", 0, 1, f"Encoding {len(class_names)} class embeddings...")
        
        class_embeddings = self.encode(class_descriptions_text)
        
        if progress_callback:
            progress_callback("classes_encoding", 1, 1, f"[OK] Encoded {len(class_names)} class embeddings")
        
        # Save class embeddings
        try:
            embeddings_np = class_embeddings.cpu().numpy()
            self.cache.save_class_cache(schema_json, embeddings_np, class_names)
            self.logger.info(f"[OK] Cached {len(class_names)} class embeddings")
        except Exception as e:
            self.logger.error(f"Failed to cache class embeddings: {e}")
            return {"status": "failed", "reason": f"class_cache_error: {e}"}
        
        # Precompute all property embeddings in one call, then split back by class
        self.logger.info("\n[2/2] Pre-computing property embeddings (single batched call)...")
        properties_to_cache = {}
        offsets = {}
        flat_texts = []
        offset = 0
        for class_name, texts in all_prop_texts.items():
            offsets[class_name] = (offset, offset + len(texts))
            flat_texts.extend(texts)
            offset += len(texts)

        if flat_texts:
            if progress_callback:
                progress_callback("properties_encoding", 0, 1, f"Encoding {len(flat_texts)} property texts...")
            all_prop_embeddings = self.encode(flat_texts)
            if progress_callback:
                progress_callback("properties_encoding", 1, 1, f"[OK] Encoded {len(flat_texts)} property texts")

            for class_name, (start, end) in offsets.items():
                properties_to_cache[class_name] = all_prop_embeddings[start:end].cpu().numpy()
        
        # Save property embeddings
        try:
            self.cache.save_property_cache(schema_json, properties_to_cache)
            self.logger.info(f"[OK] Cached property embeddings for {len(properties_to_cache)} classes")
        except Exception as e:
            self.logger.error(f"Failed to cache property embeddings: {e}")
            return {"status": "failed", "reason": f"property_cache_error: {e}"}
        
        self.logger.info("\n" + "="*80)
        self.logger.info("[OK] EMBEDDING PRECOMPUTATION COMPLETE")
        self.logger.info("="*80)
        self.logger.info(f"  Classes cached: {len(classes)}")
        self.logger.info(f"  Properties cached: {sum(len(p) for p in properties_to_cache.values())}")
        self.logger.info(f"  Next query will be instant!")
        self.logger.info("="*80 + "\n")
        
        return {
            "status": "success",
            "classes_cached": len(class_names),
            "properties_cached": sum(len(p) for p in properties_to_cache.values())
        }

    def precompute_embeddings_from_schema_file(
        self,
        schema_path,
        progress_callback=None,
        class_encode_batch_size=512,
        prop_encode_batch_size=4096,
        prop_encode_chunk_size=50000,
    ):
        """Precompute embeddings for very large schema files via streaming parse.

        Uses file-hash keyed cache and sharded property storage to avoid OOM.
        Performs two global batched encode passes (classes + properties) instead
        of per-class encode calls and supports incremental re-encoding by text hash.
        Requires optional dependency: ijson.
        """
        if not self.use_cache or not self.cache:
            self.logger.warning("Caching disabled - cannot precompute embeddings")
            return {"status": "failed", "reason": "caching_disabled"}

        schema_path = str(schema_path)
        if not Path(schema_path).exists():
            return {"status": "failed", "reason": f"schema_not_found: {schema_path}"}

        if schema_path.lower().endswith(".toon"):
            try:
                from .toon_formatter import TOONFormatter
            except Exception:
                return {"status": "failed", "reason": "toon_formatter_unavailable"}

            try:
                with open(schema_path, "r", encoding="utf-8") as f:
                    toon_text = f.read()
                schema_json = TOONFormatter.decode(toon_text)
            except Exception as e:
                self.logger.error(f"Failed to decode TOON schema file: {e}", exc_info=True)
                return {"status": "failed", "reason": f"toon_decode_error: {e}"}

            return self.precompute_embeddings(schema_json, progress_callback=progress_callback)

        try:
            import importlib
            ijson = importlib.import_module("ijson")
        except Exception:
            return {
                "status": "failed",
                "reason": "ijson_not_installed",
                "hint": "Install ijson to stream large schemas: pip install ijson",
            }

        self.logger.info("=" * 80)
        self.logger.info("PRE-COMPUTING EMBEDDINGS FROM LARGE SCHEMA FILE (STREAMING)")
        self.logger.info("=" * 80)

        schema_hash = self.cache.get_schema_hash_for_file(schema_path)
        self.logger.info(f"Schema file hash: {schema_hash}")

        old_hashes = self.cache.load_text_hashes(schema_hash)
        new_hashes = {}

        class_names = []
        class_texts = []
        class_needs_encode = []

        property_items = []
        property_needs_encode = []
        class_prop_ranges = {}

        def text_hash(text: str) -> str:
            return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:16]

        self.logger.info("[1/3] Streaming schema and collecting texts...")

        with open(schema_path, "rb") as f:
            kv_iter = ijson.kvitems(f, "classes")
            for idx, (class_full_name, class_data) in enumerate(kv_iter, 1):
                class_key = str(class_full_name)
                class_name = self.normalize_class_id(class_full_name)
                class_data = class_data if isinstance(class_data, dict) else {}

                class_desc = self.build_class_description(class_name, class_data)
                class_hash = text_hash(class_desc)
                new_hashes[f"cls:{class_key}"] = class_hash
                class_names.append(class_key)
                class_texts.append(class_desc)
                class_needs_encode.append(old_hashes.get(f"cls:{class_key}") != class_hash)

                props = class_data.get("properties", [])
                start = len(property_items)
                for prop in props:
                    prop_name = prop.get("property_name", "")
                    if not prop_name:
                        continue
                    prop_label = prop.get("property_label", "")
                    prop_desc = self.build_property_description(prop_name, prop_label, prop)
                    prop_hash = text_hash(prop_desc)
                    prop_key = f"prop:{class_key}:{prop_name}"
                    new_hashes[prop_key] = prop_hash
                    property_items.append((class_key, prop_name, prop_desc))
                    property_needs_encode.append(old_hashes.get(prop_key) != prop_hash)
                end = len(property_items)
                if end > start:
                    class_prop_ranges[class_key] = (start, end)

                if progress_callback:
                    progress_callback("streaming", idx, 0, f"Streamed {idx} classes")

        if not class_names:
            return {"status": "failed", "reason": "no_classes_found"}

        classes_to_encode = sum(class_needs_encode)
        props_to_encode = sum(property_needs_encode)
        self.logger.info(
            "  Classes: %s total, %s need encoding",
            len(class_names),
            classes_to_encode,
        )
        self.logger.info(
            "  Props: %s total, %s need encoding",
            len(property_items),
            props_to_encode,
        )

        self.logger.info("[2/3] Encoding class descriptions (batched)...")
        existing_class_embs = {}
        try:
            cached_embs, cached_names = self.cache.load_class_cache_by_hash(schema_hash)
            for name, vec in zip(cached_names, cached_embs):
                existing_class_embs[name] = vec
        except Exception:
            pass

        class_texts_to_encode = [t for t, need in zip(class_texts, class_needs_encode) if need]
        encoded_class_vecs = np.empty((0, 0), dtype=np.float32)
        if class_texts_to_encode:
            if progress_callback:
                progress_callback("classes_encoding", 0, 1, f"Encoding {len(class_texts_to_encode)} class texts")
            encoded_class_vecs = self.encode(class_texts_to_encode, batch_size=class_encode_batch_size).cpu().numpy()
            if progress_callback:
                progress_callback("classes_encoding", 1, 1, "Class encoding complete")

        class_vec_iter = iter(encoded_class_vecs)
        final_class_vecs = []
        fallback_class_texts = []
        fallback_class_indices = []

        for idx, (class_key, text, needs) in enumerate(zip(class_names, class_texts, class_needs_encode)):
            if needs:
                final_class_vecs.append(next(class_vec_iter))
                continue
            cached = existing_class_embs.get(class_key)
            if cached is not None:
                final_class_vecs.append(cached)
            else:
                fallback_class_indices.append(idx)
                fallback_class_texts.append(text)
                final_class_vecs.append(None)

        if fallback_class_texts:
            # Safety fallback for missing cache entries when hash says "unchanged".
            fallback_vecs = self.encode(fallback_class_texts, batch_size=class_encode_batch_size).cpu().numpy()
            for i, vec in enumerate(fallback_vecs):
                final_class_vecs[fallback_class_indices[i]] = vec

        class_embeddings_np = np.stack(final_class_vecs, axis=0)
        self.cache.save_class_cache_by_hash(schema_hash, class_embeddings_np, class_names)

        self.logger.info("[3/3] Encoding property descriptions (batched)...")
        property_class_index = {}
        try:
            property_class_index = self.cache.load_property_class_index_by_hash(schema_hash)
        except Exception:
            property_class_index = {}

        lazy_existing_props = {}
        full_existing_props = None

        prop_texts_to_encode = [item[2] for item, need in zip(property_items, property_needs_encode) if need]
        encoded_prop_vecs = np.empty((0, 0), dtype=np.float32)
        if prop_texts_to_encode:
            if progress_callback:
                progress_callback("properties_encoding", 0, 1, f"Encoding {len(prop_texts_to_encode)} property texts")

            encoded_prop_chunks = []
            total_to_encode = len(prop_texts_to_encode)
            for chunk_start in range(0, total_to_encode, max(1, int(prop_encode_chunk_size))):
                chunk_end = min(total_to_encode, chunk_start + max(1, int(prop_encode_chunk_size)))
                chunk_texts = prop_texts_to_encode[chunk_start:chunk_end]
                chunk_vecs = self.encode(chunk_texts, batch_size=prop_encode_batch_size).cpu().numpy()
                encoded_prop_chunks.append(chunk_vecs)

            if encoded_prop_chunks:
                encoded_prop_vecs = np.concatenate(encoded_prop_chunks, axis=0)
            if progress_callback:
                progress_callback("properties_encoding", 1, 1, "Property encoding complete")
        else:
            self.logger.info("  [SKIP] All property texts unchanged; reusing cache")

        prop_vec_iter = iter(encoded_prop_vecs)
        class_property_data = {}
        for class_key, (start, end) in class_prop_ranges.items():
            entries = property_items[start:end]
            needs_flags = property_needs_encode[start:end]

            old_embs = lazy_existing_props.get(class_key)
            if old_embs is None and class_key in property_class_index:
                safe_name = property_class_index.get(class_key)
                old_embs = self.cache.load_property_shard_by_safe_name(schema_hash, safe_name)
                if old_embs is not None:
                    lazy_existing_props[class_key] = old_embs

            # Monolithic cache fallback for legacy cache layout.
            if old_embs is None and class_key in property_class_index:
                if full_existing_props is None:
                    try:
                        full_existing_props = self.cache.load_property_cache_by_hash(schema_hash)
                    except Exception:
                        full_existing_props = {}
                old_embs = full_existing_props.get(class_key)
                if old_embs is not None:
                    lazy_existing_props[class_key] = old_embs

            vectors = []
            fallback_prop_texts = []
            fallback_prop_indices = []
            for local_idx, (_, _, prop_text) in enumerate(entries):
                if needs_flags[local_idx]:
                    vectors.append(next(prop_vec_iter))
                    continue

                if old_embs is not None and local_idx < len(old_embs):
                    vectors.append(old_embs[local_idx])
                else:
                    fallback_prop_indices.append(local_idx)
                    fallback_prop_texts.append(prop_text)
                    vectors.append(None)

            if fallback_prop_texts:
                fallback_prop_vecs = self.encode(fallback_prop_texts, batch_size=prop_encode_batch_size).cpu().numpy()
                for i, vec in enumerate(fallback_prop_vecs):
                    vectors[fallback_prop_indices[i]] = vec

            if vectors:
                class_property_data[class_key] = np.stack(vectors, axis=0)

        self.cache.save_property_shards_batch(schema_hash, class_property_data)
        self.cache.save_text_hashes(schema_hash, new_hashes)

        properties_cached_count = sum(v.shape[0] for v in class_property_data.values())

        self.logger.info("[OK] Large-schema streaming precompute complete")
        self.logger.info(f"  Classes cached: {len(class_names)}")
        self.logger.info(f"  Properties cached: {properties_cached_count}")
        self.logger.info("=" * 80)

        return {
            "status": "success",
            "schema_hash": schema_hash,
            "classes_cached": len(class_names),
            "properties_cached": properties_cached_count,
            "classes_re_encoded": classes_to_encode,
            "properties_re_encoded": props_to_encode,
            "mode": "streaming_file_batched",
        }