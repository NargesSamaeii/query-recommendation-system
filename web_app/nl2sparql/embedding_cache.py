"""
Embedding Cache Manager

Manages persistent storage and retrieval of pre-computed embeddings.
Supports separate collections for classes and properties per schema.
"""

import os
import json
import logging
import hashlib
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np


class EmbeddingCache:
    """Manages caching of embeddings for classes and properties."""
    
    def __init__(self, cache_dir: str = "cache/embeddings"):
        """Initialize cache manager.
        
        Args:
            cache_dir: Directory to store cached embeddings
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("nl2sparql.cache")
        self.storage_dtype = np.float16
        self.use_compression = os.getenv("NL2SPARQL_CACHE_COMPRESS", "1") != "0"
        self.logger.info(f"Cache directory: {self.cache_dir}")

    def _save_npz(self, path: Path, **arrays) -> None:
        """Save NPZ using compressed or uncompressed mode."""
        if self.use_compression:
            np.savez_compressed(path, **arrays)
        else:
            np.savez(path, **arrays)
    
    def _get_schema_hash(self, schema_json: Dict) -> str:
        """Generate hash of schema for cache validation.
        
        Args:
            schema_json: Schema dictionary
            
        Returns:
            SHA256 hash of schema
        """
        schema_str = json.dumps(schema_json, sort_keys=True)
        return hashlib.sha256(schema_str.encode()).hexdigest()[:16]

    def get_schema_hash_for_file(self, schema_path: str) -> str:
        """Generate hash from file bytes for very large schema files."""
        h = hashlib.sha256()
        with open(schema_path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()[:16]
    
    def _get_class_cache_path(self, schema_hash: str) -> Path:
        """Get path for class embeddings cache."""
        return self.cache_dir / f"classes_{schema_hash}.npz"
    
    def _get_property_cache_path(self, schema_hash: str) -> Path:
        """Get path for property embeddings cache."""
        return self.cache_dir / f"properties_{schema_hash}.npz"
    
    def _get_metadata_path(self, schema_hash: str) -> Path:
        """Get path for metadata (class/property names mapping)."""
        return self.cache_dir / f"metadata_{schema_hash}.json"

    def _get_property_shard_dir(self, schema_hash: str) -> Path:
        """Get directory for sharded property cache (large schema mode)."""
        return self.cache_dir / f"properties_{schema_hash}_shards"

    def _get_text_hashes_path(self, schema_hash: str) -> Path:
        """Get path for incremental text hash cache."""
        return self.cache_dir / f"text_hashes_{schema_hash}.json"

    def _safe_name(self, class_name: str) -> str:
        """Create short deterministic file-safe name for shard files.

        Hash-based naming avoids Windows path-length issues for long/unicode class names.
        """
        raw = str(class_name or "class")
        digest = hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:20]
        return f"cls_{digest}"

    def has_cached_classes_for_file(self, schema_path: str) -> bool:
        schema_hash = self.get_schema_hash_for_file(schema_path)
        cache_path = self._get_class_cache_path(schema_hash)
        exists = cache_path.exists()
        if exists:
            self.logger.info(f"[FOUND] Class cache found for schema file hash {schema_hash}")
        else:
            self.logger.info(f"[NOT FOUND] No class cache found for schema file hash {schema_hash}")
        return exists

    def has_cached_properties_for_file(self, schema_path: str) -> bool:
        schema_hash = self.get_schema_hash_for_file(schema_path)
        mono_path = self._get_property_cache_path(schema_hash)
        shard_dir = self._get_property_shard_dir(schema_hash)
        exists = mono_path.exists() or shard_dir.exists()
        if exists:
            self.logger.info(f"[FOUND] Property cache found for schema file hash {schema_hash}")
        else:
            self.logger.info(f"[NOT FOUND] No property cache found for schema file hash {schema_hash}")
        return exists
    
    def has_cached_classes(self, schema_json: Dict) -> bool:
        """Check if classes are cached for this schema.
        
        Args:
            schema_json: Schema dictionary
            
        Returns:
            True if cache exists and is valid
        """
        schema_hash = self._get_schema_hash(schema_json)
        cache_path = self._get_class_cache_path(schema_hash)
        
        exists = cache_path.exists()
        if exists:
            self.logger.info(f"[FOUND] Class cache found for schema {schema_hash}")
        else:
            self.logger.info(f"[NOT FOUND] No class cache found for schema {schema_hash}")
        return exists
    
    def has_cached_properties(self, schema_json: Dict) -> bool:
        """Check if properties are cached for this schema.
        
        Args:
            schema_json: Schema dictionary
            
        Returns:
            True if cache exists and is valid
        """
        schema_hash = self._get_schema_hash(schema_json)
        cache_path = self._get_property_cache_path(schema_hash)
        shard_dir = self._get_property_shard_dir(schema_hash)

        exists = cache_path.exists() or shard_dir.exists()
        if exists:
            self.logger.info(f"[FOUND] Property cache found for schema {schema_hash}")
        else:
            self.logger.info(f"[NOT FOUND] No property cache found for schema {schema_hash}")
        return exists
    
    def save_class_cache(self, schema_json: Dict, embeddings: np.ndarray, 
                         class_names: List[str]) -> None:
        """Save class embeddings to cache.
        
        Args:
            schema_json: Schema dictionary
            embeddings: Class embeddings array (n_classes, embedding_dim)
            class_names: List of class names in order
        """
        schema_hash = self._get_schema_hash(schema_json)
        self.save_class_cache_by_hash(schema_hash, embeddings, class_names)

    def save_class_cache_by_hash(self, schema_hash: str, embeddings: np.ndarray, class_names: List[str]) -> None:
        """Save class embeddings when hash is already known (e.g., file-hash mode)."""
        cache_path = self._get_class_cache_path(schema_hash)
        metadata_path = self._get_metadata_path(schema_hash)
        
        self.logger.info(f"Saving {len(class_names)} class embeddings to cache...")
        
        # Save embeddings
        to_store = embeddings.astype(self.storage_dtype, copy=False)
        self._save_npz(cache_path, embeddings=to_store)
        self.logger.info(f"  [OK] Embeddings saved: {cache_path}")
        
        # Save metadata
        metadata = {
            "schema_hash": schema_hash,
            "class_names": class_names,
            "n_classes": len(class_names),
            "embedding_dim": embeddings.shape[1]
        }
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        self.logger.info(f"  [OK] Metadata saved: {metadata_path}")
    
    def load_class_cache(self, schema_json: Dict) -> Tuple[np.ndarray, List[str]]:
        """Load cached class embeddings.
        
        Args:
            schema_json: Schema dictionary
            
        Returns:
            Tuple of (embeddings array, class names list)
        """
        schema_hash = self._get_schema_hash(schema_json)
        return self.load_class_cache_by_hash(schema_hash)

    def load_class_cache_by_hash(self, schema_hash: str) -> Tuple[np.ndarray, List[str]]:
        """Load class cache by explicit hash."""
        cache_path = self._get_class_cache_path(schema_hash)
        metadata_path = self._get_metadata_path(schema_hash)
        
        if not cache_path.exists():
            raise FileNotFoundError(f"Class cache not found: {cache_path}")
        
        self.logger.info(f"Loading class embeddings from cache...")
        
        # Load embeddings
        data = np.load(cache_path)
        embeddings = data['embeddings'].astype(np.float32, copy=False)
        
        # Load metadata
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        class_names = metadata['class_names']
        self.logger.info(f"  [OK] Loaded {len(class_names)} class embeddings (dim={embeddings.shape[1]})")
        
        return embeddings, class_names
    
    def save_property_cache(self, schema_json: Dict, property_data: Dict[str, np.ndarray]) -> None:
        """Save property embeddings to cache.
        
        Property data format: {class_name: embeddings_array}
        
        Args:
            schema_json: Schema dictionary
            property_data: Dict mapping class names to property embeddings
        """
        schema_hash = self._get_schema_hash(schema_json)
        self.save_property_cache_by_hash(schema_hash, property_data)

    def save_property_cache_by_hash(self, schema_hash: str, property_data: Dict[str, np.ndarray]) -> None:
        """Save monolithic property cache by explicit hash."""
        cache_path = self._get_property_cache_path(schema_hash)
        metadata_path = self._get_metadata_path(schema_hash)
        
        self.logger.info(f"Saving property embeddings to cache...")
        
        # Create dict for savez_compressed
        save_dict = {}
        metadata = {
            "schema_hash": schema_hash,
            "classes": {}
        }
        
        for class_name, embeddings in property_data.items():
            # Save as arrays with safe names
            safe_name = class_name.replace(":", "_").replace("/", "_")
            save_dict[safe_name] = embeddings.astype(self.storage_dtype, copy=False)
            metadata["classes"][class_name] = {
                "safe_name": safe_name,
                "n_properties": embeddings.shape[0],
                "embedding_dim": embeddings.shape[1]
            }
        
        # Save embeddings
        self._save_npz(cache_path, **save_dict)
        self.logger.info(f"  [OK] Property embeddings saved: {cache_path}")
        
        # Update metadata (merge with existing if present)
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                existing = json.load(f)
            existing.update(metadata)
            metadata = existing
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        self.logger.info(f"  [OK] Property metadata updated: {metadata_path}")
    
    def load_property_cache(self, schema_json: Dict) -> Dict[str, np.ndarray]:
        """Load cached property embeddings.
        
        Returns:
            Dict mapping class names to property embeddings arrays
        """
        schema_hash = self._get_schema_hash(schema_json)
        return self.load_property_cache_by_hash(schema_hash)

    def load_property_cache_by_hash(self, schema_hash: str) -> Dict[str, np.ndarray]:
        """Load property cache by explicit hash (supports monolithic and sharded cache)."""
        cache_path = self._get_property_cache_path(schema_hash)
        metadata_path = self._get_metadata_path(schema_hash)
        shard_dir = self._get_property_shard_dir(schema_hash)
        
        if not cache_path.exists() and not shard_dir.exists():
            raise FileNotFoundError(f"Property cache not found for hash: {schema_hash}")
        
        self.logger.info(f"Loading property embeddings from cache...")
        
        # Load metadata
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        properties = {}

        if cache_path.exists():
            data = np.load(cache_path)
            for class_name, class_meta in metadata.get("classes", {}).items():
                safe_name = class_meta["safe_name"]
                if safe_name in data:
                    embeddings = data[safe_name].astype(np.float32, copy=False)
                    properties[class_name] = embeddings
        elif shard_dir.exists():
            for meta_key, class_meta in metadata.get("classes", {}).items():
                # New format: key is safe_name, class_name is stored in payload.
                # Legacy format: key is class_name, safe_name in payload.
                safe_name = class_meta.get("safe_name") or meta_key
                class_name = class_meta.get("class_name") or meta_key
                if not safe_name:
                    continue
                shard_path = shard_dir / f"{safe_name}.npz"
                if not shard_path.exists():
                    continue
                shard_data = np.load(shard_path)
                if "embeddings" in shard_data:
                    properties[class_name] = shard_data["embeddings"].astype(np.float32, copy=False)
        
        self.logger.info(f"  [OK] Loaded embeddings for {len(properties)} classes")
        for class_name, embeddings in properties.items():
            self.logger.info(f"    - {class_name}: {embeddings.shape[0]} properties")
        
        return properties

    def load_property_class_index_by_hash(self, schema_hash: str) -> Dict[str, str]:
        """Load class_name -> safe_name index for property cache entries."""
        metadata_path = self._get_metadata_path(schema_hash)
        if not metadata_path.exists():
            return {}

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception:
            return {}

        index = {}
        for meta_key, class_meta in metadata.get("classes", {}).items():
            safe_name = class_meta.get("safe_name") or meta_key
            class_name = class_meta.get("class_name") or meta_key
            if class_name and safe_name:
                index[class_name] = safe_name
        return index

    def load_property_shard_by_safe_name(self, schema_hash: str, safe_name: str) -> Optional[np.ndarray]:
        """Load one property shard by safe_name without loading all classes."""
        if not safe_name:
            return None

        shard_path = self._get_property_shard_dir(schema_hash) / f"{safe_name}.npz"
        if not shard_path.exists():
            return None

        try:
            shard_data = np.load(shard_path)
            if "embeddings" in shard_data:
                return shard_data["embeddings"].astype(np.float32, copy=False)
        except Exception:
            return None
        return None

    def save_property_cache_shard(self, schema_hash: str, class_name: str, embeddings: np.ndarray) -> None:
        """Save a single class property embedding shard for large schemas."""
        self.save_property_shards_batch(schema_hash, {class_name: embeddings})

    def save_property_shards_batch(self, schema_hash: str, class_property_data: Dict[str, np.ndarray]) -> None:
        """Write all property shards and metadata in one operation.

        This avoids concurrent metadata read-modify-write races when many
        classes are persisted in parallel.
        """
        shard_dir = self._get_property_shard_dir(schema_hash)
        shard_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = self._get_metadata_path(schema_hash)

        classes_meta = {}
        shard_jobs = []
        for class_name, embeddings in class_property_data.items():
            safe_name = self._safe_name(class_name)
            shard_path = shard_dir / f"{safe_name}.npz"
            shard_jobs.append((shard_path, embeddings))
            classes_meta[safe_name] = {
                "class_name": class_name,
                "safe_name": safe_name,
                "n_properties": int(embeddings.shape[0]),
                "embedding_dim": int(embeddings.shape[1]) if embeddings.ndim > 1 else 0,
                "storage": "shard",
            }

        def write_shard(job):
            path, emb = job
            self._save_npz(path, embeddings=emb.astype(self.storage_dtype, copy=False))

        if shard_jobs:
            max_workers = min(8, len(shard_jobs))
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                list(pool.map(write_shard, shard_jobs))

        existing_meta = {}
        if metadata_path.exists():
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    existing_meta = json.load(f)
            except Exception:
                existing_meta = {}

        existing_meta.setdefault("schema_hash", schema_hash)
        existing_meta["classes"] = classes_meta
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(existing_meta, f, indent=2)

        self.logger.info(
            "  [OK] %s property shards written, metadata saved once",
            len(shard_jobs),
        )

    def save_text_hashes(self, schema_hash: str, hashes: Dict[str, str]) -> None:
        """Persist per-text hashes for incremental re-encode detection."""
        path = self._get_text_hashes_path(schema_hash)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(hashes, f)

    def load_text_hashes(self, schema_hash: str) -> Dict[str, str]:
        """Load previously saved per-text hashes."""
        path = self._get_text_hashes_path(schema_hash)
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def get_cached_counts_for_file(self, schema_path: str) -> Dict:
        """Return cached class/property counts for file-hash cache (if present)."""
        schema_hash = self.get_schema_hash_for_file(schema_path)
        metadata_path = self._get_metadata_path(schema_hash)
        class_path = self._get_class_cache_path(schema_hash)
        property_path = self._get_property_cache_path(schema_hash)
        shard_dir = self._get_property_shard_dir(schema_hash)

        output = {
            "schema_hash": schema_hash,
            "class_cached": class_path.exists(),
            "property_cached": property_path.exists() or shard_dir.exists(),
            "class_count": None,
            "property_class_count": None,
        }

        if metadata_path.exists():
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                if isinstance(metadata.get("class_names"), list):
                    output["class_count"] = len(metadata.get("class_names", []))
                if isinstance(metadata.get("classes"), dict):
                    output["property_class_count"] = len(metadata.get("classes", {}))
            except Exception:
                pass

        return output
    
    def clear_cache(self, schema_json: Optional[Dict] = None) -> None:
        """Clear cache for specific schema or all caches.
        
        Args:
            schema_json: Schema dict to clear specific cache, or None to clear all
        """
        if schema_json:
            schema_hash = self._get_schema_hash(schema_json)
            for suffix in ["_classes", "_properties", "_metadata"]:
                pattern = f"*{schema_hash}.npz" if "npz" in suffix else f"*{schema_hash}.json"
                for f in self.cache_dir.glob(pattern):
                    f.unlink()
                    self.logger.info(f"Cleared cache: {f}")
        else:
            import shutil
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info("Cleared all embeddings cache")
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache size and cache files count
        """
        total_size = 0
        cache_files = {"classes": 0, "properties": 0, "metadata": 0, "property_shards": 0}

        for f in self.cache_dir.rglob("*"):
            if not f.is_file():
                continue
            total_size += f.stat().st_size
            if "metadata" in f.name:
                cache_files["metadata"] += 1
            elif "classes" in f.name:
                cache_files["classes"] += 1
            elif "properties_" in str(f.parent) and str(f.parent).endswith("_shards"):
                cache_files["property_shards"] += 1
            elif "properties" in f.name:
                cache_files["properties"] += 1
        
        total_schemas = cache_files["classes"]
        
        return {
            "cache_dir": str(self.cache_dir),
            "total_size_mb": round(total_size / (1024**2), 2),
            "schemas_cached": total_schemas,
            "cache_files": cache_files
        }
