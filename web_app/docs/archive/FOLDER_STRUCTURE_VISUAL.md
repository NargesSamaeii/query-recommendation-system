# Evaluation Folder & Data Flow Visualization

## 📂 Complete Folder Structure

```
nl2sparql/
│
├── 📄 config.yaml                    ← EDIT THIS to select KG and Model
│
├── 🐍 Pipeline Scripts
│   ├── pipeline.py                   ← Main pipeline (runs auto-evaluation)
│   ├── gui_v2.py                     ← GUI interface
│   ├── run_query.py                  ← CLI interface
│   └── ...
│
├── 📊 Analysis Scripts
│   ├── organized_evaluation.py        ← Generate text comparison reports
│   ├── generate_comparison_plots.py   ← Create visualization PNG files
│   ├── show_evaluation_structure.py   ← Display folder status
│   └── results_organizer.py           ← Auto-organize results
│
├── 📚 Knowledge Graphs
│   └── data/input/
│       ├── copypu.ttl                ← Your main RDF/TTL file
│       └── dbpedia.ttl               ← Optional: Add more KGs
│
└── 📈 EVALUATION RESULTS (Auto-created)
    │
    ├── copypu_gemini/                ← KG_Model (Gemini on Copypu)
    │   ├── ground_truth/             ← Questions + correct answers
    │   │   ├── gt_q001.json          ← Q&A pair 1
    │   │   ├── gt_q002.json          ← Q&A pair 2
    │   │   └── ... (50+ JSON files)
    │   │
    │   ├── results/                  ← Query execution results
    │   │   ├── result_20260225_101530.json
    │   │   ├── result_20260225_101545.json
    │   │   └── ... (50+ JSON files)
    │   │
    │   ├── evaluation/               ← Calculated metrics
    │   │   ├── eval_q001_eval.json   ← F1=0.85, P=0.82, R=0.88
    │   │   ├── eval_q002_eval.json   ← F1=0.65, P=0.63, R=0.68
    │   │   └── ... (50+ JSON files)
    │   │
    │   └── summary.json              ← Overall metrics
    │       {
    │         "kg": "copypu",
    │         "model": "gemini",
    │         "overall_f1": 0.3512,
    │         "evaluation_count": 50,
    │         "stages": {
    │           "class_extraction": {"f1": 0.85},
    │           "property_extraction": {"f1": 0.65},
    │           "missing_id_extraction": {"f1": 0.25},
    │           "query_execution": {"f1": 0.28}
    │         }
    │       }
    │
    ├── copypu_mistral/               ← KG_Model (Mistral on Copypu)
    │   ├── ground_truth/
    │   ├── results/
    │   ├── evaluation/
    │   └── summary.json
    │
    ├── dbpedia_gemini/               ← KG_Model (Gemini on DBpedia)
    │   ├── ground_truth/
    │   ├── results/
    │   ├── evaluation/
    │   └── summary.json
    │
    └── Visualization Outputs
        ├── comparison_kg_model_matrix.png      ← Heatmap
        ├── comparison_per_kg_models.png        ← Bar charts per KG
        ├── comparison_per_model_kgs.png        ← Bar charts per model
        └── comparison_stage_performance.png    ← 4-subplot grid
```

---

## 🔄 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                  USER CONFIGURATION PHASE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  config.yaml                                                     │
│  ┌──────────────────────┐     ┌──────────────────────┐          │
│  │ kg:                  │     │ llm:                 │          │
│  │   name: copypu       │────▶│   provider: gemini   │          │
│  │   source: local_rdf  │     │   model_name: ...    │          │
│  └──────────────────────┘     └──────────────────────┘          │
│          ▲                              ▲                        │
│          │                              │                        │
│   User edits when           User edits when                     │
│   switching KGs             switching models                    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│             QUESTION PROCESSING PHASE (User asks)               │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Question: "What are all products?"                             │
│          │                                                       │
│          ▼                                                       │
│  ┌──────────────────────────────────────────┐                  │
│  │ Stage 1: Class Extraction                │                  │
│  │ ML Model extracts: "Product"             │                  │
│  └──────────────────────────────────────────┘                  │
│          │                                                       │
│          ▼                                                       │
│  ┌──────────────────────────────────────────┐                  │
│  │ Stage 2: Property Extraction             │                  │
│  │ ML Model extracts: ["name", "id", ...]   │                  │
│  └──────────────────────────────────────────┘                  │
│          │                                                       │
│          ▼                                                       │
│  ┌──────────────────────────────────────────┐                  │
│  │ Stage 3: Missing ID Extraction           │                  │
│  │ LLM finds entity references              │                  │
│  └──────────────────────────────────────────┘                  │
│          │                                                       │
│          ▼                                                       │
│  ┌──────────────────────────────────────────┐                  │
│  │ Stage 4: SPARQL Generation               │                  │
│  │ LLM generates: SELECT ?product WHERE ... │                  │
│  └──────────────────────────────────────────┘                  │
│          │                                                       │
│          ▼                                                       │
│  ┌──────────────────────────────────────────┐                  │
│  │ Stage 5: Query Execution                 │                  │
│  │ Execute SPARQL on KG                     │                  │
│  │ Results: {...product1...}, {...prod2...}│                  │
│  └──────────────────────────────────────────┘                  │
│          │                                                       │
│          ▼                                                       │
│  results/ folder                                                │
│  └─ result_20260225_101530.json                                 │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│          AUTO-EVALUATION PHASE (Automatic)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  EvaluationResultsManager loads:                                │
│  ├─ Ground Truth (gt_q001.json):                                │
│  │  Expected: {"class": "Product", "properties": ["name", "id"]}│
│  │                                                               │
│  └─ Actual Results (result_*.json):                             │
│     Predicted: {"class": "Product", "properties": ["name"]}     │
│                                                                   │
│  Comparison (4 stages):                                         │
│  ┌─────────────────────────────────────────┐                   │
│  │ Stage 1 P: predicted_classes ⟺ expected │ ─▶ F1=0.85       │
│  │ Stage 2 P: predicted_props ⟺ expected   │ ─▶ F1=0.65       │
│  │ Stage 3: predicted_entities ⟺ expected  │ ─▶ F1=0.25       │
│  │ Stage 4: predicted_rows ⟺ expected_rows │ ─▶ F1=0.28       │
│  └─────────────────────────────────────────┘                   │
│                                                                   │
│  Average F1 = (0.85 + 0.65 + 0.25 + 0.28) / 4 = 0.3575        │
│                                                                   │
│  evaluation/ folder                                             │
│  └─ eval_q001_eval.json                                        │
│     {                                                            │
│       "kg": "copypu",         ◄─── AUTO-TAGGED                 │
│       "model": "gemini",      ◄─── AUTO-TAGGED                 │
│       "question": "...",                                        │
│       "overall": {"average_f1": 0.3575},                       │
│       "stages": {...}                                           │
│     }                                                            │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│        AUTO-ORGANIZATION PHASE (Automatic)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ResultsOrganizer reads:                                        │
│  ├─ kg = "copypu" (from eval file tag)                          │
│  ├─ model = "gemini" (from eval file tag)                       │
│  └─ Creates folder: evaluation_results/copypu_gemini/           │
│                                                                   │
│  Files moved:                                                    │
│  ├─ eval_q001_eval.json →                                       │
│  │  evaluation_results/copypu_gemini/evaluation/eval_q001_eval. │
│  │                                                               │
│  └─ After 50 questions:                                         │
│     evaluation_results/copypu_gemini/evaluation/ (50 files)      │
│                                                                   │
│  Summary generated:                                             │
│  └─ summary.json                                                │
│     {                                                            │
│       "kg": "copypu",                                           │
│       "model": "gemini",                                        │
│       "overall_f1": 0.3512,        (average of 50 evals)        │
│       "evaluation_count": 50,                                   │
│       "stages": {                                               │
│         "class_extraction": {"f1": 0.85},                       │
│         ...                                                      │
│       }                                                          │
│     }                                                            │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Comparison & Visualization Phase

```
After 2+ KG+Model combinations:

evaluation_results/
├── copypu_gemini/
│   └── summary.json          ┐
│                              │
├── copypu_mistral/           │  organized_evaluation.py
│   └── summary.json          │  Loads these summaries
│                              │
└── dbpedia_gemini/           │
    └── summary.json          ┘
         │
         ▼
    ┌─────────────────────────────────┐
    │ analyze_kg_model_combination()   │
    │ aggregate_metrics()              │
    │ generate_comparison_tables()     │
    └─────────────────────────────────┘
         │
         ▼
    ╔════════════════════════════════════════════════════════╗
    ║ TEXT REPORT 1: Per Combo                              ║
    ║                                                        ║
    ║ copypu + gemini (50 evals): F1=0.3512                ║
    ║ copypu + mistral (50 evals): F1=0.3245               ║
    ║ dbpedia + gemini (50 evals): F1=0.2890               ║
    ╚════════════════════════════════════════════════════════╝

    ╔════════════════════════════════════════════════════════╗
    ║ TEXT REPORT 2: Per KG (Which model is best?)          ║
    ║                                                        ║
    ║ COPYPU:                                               ║
    ║  1. gemini:   F1=0.3512 ✅ BEST                       ║
    ║  2. mistral:  F1=0.3245                               ║
    ║                                                        ║
    ║ DBPEDIA:                                              ║
    ║  1. gemini:   F1=0.2890                               ║
    ╚════════════════════════════════════════════════════════╝

    ╔════════════════════════════════════════════════════════╗
    ║ TEXT REPORT 3: Per Model (Which KG is best?)          ║
    ║                                                        ║
    ║ GEMINI:                                               ║
    ║  1. copypu:   F1=0.3512 ✅ BEST                       ║
    ║  2. dbpedia:  F1=0.2890                               ║
    ║                                                        ║
    ║ MISTRAL:                                              ║
    ║  1. copypu:   F1=0.3245                               ║
    ╚════════════════════════════════════════════════════════╝
         │
         └─ CONSOLE OUTPUT (text-based)


         ▼
    generate_comparison_plots.py
    Loads summary.json files
         │
         ├─▶ Plot 1: KG × Model Matrix (Heatmap)
         │   ┌─────────────────────────────┐
         │   │           gemini  mistral    │
         │   │ copypu:    0.35    0.32      │
         │   │ dbpedia:   0.29             │
         │   └─────────────────────────────┘
         │
         ├─▶ Plot 2: Per-KG Comparison
         │   ┌─────────────────────────────┐
         │   │ COPYPU                      │
         │   │ gemini  █████ 0.35          │
         │   │ mistral ██████ 0.32         │
         │   │                             │
         │   │ DBPEDIA                     │
         │   │ gemini  ██████ 0.29         │
         │   └─────────────────────────────┘
         │
         ├─▶ Plot 3: Per-Model Comparison
         │   ┌─────────────────────────────┐
         │   │ GEMINI                      │
         │   │ copypu  █████ 0.35          │
         │   │ dbpedia ██████ 0.29         │
         │   │                             │
         │   │ MISTRAL                     │
         │   │ copypu  ██████ 0.32         │
         │   └─────────────────────────────┘
         │
         └─▶ Plot 4: Stage-wise Breakdown
            ┌─────────────────────────────┐
            │ CLASS EXN      │ PROP EXN    │
            │ ████ 0.85      │ ██ 0.65     │
            │                             │
            │ MISSING ID     │ QUERY EXN   │
            │ █ 0.25         │ █ 0.28      │
            └─────────────────────────────┘
         │
         ▼
    evaluation_results/
    ├── comparison_kg_model_matrix.png
    ├── comparison_per_kg_models.png
    ├── comparison_per_model_kgs.png
    └── comparison_stage_performance.png
         │
         (User views PNG files in image viewer)
```

---

## 🔌 Single Result File Structure

### ground_truth/gt_q001.json
```json
{
  "question": "What are all products?",
  "kg": "copypu",
  "expected_outputs": {
    "class": "Product",
    "properties": ["name", "id", "supplier"],
    "entities": [],
    "sparql": "SELECT ?product WHERE { ?product a Product . }",
    "rows": [
      {"product": "http://example.org/Product1"},
      {"product": "http://example.org/Product2"}
    ]
  }
}
```

### results/result_*.json
```json
{
  "question": "What are all products?",
  "timestamp": "2026-02-25 10:15:30",
  "model_outputs": {
    "predicted_class": "Product",
    "predicted_properties": ["name", "id"],
    "predicted_entities": [],
    "sparql": "SELECT ?product WHERE { ?product a Product . }",
    "actual_rows": [
      {"product": "http://example.org/Product1"},
      {"product": "http://example.org/Product2"},
      {"product": "http://example.org/Product3"}
    ]
  }
}
```

### evaluation/eval_q001_eval.json
```json
{
  "question": "What are all products?",
  "kg": "copypu",
  "model": "gemini",
  "timestamp": "2026-02-25 10:15:31",
  "overall": {
    "average_f1": 0.3575
  },
  "stages": {
    "class_extraction": {
      "f1": 0.85,
      "precision": 0.82,
      "recall": 0.88
    },
    "property_extraction": {
      "f1": 0.65,
      "precision": 0.63,
      "recall": 0.68
    },
    "missing_id_extraction": {
      "f1": 0.25,
      "precision": 0.28,
      "recall": 0.22
    },
    "query_execution": {
      "f1": 0.28,
      "precision": 0.32,
      "recall": 0.25
    }
  }
}
```

### summary.json
```json
{
  "kg": "copypu",
  "model": "gemini",
  "overall_f1": 0.3512,
  "evaluation_count": 50,
  "stages": {
    "class_extraction": {
      "f1": 0.85,
      "precision": 0.82,
      "recall": 0.88
    },
    "property_extraction": {
      "f1": 0.65,
      "precision": 0.63,
      "recall": 0.68
    },
    "missing_id_extraction": {
      "f1": 0.25,
      "precision": 0.28,
      "recall": 0.22
    },
    "query_execution": {
      "f1": 0.28,
      "precision": 0.32,
      "recall": 0.25
    }
  }
}
```

---

## 🎯 Key Takeaways

1. **Configuration** → Everything determined by config.yaml
2. **Auto-Evaluation** → Happens during pipeline, no manual setup
3. **Auto-Organization** → Files move to KG_Model folders automatically
4. **Auto-Tagging** → Each result tagged with KG and Model
5. **Analysis** → Simple scripts generate reports and plots
6. **Comparison** → Multiple combos compared instantly

No manual file management needed! 🎉
