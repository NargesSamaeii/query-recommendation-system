"""
Embedding-based Evaluator

Uses semantic embeddings to evaluate class and property relevance.
Enhanced with direct JSON schema access for reliability.
"""

import re
import logging
import numpy as np
from typing import List, Dict, Tuple


class EmbeddingEvaluator:
    """Evaluates relevance using semantic embeddings with enhanced features."""
    
    # Keyword synonyms for query expansion
    SYNONYMS = {
        'longitude': ['long', 'lon', 'x coordinate', 'east west', 'geographic coordinate', 'longitude'],
        'latitude': ['lat', 'y coordinate', 'north south', 'geographic coordinate', 'latitude'],
        'id': ['identifier', 'code', 'key', 'reference', 'unique', 'id'],
        'name': ['label', 'title', 'designation', 'called', 'name'],
        'port': ['harbor', 'harbour', 'dock', 'terminal', 'maritime', 'port'],
        'airport': ['airfield', 'aerodrome', 'aviation', 'flight', 'airport'],
        'country': ['nation', 'state', 'territory', 'region', 'country'],
        'location': ['position', 'place', 'coordinate', 'geographic', 'where', 'location'],
        'type': ['kind', 'category', 'class', 'classification', 'type'],
        'size': ['dimension', 'capacity', 'scale', 'magnitude', 'size'],
        'depth': ['deep', 'draft', 'draught', 'depth'],
        'what': ['which', 'find', 'get', 'show', 'retrieve'],
        'how many': ['count', 'number', 'total', 'quantity'],
    }
    
    def __init__(self, model_name="sentence-transformers/all-MiniLM-L6-v2"):
        """
        Initialize evaluator with embedding model.
        
        Args:
            model_name: Name of the sentence-transformers model to use
        """
        self.logger = logging.getLogger("nl2sparql.pipeline")
        self.model_name = model_name
        self.model = None
        self.schema_json = None  # Store raw JSON schema
        self._init_model()
    
    def _init_model(self):
        """Initialize the embedding model."""
        try:
            from sentence_transformers import SentenceTransformer
            self.logger.info(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            self.logger.info("Embedding model loaded successfully")
        except ImportError:
            self.logger.error(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
            raise
        except Exception as e:
            self.logger.error(f"Failed to load embedding model: {e}")
            raise
    
    def set_schema_json(self, schema_json):
        """Store the raw JSON schema for direct access."""
        self.schema_json = schema_json
    
    def expand_query(self, question):
        """
        Expand the question with synonyms and related terms.
        
        Args:
            question: Original question string
            
        Returns:
            Expanded question with synonyms added
        """
        expanded_parts = [question]
        question_lower = question.lower()
        
        for keyword, synonyms in self.SYNONYMS.items():
            if keyword in question_lower:
                expanded_parts.extend(synonyms)
        
        return " ".join(expanded_parts)
    
    def encode(self, texts):
        """
        Encode texts into embeddings.
        
        Args:
            texts: String or list of strings to encode
            
        Returns:
            numpy array of embeddings
        """
        if isinstance(texts, str):
            texts = [texts]
        return self.model.encode(texts, convert_to_numpy=True)
    
    def compute_similarity(self, embedding1, embedding2):
        """
        Compute cosine similarity between embeddings.
        
        Args:
            embedding1: First embedding (numpy array)
            embedding2: Second embedding or array of embeddings
            
        Returns:
            Similarity score(s)
        """
        # Normalize embeddings
        norm1 = embedding1 / np.linalg.norm(embedding1)
        
        if len(embedding2.shape) == 1:
            norm2 = embedding2 / np.linalg.norm(embedding2)
            return np.dot(norm1, norm2)
        else:
            norm2 = embedding2 / np.linalg.norm(embedding2, axis=1, keepdims=True)
            return np.dot(norm2, norm1)
    
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
    
    def extract_class_info(self, block):
        """
        Extract class name and description from a class block.
        
        Args:
            block: Text block containing class information
            
        Returns:
            Tuple of (class_name, description_text)
        """
        # Extract class name
        match = re.search(r"Class Name:\s*(\S+)", block)
        if not match:
            return None, ""
        
        class_name_raw = match.group(1)
        class_name = self.normalize_class_id(class_name_raw)
        
        # Extract description if available
        desc_match = re.search(r"Description:\s*(.+?)(?=\n[A-Z]|\Z)", block, re.DOTALL)
        description = desc_match.group(1).strip() if desc_match else ""
        
        # If no description, use the whole block (truncated)
        if not description:
            description = block[:500]
        
        # Create a meaningful text representation
        text = f"{class_name} {description}"
        
        return class_name, text
    
    def extract_property_info(self, block):
        """
        Extract property names and descriptions from a class block.
        
        Args:
            block: Text block containing class and property information
            
        Returns:
            List of tuples (property_name, description_text, is_generic)
        """
        properties = []
        
        # Find all property lines (format: "  - Property: name | Label: label | ...")
        property_lines = re.findall(
            r"-\s*Property:\s*(\S+)\s*\|\s*Label:\s*(\S+)(.*?)(?=\n|$)",
            block
        )
        
        # Generic/metadata properties to deprioritize
        generic_props = {
            'hadPrimarySource', 'wasDerivedFrom', 'wasGeneratedBy',
            'wasAttributedTo', 'type', 'label', 'comment'
        }
        
        for prop_full, prop_label, prop_rest in property_lines:
            prop_name = self.normalize_class_id(prop_full)
            
            # Extract examples if present
            examples_match = re.search(r"\|\s*Examples:\s*([^\n|]*)", prop_rest)
            examples = examples_match.group(1).strip() if examples_match else ""
            
            # Extract datatype if present
            datatype_match = re.search(r"\|\s*Datatype:\s*(\S+)", prop_rest)
            datatype = datatype_match.group(1) if datatype_match else ""
            
            # Create enhanced text representation
            # Emphasize property name by repeating it multiple times
            text_parts = [
                prop_name,  # Main property name
                prop_name,  # Repeat for emphasis
                prop_label,  # Label version
                prop_label.lower(),  # Lowercase label
                examples[:100] if examples else "",  # Example values
                datatype if datatype else ""  # Datatype
            ]
            
            # Add powerful semantic hints based on property name
            prop_lower = prop_name.lower()
            label_lower = prop_label.lower()
            
            if any(kw in prop_lower or kw in label_lower for kw in ['id', 'identifier', 'code']):
                text_parts.append("identifier code ID unique reference key")
            if 'longitude' in prop_lower or 'longitude' in label_lower or 'long' in label_lower:
                text_parts.append("longitude long coordinate east west geographic location position")
            if 'latitude' in prop_lower or 'latitude' in label_lower or 'lat' in label_lower:
                text_parts.append("latitude lat coordinate north south geographic location position")
            if any(kw in prop_lower or kw in label_lower for kw in ['coord', 'location', 'geo']):
                text_parts.append("coordinate location position geographic spatial")
            if any(kw in prop_lower or kw in label_lower for kw in ['name', 'label', 'title']):
                text_parts.append("name label title designation")
            if any(kw in prop_lower or kw in label_lower for kw in ['port', 'harbor', 'harbour']):
                text_parts.append("port harbor harbour maritime")
            
            text = " ".join(filter(None, text_parts))
            
            # Mark if it's a generic property (for deprioritization)
            is_generic = prop_name in generic_props or prop_label in generic_props
            properties.append((prop_name, text, is_generic))
        
        return properties
    
    def evaluate_classes(self, question, formatted_schema, top_k=5, threshold=0.3):
        """
        Evaluate which classes are relevant using embeddings.
        
        Args:
            question: User's natural language question
            formatted_schema: Formatted schema string
            top_k: Number of top classes to return
            threshold: Minimum similarity threshold
            
        Returns:
            List of relevant class names
        """
        self.logger.info("Evaluating class relevance using embeddings...")
        
        # Expand question with synonyms for better matching
        expanded_question = self.expand_query(question)
        self.logger.info(f"Expanded query: {expanded_question[:100]}...")
        
        # Split schema into class blocks
        split_schema = re.split(r"\nClass Name: ", formatted_schema, maxsplit=1)
        if len(split_schema) > 1:
            class_blocks_text = "Class Name: " + split_schema[1]
        else:
            class_blocks_text = formatted_schema
        
        class_blocks = re.split(r"\n(?=Class Name: )", class_blocks_text.strip())
        class_blocks = [blk for blk in class_blocks if "Class Name:" in blk]
        
        if not class_blocks:
            self.logger.warning("No class blocks found in schema")
            return []
        
        # Encode EXPANDED question
        question_embedding = self.encode(expanded_question)[0]
        
        # Extract and encode all classes with enhanced text
        class_data = []
        class_texts = []
        class_blocks_map = {}  # Store blocks for later property extraction
        
        for block in class_blocks:
            class_name, text = self.extract_class_info(block)
            if class_name:
                class_data.append(class_name)
                class_texts.append(text)
                class_blocks_map[class_name] = block
        
        if not class_data:
            self.logger.warning("No valid classes extracted")
            return []
        
        self.logger.info(f"Encoding {len(class_texts)} classes...")
        class_embeddings = self.encode(class_texts)
        
        # Compute similarities
        similarities = self.compute_similarity(question_embedding, class_embeddings)
        
        # Apply keyword boosting for class names
        question_lower = question.lower()
        question_words = set(re.findall(r'\w+', question_lower))
        
        boosted_scores = []
        for idx, sim in enumerate(similarities):
            score = float(sim)
            class_name_lower = class_data[idx].lower()
            class_words = set(re.findall(r'[a-z]+', class_name_lower))
            
            # Boost for word overlap between question and class name
            overlap = len(question_words & class_words)
            if overlap > 0:
                score += 0.15 * overlap
            
            # Boost if class name appears in question
            if class_name_lower in question_lower:
                score += 0.25
            
            boosted_scores.append((idx, score))
        
        # Sort by boosted score
        boosted_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Take top-k above threshold
        relevant_classes = []
        for idx, score in boosted_scores[:top_k]:
            if score >= threshold:
                class_name = class_data[idx]
                relevant_classes.append(class_name)
                self.logger.info(f"  OK {class_name} (score: {score:.3f})")
        
        self.logger.info(f"Selected {len(relevant_classes)} relevant classes using embeddings")
        return relevant_classes
    
    def evaluate_properties(self, question, relevant_classes, formatted_schema, 
                          top_k_per_class=10, threshold=0.3):
        """
        Evaluate relevant properties using embeddings.
        
        Args:
            question: User's natural language question
            relevant_classes: List of relevant class names
            formatted_schema: Formatted schema string
            top_k_per_class: Number of top properties per class
            threshold: Minimum similarity threshold
            
        Returns:
            List of dictionaries with class_name and relevant_properties
        """
        self.logger.info("Evaluating property relevance using embeddings...")
        
        if not relevant_classes:
            self.logger.warning("No relevant classes provided")
            return []
        
        # Expand question with synonyms
        expanded_question = self.expand_query(question)
        self.logger.info(f"Expanded query for properties: {expanded_question[:80]}...")
        
        # Split schema
        split_schema = re.split(r"\nClass Name: ", formatted_schema, maxsplit=1)
        if len(split_schema) > 1:
            class_blocks_text = "Class Name: " + split_schema[1]
        else:
            class_blocks_text = formatted_schema
        
        class_blocks = re.split(r"\n(?=Class Name: )", class_blocks_text.strip())
        
        # Normalize relevant classes
        relevant_classes_set = set([self.normalize_class_id(c) for c in relevant_classes])
        
        # Encode EXPANDED question
        question_embedding = self.encode(expanded_question)[0]
        
        # Extract key concepts from question for direct matching
        question_lower = question.lower()
        question_words = set(re.findall(r'\w+', question_lower))
        expanded_words = set(re.findall(r'\w+', expanded_question.lower()))
        
        results = []
        
        for block in class_blocks:
            block = block.strip()
            if not block:
                continue
            
            # Extract class name
            match = re.search(r"Class Name:\s*(\S+)", block)
            if not match:
                continue
            
            class_name_raw = match.group(1)
            class_name = self.normalize_class_id(class_name_raw)
            
            # Skip if not in relevant classes
            if class_name not in relevant_classes_set:
                continue
            
            # Extract properties
            properties = self.extract_property_info(block)
            
            if not properties:
                self.logger.info(f"  No properties found for {class_name}")
                results.append({
                    "class_name": class_name,
                    "relevant_properties": []
                })
                continue
            
            # Separate property data
            prop_names = [p[0] for p in properties]
            prop_texts = [p[1] for p in properties]
            prop_is_generic = [p[2] for p in properties]
            
            self.logger.info(f"  Encoding {len(prop_texts)} properties for {class_name}...")
            prop_embeddings = self.encode(prop_texts)
            
            # Compute base similarities
            similarities = self.compute_similarity(question_embedding, prop_embeddings)
            
            # Apply aggressive keyword boosting
            boosted_scores = []
            for idx, sim in enumerate(similarities):
                score = float(sim)
                prop_name_lower = prop_names[idx].lower()
                prop_words = set(re.findall(r'[a-z]+', prop_name_lower))
                
                # Strong boost for direct property name match in question
                if prop_name_lower in question_lower:
                    score += 0.4
                
                # Boost for word overlap with original question
                overlap = len(question_words & prop_words)
                if overlap > 0:
                    score += 0.2 * overlap
                
                # Additional boost for overlap with expanded question (synonyms)
                expanded_overlap = len(expanded_words & prop_words)
                if expanded_overlap > overlap:
                    score += 0.1 * (expanded_overlap - overlap)
                
                # Penalize generic/metadata properties heavily
                if prop_is_generic[idx]:
                    score *= 0.3
                
                boosted_scores.append(score)
            
            # Get ALL properties above threshold (or top-k if none qualify)
            relevant_props = []
            for idx, score in enumerate(boosted_scores):
                relevant_props.append((prop_names[idx], score))
            
            # Sort by score
            relevant_props.sort(key=lambda x: x[1], reverse=True)
            
            # Take top-k or all above threshold
            filtered_props = [(p, s) for p, s in relevant_props if s >= threshold]
            if not filtered_props:
                # If nothing above threshold, take top 3 anyway
                filtered_props = relevant_props[:3]
                self.logger.info(f"    (Using top 3 despite low scores)")
            
            filtered_props = filtered_props[:top_k_per_class]
            selected_props = [p[0] for p in filtered_props]
            
            self.logger.info(f"  OK {class_name}: {len(selected_props)} properties")
            for prop, score in filtered_props:
                self.logger.info(f"    - {prop} (score: {score:.3f})")
            
            results.append({
                "class_name": class_name,
                "relevant_properties": selected_props
            })
        
        self.logger.info(f"Property evaluation completed for {len(results)} classes")
        return results
