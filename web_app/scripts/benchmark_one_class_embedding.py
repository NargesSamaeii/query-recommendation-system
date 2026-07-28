"""Benchmark embedding time for a single class from a schema JSON file.

Usage examples:
  python scripts/benchmark_one_class_embedding.py
  python scripts/benchmark_one_class_embedding.py --schema data/output/gptkb.json
  python scripts/benchmark_one_class_embedding.py --class-key prod_vocab:Employee
  python scripts/benchmark_one_class_embedding.py --rounds 3 --with-properties
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

# Make project imports work when executed directly from scripts/
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark one-class embedding time")
    parser.add_argument(
        "--schema",
        default="data/output/gptkb.json",
        help="Path to schema JSON (default: data/output/gptkb.json)",
    )
    parser.add_argument(
        "--class-key",
        default=None,
        help="Exact class key in schema['classes'] (default: first class)",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=3,
        help="Number of encode timing rounds (default: 3)",
    )
    parser.add_argument(
        "--with-properties",
        action="store_true",
        help="Also benchmark encoding all property texts for the selected class",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    from nl2sparql.config import Config
    from nl2sparql.embedding_evaluator_v2 import EmbeddingEvaluator

    cfg = Config()
    emb_cfg = cfg.get("pipeline.extraction.embedding", {}) or {}
    cache_cfg = emb_cfg.get("cache", {}) or {}

    model_name = emb_cfg.get("model", "all-mpnet-base-v2")
    include_descriptions = bool(emb_cfg.get("include_descriptions", True))
    include_examples = bool(emb_cfg.get("include_examples", True))
    use_cache = bool(cache_cfg.get("enabled", True))
    cache_dir = cache_cfg.get("cache_dir", "cache/embeddings")

    schema_path = Path(args.schema)
    if not schema_path.exists():
        print(f"[ERROR] Schema file not found: {schema_path}")
        return 1

    print("=" * 72)
    print("ONE-CLASS EMBEDDING BENCHMARK")
    print("=" * 72)
    print(f"schema: {schema_path}")
    print(f"model: {model_name}")
    print(f"config include_descriptions={include_descriptions}")
    print(f"config include_examples={include_examples}")
    print(f"config cache_enabled={use_cache} cache_dir={cache_dir}")

    t0 = time.perf_counter()
    evaluator = EmbeddingEvaluator(
        model_name=model_name,
        include_descriptions=include_descriptions,
        include_examples=include_examples,
        use_cache=use_cache,
        cache_dir=cache_dir,
    )
    model_load_s = time.perf_counter() - t0

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    classes = schema.get("classes", {})
    if not classes:
        print("[ERROR] Schema has no classes")
        return 1

    if args.class_key:
        if args.class_key not in classes:
            print(f"[ERROR] class-key not found: {args.class_key}")
            print("Tip: run without --class-key to benchmark the first class")
            return 1
        class_key = args.class_key
    else:
        class_key = next(iter(classes.keys()))

    class_data = classes[class_key]
    class_name = evaluator.normalize_class_id(class_key)

    t1 = time.perf_counter()
    class_text = evaluator.build_class_description(class_name, class_data)
    class_build_s = time.perf_counter() - t1

    class_encode_times = []
    for _ in range(max(1, args.rounds)):
        ts = time.perf_counter()
        emb = evaluator.encode(class_text)
        _ = tuple(emb.shape)
        class_encode_times.append(time.perf_counter() - ts)

    print("-" * 72)
    print(f"selected class key: {class_key}")
    print(f"normalized class: {class_name}")
    print(f"property count in class: {len(class_data.get('properties', []))}")
    print(f"embedding device: {evaluator.device}")
    print(f"model load time: {model_load_s:.3f}s")
    print(f"class text build time: {class_build_s:.3f}s")
    print(
        "class encode time (s): "
        f"min={min(class_encode_times):.3f}, "
        f"avg={statistics.mean(class_encode_times):.3f}, "
        f"max={max(class_encode_times):.3f}, "
        f"rounds={len(class_encode_times)}"
    )

    if args.with_properties:
        prop_texts = []
        for prop in class_data.get("properties", []):
            prop_name = prop.get("property_name", "")
            if not prop_name:
                continue
            prop_label = prop.get("property_label", "")
            prop_texts.append(evaluator.build_property_description(prop_name, prop_label, prop))

        if prop_texts:
            prop_encode_times = []
            for _ in range(max(1, args.rounds)):
                ts = time.perf_counter()
                prop_emb = evaluator.encode(prop_texts)
                _ = tuple(prop_emb.shape)
                prop_encode_times.append(time.perf_counter() - ts)

            print(
                "properties encode time (s): "
                f"min={min(prop_encode_times):.3f}, "
                f"avg={statistics.mean(prop_encode_times):.3f}, "
                f"max={max(prop_encode_times):.3f}, "
                f"rounds={len(prop_encode_times)}, "
                f"texts={len(prop_texts)}"
            )
        else:
            print("properties encode: skipped (no property texts)")

    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
