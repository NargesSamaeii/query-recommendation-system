"""
NL2SPARQL Interactive GUI v2 - Enhanced Professional Version

Features:
- Working toggle controls for stage visibility
- LLM prompt inspection at each stage
- Professional logging display aligned with actual pipeline execution
- Missing ID Generation stage support
- Real-time stage progress tracking
- Export capabilities
"""

import streamlit as st
import json
import os
import sys
import logging
import io
import copy
import re
from datetime import datetime
from pathlib import Path
import streamlit.components.v1 as components

# Handle imports
try:
    from nl2sparql.pipeline import NL2SPARQLPipeline
    from nl2sparql.config import Config
    from nl2sparql.utils import detect_schema_from_question, list_available_schemas
    from nl2sparql.toon_formatter import TOONFormatter
    from nl2sparql.kg_registry import load_enabled_kgs
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from nl2sparql.pipeline import NL2SPARQLPipeline
    from nl2sparql.config import Config
    from nl2sparql.utils import detect_schema_from_question, list_available_schemas
    from nl2sparql.toon_formatter import TOONFormatter
    from nl2sparql.kg_registry import load_enabled_kgs

# repo_root/recommender is a sibling of web_app, not a subpackage of it -- add
# the repo root so the Phase 2 recommender API contract is importable from here.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
try:
    from recommender.api.schemas import RecommendRequest
    from recommender.api.service import handle_recommend
except ImportError:
    RecommendRequest = None
    handle_recommend = None


def init_session_state():
    """Initialize session state with proper defaults."""
    defaults = {
        "messages": [],
        "pipeline": None,
        "config": None,
        "schema_path": None,
        "show_classes": True,
        "show_properties": True,
        "show_entity_extraction": True,
        "show_missing_id": True,
        "show_query": True,
        "show_execution": True,
        "show_prompts": False,
        "pending_question": None,
        "is_processing": False,
        "last_processed_question": None,
        "open_eval": False,
        "user_id": "user_00001",
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _derive_kg_name_from_schema_path(schema_path):
    """Derive KG name from schema filename for both mSchema JSON and TOON files."""
    schema_name = Path(schema_path).name
    # Handle names like: corporate_mschema.json, corporate_mschema.toon, corporate.toon
    base = re.sub(r"_mschema\.(json|toon)$", "", schema_name, flags=re.IGNORECASE)
    if base == schema_name:
        base = Path(schema_name).stem
    return base


def _apply_domain_selection(kg_entry):
    """Switch schema_path + SPARQL endpoint config to the selected KG registry entry."""
    name = kg_entry.get("name")
    st.session_state.schema_path = f"data/output/{name}_mschema.json"

    sparql_cfg = st.session_state.config.config.setdefault("sparql", {})
    original_sparql = st.session_state.get("_default_sparql_config", {})
    if kg_entry.get("source_type") == "sparql_endpoint":
        # Ontop-backed KGs (movie/tourism): no named graph, endpoint from the registry.
        sparql_cfg["endpoint_url"] = kg_entry.get("sparql_endpoint")
        sparql_cfg["default_graph"] = None
    else:
        # Local RDF / Virtuoso-backed KGs: restore whatever config.yaml originally had.
        sparql_cfg["endpoint_url"] = original_sparql.get("endpoint_url")
        sparql_cfg["default_graph"] = original_sparql.get("default_graph")

    st.session_state.config.config.setdefault("kg", {})["name"] = name


def render_sidebar():
    """Render professional configuration sidebar."""
    with st.sidebar:
        st.title("⚙️ Configuration")

        # Ensure config is always initialized
        if "config" not in st.session_state or st.session_state.config is None:
            st.session_state.config = Config("config.yaml")
        if "_default_sparql_config" not in st.session_state:
            st.session_state["_default_sparql_config"] = dict(st.session_state.config.config.get("sparql", {}))

        # Domain selection
        st.subheader("🌐 Domain")
        available_kgs = load_enabled_kgs()
        if available_kgs:
            kg_names = [kg["name"] for kg in available_kgs]
            active_domain = st.session_state.get("active_domain")
            if active_domain not in kg_names:
                inferred = (
                    _derive_kg_name_from_schema_path(st.session_state.schema_path)
                    if st.session_state.get("schema_path") else None
                )
                active_domain = inferred if inferred in kg_names else kg_names[0]

            labels = [f"{kg['name']} — {kg.get('description', '')}" for kg in available_kgs]
            default_index = kg_names.index(active_domain)
            selected_label = st.selectbox(
                "Select domain",
                labels,
                index=default_index,
                key="domain_selector",
            )
            selected_kg = available_kgs[labels.index(selected_label)]

            if st.session_state.get("active_domain") != selected_kg["name"]:
                st.session_state.active_domain = selected_kg["name"]
                _apply_domain_selection(selected_kg)
                st.rerun()

            if selected_kg.get("notes"):
                st.caption(selected_kg["notes"])
        else:
            st.warning("❌ No knowledge graphs registered in config/kg_config.yaml")

        st.divider()

        # User selection -- harness-only stand-in for the external app's user picker
        # (docs/THESIS_PROJECT_PLAN.md SS7 Phase 2: threads user_id through the same
        # /recommend contract the recommender API exposes).
        st.subheader("👤 User")
        st.session_state.user_id = st.text_input(
            "User ID (for recommender API calls)",
            value=st.session_state.get("user_id", "user_00001"),
            help="Movie-domain profiles use ids like user_00001..user_10300 "
                 "(see recommender/output/behavioral_profiles/).",
            key="user_id_input",
        ).strip() or "user_00001"

        st.divider()

        # Schema file selection
        st.subheader("📄 Schema File")
        schema_dir = "data/output"
        
        if os.path.exists(schema_dir):
            schema_files = sorted([f for f in os.listdir(schema_dir) if f.endswith(('.json', '.toon'))])
            if schema_files:
                current_schema_name = None
                if st.session_state.get("schema_path"):
                    current_schema_name = Path(st.session_state.schema_path).name
                default_index = schema_files.index(current_schema_name) if current_schema_name in schema_files else 0

                selected_schema = st.selectbox(
                    "Select Schema",
                    schema_files,
                    index=default_index,
                    key="schema_selector"
                )
                selected_schema_path = os.path.join(schema_dir, selected_schema)
                if st.session_state.get("schema_path") != selected_schema_path:
                    st.session_state.schema_path = selected_schema_path
            else:
                st.warning("❌ No schema files found in data/output/")
        else:
            st.warning(f"❌ Schema directory not found: {schema_dir}")
        
        custom_path = st.text_input("Or enter custom path:")
        if custom_path:
            st.session_state.schema_path = custom_path

        st.markdown("**Auto-generate from SHACL (.ttl)**")
        ttl_input_dir = st.session_state.config.get("schema.input_dir", "data/input")
        ttl_files = []
        if os.path.exists(ttl_input_dir):
            ttl_files = sorted([f for f in os.listdir(ttl_input_dir) if f.lower().endswith('.ttl')])

        selected_ttl = st.selectbox(
            "Select SHACL TTL",
            options=ttl_files if ttl_files else ["(no .ttl files found)"],
            disabled=not bool(ttl_files),
            key="ttl_selector",
        )
        custom_ttl_path = st.text_input("Or enter TTL path:", key="custom_ttl_path")
        output_name = st.text_input(
            "Output schema filename",
            value=(f"{Path(selected_ttl).stem}_mschema.json" if ttl_files and selected_ttl != "(no .ttl files found)" else "schema_mschema.json"),
            key="ttl_output_schema_name",
        ).strip()

        if st.button("🛠️ Generate m_schema from TTL", use_container_width=True):
            ttl_path = custom_ttl_path.strip()
            if not ttl_path:
                if ttl_files and selected_ttl != "(no .ttl files found)":
                    ttl_path = os.path.join(ttl_input_dir, selected_ttl)

            if not ttl_path or not os.path.exists(ttl_path):
                st.error("❌ TTL path is invalid or file not found")
            else:
                try:
                    with st.spinner("Extracting schema from SHACL TTL..."):
                        if st.session_state.pipeline is None:
                            config_path = Path("config.yaml")
                            if not config_path.exists():
                                config_path = Path(__file__).parent.parent / "config.yaml"
                            st.session_state.pipeline = NL2SPARQLPipeline(str(config_path))
                            st.session_state.config = st.session_state.pipeline.config

                        normalized_output = output_name or (Path(ttl_path).stem + "_mschema.json")
                        if not normalized_output.lower().endswith(".json"):
                            normalized_output += ".json"

                        st.session_state.pipeline.extract_schema(ttl_path, output_name=normalized_output)

                    generated_path = os.path.join(schema_dir, normalized_output)
                    if os.path.exists(generated_path):
                        st.session_state.schema_path = generated_path
                        st.success(f"✓ Generated schema: {normalized_output}")
                    else:
                        st.success("✓ Schema extraction completed")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to generate schema: {e}")

        if st.button("✅ Validate Schema", use_container_width=True):
            if st.session_state.schema_path and os.path.exists(st.session_state.schema_path):
                st.success(f"✓ Schema loaded: {Path(st.session_state.schema_path).name}")
            else:
                st.error("❌ Schema path is invalid or not found")

        st.markdown("**TOON Format (Token Optimization)**")
        st.caption("Convert schema to TOON to reduce tokens for LLM prompts (~50% savings).")
        
        col_toon1, col_toon2 = st.columns(2)
        with col_toon1:
            if st.button("📦 Convert to TOON", use_container_width=True):
                if not st.session_state.schema_path or not os.path.exists(st.session_state.schema_path):
                    st.error("❌ Select a valid schema first")
                else:
                    try:
                        with st.spinner("Converting schema to TOON format..."):
                            if st.session_state.pipeline is None:
                                config_path = Path("config.yaml")
                                if not config_path.exists():
                                    config_path = Path(__file__).parent.parent / "config.yaml"
                                st.session_state.pipeline = NL2SPARQLPipeline(str(config_path))
                                st.session_state.config = st.session_state.pipeline.config
                            
                            toon_path = st.session_state.pipeline.schema_to_toon(st.session_state.schema_path)
                        st.success(f"✓ Converted to TOON: {Path(toon_path).name}")
                        st.caption(f"Saved to: {toon_path}")
                    except Exception as e:
                        st.error(f"❌ Conversion failed: {e}")
        
        with col_toon2:
            if st.button("🔄 Use TOON Schema", use_container_width=True):
                # Find corresponding TOON file
                if not st.session_state.schema_path:
                    st.error("❌ Select a JSON schema first")
                else:
                    base_path = st.session_state.schema_path.rsplit('.', 1)[0]
                    toon_path = f"{base_path}.toon"
                    if os.path.exists(toon_path):
                        st.session_state.schema_path = toon_path
                        st.success(f"✓ Switched to TOON schema: {Path(toon_path).name}")
                        st.rerun()
                    else:
                        st.error(f"❌ TOON file not found. Convert first or generate at {toon_path}")

        st.markdown("**TOON Prompt Options**")
        st.caption("These options are used when TOON input is selected for class extraction, property extraction, missing-ID handling, and query generation.")

        toon_formatting = st.session_state.config.config.setdefault("toon", {}).setdefault("formatting", {})
        toon_col1, toon_col2 = st.columns(2)

        with toon_col1:
            toon_include_examples = st.checkbox(
                "Include examples",
                value=bool(toon_formatting.get("include_examples", True)),
                key="toon_include_examples_sidebar",
                help="Include representative examples in TOON prompts",
            )
            toon_formatting["include_examples"] = toon_include_examples

        with toon_col2:
            st.caption("Descriptions are not exposed as a TOON prompt option.")
            toon_formatting["include_descriptions"] = False

        toon_max_examples = st.number_input(
            "Max examples per class",
            min_value=0,
            max_value=20,
            value=int(toon_formatting.get("max_examples", 2) or 0),
            step=1,
            key="toon_max_examples_sidebar",
        )
        toon_formatting["max_examples"] = int(toon_max_examples)

        st.divider()

        # --- LLM Model Selector ---
        st.subheader("🤖 LLM Model")
        provider_options = ["mistral", "gemini", "openai", "azure"]
        current_provider = st.session_state.config.get("llm.provider", "mistral")
        try:
            default_index = provider_options.index(current_provider) if current_provider in provider_options else 0
        except Exception:
            default_index = 0

        selected_provider = st.selectbox(
            "Select LLM Provider",
            provider_options,
            index=default_index,
            key="llm_provider_selector_bottom",
        )
        st.session_state.config.config.setdefault("llm", {})["provider"] = selected_provider

        model_name_default = st.session_state.config.get("llm.model_name", "") or ""
        model_name_input = st.text_input(
            "Model name / path",
            value=model_name_default,
            key="model_name_input_bottom",
        )
        st.session_state.config.config["llm"]["model_name"] = model_name_input
        model_name = model_name_input.strip() or selected_provider

        if st.session_state.get("schema_path"):
            kg_name = _derive_kg_name_from_schema_path(st.session_state.schema_path)
            st.session_state.config.config.setdefault("kg", {})["name"] = kg_name
            st.session_state.config.config.setdefault("llm", {})["provider"] = selected_provider
            st.session_state.config.config["llm"]["model_name"] = model_name
            st.caption(f"📁 Output context: KG={kg_name}, Model={model_name}")

        record_enabled = st.checkbox(
            "Record & evaluate processed questions (starts now)",
            value=st.session_state.config.get("pipeline.record_and_evaluate", False),
        )
        st.session_state.config.config.setdefault("pipeline", {})["record_and_evaluate"] = bool(record_enabled)
        st.session_state.config.config["pipeline"]["enable_evaluation"] = bool(record_enabled)

        query_gen_cfg = (
            st.session_state.config.config
            .setdefault("pipeline", {})
            .setdefault("schema", {})
            .setdefault("query_generation", {})
        )
        query_gen_cfg["include_resolved_entity_labels"] = st.checkbox(
            "Include labels in RESOLVED ENTITIES prompt context",
            value=bool(query_gen_cfg.get("include_resolved_entity_labels", True)),
            help="If enabled: 'Label -> <IRI>'. If disabled: only '<IRI>' is shown in the final query prompt.",
            key="query_generation_include_resolved_entity_labels",
        )

        st.divider()

        st.subheader("🧩 Extraction Method")
        extraction_cfg = st.session_state.config.config.setdefault("pipeline", {}).setdefault("extraction", {})
        current_method = str(extraction_cfg.get("method", "llm")).lower()
        extraction_method = st.selectbox(
            "Class/Property extraction",
            ["llm", "embedding"],
            index=1 if current_method == "embedding" else 0,
            help="LLM uses model reasoning. Embedding uses cosine similarity with cached vectors.",
            key="extraction_method_selector",
        )
        extraction_cfg["method"] = extraction_method

        embedding_cfg = extraction_cfg.setdefault("embedding", {})
        cache_cfg = embedding_cfg.setdefault("cache", {})

        if extraction_method == "embedding":
            embedding_cfg["model"] = st.text_input(
                "Embedding model",
                value=str(embedding_cfg.get("model", "all-mpnet-base-v2")),
                key="embedding_model_input",
            ).strip() or "all-mpnet-base-v2"

            embedding_cfg["include_descriptions"] = st.checkbox(
                "Include descriptions in embeddings",
                value=bool(embedding_cfg.get("include_descriptions", True)),
                key="embedding_include_descriptions",
            )
            embedding_cfg["include_examples"] = st.checkbox(
                "Include examples in embeddings",
                value=bool(embedding_cfg.get("include_examples", True)),
                key="embedding_include_examples",
            )

            embedding_cfg["toon_direct_mode"] = st.checkbox(
                "Experimental: direct TOON embedding mode",
                value=bool(embedding_cfg.get("toon_direct_mode", False)),
                key="embedding_toon_direct_mode",
                help="When enabled and a .toon schema is selected, embed TOON class/property text blocks directly instead of decoded JSON structures.",
            )

            # Verbose embedding logs toggle - control per-run verbose flag
            embedding_cfg["verbose_logs"] = st.checkbox(
                "Verbose embedding logs (print per-class/property similarity)",
                value=bool(embedding_cfg.get("verbose_logs", False)),
                key="embedding_verbose_logs",
                help="When enabled, embedding evaluator will log per-class and per-property similarity lines to the pipeline log output.",
            )

            cache_cfg["enabled"] = st.checkbox(
                "Enable embedding cache",
                value=bool(cache_cfg.get("enabled", True)),
                key="embedding_cache_enabled",
            )
            cache_cfg["cache_dir"] = st.text_input(
                "Cache directory",
                value=str(cache_cfg.get("cache_dir", "cache/embeddings")),
                key="embedding_cache_dir",
            ).strip() or "cache/embeddings"

            cache_dir_path = Path(cache_cfg["cache_dir"])
            if cache_dir_path.exists() and cache_dir_path.is_dir():
                files = [p for p in cache_dir_path.rglob("*") if p.is_file()]
                total_size_mb = round(sum(p.stat().st_size for p in files) / (1024 * 1024), 2)
                st.caption(f"Cache files: {len(files)} | Size: {total_size_mb} MB")
            else:
                st.caption("Cache directory will be created on first embedding run.")

            st.markdown("**Selected Schema Cache Status**")
            schema_cache_status = {
                "schema_name": "N/A",
                "class_cached": False,
                "property_cached": False,
                "class_count": None,
                "property_class_count": None,
            }
            max_schema_size_mb = 300
            is_large_schema = False

            if st.session_state.get("schema_path") and os.path.exists(st.session_state.schema_path):
                try:
                    schema_file = Path(st.session_state.schema_path)
                    schema_cache_status["schema_name"] = schema_file.name
                    schema_size_mb = round(schema_file.stat().st_size / (1024 * 1024), 2)
                    is_large_schema = schema_size_mb > max_schema_size_mb

                    from nl2sparql.embedding_cache import EmbeddingCache

                    cache_mgr = EmbeddingCache(cache_cfg["cache_dir"])
                    if schema_size_mb > max_schema_size_mb:
                        st.warning(
                            f"Schema file is very large ({schema_size_mb} MB). "
                            "Using streamed file-hash cache status (large-schema mode)."
                        )
                        counts = cache_mgr.get_cached_counts_for_file(str(schema_file))
                        schema_cache_status["class_cached"] = bool(counts.get("class_cached"))
                        schema_cache_status["property_cached"] = bool(counts.get("property_cached"))
                        schema_cache_status["class_count"] = counts.get("class_count")
                        schema_cache_status["property_class_count"] = counts.get("property_class_count")
                    else:
                        with open(schema_file, "r", encoding="utf-8") as sf:
                            if schema_file.suffix.lower() == ".toon":
                                schema_json = TOONFormatter.decode(sf.read())
                            else:
                                schema_json = json.load(sf)
                        class_cached = cache_mgr.has_cached_classes(schema_json)
                        property_cached = cache_mgr.has_cached_properties(schema_json)
                        schema_cache_status["class_cached"] = bool(class_cached)
                        schema_cache_status["property_cached"] = bool(property_cached)

                        if class_cached:
                            try:
                                _, class_names = cache_mgr.load_class_cache(schema_json)
                                schema_cache_status["class_count"] = len(class_names)
                            except Exception:
                                pass

                        if property_cached:
                            try:
                                prop_map = cache_mgr.load_property_cache(schema_json)
                                schema_cache_status["property_class_count"] = len(prop_map)
                            except Exception:
                                pass
                except Exception as cache_err:
                    st.caption(f"Cache status check failed: {cache_err}")

            class_status_txt = "yes" if schema_cache_status["class_cached"] else "no"
            prop_status_txt = "yes" if schema_cache_status["property_cached"] else "no"
            class_suffix = f" ({schema_cache_status['class_count']} classes)" if schema_cache_status["class_count"] is not None else ""
            prop_suffix = f" ({schema_cache_status['property_class_count']} class buckets)" if schema_cache_status["property_class_count"] is not None else ""
            st.caption(f"Schema: {schema_cache_status['schema_name']}")
            st.caption(f"Class cached: {class_status_txt}{class_suffix}")
            st.caption(f"Property cached: {prop_status_txt}{prop_suffix}")
            if schema_cache_status["property_cached"] and not schema_cache_status["class_cached"]:
                st.warning(
                    "Property shard cache exists but class cache is missing. "
                    "This usually means precompute stopped before final class-cache write. "
                    "Re-run precompute to finalize class cache."
                )
            st.session_state["selected_schema_cache_status"] = schema_cache_status

            precompute_disabled = not bool(cache_cfg.get("enabled", True))
            if precompute_disabled:
                st.caption("Enable embedding cache to precompute and save embeddings.")
            elif is_large_schema:
                st.caption("Large-schema mode: streamed precompute + indexed (sharded) property cache.")

            if st.button(
                "⚡ Precompute Embeddings for Selected Schema",
                key="precompute_selected_schema_embeddings",
                use_container_width=True,
                disabled=precompute_disabled,
            ):
                if not st.session_state.get("schema_path") or not os.path.exists(st.session_state.schema_path):
                    st.error("Select a valid schema first.")
                else:
                    try:
                        with st.spinner("Precomputing class/property embeddings and saving cache..."):
                            schema_path = Path(st.session_state.schema_path)
                            schema_size_mb = round(schema_path.stat().st_size / (1024 * 1024), 2)
                            is_toon_schema = schema_path.suffix.lower() == ".toon"

                            from nl2sparql.embedding_evaluator_v2 import EmbeddingEvaluator

                            evaluator = EmbeddingEvaluator(
                                model_name=embedding_cfg.get("model", "all-mpnet-base-v2"),
                                include_descriptions=bool(embedding_cfg.get("include_descriptions", True)),
                                include_examples=bool(embedding_cfg.get("include_examples", True)),
                                use_cache=True,
                                cache_dir=cache_cfg.get("cache_dir", "cache/embeddings"),
                            )
                            if is_toon_schema:
                                with open(schema_path, "r", encoding="utf-8") as sf:
                                    toon_schema = TOONFormatter.decode(sf.read())
                                precompute_result = evaluator.precompute_embeddings(toon_schema)
                            elif schema_size_mb > max_schema_size_mb:
                                precompute_result = evaluator.precompute_embeddings_from_schema_file(str(schema_path))
                            else:
                                with open(schema_path, "r", encoding="utf-8") as sf:
                                    if schema_path.suffix.lower() == ".toon":
                                        schema_json = TOONFormatter.decode(sf.read())
                                    else:
                                        schema_json = json.load(sf)
                                precompute_result = evaluator.precompute_embeddings(schema_json)

                        if precompute_result.get("status") == "success":
                            st.success(
                                f"Cached embeddings: classes={precompute_result.get('classes_cached', 0)}, "
                                f"properties={precompute_result.get('properties_cached', 0)}"
                            )
                            if precompute_result.get("mode") == "streaming_file":
                                st.caption("Used streamed large-schema indexing mode.")
                            st.rerun()
                        else:
                            err = precompute_result.get("reason", "unknown error")
                            hint = precompute_result.get("hint")
                            st.error(f"Precompute failed: {err}")
                            if hint:
                                st.caption(hint)
                    except Exception as precompute_err:
                        st.error(f"Precompute failed: {precompute_err}")
        
        st.divider()
        
        # Pipeline stages visibility toggles
        st.subheader("📊 Pipeline Stages")
        st.text("Which stages to display:")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.session_state.show_classes = st.checkbox(
                "🏷️ Class Evaluation",
                value=st.session_state.show_classes,
                help="Identify relevant classes"
            )
            st.session_state.show_entity_extraction = st.checkbox(
                "🧠 Entity Extraction",
                value=st.session_state.show_entity_extraction,
                help="Display mentions extracted before Missing-ID query generation",
            )
            st.session_state.show_missing_id = st.checkbox(
                "🔍 Missing ID Generation",
                value=st.session_state.show_missing_id,
                help="Find entity IRIs"
            )
            st.session_state.show_execution = st.checkbox(
                "🎯 Query Execution",
                value=st.session_state.show_execution,
                help="Display query results"
            )
        
        with col2:
            st.session_state.show_properties = st.checkbox(
                "⚡ Property Evaluation",
                value=st.session_state.show_properties,
                help="Select relevant properties"
            )
            st.session_state.show_query = st.checkbox(
                "📝 Query Generation",
                value=st.session_state.show_query,
                help="Display SPARQL query"
            )
        
        st.divider()
        
        # Debug options
        st.subheader("🔬 Debug Options")
        st.session_state.show_prompts = st.checkbox(
            "👁️ Show LLM Prompts",
            value=st.session_state.show_prompts,
            help="Display prompts sent to language models at each stage"
        )
        
        st.divider()
        
        # LLM Configuration Info
        st.subheader("🤖 Active Models")
        if st.session_state.config:
            llm_config = st.session_state.config.config.get("llm", {})
            st.markdown("**Reasoning LLM:**")
            reasoning_stage = llm_config.get("stages", {}).get("class_extraction", {}) if isinstance(llm_config.get("stages", {}), dict) else {}
            reasoning_provider = reasoning_stage.get("provider", llm_config.get("provider", "mistral"))
            st.caption(f"{reasoning_provider}")
            st.markdown("**Generation LLM:**")
            generation_stage = llm_config.get("stages", {}).get("query_generation", {}) if isinstance(llm_config.get("stages", {}), dict) else {}
            gen_provider = generation_stage.get("provider", llm_config.get("provider", "gemini"))
            gen_model = generation_stage.get("model_name", llm_config.get('model_name', 'gemini-2.5-flash'))
            st.caption(f"{gen_provider} :: {gen_model}")

        # Quick navigation to Evaluation UI
        if st.button("🔎 Open Evaluation Section", key="open_eval_sidebar"):
            st.session_state["open_eval"] = True


def display_stage_results(results, show_prompts):
    """Display pipeline results with professional formatting and working toggles."""
    
    if not results:
        st.error("❌ No results returned from pipeline")
        return
    
    intermediate = results.get("intermediate", {})
    extraction_method = intermediate.get("extraction_method")
    if extraction_method:
        st.caption(f"Extraction method used: {extraction_method}")
        if extraction_method == "embedding":
            embedding_mode = intermediate.get("embedding_mode")
            if embedding_mode:
                st.caption(f"Embedding mode used: {embedding_mode}")

    routing = intermediate.get("query_routing")
    if routing:
        route = routing.get("route", "sparql")
        confidence = routing.get("confidence")
        reason = routing.get("reason", "")
        with st.expander("🧭 **Routing Decision** - Query Type Selection", expanded=True):
            st.markdown(f"**Route:** `{route}`")
            if confidence is not None:
                try:
                    st.metric("Confidence", f"{float(confidence):.2f}")
                except Exception:
                    st.caption(f"Confidence: {confidence}")
            if reason:
                st.caption(f"Reason: {reason}")
            if results.get("message"):
                st.info(results.get("message"))

    evaluation = results.get("evaluation") or intermediate.get("evaluation")
    if isinstance(evaluation, dict):
        overall = evaluation.get("overall", {}) or {}
        stage_metrics = evaluation.get("stages", {}) or {}
        with st.expander("📊 **Evaluation Metrics** - Precision / Recall / F1", expanded=False):
            cols = st.columns(3)
            cols[0].metric("Average F1", f"{float(overall.get('average_f1', 0.0)):.4f}" if overall.get("average_f1") is not None else "N/A")
            cols[1].metric("Stages Evaluated", str(overall.get("stages_evaluated", len(stage_metrics))))
            cols[2].metric("Stages Included", str(len(overall.get("stages", list(stage_metrics.keys())))))

            rows = []
            for stage_name, metrics in stage_metrics.items():
                if not isinstance(metrics, dict):
                    continue
                precision = metrics.get("precision")
                recall = metrics.get("recall")
                f1 = metrics.get("f1")
                if precision is None:
                    precision = metrics.get("set_precision")
                if recall is None:
                    recall = metrics.get("set_recall")
                if f1 is None:
                    f1 = metrics.get("set_f1")
                if f1 is None and metrics.get("macro_average"):
                    f1 = metrics.get("macro_average", {}).get("f1")
                    precision = precision if precision is not None else metrics.get("macro_average", {}).get("precision")
                    recall = recall if recall is not None else metrics.get("macro_average", {}).get("recall")

                rows.append({
                    "Stage": stage_name.replace("_", " ").title(),
                    "Precision": None if precision is None else round(float(precision), 4),
                    "Recall": None if recall is None else round(float(recall), 4),
                    "F1": None if f1 is None else round(float(f1), 4),
                })

            if rows:
                try:
                    import pandas as pd
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                except Exception:
                    for row in rows:
                        st.markdown(
                            f"- **{row['Stage']}**: precision={row['Precision']} | recall={row['Recall']} | f1={row['F1']}"
                        )
    
    # ==================== CLASS EVALUATION ====================
    if st.session_state.show_classes:
        with st.expander("🏷️ **Class Evaluation** - Identifying Relevant Classes", expanded=True):
            relevant_classes = intermediate.get("relevant_classes", [])
            
            if relevant_classes:
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**Found {len(relevant_classes)} class(es):**")
                    for cls in relevant_classes:
                        st.markdown(f"  • `{cls}`")
                
                with col2:
                    st.metric("Classes Found", len(relevant_classes))
            else:
                st.info("ℹ️ No relevant classes identified")
            
            # Show prompts if enabled
            if show_prompts and "class_prompts" in intermediate:
                st.divider()
                with st.expander("📝 View Class Evaluation Prompts", expanded=False):
                    class_prompts = intermediate.get("class_prompts", [])
                    if class_prompts:
                        for i, item in enumerate(class_prompts, 1):
                            class_name = item.get('class_name', 'Unknown')
                            prompt_text = item.get("prompt", "")
                            
                            st.markdown(f"**Class {i}:** `{class_name}`")
                            st.code(prompt_text, language="text", line_numbers=True)
                            st.divider()
    
    # ==================== PROPERTY EVALUATION ====================
    if st.session_state.show_properties:
        with st.expander("⚡ **Property Evaluation** - Selecting Relevant Properties", expanded=True):
            property_selection = intermediate.get("property_selection", [])
            
            if property_selection:
                for i, item in enumerate(property_selection, 1):
                    class_name = item.get("class_name", "Unknown")
                    props = item.get("relevant_properties", [])
                    
                    with st.container(border=True):
                        col1, col2 = st.columns([0.8, 0.2])
                        with col1:
                            st.markdown(f"**Class {i}:** `{class_name}`")
                        with col2:
                            st.metric("Properties", len(props))
                        
                        if props:
                            props_display = ", ".join([f"`{p}`" for p in props])
                            st.markdown(f"**Properties:** {props_display}")
                        else:
                            st.caption("No properties selected for this class")
            else:
                st.info("ℹ️ No property selection available")
            
            # Show prompts if enabled
            if show_prompts and "property_prompts" in intermediate:
                st.divider()
                with st.expander("📝 View Property Evaluation Prompts", expanded=False):
                    property_prompts = intermediate.get("property_prompts", [])
                    if property_prompts:
                        for i, item in enumerate(property_prompts, 1):
                            class_name = item.get('class_name', 'Unknown')
                            prompt_text = item.get("prompt", "")
                            
                            st.markdown(f"**Class {i}:** `{class_name}`")
                            st.code(prompt_text, language="text", line_numbers=True)
                            st.divider()
    
    # ==================== ENTITY EXTRACTION ====================
    if st.session_state.show_entity_extraction and st.session_state.show_missing_id:
        with st.expander("🧠 **Entity Extraction** - Missing-ID Mentions", expanded=True):
            extracted_mentions = intermediate.get("entity_extraction_mentions", [])
            if extracted_mentions:
                st.markdown(f"**Extracted {len(extracted_mentions)} mention(s):**")
                for mention in extracted_mentions:
                    st.markdown(f"  • `{mention}`")
            else:
                st.caption("No entity mentions extracted")

            if show_prompts and "entity_extraction_prompt" in intermediate:
                st.divider()
                with st.expander("📝 View Entity Extraction Prompt", expanded=False):
                    st.code(intermediate.get("entity_extraction_prompt", ""), language="text", line_numbers=True)

            entity_extraction_response = intermediate.get("entity_extraction_response", "")
            if entity_extraction_response:
                st.divider()
                with st.expander("📤 View Entity Extraction LLM Output", expanded=False):
                    st.code(entity_extraction_response, language="text", line_numbers=True)

    # ==================== MISSING ID GENERATION ====================
    if st.session_state.show_missing_id:
        with st.expander("🔍 **Missing ID Generation** - Finding Entity IRIs", expanded=True):
            missing_id_query = intermediate.get("missing_id_query", "")
            
            if missing_id_query:
                col1, col2 = st.columns([0.8, 0.2])
                with col1:
                    st.markdown("**SPARQL Query for ID Lookup:**")
                with col2:
                    st.caption("Generated by Gemini")
                
                st.code(missing_id_query, language="sparql", line_numbers=True)
                
                # Show found IRIs
                missing_iris = intermediate.get("missing_iris", {})
                if missing_iris:
                    st.markdown("**Found Entity IRIs:**")
                    for entity, iris in missing_iris.items():
                        if isinstance(iris, list):
                            for iri in iris:
                                st.markdown(f"  • **{entity}** → `<{iri}>`")
                        else:
                            st.markdown(f"  • **{entity}** → `<{iris}>`")
                else:
                    st.caption("No entity IRIs found")
            else:
                st.info("ℹ️ No missing ID query generated")
            
            # Show prompts if enabled
            if show_prompts and "missing_id_prompt" in intermediate:
                st.divider()
                with st.expander("📝 View Missing ID Generation Prompt", expanded=False):
                    prompt_text = intermediate.get("missing_id_prompt", "")
                    st.code(prompt_text, language="text", line_numbers=True)
    
    # ==================== QUERY GENERATION ====================
    if st.session_state.show_query:
        with st.expander("📝 **Query Generation** - Final SPARQL Query", expanded=True):
            final_query = intermediate.get("final_query", "")
            
            if final_query:
                col1, col2 = st.columns([0.8, 0.2])
                with col1:
                    st.markdown("**Generated SPARQL Query:**")
                with col2:
                    st.caption("Generated by Gemini")
                
                st.code(final_query, language="sparql", line_numbers=True)
            else:
                st.info("ℹ️ No query generated")
            
            # Show prompts if enabled
            if show_prompts and "final_query_prompt" in intermediate:
                st.divider()
                with st.expander("📝 View Query Generation Prompt", expanded=False):
                    prompt_text = intermediate.get("final_query_prompt", "")
                    st.code(prompt_text, language="text", line_numbers=True)
    
    # ==================== QUERY EXECUTION ====================
    if st.session_state.show_execution:
        with st.expander("🎯 **Query Execution** - Results", expanded=True):
            query_results = results.get("query_results", {})
            
            if not query_results:
                st.info("ℹ️ No results available")
            elif query_results.get("error"):
                st.error(f"❌ Query Execution Error: {query_results.get('error')}")
            else:
                # Handle ASK queries (boolean results)
                if "boolean" in query_results:
                    boolean_result = query_results["boolean"]
                    if boolean_result:
                        st.success("✅ **Query Result: TRUE**", icon="✅")
                    else:
                        st.error("❌ **Query Result: FALSE**", icon="❌")
                    st.divider()
                
                # Handle SELECT queries (bindings)
                bindings = query_results.get("results", {}).get("bindings", [])
                
                if bindings:
                    col_count, col_source = st.columns([0.5, 0.5])
                    with col_count:
                        st.metric("Results Found", len(bindings))
                    with col_source:
                        st.caption("From SPARQL Endpoint")
                    
                    # Display as interactive table, with inline images for image URL columns
                    try:
                        import pandas as pd
                        import re as _re

                        _IMAGE_EXT_RE = _re.compile(
                            r'https?://.+\.(?:jpg|jpeg|png|gif|webp|svg|bmp)(\?.*)?$',
                            _re.IGNORECASE,
                        )

                        def _is_image_url(val):
                            return isinstance(val, str) and bool(_IMAGE_EXT_RE.match(val.strip()))

                        def _col_is_image(series):
                            non_empty = [v for v in series if v and str(v).strip()]
                            if not non_empty:
                                return False
                            return sum(_is_image_url(str(v)) for v in non_empty) / len(non_empty) >= 0.5

                        df_data = []
                        for binding in bindings:
                            row = {}
                            for var, val in binding.items():
                                if isinstance(val, dict):
                                    row[var] = val.get("value", str(val))
                                else:
                                    row[var] = val
                            df_data.append(row)

                        if df_data:
                            df = pd.DataFrame(df_data)

                            image_cols = [c for c in df.columns if _col_is_image(df[c])]
                            text_cols  = [c for c in df.columns if c not in image_cols]

                            # Show non-image columns in a regular table
                            if text_cols:
                                st.dataframe(df[text_cols], use_container_width=True, height=400)

                            # Show image columns as inline image galleries
                            for img_col in image_cols:
                                st.markdown(f"**🖼 Column: `{img_col}`**")
                                urls = [str(v).strip() for v in df[img_col] if v and str(v).strip()]
                                # Show up to 5 images per row
                                cols_per_row = 5
                                for chunk_start in range(0, len(urls), cols_per_row):
                                    chunk = urls[chunk_start:chunk_start + cols_per_row]
                                    # Always create the same number of columns to keep layout consistent
                                    img_cols_ui = st.columns(cols_per_row)
                                    for i in range(cols_per_row):
                                        with img_cols_ui[i]:
                                            if i < len(chunk):
                                                url = chunk[i]
                                                try:
                                                    img_html = f'<img src="{url}" style="max-width:180px; width:100%; height:auto; display:block; margin:auto;" />'
                                                    components.html(img_html, height=200)
                                                    st.caption(url.rsplit("/", 1)[-1][:40])
                                                except Exception:
                                                    try:
                                                        st.image(url, use_container_width=True)
                                                        st.caption(url.rsplit("/", 1)[-1][:40])
                                                    except Exception:
                                                        st.markdown(f"[🔗 image]({url})")
                                            else:
                                                # Empty placeholder to keep grid alignment
                                                st.write("")

                            # Download option (always uses full df)
                            csv = df.to_csv(index=False)
                            json_str = json.dumps(df_data, indent=2, ensure_ascii=False)

                            col_csv, col_json = st.columns(2)
                            with col_csv:
                                st.download_button(
                                    label="📥 Download (CSV)",
                                    data=csv,
                                    file_name=f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                    mime="text/csv"
                                )
                            with col_json:
                                st.download_button(
                                    label="📥 Download (JSON)",
                                    data=json_str,
                                    file_name=f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                                    mime="application/json"
                                )
                    except ImportError:
                        st.json(bindings)
                elif "boolean" not in query_results:
                    st.info("ℹ️ Query executed successfully but returned no results")


def display_execution_log(log_lines):
    """Display execution log in a professional, clean format by stage."""
    if not log_lines:
        return
    
    st.markdown("### 📋 Execution Log (Organized by Stage)")
    
    # Group logs by stage
    stages_display = {
        "Class Evaluation": [],
        "Property Evaluation": [],
        "Missing ID Generation": [],
        "Query Generation": [],
        "Query Execution": []
    }
    cache_lines = []
    
    current_stage = None
    
    for line in log_lines:
        line_lower = line.lower()
        
        # Detect stage from log content
        if "class" in line_lower and "evaluat" in line_lower:
            current_stage = "Class Evaluation"
        elif "propert" in line_lower and "evaluat" in line_lower:
            current_stage = "Property Evaluation"
        elif "missing" in line_lower and ("id" in line_lower or "iri" in line_lower):
            current_stage = "Missing ID Generation"
        elif ("generating" in line_lower or "generate" in line_lower) and "query" in line_lower:
            current_stage = "Query Generation"
        elif ("executing" in line_lower or "execute" in line_lower) and "query" in line_lower:
            current_stage = "Query Execution"
        
        is_cache_line = (
            "cache" in line_lower
            or "[cache hit]" in line_lower
            or "[found]" in line_lower
            or "[not found]" in line_lower
            or "[computing]" in line_lower
        )
        if is_cache_line:
            cache_lines.append(line)

        if current_stage and line.strip():
            stages_display[current_stage].append(line)

    def infer_cache_status(lines):
        merged = "\n".join(lines).lower()
        if "[cache hit]" in merged or "loaded property embeddings from cache" in merged:
            return "Cache hit: precomputed embeddings loaded"
        if "[not found]" in merged:
            return "Cache not computed yet: computing fresh embeddings"
        if "[computing]" in merged and "embeddings" in merged:
            return "Computing embeddings (fresh run)"
        if "saved to cache" in merged or "embeddings saved" in merged:
            return "Fresh embeddings computed and cached"
        return "No cache events detected"

    class_cache_status = infer_cache_status(stages_display["Class Evaluation"] + cache_lines)
    property_cache_status = infer_cache_status(stages_display["Property Evaluation"] + cache_lines)
    
    # Display by stage in professional format
    col1, col2 = st.columns([0.7, 0.3])
    
    with col1:
        st.markdown("#### 🏷️ Class Evaluation")
    st.caption(f"Cache status: {class_cache_status}")
    if stages_display["Class Evaluation"]:
        for log_line in stages_display["Class Evaluation"][-6:]:
            st.caption(log_line)
    else:
        st.caption("*Skipped*")
    
    st.markdown("---")
    
    with col1:
        st.markdown("#### ⚡ Property Evaluation")
    st.caption(f"Cache status: {property_cache_status}")
    if stages_display["Property Evaluation"]:
        for log_line in stages_display["Property Evaluation"][-6:]:
            st.caption(log_line)
    else:
        st.caption("*Skipped*")

    if cache_lines:
        st.markdown("---")
        with col1:
            st.markdown("#### 🗄️ Embedding Cache Events")
        for log_line in cache_lines[-10:]:
            st.caption(log_line)
    
    st.markdown("---")
    
    with col1:
        st.markdown("#### 🔍 Missing ID Generation")
    if stages_display["Missing ID Generation"]:
        for log_line in stages_display["Missing ID Generation"][-3:]:
            st.caption(log_line)
    else:
        st.caption("*Skipped*")
    
    st.markdown("---")
    
    with col1:
        st.markdown("#### 📝 Query Generation")
    if stages_display["Query Generation"]:
        for log_line in stages_display["Query Generation"][-3:]:
            st.caption(log_line)
    else:
        st.caption("*Skipped*")
    
    st.markdown("---")
    
    with col1:
        st.markdown("#### 🎯 Query Execution")
    if stages_display["Query Execution"]:
        for log_line in stages_display["Query Execution"][-3:]:
            st.caption(log_line)
    else:
        st.caption("*Skipped*")


def process_question(question):
    """Process question through pipeline."""

    if not st.session_state.schema_path:
        detected_schema = detect_schema_from_question(question)
        if detected_schema:
            st.session_state.schema_path = detected_schema
            st.info(f"ℹ️ Auto-detected schema: {Path(detected_schema).name}")
            try:
                detected_kg = _derive_kg_name_from_schema_path(detected_schema)
                if st.session_state.get("config"):
                    st.session_state.config.config.setdefault("kg", {})["name"] = detected_kg
            except Exception:
                pass
        else:
            st.error("❌ No schema file found! Please place schema files in data/output/")
            return None
    
    if not os.path.exists(st.session_state.schema_path):
        st.error(f"❌ Schema file not found: {st.session_state.schema_path}")
        return None
    
    # Initialize pipeline if needed
    if st.session_state.pipeline is None:
        with st.spinner("🔄 Initializing NL2SPARQL Pipeline..."):
            try:
                ui_config_snapshot = None
                if st.session_state.get("config") and hasattr(st.session_state.config, "config"):
                    ui_config_snapshot = copy.deepcopy(st.session_state.config.config)

                config_path = Path("config.yaml")
                if not config_path.exists():
                    config_path = Path(__file__).parent.parent / "config.yaml"
                
                st.session_state.pipeline = NL2SPARQLPipeline(str(config_path))

                if ui_config_snapshot:
                    for section_key, section_value in ui_config_snapshot.items():
                        if isinstance(section_value, dict):
                            st.session_state.pipeline.config.config.setdefault(section_key, {}).update(section_value)
                        else:
                            st.session_state.pipeline.config.config[section_key] = section_value

                st.session_state.config = st.session_state.pipeline.config
                st.success("✓ Pipeline initialized successfully!")
            except Exception as e:
                st.error(f"❌ Failed to initialize pipeline: {e}")
                import traceback
                st.code(traceback.format_exc())
                return None
    
    # Apply stage toggles to pipeline configuration
    if st.session_state.pipeline and st.session_state.pipeline.config:
        pipeline_config = st.session_state.pipeline.config.config
        if "pipeline" not in pipeline_config:
            pipeline_config["pipeline"] = {}
        if "stages" not in pipeline_config["pipeline"]:
            pipeline_config["pipeline"]["stages"] = {}

        stages = pipeline_config["pipeline"]["stages"]
        stages["class_extraction"] = st.session_state.show_classes
        stages["property_extraction"] = st.session_state.show_properties
        stages["missing_id_extraction"] = st.session_state.show_missing_id
        stages["query_generation"] = st.session_state.show_query
        stages["query_execution"] = st.session_state.show_execution
        pipeline_config["pipeline"]["record_and_evaluate"] = st.session_state.config.get("pipeline.record_and_evaluate", False)
    
    # Process with status display
    results = None
    try:
        with st.status("🤔 Processing your question...", expanded=True) as status:
            st.write("Setting up pipeline...")
            
            # Capture both pipeline and cache logs in the UI panel
            logger = logging.getLogger("nl2sparql.pipeline")
            cache_logger = logging.getLogger("nl2sparql.cache")
            logger.setLevel(logging.INFO)
            cache_logger.setLevel(logging.INFO)
            
            log_stream = io.StringIO()
            handler = logging.StreamHandler(log_stream)
            handler.setLevel(logging.INFO)
            formatter = logging.Formatter('%(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            cache_logger.addHandler(handler)
            
            # Run pipeline
            results = st.session_state.pipeline.answer_question(
                question,
                st.session_state.schema_path
            )
            
            all_logs = log_stream.getvalue()
            log_lines = [line.strip() for line in all_logs.split('\n') if line.strip()]

            # Prevent duplicate handlers on rerun
            logger.removeHandler(handler)
            cache_logger.removeHandler(handler)
            
            # Display logs
            st.write("📋 **Pipeline Execution Log:**")
            display_execution_log(log_lines)
            
            status.update(label="✅ Processing complete!", state="complete")
        
        return results
        
    except Exception as e:
        st.error(f"❌ Error processing question: {e}")
        import traceback
        st.code(traceback.format_exc())
        return None


def render_evaluation_section():
    st.divider()
    st.subheader("📈 Evaluation & Comparison")
    if st.button("❌ Close Evaluation Section", key="close_eval_section"):
        st.session_state['open_eval'] = False
        st.rerun()

    plotting_available = True
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        import pandas as pd
    except Exception:
        plotting_available = False
        pd = None

    import statistics

    if not plotting_available:
        st.warning("Plotting libraries not available (matplotlib/seaborn/pandas).\nInstall them with `pip install matplotlib seaborn pandas` to enable plots.")

    eval_bases = [
        (Path("tests/evaluation_results"), "mschema"),
        (Path("tests/evaluation_results_toon"), "toon"),
    ]
    combos = set()
    for eval_base, schema_format in eval_bases:
        if not eval_base.exists():
            continue
        for entry in eval_base.iterdir():
            if entry.is_dir() and '_' in entry.name:
                parts = entry.name.split('_', 1)
                if len(parts) == 2 and list((entry / "evaluation").glob("*.json")):
                    combos.add((parts[0], parts[1], schema_format))

    if not combos:
        st.info("No evaluation files found in tests/evaluation_results or tests/evaluation_results_toon.")
        return

    available_kgs = sorted({k for k, _, _ in combos})
    available_models = sorted({m for _, m, _ in combos})

    selected_kgs = st.multiselect("Select KGs to include", available_kgs, default=available_kgs, key="eval_selected_kgs")
    selected_models = st.multiselect("Select Models to include", available_models, default=available_models, key="eval_selected_models")
    selected_schema_format = st.selectbox("Schema format", ["All", "mschema", "toon"], index=0, key="eval_schema_format")
    selected_embedding_mode = st.selectbox(
        "Embedding mode",
        ["All", "llm", "decoded_json", "direct_toon"],
        index=0,
        key="eval_embedding_mode",
    )
    examples_filter_choice = st.selectbox("Filter by schema examples", ["All", "With examples", "Without examples"], index=0, key="eval_examples_filter")

    filtered_combos = sorted([
        (kg, model, schema_format)
        for kg, model, schema_format in combos
        if kg in selected_kgs and model in selected_models and (selected_schema_format == "All" or schema_format == selected_schema_format)
    ])
    combo_label_to_pair = {
        f"{kg} | {model} | {schema_format}": (kg, model, schema_format)
        for kg, model, schema_format in filtered_combos
    }
    if filtered_combos:
        st.caption(f"Active KG+Model pairs: {', '.join([f'{kg} | {model} | {schema_format}' for kg, model, schema_format in filtered_combos])}")
    else:
        st.caption("Active KG+Model pairs: none")

    examples_filter = None
    if examples_filter_choice == "With examples":
        examples_filter = True
    elif examples_filter_choice == "Without examples":
        examples_filter = False

    embedding_filter = None if selected_embedding_mode == "All" else selected_embedding_mode

    def load_eval_files(kg, model, schema_format):
        eval_base = Path("tests/evaluation_results_toon") if schema_format == "toon" else Path("tests/evaluation_results")
        folder = eval_base / f"{kg}_{model}" / "evaluation"
        items = []
        if not folder.exists():
            return items
        for jf in folder.glob('*.json'):
            try:
                text = jf.read_text(encoding='utf-8')
                if text.startswith('\ufeff'):
                    text = text.lstrip('\ufeff')
                record = json.loads(text)
                record.setdefault("schema_format", schema_format)
                items.append(record)
            except Exception:
                continue
        return items

    def query_exec_metrics(eval_data):
        q = eval_data.get('stages', {}).get('query_execution', {})
        if not isinstance(q, dict):
            return None
        f1 = q.get('f1')
        precision = q.get('precision')
        recall = q.get('recall')
        accuracy = q.get('accuracy')
        if f1 is None:
            f1 = q.get('set_f1')
        if precision is None:
            precision = q.get('set_precision')
        if recall is None:
            recall = q.get('set_recall')
        if f1 is None and q.get('macro_average'):
            f1 = q.get('macro_average', {}).get('f1')
        if precision is None and q.get('macro_average'):
            precision = q.get('macro_average', {}).get('precision')
        if recall is None and q.get('macro_average'):
            recall = q.get('macro_average', {}).get('recall')
        if all(v is None for v in [f1, precision, recall, accuracy]):
            return None
        return {
            'f1': float(f1) if f1 is not None else None,
            'precision': float(precision) if precision is not None else None,
            'recall': float(recall) if recall is not None else None,
            'accuracy': float(accuracy) if accuracy is not None else None,
        }

    def average_metric(metric_rows, key):
        vals = [r[key] for r in metric_rows if r.get(key) is not None]
        return round(statistics.mean(vals), 4) if vals else None

    def normalized_examples_flag(eval_data):
        candidates = [
            eval_data.get('with_examples'),
            eval_data.get('metadata', {}).get('with_examples'),
            eval_data.get('config', {}).get('pipeline', {}).get('schema', {}).get('query_generation', {}).get('include_examples'),
        ]
        for raw in candidates:
            if isinstance(raw, bool):
                return raw
            if isinstance(raw, (int, float)):
                return bool(raw)
            if isinstance(raw, str):
                txt = raw.strip().lower()
                if txt in {"true", "1", "yes", "y", "with", "with examples", "with_examples"}:
                    return True
                if txt in {"false", "0", "no", "n", "without", "without examples", "without_examples"}:
                    return False
        return None

    def normalized_embedding_mode(eval_data):
        direct_candidates = [
            eval_data.get("embedding_mode"),
            eval_data.get("metadata", {}).get("embedding_mode"),
        ]
        for raw in direct_candidates:
            if raw is None:
                continue
            txt = str(raw).strip().lower()
            if txt in {"llm", "decoded_json", "direct_toon"}:
                return txt

        extraction_candidates = [
            eval_data.get("extraction_method"),
            eval_data.get("metadata", {}).get("extraction_method"),
            eval_data.get("config", {}).get("pipeline", {}).get("extraction", {}).get("method"),
        ]
        extraction_method_value = None
        for raw in extraction_candidates:
            if raw is None:
                continue
            txt = str(raw).strip().lower()
            if txt in {"llm", "embedding"}:
                extraction_method_value = txt
                break

        if extraction_method_value == "llm":
            return "llm"

        if extraction_method_value == "embedding":
            direct_flag_candidates = [
                eval_data.get("config", {}).get("pipeline", {}).get("extraction", {}).get("embedding", {}).get("toon_direct_mode"),
                eval_data.get("metadata", {}).get("toon_direct_mode"),
            ]
            for raw in direct_flag_candidates:
                if isinstance(raw, bool):
                    return "direct_toon" if raw else "decoded_json"
                if isinstance(raw, (int, float)):
                    return "direct_toon" if bool(raw) else "decoded_json"
                if isinstance(raw, str):
                    txt = raw.strip().lower()
                    if txt in {"true", "1", "yes", "y"}:
                        return "direct_toon"
                    if txt in {"false", "0", "no", "n"}:
                        return "decoded_json"
            return "decoded_json"

        return "unknown"

    st.markdown("**Overall KG/Model Comparison**")
    enable_questionwise_compare = st.checkbox(
        "Enable question-wise comparison (optional)",
        value=False,
        key="eval_enable_questionwise_compare"
    )
    selected_pair_labels = []
    compare_common_only = True
    use_examples_filter_for_pair_compare = False
    if enable_questionwise_compare:
        selected_pair_labels = st.multiselect(
            "Select KG+Model pairs for same-question comparison",
            options=list(combo_label_to_pair.keys()),
            default=list(combo_label_to_pair.keys()),
            key="eval_selected_pairs"
        )
        compare_common_only = st.checkbox(
            "Compare only questions common to all selected pairs",
            value=True,
            key="eval_compare_common_only"
        )
        use_examples_filter_for_pair_compare = st.checkbox(
            "Apply examples filter to same-question comparison",
            value=False,
            key="eval_compare_apply_examples_filter"
        )

    def normalize_question_key(question_text):
        if question_text is None:
            return None
        text = str(question_text).strip()
        if not text:
            return None
        return " ".join(text.split()).lower()

    def parse_eval_timestamp(eval_data):
        raw = eval_data.get('timestamp')
        if not raw:
            return datetime.min
        try:
            return datetime.fromisoformat(str(raw).replace('Z', '+00:00')).replace(tzinfo=None)
        except Exception:
            return datetime.min

    valid_pipeline_stages = {
        'class_extraction',
        'property_extraction',
        'missing_id_extraction',
        'query_execution',
    }

    if st.button("🔍 Run Overall KG/Model Comparison", use_container_width=True):
        rows = []
        examples_compare_rows = []
        stage_f1_rows = []
        total_eval_files_loaded = 0
        total_questions_with_query_metrics = 0
        total_questions_considered = 0
        included_question_keys = set()
        included_question_text_by_key = {}
        question_trace_rows = []
        evals_by_combo = {}

        def latest_timestamp_text(pool_entries):
            if not pool_entries:
                return None
            latest_ts = max((entry.get('timestamp', datetime.min) for entry in pool_entries), default=datetime.min)
            if latest_ts == datetime.min:
                return None
            return latest_ts.strftime("%Y-%m-%d %H:%M:%S")

        for kg, model, schema_format in filtered_combos:
            evals = load_eval_files(kg, model, schema_format)
            if not evals:
                continue
            evals_by_combo[(kg, model, schema_format)] = evals
            total_eval_files_loaded += len(evals)

            embedding_modes = ["llm", "decoded_json", "direct_toon", "unknown"]
            mode_pool_maps = {
                "With examples": {mode: {} for mode in embedding_modes},
                "Without examples": {mode: {} for mode in embedding_modes},
            }
            mode_record_counts = {
                "With examples": {mode: 0 for mode in embedding_modes},
                "Without examples": {mode: 0 for mode in embedding_modes},
            }
            mode_duplicates_dropped = {
                "With examples": {mode: 0 for mode in embedding_modes},
                "Without examples": {mode: 0 for mode in embedding_modes},
            }
            for data in evals:
                flag = normalized_examples_flag(data)
                embedding_mode = normalized_embedding_mode(data)
                qm = query_exec_metrics(data)
                question_text = data.get('question') or data.get('metadata', {}).get('question')
                question_key = normalize_question_key(question_text)
                ts = parse_eval_timestamp(data)
                mode_label = 'With examples' if flag is True else ('Without examples' if flag is False else 'Unknown')
                has_qm = qm is not None
                included_in_overall = False
                exclude_reason = ""

                if embedding_filter is not None and embedding_mode != embedding_filter:
                    question_trace_rows.append({
                        'KG': kg,
                        'Model': model,
                        'Schema Format': schema_format,
                        'Question': question_text or "<missing question>",
                        'Mode': mode_label,
                        'Embedding Mode': embedding_mode,
                        'has_query_execution_metrics': has_qm,
                        'included_in_overall': False,
                        'exclude_reason': "Excluded by embedding mode filter",
                    })
                    continue

                if not qm:
                    exclude_reason = "Missing query_execution metrics"
                    question_trace_rows.append({
                        'KG': kg,
                        'Model': model,
                        'Schema Format': schema_format,
                        'Question': question_text or "<missing question>",
                        'Mode': mode_label,
                        'Embedding Mode': embedding_mode,
                        'has_query_execution_metrics': has_qm,
                        'included_in_overall': included_in_overall,
                        'exclude_reason': exclude_reason,
                    })
                    continue

                total_questions_with_query_metrics += 1
                if flag is True:
                    mode_record_counts["With examples"][embedding_mode] += 1
                    if question_key:
                        existing = mode_pool_maps["With examples"][embedding_mode].get(question_key)
                        if existing is None or ts >= existing['timestamp']:
                            if existing is not None:
                                mode_duplicates_dropped["With examples"][embedding_mode] += 1
                            mode_pool_maps["With examples"][embedding_mode][question_key] = {
                                'question': question_text or question_key,
                                'question_key': question_key,
                                'timestamp': ts,
                                'metrics': qm,
                            }
                        else:
                            mode_duplicates_dropped["With examples"][embedding_mode] += 1
                    else:
                        exclude_reason = "Missing question text"
                    if examples_filter_choice in ["All", "With examples"]:
                        included_in_overall = bool(question_key)
                elif flag is False:
                    mode_record_counts["Without examples"][embedding_mode] += 1
                    if question_key:
                        existing = mode_pool_maps["Without examples"][embedding_mode].get(question_key)
                        if existing is None or ts >= existing['timestamp']:
                            if existing is not None:
                                mode_duplicates_dropped["Without examples"][embedding_mode] += 1
                            mode_pool_maps["Without examples"][embedding_mode][question_key] = {
                                'question': question_text or question_key,
                                'question_key': question_key,
                                'timestamp': ts,
                                'metrics': qm,
                            }
                        else:
                            mode_duplicates_dropped["Without examples"][embedding_mode] += 1
                    else:
                        exclude_reason = "Missing question text"
                    if examples_filter_choice in ["All", "Without examples"]:
                        included_in_overall = bool(question_key)
                else:
                    exclude_reason = "Unknown with_examples flag"

                if included_in_overall:
                    included_question_keys.add(question_key)
                    included_question_text_by_key[question_key] = question_text or question_key
                else:
                    if not exclude_reason:
                        exclude_reason = "Excluded by examples filter"

                question_trace_rows.append({
                    'KG': kg,
                    'Model': model,
                    'Schema Format': schema_format,
                    'Question': question_text or "<missing question>",
                    'Mode': mode_label,
                    'Embedding Mode': embedding_mode,
                    'has_query_execution_metrics': has_qm,
                    'included_in_overall': included_in_overall,
                    'exclude_reason': exclude_reason if not included_in_overall else "",
                })

            selected_embedding_modes = [embedding_filter] if embedding_filter is not None else embedding_modes

            if examples_filter_choice == "All":
                for mode_name in ["With examples", "Without examples"]:
                    for emb_mode in selected_embedding_modes:
                        pool_entries = list(mode_pool_maps[mode_name][emb_mode].values())
                        pool = [entry['metrics'] for entry in pool_entries]
                        if not pool:
                            continue
                        for entry in pool_entries:
                            key = entry.get('question_key')
                            if key:
                                included_question_keys.add(key)
                                included_question_text_by_key[key] = entry.get('question') or key
                        rows.append({
                            'KG': kg,
                            'Model': model,
                            'Mode': mode_name,
                            'Embedding Mode': emb_mode,
                            'evaluations': len(pool),
                            'latest_eval_timestamp': latest_timestamp_text(pool_entries),
                            'records_loaded': mode_record_counts[mode_name][emb_mode],
                            'duplicates_dropped': mode_duplicates_dropped[mode_name][emb_mode],
                            'final_f1': average_metric(pool, 'f1'),
                            'final_precision': average_metric(pool, 'precision'),
                            'final_recall': average_metric(pool, 'recall'),
                            'final_accuracy': average_metric(pool, 'accuracy'),
                        })
                        total_questions_considered += len(pool)
            else:
                mode_name = "With examples" if examples_filter is True else "Without examples"
                for emb_mode in selected_embedding_modes:
                    pool_entries = list(mode_pool_maps.get(mode_name, {}).get(emb_mode, {}).values())
                    pool = [entry['metrics'] for entry in pool_entries]
                    if pool:
                        for entry in pool_entries:
                            key = entry.get('question_key')
                            if key:
                                included_question_keys.add(key)
                                included_question_text_by_key[key] = entry.get('question') or key
                        rows.append({
                            'KG': kg,
                            'Model': model,
                            'Mode': mode_name,
                            'Embedding Mode': emb_mode,
                            'evaluations': len(pool),
                            'latest_eval_timestamp': latest_timestamp_text(pool_entries),
                            'records_loaded': mode_record_counts[mode_name][emb_mode],
                            'duplicates_dropped': mode_duplicates_dropped[mode_name][emb_mode],
                            'final_f1': average_metric(pool, 'f1'),
                            'final_precision': average_metric(pool, 'precision'),
                            'final_recall': average_metric(pool, 'recall'),
                            'final_accuracy': average_metric(pool, 'accuracy'),
                        })
                        total_questions_considered += len(pool)

            def append_stage_rows_for_mode(mode_name, mode_flag, emb_mode):
                stage_values = {}
                latest_stage_eval_by_question = {}

                for data in evals:
                    flag = normalized_examples_flag(data)
                    embedding_mode = normalized_embedding_mode(data)
                    if flag != mode_flag:
                        continue
                    if embedding_mode != emb_mode:
                        continue

                    question_text = data.get('question') or data.get('metadata', {}).get('question')
                    question_key = normalize_question_key(question_text)
                    if not question_key:
                        continue

                    ts = parse_eval_timestamp(data)
                    existing = latest_stage_eval_by_question.get(question_key)
                    if existing is None or ts >= existing['timestamp']:
                        latest_stage_eval_by_question[question_key] = {
                            'timestamp': ts,
                            'stages': data.get('stages', {})
                        }

                for entry in latest_stage_eval_by_question.values():
                    for stage_name, stage_data in entry.get('stages', {}).items():
                        if stage_name not in valid_pipeline_stages:
                            continue
                        if not isinstance(stage_data, dict):
                            continue
                        stage_f1 = stage_data.get('f1')
                        stage_precision = stage_data.get('precision')
                        stage_recall = stage_data.get('recall')
                        if stage_f1 is None:
                            stage_f1 = stage_data.get('set_f1')
                        if stage_precision is None:
                            stage_precision = stage_data.get('set_precision')
                        if stage_recall is None:
                            stage_recall = stage_data.get('set_recall')
                        if stage_f1 is None and stage_data.get('macro_average'):
                            stage_f1 = stage_data.get('macro_average', {}).get('f1')
                            stage_precision = stage_precision if stage_precision is not None else stage_data.get('macro_average', {}).get('precision')
                            stage_recall = stage_recall if stage_recall is not None else stage_data.get('macro_average', {}).get('recall')
                        if stage_f1 is not None:
                            stage_values.setdefault(stage_name, {'f1': [], 'precision': [], 'recall': []})
                            stage_values[stage_name]['f1'].append(float(stage_f1))
                            if stage_precision is not None:
                                stage_values[stage_name]['precision'].append(float(stage_precision))
                            if stage_recall is not None:
                                stage_values[stage_name]['recall'].append(float(stage_recall))

                for stage_name, metrics in stage_values.items():
                    f1_vals = metrics.get('f1', [])
                    precision_vals = metrics.get('precision', [])
                    recall_vals = metrics.get('recall', [])
                    stage_f1_rows.append({
                        'KG': kg,
                        'Model': model,
                        'Mode': mode_name,
                        'Embedding Mode': emb_mode,
                        'Stage': stage_name,
                        'evaluations': len(f1_vals),
                        'overall_f1': round(statistics.mean(f1_vals), 4) if f1_vals else None,
                        'std_f1': round(statistics.pstdev(f1_vals), 4) if len(f1_vals) > 1 else (0.0 if f1_vals else None),
                        'overall_precision': round(statistics.mean(precision_vals), 4) if precision_vals else None,
                        'overall_recall': round(statistics.mean(recall_vals), 4) if recall_vals else None,
                    })

            if examples_filter_choice == "All":
                for emb_mode in selected_embedding_modes:
                    append_stage_rows_for_mode("With examples", True, emb_mode)
                    append_stage_rows_for_mode("Without examples", False, emb_mode)
            elif examples_filter is True:
                for emb_mode in selected_embedding_modes:
                    append_stage_rows_for_mode("With examples", True, emb_mode)
            elif examples_filter is False:
                for emb_mode in selected_embedding_modes:
                    append_stage_rows_for_mode("Without examples", False, emb_mode)

            for mode_name in ["With examples", "Without examples"]:
                for emb_mode in selected_embedding_modes:
                    mode_rows = [entry['metrics'] for entry in mode_pool_maps[mode_name][emb_mode].values()]
                    if mode_rows:
                        examples_compare_rows.append({
                            'KG': kg,
                            'Model': model,
                            'Mode': mode_name,
                            'Embedding Mode': emb_mode,
                            'evaluations': len(mode_rows),
                            'final_f1': average_metric(mode_rows, 'f1'),
                            'final_precision': average_metric(mode_rows, 'precision'),
                            'final_recall': average_metric(mode_rows, 'recall'),
                            'final_accuracy': average_metric(mode_rows, 'accuracy'),
                        })

        total_questions_considered = len(included_question_keys)

        if not rows:
            st.warning("No query_execution evaluation metrics found for selected KG/model/filter.")
            st.caption(
                f"Loaded {total_eval_files_loaded} evaluation files; "
                f"{total_questions_with_query_metrics} had query_execution metrics; "
                f"0 matched the selected examples filter."
            )
            if question_trace_rows and plotting_available:
                question_trace_df = pd.DataFrame(question_trace_rows)
                st.markdown("**Question Coverage (Overall Comparison)**")
                st.caption("These are question records discovered and why each one was included/excluded.")
                st.dataframe(question_trace_df.fillna('N/A'))
        else:
            df = pd.DataFrame(rows)
            st.subheader("Overall Final Query Execution Metrics (per KG+Model)")
            st.caption(
                f"Questions considered in final evaluation: {total_questions_considered} "
                f"(from {total_questions_with_query_metrics} records with query_execution metrics, "
                f"loaded from {total_eval_files_loaded} evaluation files)."
            )
            st.dataframe(df.fillna('N/A'))

            # Export controls for aggregated metrics
            try:
                csv_buf = df.to_csv(index=False)
                json_buf = df.to_json(orient='records', force_ascii=False)

                col_exp1, col_exp2, col_exp3 = st.columns([1,1,1])
                with col_exp1:
                    st.download_button(
                        label="📥 Download aggregated (CSV)",
                        data=csv_buf,
                        file_name=f"aggregated_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                    )
                with col_exp2:
                    st.download_button(
                        label="📥 Download aggregated (JSON)",
                        data=json_buf,
                        file_name=f"aggregated_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                    )
                with col_exp3:
                    if st.button("💾 Save aggregated to disk", key="save_aggregated_to_disk"):
                        try:
                            out_base = st.session_state.config.get("output.evaluation_results_dir", "tests/evaluation_results") if st.session_state.get("config") else "tests/evaluation_results"
                            export_dir = os.path.join(out_base, "gui_exports")
                            os.makedirs(export_dir, exist_ok=True)
                            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                            csv_path = os.path.join(export_dir, f"aggregated_metrics_{ts}.csv")
                            json_path = os.path.join(export_dir, f"aggregated_metrics_{ts}.json")
                            with open(csv_path, 'w', encoding='utf-8') as f:
                                f.write(csv_buf)
                            with open(json_path, 'w', encoding='utf-8') as f:
                                f.write(json_buf)
                            st.success(f"Saved aggregated metrics to {export_dir}")
                            st.caption(f"Files: {os.path.basename(csv_path)}, {os.path.basename(json_path)}")
                        except Exception as e:
                            st.error(f"Failed to save aggregated metrics: {e}")
            except Exception:
                pass

            if question_trace_rows and plotting_available:
                question_trace_df = pd.DataFrame(question_trace_rows)
                st.markdown("**Question Coverage (Overall Comparison)**")
                st.caption("Use this table to verify which question records were included for the active filter.")
                st.dataframe(question_trace_df.fillna('N/A'))

            if plotting_available:
                plot_rows = []
                for _, r in df.iterrows():
                    combo = f"{r['KG']}\n{r['Model']}\n{r.get('Embedding Mode', 'unknown')}"
                    mode = r.get('Mode', 'N/A')
                    embedding_mode = r.get('Embedding Mode', 'unknown')
                    for metric in ['final_f1', 'final_precision', 'final_recall', 'final_accuracy']:
                        val = r.get(metric)
                        if val is not None:
                            plot_rows.append({
                                'combo': combo,
                                'mode': mode,
                                'embedding': embedding_mode,
                                'metric': metric.replace('final_', '').upper(),
                                'value': val
                            })

                p_df = pd.DataFrame(plot_rows)
                if not p_df.empty:
                    if examples_filter_choice == "All":
                        f1_df = p_df[p_df['metric'] == 'F1'].copy()
                        f1_df['hue_label'] = f1_df['mode'] + " | " + f1_df['embedding']
                        fig, ax = plt.subplots(figsize=(12, 6))
                        sns.barplot(data=f1_df, x='combo', y='value', hue='hue_label', ax=ax)
                        ax.set_ylabel('Final F1')
                        ax.set_xlabel('KG / Model')
                        ax.set_title('Final F1 Comparison: Examples + Embedding Mode')
                        st.pyplot(fig)
                    else:
                        fig, ax = plt.subplots(figsize=(12, 6))
                        if embedding_filter is None:
                            f1_df = p_df[p_df['metric'] == 'F1']
                            sns.barplot(data=f1_df, x='combo', y='value', hue='embedding', ax=ax)
                            ax.set_title('Final F1 Comparison by Embedding Mode')
                        else:
                            sns.barplot(data=p_df, x='combo', y='value', hue='metric', ax=ax)
                            ax.set_title('Final Query Execution Metrics Comparison')
                        ax.set_ylabel('Score')
                        ax.set_xlabel('KG / Model')
                        st.pyplot(fig)

            if stage_f1_rows and plotting_available:
                stage_df = pd.DataFrame(stage_f1_rows)
                st.subheader("Per-Step Overall Metrics (per KG+Model)")
                st.dataframe(stage_df.fillna('N/A'))

                stage_plot = stage_df.copy()
                stage_plot['combo'] = stage_plot['KG'] + "\n" + stage_plot['Model'] + "\n" + stage_plot['Embedding Mode']
                
                # Create subplots for Precision, Recall, and F1
                for metric_col, metric_name in [('overall_precision', 'Precision'), ('overall_recall', 'Recall'), ('overall_f1', 'F1')]:
                    if metric_col not in stage_plot.columns:
                        continue
                        
                    if examples_filter_choice == "All" and 'Mode' in stage_plot.columns:
                        for mode_name in ["With examples", "Without examples"]:
                            mode_plot = stage_plot[stage_plot['Mode'] == mode_name]
                            if mode_plot.empty:
                                continue
                            fig_steps, ax_steps = plt.subplots(figsize=(12, 6))
                            sns.barplot(data=mode_plot, x='combo', y=metric_col, hue='Stage', ax=ax_steps)
                            ax_steps.set_ylabel(f'Overall {metric_name}')
                            ax_steps.set_xlabel('KG / Model')
                            ax_steps.set_title(f'Per-Step Overall {metric_name} Comparison ({mode_name})')
                            st.pyplot(fig_steps)
                    else:
                        fig_steps, ax_steps = plt.subplots(figsize=(12, 6))
                        sns.barplot(data=stage_plot, x='combo', y=metric_col, hue='Stage', ax=ax_steps)
                        ax_steps.set_ylabel(f'Overall {metric_name}')
                        ax_steps.set_xlabel('KG / Model')
                        ax_steps.set_title(f'Per-Step Overall {metric_name} Comparison')
                        st.pyplot(fig_steps)

            if examples_compare_rows and examples_filter_choice != "All" and plotting_available:
                cmp_df = pd.DataFrame(examples_compare_rows)
                st.subheader("With vs Without Examples (Final Query Execution)")
                st.dataframe(cmp_df.fillna('N/A'))

                cmp_plot = cmp_df.copy()
                cmp_plot['combo'] = cmp_plot['KG'] + "\n" + cmp_plot['Model'] + "\n" + cmp_plot['Embedding Mode']
                fig2, ax2 = plt.subplots(figsize=(12, 6))
                sns.barplot(data=cmp_plot, x='combo', y='final_f1', hue='Mode', ax=ax2)
                ax2.set_ylabel('Final F1')
                ax2.set_xlabel('KG / Model')
                ax2.set_title('With vs Without Examples - Final F1')
                st.pyplot(fig2)

        selected_pairs = [combo_label_to_pair[label] for label in selected_pair_labels if label in combo_label_to_pair]
        if enable_questionwise_compare and len(selected_pairs) >= 1 and plotting_available:
            per_pair_questions = {}
            for kg, model, schema_format in selected_pairs:
                evals = load_eval_files(kg, model, schema_format)
                question_map = {}

                for data in evals:
                    flag = normalized_examples_flag(data)
                    emb_mode = normalized_embedding_mode(data)
                    if use_examples_filter_for_pair_compare and examples_filter is not None and flag != examples_filter:
                        continue
                    if embedding_filter is not None and emb_mode != embedding_filter:
                        continue

                    qm = query_exec_metrics(data)
                    if not qm:
                        continue

                    question_text = data.get('question') or data.get('metadata', {}).get('question')
                    q_key = normalize_question_key(question_text)
                    if not q_key:
                        continue

                    ts = parse_eval_timestamp(data)
                    existing = question_map.get(q_key)
                    if existing is None or ts >= existing['timestamp']:
                        question_map[q_key] = {
                            'question': question_text,
                            'timestamp': ts,
                            'mode': 'With examples' if flag is True else ('Without examples' if flag is False else 'Unknown'),
                            'embedding_mode': emb_mode,
                            'metrics': qm
                        }

                per_pair_questions[(kg, model, schema_format)] = question_map

            question_key_sets = [set(v.keys()) for v in per_pair_questions.values() if v]
            question_keys = set()
            if question_key_sets:
                if compare_common_only:
                    question_keys = set.intersection(*question_key_sets)
                else:
                    question_keys = set.union(*question_key_sets)

            st.subheader("Same-Question Comparison Across Selected KG+Model Pairs")
            if not question_keys:
                st.info("No overlapping questions found for the selected pairs and filter. Try disabling common-only mode or changing the examples filter.")
            else:
                question_rows = []
                for q_key in sorted(question_keys):
                    for kg, model, schema_format in selected_pairs:
                        entry = per_pair_questions.get((kg, model, schema_format), {}).get(q_key)
                        if not entry:
                            if compare_common_only:
                                continue
                            question_rows.append({
                                'Question': q_key,
                                'Pair': f"{kg} | {model} | {schema_format}",
                                'KG': kg,
                                'Model': model,
                                'Schema Format': schema_format,
                                'Mode': 'N/A',
                                'Embedding Mode': 'N/A',
                                'final_f1': None,
                                'final_precision': None,
                                'final_recall': None,
                                'final_accuracy': None,
                            })
                            continue

                        question_rows.append({
                            'Question': entry['question'],
                            'Pair': f"{kg} | {model} | {schema_format}",
                            'KG': kg,
                            'Model': model,
                            'Schema Format': schema_format,
                            'Mode': entry['mode'],
                            'Embedding Mode': entry.get('embedding_mode', 'unknown'),
                            'final_f1': entry['metrics'].get('f1'),
                            'final_precision': entry['metrics'].get('precision'),
                            'final_recall': entry['metrics'].get('recall'),
                            'final_accuracy': entry['metrics'].get('accuracy'),
                        })

                question_df = pd.DataFrame(question_rows)
                compared_questions_count = len(question_keys)
                st.caption(
                    f"Compared {compared_questions_count} questions across {len(selected_pairs)} selected pairs "
                    f"({', '.join(selected_pair_labels)})."
                )
                st.dataframe(question_df.fillna('N/A'))

                summary_df = question_df.groupby(['Pair', 'KG', 'Model', 'Schema Format', 'Embedding Mode'], as_index=False).agg({
                    'final_f1': 'mean',
                    'final_precision': 'mean',
                    'final_recall': 'mean',
                    'final_accuracy': 'mean'
                })
                summary_df['questions_compared'] = compared_questions_count
                st.markdown("**Average on Same Questions**")
                st.dataframe(summary_df.fillna('N/A'))

                fig3, ax3 = plt.subplots(figsize=(12, 6))
                sns.barplot(data=summary_df, x='Pair', y='final_f1', ax=ax3)
                ax3.set_ylabel('Average Final F1')
                ax3.set_xlabel('KG | Model')
                ax3.set_title('Same-Question Comparison: Average Final F1 by Pair')
                ax3.tick_params(axis='x', rotation=20)
                st.pyplot(fig3)

                pivot_f1 = question_df.pivot(index='Question', columns='Pair', values='final_f1')
                if not pivot_f1.empty:
                    fig4, ax4 = plt.subplots(figsize=(12, min(14, 0.45 * max(1, len(pivot_f1)) + 2)))
                    sns.heatmap(pivot_f1, cmap='YlGnBu', annot=False, cbar=True, ax=ax4)
                    ax4.set_title('Final F1 Heatmap by Question and Pair')
                    ax4.set_xlabel('KG | Model')
                    ax4.set_ylabel('Question')
                    st.pyplot(fig4)
        elif enable_questionwise_compare:
            st.info("Select at least one KG+Model pair to run same-question comparison.")


def main():
    """Main GUI application."""
    st.set_page_config(
        page_title="NL2SPARQL",
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    init_session_state()
    
    # Handle pending question from example button clicks
    # Set it BEFORE any widgets are created to avoid extra reruns
    if "pending_question" not in st.session_state:
        st.session_state.pending_question = None
    if "question_input" not in st.session_state:
        st.session_state.question_input = ""
        
    if st.session_state.pending_question:
        # Only set if different to avoid unnecessary rerun
        if st.session_state.question_input != st.session_state.pending_question:
            st.session_state.question_input = st.session_state.pending_question
        st.session_state.pending_question = None
        st.rerun()
    
    # Main header
    col_title, col_subtitle = st.columns([0.8, 0.2])
    with col_title:
        st.title("🔍 NL2SPARQL - Natural Language to SPARQL Converter")
    
    st.markdown(
        "Convert natural language questions into structured SPARQL queries "
        "using AI-powered schema understanding and reasoning."
    )
    
    # Render sidebar
    render_sidebar()

    cache_status = st.session_state.get("selected_schema_cache_status")
    if cache_status:
        schema_name = cache_status.get("schema_name", "N/A")
        class_cached = "yes" if cache_status.get("class_cached") else "no"
        prop_cached = "yes" if cache_status.get("property_cached") else "no"
        st.caption(
            f"Selected schema cache status ({schema_name}): class cached={class_cached}, property cached={prop_cached}"
        )
    
    st.divider()
    
    # Main chat interface
    st.subheader("💬 Ask Your Question")
    
    # Question input (managed by session state via key)
    question = st.text_area(
        "Enter your natural language question:",
        placeholder="Example: Find all companies founded before 2010 with more than 100 employees",
        height=100,
        key="question_input",
    )
    
    col_ask, col_clear = st.columns([0.8, 0.2])

    with col_ask:
        # Place preview before the main processing button and give stable keys
        preview_route = st.button("🔍Routing", key="preview_routing_btn", use_container_width=True)
        ask_button = st.button("🚀 Process Question", key="process_question_btn", use_container_width=True, type="primary")
    
    def clear_question():
        st.session_state.question_input = ""
    
    with col_clear:
        st.button("🗑️ Clear", use_container_width=True, on_click=clear_question)
    
    # Preview routing if requested
    if preview_route:
        # Lightweight routing preview using pipeline's router
        if not question.strip():
            st.warning("Enter a question to preview routing")
        else:
            try:
                # Ensure pipeline is initialized
                if st.session_state.pipeline is None:
                    config_path = Path("config.yaml")
                    if not config_path.exists():
                        config_path = Path(__file__).parent.parent / "config.yaml"
                    st.session_state.pipeline = NL2SPARQLPipeline(str(config_path))
                    st.session_state.config = st.session_state.pipeline.config

                # Initialize router LLM if needed
                from nl2sparql.query_router import QueryRouter
                if st.session_state.pipeline.llm_reasoning is None:
                    llm_inst, _ = st.session_state.pipeline._init_stage_llm(
                        "query_routing",
                        "Routing (preview)",
                    )
                    st.session_state.pipeline.llm_reasoning = llm_inst

                router_llm = st.session_state.pipeline.llm_reasoning
                # Wrap Mistral-style callable into wrapper used elsewhere
                from nl2sparql.llm_interface import MistralLLMWrapper
                router_llm_wrapped = MistralLLMWrapper(router_llm) if hasattr(router_llm, '__call__') else router_llm
                router = QueryRouter(router_llm_wrapped)
                # Build a small schema summary
                try:
                    schema_path = st.session_state.schema_path
                    with open(schema_path, 'r', encoding='utf-8') as sf:
                        import json as _json
                        if str(schema_path).lower().endswith('.toon'):
                            from nl2sparql.toon_formatter import TOONFormatter as _TF
                            sch = _TF.decode(sf.read())
                        else:
                            sch = _json.load(sf)
                    cls = list((sch or {}).get('classes', {}).keys())
                    schema_summary = f"Classes: {len(cls)} | Samples: {', '.join(cls[:6])}"
                except Exception:
                    schema_summary = "(schema summary unavailable)"

                decision = router.route(question, schema_summary=schema_summary)
                # Display routing preview in human-readable form
                route = decision.get('route', 'sparql')
                conf = decision.get('confidence')
                reason_text = decision.get('reason', '')

                route_label = {
                    'sparql': 'SPARQL retrieval',
                    'analytical': 'Analytical (ML/statistics)',
                    'hybrid': 'Hybrid (retrieval + analysis)'
                }.get(route, route)

                st.markdown("---")
                st.subheader("🧭 Routing Decision")
                st.write(f"**Suggested Route:** {route_label}")
                if conf is not None:
                    try:
                        st.write(f"**Confidence:** {float(conf):.2f}")
                    except Exception:
                        st.write(f"**Confidence:** {conf}")

                # Prefer a short, natural-language reasoning summary for the user
                natural_reason = reason_text
                # If the router returned an opaque JSON or raw text, keep it concise
                if isinstance(natural_reason, str) and len(natural_reason) > 400:
                    natural_reason = natural_reason[:400] + '...'

                st.write("**Reasoning:**")
                st.info(natural_reason or "(no reason provided)")
                # Show raw LLM output in an expander for debugging
                with st.expander("Raw router response"):
                    st.code(decision.get('raw_response', ''), language='')
                st.markdown("---")
            except Exception as e:
                st.error(f"Routing preview failed: {e}")

    # Process question if requested
    if ask_button and question.strip():
        st.session_state.is_processing = True
        
        results = process_question(question)
        
        if results:
            st.divider()
            st.subheader("📊 Pipeline Results")

            # Display all results based on toggles
            display_stage_results(results, st.session_state.show_prompts)

            # Save to history
            st.session_state.messages.append({
                "question": question,
                "timestamp": datetime.now().isoformat(),
                "results": results
            })

            # Phase 2: exercise the same /recommend contract the standalone
            # recommender API exposes, so this harness stays a valid dev/test
            # path for it (docs/THESIS_PROJECT_PLAN.md SS7 Phase 2). Candidate
            # generation is Phase 4 -- suggestions are empty until then.
            if RecommendRequest is not None and handle_recommend is not None:
                try:
                    query_results = results.get("query_results") or {}
                    bindings = (query_results.get("results", {}) or {}).get("bindings", [])
                    sparql_query = results.get("sparql_query")
                    recommend_response = handle_recommend(RecommendRequest(
                        user_id=st.session_state.user_id,
                        domain=st.session_state.get("active_domain") or "unknown",
                        query_text=question,
                        generated_sparql=sparql_query if isinstance(sparql_query, str) else None,
                        result_summary={"row_count": len(bindings)} if bindings else None,
                    ))
                    st.divider()
                    st.subheader("💡 Suggested Follow-up Queries")
                    if recommend_response.suggestions:
                        for s in recommend_response.suggestions:
                            st.write(f"- {s}")
                    else:
                        st.caption(
                            "(No suggestions -- either no candidates survived generation/validation, "
                            "or GEMINI_API_KEY in .env is still the placeholder value. This query was logged either way.)"
                        )
                except Exception as e:
                    st.caption(f"(Recommender call skipped: {e})")
        
        st.session_state.is_processing = False
    
    # Example questions (shown when no questions asked yet)
    if not st.session_state.messages:
        st.divider()
        st.subheader("💡 Example Questions")
        
        examples_by_domain = {
            "movie": [
                "What movies have the genre Action?",
                "Show me all movies with an IMDB rating above 8",
                "What movies were produced in the United States?",
            ],
            "tourism": [
                "Churches in Verona",
                "Roman Churches in Verona",
                "Show me all art categories",
            ],
            "copypu": [
                "What is the longitude of the port with the ID 'USJNU'?",
                "Show me all airports in the database",
                "What are the properties of maritime ports?",
            ],
        }
        active_domain = st.session_state.get("active_domain")
        examples = examples_by_domain.get(active_domain, examples_by_domain["copypu"])
        
        def set_pending_question(q):
            """Callback to set pending question."""
            st.session_state.pending_question = q
        
        cols = st.columns(len(examples))
        for col, example in zip(cols, examples):
            with col:
                st.button(example, use_container_width=True, 
                         on_click=set_pending_question, args=(example,),
                         key=f"example_{examples.index(example)}")
    
    # History section
    if st.session_state.messages:
        st.divider()
        with st.expander("📚 Question History", expanded=False):
            for i, msg in enumerate(reversed(st.session_state.messages), 1):
                with st.container(border=True):
                    st.markdown(f"**Question {len(st.session_state.messages) - i + 1}:** {msg['question']}")
                    st.caption(f"Time: {msg['timestamp']}")
                    
                    if st.button(f"View Details", key=f"history_{i}"):
                        st.write(msg['results']['intermediate'])

    # Keep evaluation visible until explicitly closed
    if st.session_state.get("open_eval"):
        try:
            render_evaluation_section()
        except Exception as e:
            st.error(f"Failed to render Evaluation section: {e}")


if __name__ == "__main__":
    main()