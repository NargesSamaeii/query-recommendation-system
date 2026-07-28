# Multi-KG Multi-Model Evaluation Workflow

## Quick Overview

Your evaluation system automatically organizes results by **Knowledge Graph** and **LLM Model**. Here's how it works:

```
config.yaml → Pipeline → Questions → Results → Auto-Organization → Folders
   (KG & Model)                              (by KG+Model)    (evaluation_results/)
```

---

## Step-by-Step Workflow

### Step 1: Configure KG and Model (config.yaml)

```yaml
# config.yaml

kg:
  name: "copypu"                    # Which Knowledge Graph to use
  source: "local_rdf"               # Where to load it from
  ttl_file: "data/input/copypu.ttl" # Path to RDF file

llm:
  provider: "gemini"                # Which LLM model to use
  model_name: "gemini-1.5-pro"      # Specific model name
```

**Example configurations:**
- Copypu + Gemini: `kg.name: copypu`, `llm.provider: gemini`
- Copypu + Mistral: `kg.name: copypu`, `llm.provider: mistral`
- DBPedia + Gemini: `kg.name: dbpedia`, `llm.provider: gemini`

### Step 2: Run the Pipeline

Run either the **GUI** or **CLI** to ask questions:

```bash
# Option A: GUI (interactive)
python -m nl2sparql.gui_v2

# Option B: CLI
python run_query.py "What are all products?" -kg copypu
```

The pipeline will:
- ✅ Extract classes from the question
- ✅ Extract properties
- ✅ Identify missing entities
- ✅ Generate SPARQL query
- ✅ Execute query
- ✅ **Automatically evaluate** each question
- ✅ **Save results with KG+Model tags**

### Step 3: Auto-Organization (Happens Automatically)

As results are saved, `ResultsOrganizer` automatically moves them:

```
evaluation_results/
├── copypu_gemini/          ← KG_Model folder
│   ├── ground_truth/       ← Ground truth files for this combo
│   ├── results/            ← Query execution results
│   ├── evaluation/         ← Auto-generated evaluation files
│   └── summary.json        ← Overall metrics for this combo
│
├── copypu_mistral/         ← Different model, same KG
│   ├── ground_truth/
│   ├── results/
│   ├── evaluation/
│   └── summary.json
│
└── dbpedia_gemini/         ← Different KG, same model
    ├── ground_truth/
    ├── results/
    ├── evaluation/
    └── summary.json
```

### Step 4: Generate Reports

After running evaluations, generate numerical reports:

```bash
python organized_evaluation.py
```

**Output example:**
```
=== PER KG+MODEL EVALUATION RESULTS ===

copypu + gemini (50 questions):
  Overall F1: 0.3512
  - Class Extraction: F1=0.85, Precision=0.82, Recall=0.88
  - Property Extraction: F1=0.65, Precision=0.63, Recall=0.68
  - Missing ID: F1=0.25, Precision=0.28, Recall=0.22
  - Query Execution: F1=0.28, Precision=0.32, Recall=0.25

copypu + mistral (50 questions):
  Overall F1: 0.3245
  - Class Extraction: F1=0.80, Precision=0.78, Recall=0.82
  - ...

=== COPYPU: WHICH MODEL IS BEST? ===
  1. gemini:   F1=0.3512 (50 evals)
  2. mistral:  F1=0.3245 (50 evals)

=== GEMINI: WHICH KG IS BEST? ===
  1. copypu:   F1=0.3512 (50 evals)
  2. dbpedia:  F1=0.2890 (50 evals)
```

### Step 5: Generate Visualizations

Create graphical comparisons:

```bash
python generate_comparison_plots.py
```

**Generates 4 PNG files:**

1. **comparison_kg_model_matrix.png** - Heatmap
   - Rows = Knowledge Graphs
   - Columns = Models
   - Color = F1 Score (brighter = better)
   
2. **comparison_per_kg_models.png** - Bar Charts
   - One chart per KG
   - Bars = Different models
   - Compares which model works best on each KG

3. **comparison_per_model_kgs.png** - Bar Charts
   - One chart per Model
   - Bars = Different KGs
   - Compares which KG works best with each model

4. **comparison_stage_performance.png** - 4-Subplot Grid
   - One subplot per evaluation stage
   - Shows F1 scores across all KG+Model combinations

---

## Auto-Tagging Mechanism

Each evaluation file is automatically tagged with KG and Model information:

**Evaluation file content (eval_*.json):**
```json
{
  "question": "What are all products?",
  "timestamp": "2026-02-25 10:30:45",
  "kg": "copypu",           ← Auto-tagged by ResultsOrganizer
  "kg_source": "local_rdf", ← From config.yaml
  "model": "gemini",        ← Auto-tagged by ResultsOrganizer
  "overall": {
    "average_f1": 0.3512
  },
  "stages": {
    "class_extraction": { ... },
    "property_extraction": { ... },
    "missing_id_extraction": { ... },
    "query_execution": { ... }
  }
}
```

These tags allow automatic organization and later filtering/comparison.

---

## Usage Examples

### Example 1: Test One KG with Multiple Models

```
Session 1: Copypu + Gemini
├── Update config.yaml: kg.name=copypu, llm.provider=gemini
├── Run 50 questions in GUI
└── Results → evaluation_results/copypu_gemini/

Session 2: Copypu + Mistral
├── Update config.yaml: kg.name=copypu, llm.provider=mistral
├── Run 50 questions in GUI
└── Results → evaluation_results/copypu_mistral/

Analysis:
├── python organized_evaluation.py
│   └── Output: Which model works better on copypu?
└── python generate_comparison_plots.py
    └── Output: Bar chart comparing gemini vs mistral on copypu
```

### Example 2: Test One Model with Multiple KGs

```
Session 1: Copypu + Gemini
├── Update config.yaml: kg.name=copypu, llm.provider=gemini
├── Run 50 questions
└── Results → evaluation_results/copypu_gemini/

Session 2: DBPedia + Gemini
├── Update config.yaml: kg.name=dbpedia, llm.provider=gemini
├── Run 50 questions
└── Results → evaluation_results/dbpedia_gemini/

Analysis:
├── python organized_evaluation.py
│   └── Output: Which KG works better with gemini?
└── python generate_comparison_plots.py
    └── Output: Bar chart comparing copypu vs dbpedia with gemini
```

### Example 3: Full Matrix (Multiple KGs × Multiple Models)

```
Run these sessions (in any order):
├── copypu + gemini   → evaluation_results/copypu_gemini/
├── copypu + mistral  → evaluation_results/copypu_mistral/
├── dbpedia + gemini  → evaluation_results/dbpedia_gemini/
├── dbpedia + mistral → evaluation_results/dbpedia_mistral/
└── freebase + gemini → evaluation_results/freebase_gemini/

Then analyze:
├── python organized_evaluation.py
│   ├── Per-combo comparison (5 combinations)
│   ├── Per-KG comparison (which model best on each KG?)
│   └── Per-model comparison (which KG best with each model?)
└── python generate_comparison_plots.py
    ├── Heatmap of 3 KGs × 2 models
    ├── Bar charts for each KG
    ├── Bar charts for each model
    └── Stage-wise performance grid
```

---

## Folder Organization

### Root Structure
```
nl2sparql/
├── config.yaml                          ← Configure KG and Model
├── organized_evaluation.py               ← Generate reports
├── generate_comparison_plots.py          ← Generate visualizations
├── results_organizer.py                  ← Auto-organization logic
├── pipeline.py                           ← Main pipeline (runs auto-tagging)
├── nl2sparql/                            ← Core library
│   ├── gui_v2.py                         ← GUI interface
│   ├── pipeline.py                       ← Pipeline implementation
│   ├── ground_truth_manager.py           ← Evaluation manager
│   └── ...
│
├── data/
│   └── input/
│       ├── copypu.ttl                    ← Knowledge Graph 1
│       └── dbpedia.ttl                   ← Knowledge Graph 2 (optional)
│
└── evaluation_results/                   ← All results organized here
    ├── copypu_gemini/
    │   ├── ground_truth/                 ← Questions for this combo
    │   ├── results/                      ← Query execution results
    │   ├── evaluation/                   ← Evaluation metrics
    │   └── summary.json                  ← Overall F1, per-stage F1
    │
    ├── copypu_mistral/
    │   ├── ground_truth/
    │   ├── results/
    │   ├── evaluation/
    │   └── summary.json
    │
    ├── dbpedia_gemini/
    │   ├── ground_truth/
    │   ├── results/
    │   ├── evaluation/
    │   └── summary.json
    │
    └── [comparison visualizations]
        ├── comparison_kg_model_matrix.png
        ├── comparison_per_kg_models.png
        ├── comparison_per_model_kgs.png
        └── comparison_stage_performance.png
```

### Key Folders Explained

| Folder | Purpose | Auto-Created? |
|--------|---------|---------------|
| `evaluation_results/{kg}_{model}/` | Stores all data for one KG+Model combo | ✅ Yes |
| `evaluation_results/{kg}_{model}/ground_truth/` | Questions/expected answers for this combo | ✅ Yes |
| `evaluation_results/{kg}_{model}/results/` | Query execution results from pipeline | ✅ Yes |
| `evaluation_results/{kg}_{model}/evaluation/` | Calculated metrics (F1, Precision, Recall) | ✅ Yes |
| `evaluation_results/{kg}_{model}/summary.json` | Overall performance summary | ✅ Yes (on first analysis) |

---

## Complete Pipeline Data Flow

```
1. USER CONFIGURATION
   config.yaml (KG + Model) → Pipeline

2. QUESTION PROCESSING
   GUI/CLI Input
   ↓
   Class Extraction (ML) → predicted_class
   ↓
   Property Extraction (ML) → predicted_properties
   ↓
   Missing ID Extraction (ML) → predicted_entities
   ↓
   SPARQL Generation (LLM) → sparql_query
   ↓
   Query Execution (SPARQL) → actual_results

3. RESULTS SAVING
   results/ folder ← actual_results (with timestamp)
   ↓
   Tagged with: {"kg": "copypu", "model": "gemini"}

4. AUTO-EVALUATION
   EvaluationResultsManager loads:
   - Ground truth (expected outputs) ← "what should the answer be?"
   - Actual results ← "what did the system produce?"
   
   Compares for each stage:
   ├── class_extraction: predicted vs expected classes
   ├── property_extraction: predicted vs expected properties
   ├── missing_id: predicted vs expected entities (by IRI)
   └── query_execution: predicted rows vs expected rows
   
   Calculates:
   ├── Precision = (correct predictions) / (total predictions)
   ├── Recall = (correct predictions) / (total expected)
   └── F1 = 2 * (Precision * Recall) / (Precision + Recall)

5. AUTO-ORGANIZATION
   evaluation/ folder ← evaluation file
   └── ResultsOrganizer moves it to:
       evaluation_results/copypu_gemini/evaluation/eval_*.json

6. REPORTING & VISUALIZATION
   organized_evaluation.py ← Loads all evaluation files
   ├── Groups by KG+Model
   ├── Aggregates metrics
   └── Outputs comparison tables
   
   generate_comparison_plots.py ← Loads all summaries
   ├── Creates heatmap
   ├── Creates per-KG charts
   ├── Creates per-model charts
   └── Creates stage-wise grid
```

---

## Key Scripts Reference

### 1. Run Pipeline
```bash
python -m nl2sparql.gui_v2        # Interactive GUI
# or
python run_query.py "Question?"   # Single query
```

### 2. Generate Reports (Text)
```bash
python organized_evaluation.py
```
Outputs three comparison tables:
- Per KG+Model (all combinations)
- Per KG (which model is best?)
- Per Model (which KG is best?)

### 3. Generate Visualizations (Graphs)
```bash
python generate_comparison_plots.py
```
Creates 4 PNG files showing F1 scores across different perspectives.

### 4. View Folder Structure
```bash
# PowerShell
tree /F evaluation_results

# Or use Python script (optional)
python show_evaluation_structure.py
```

---

## Quick Start Checklist

- [ ] **Step 1**: Update `config.yaml` with first KG and model
- [ ] **Step 2**: Run 50-100 questions in GUI or CLI
- [ ] **Step 3**: Results auto-saved to `evaluation_results/{kg}_{model}/`
- [ ] **Step 4**: Update `config.yaml` with second KG or model
- [ ] **Step 5**: Run another 50-100 questions
- [ ] **Step 6**: Run `python organized_evaluation.py` for report
- [ ] **Step 7**: Run `python generate_comparison_plots.py` for visualizations
- [ ] **Step 8**: Check `evaluation_results/` folder for reports
- [ ] **Step 9**: Open PNG files to see graphical comparisons

---

## Troubleshooting

**Q: Results not appearing in organized folders?**
A: Check that `ResultsOrganizer` is imported and enabled in pipeline.py (should be automatic, but may need restart).

**Q: No summary.json file?**
A: Run `python organized_evaluation.py` once to generate summary files for each combo.

**Q: Charts look empty?**
A: Ensure at least 2 different KG+Model combinations have been evaluated.

**Q: How do I switch from copypu to dbpedia?**
A: Update `config.yaml`: change `kg.name: copypu` to `kg.name: dbpedia`

---

## Next Steps

After understanding this workflow:

1. **Run your first evaluation**: copypu + gemini (50 questions)
2. **Run second evaluation**: copypu + mistral (50 questions)  
3. **Compare models**: `python organized_evaluation.py`
4. **Visualize**: `python generate_comparison_plots.py`
5. **Extend**: Add more KGs and models as needed

Good luck! 🚀
