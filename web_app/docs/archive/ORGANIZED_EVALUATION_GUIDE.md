# Organized Multi-KG Multi-Model Evaluation Guide

## New Folder Structure

```
evaluation_results/
├── copypu_gemini/
│   ├── ground_truth/          # Ground truth files for this KG+Model
│   │   └── gt_*.json
│   ├── results/               # Query results
│   │   └── result_*.json
│   ├── evaluation/            # Evaluation results
│   │   └── eval_*_eval.json
│   └── summary.json           # Final summary for this combo
│
├── copypu_mistral/
│   ├── ground_truth/
│   ├── results/
│   ├── evaluation/
│   └── summary.json
│
├── dbpedia_gemini/
│   └── ...
│
└── dbpedia_mistral/
    └── ...
```

Each combination gets its OWN folder with separate subfolders for ground truth, results, and evaluations.

## Workflow Example

### Session 1: Copypu + Gemini (50 questions)

```bash
# 1. Update config.yaml
kg:
  name: "copypu"
  model: "gemini"
model: "gemini"

# 2. Run GUI and ask 50 questions (+ evaluation auto-runs)
python -m nl2sparql.gui_v2

# Results auto-organized in: evaluation_results/copypu_gemini/
# - evaluate_results/copypu_gemini/ground_truth/gt_*.json
# - evaluation_results/copypu_gemini/results/result_*.json
# - evaluation_results/copypu_gemini/evaluation/eval_*_eval.json
```

**On completion:** Copypu+Gemini gets `summary.json` with:
```json
{
  "kg": "copypu",
  "model": "gemini",
  "evaluation_count": 50,
  "overall_f1": 0.3847,
  "stats": {
    "class_extraction": {"f1": {"mean": 0.35, ...}},
    "property_extraction": {"f1": {"mean": 0.38, ...}},
    "missing_id_extraction": {"f1": {"mean": 0.41, ...}},
    "query_execution": {"f1": {"mean": 0.42, ...}}
  }
}
```

### Session 2: Copypu + Mistral (50 questions)

```bash
# 1. Update config.yaml
kg:
  name: "copypu"
  model: "mistral"
model: "mistral"

# 2. Run GUI - 50 more questions
python -m nl2sparql.gui_v2

# Results go to: evaluation_results/copypu_mistral/
```

### Session 3: DBPedia + Gemini

```bash
# 1. Update config.yaml
kg:
  name: "dbpedia"
  model: "gemini"

# 2. Run - different KG, different folder
python -m nl2sparql.gui_v2
```

## Generate Reports

### After ALL sessions complete:

```bash
# All combinations organized in separate folders
# Generate comprehensive comparison reports:

python organized_evaluation.py
```

**Outputs:**

#### 1. **Per KG-Model Report** (Numerical)
```
[COPYPU + GEMINI]
  Total Evaluations: 50
  Overall F1 Score: 0.3847
  
  Stage-wise Performance:
    class_extraction.................................. F1=0.3500 (±0.1200)
    property_extraction............................... F1=0.3800 (±0.1800)
    missing_id_extraction............................. F1=0.4100 (±0.1500)
    query_execution................................... F1=0.4200 (±0.1600)

[COPYPU + MISTRAL]
  Total Evaluations: 50
  Overall F1 Score: 0.3562
  ...
  
[DBPEDIA + GEMINI]
  ...
```

#### 2. **KG Comparison** (i.e., copypu: gemini vs mistral vs other models)
```
[COPYPU]
Model             F1 Score        Evaluations    Class    Property    Missing ID    Query
─────────────────────────────────────────────────────────────────────────────────────────
gemini            0.3847          50             0.3500   0.3800      0.4100        0.4200
mistral           0.3562          50             0.3200   0.3400      0.3800        0.3900
gpt-4             0.4120          50             0.3900   0.4100      0.4300        0.4400
```

#### 3. **Model Comparison** (i.e., gemini: copypu vs dbpedia vs other KGs)
```
[GEMINI]
KG                F1 Score        Evaluations    Class    Property    Missing ID    Query
─────────────────────────────────────────────────────────────────────────────────────────
dbpedia           0.4210          50             0.3800   0.4200      0.4500        0.4600
copypu            0.3847          50             0.3500   0.3800      0.4100        0.4200
freebase          0.3925          50             0.3600   0.3900      0.4200        0.4300
```

### Generate Visual Comparisons

```bash
python generate_comparison_plots.py
```

**Generates 4 PNG files:**

1. **`comparison_kg_model_matrix.png`** - Heatmap of all KG×Model combinations
   ```
   Shows F1 scores in color grid
   Rows: KGs
   Columns: Models
   ```

2. **`comparison_per_kg_models.png`** - Bar chart for each KG (models compared)
   ```
   For copypu: gemini vs mistral vs gpt-4 (bars sorted by F1)
   For dbpedia: gemini vs mistral vs gpt-4 (bars sorted by F1)
   ```

3. **`comparison_per_model_kgs.png`** - Bar chart for each model (KGs compared)
   ```
   For gemini: copypu vs dbpedia vs freebase (bars sorted by F1)
   For mistral: copypu vs dbpedia vs freebase (bars sorted by F1)
   ```

4. **`comparison_stage_performance.png`** - Stage-wise F1 for all combinations
   ```
   4 subplots (class, property, missing_id, query)
   X-axis: All KG+Model combinations
   Y-axis: F1 score for that stage
   ```

## Python API Usage

```python
from organized_evaluation import OrganizedEvaluationManager

# Initialize
manager = OrganizedEvaluationManager()

# Get analysis for specific KG+Model
analysis = manager.analyze_kg_model_combination("copypu", "gemini")
print(f"F1 Score: {analysis['overall_f1']:.4f}")
print(f"Evaluations: {analysis['evaluation_count']}")

# Generate summary report
summary = manager.generate_kg_model_summary("copypu", "gemini")

# Get all combinations
combinations = manager.get_all_kg_model_combinations()
# [('copypu', 'gemini'), ('copypu', 'mistral'), ('dbpedia', 'gemini'), ...]

# Print human-readable reports
manager.print_per_kg_model_report()  # Summary for each combo
manager.print_per_kg_comparison()    # Models compared per KG
manager.print_per_model_comparison() # KGs compared per model
```

## How Folder Organization Works

Each KG+Model combination automatically gets its own folder via the updatedpipeline:

1. **Config specifies:** `kg.name = "copypu"` and `model = "gemini"`
2. **During evaluation:** System auto-tags results with `kg` and `model` fields
3. **Post-processing:** Results organized into `evaluation_results/copypu_gemini/`
4. **Folder structure:**
   - Ground truth → `ground_truth/` subfolder
   - Results → `results/` subfolder
   - Evaluations → `evaluation/` subfolder
   - Summary → `summary.json` file

This happens AUTOMATICALLY - you don't manually organize files!

## Key Features

✅ **Automatic organization** by KG and Model  
✅ **Separate tracking** for each combination  
✅ **Easy comparison** across models and KGs  
✅ **Numerical reports** (tables with F1, precision, recall)  
✅ **Visual comparisons** (heatmaps, bar charts)  
✅ **Stage-wise breakdown** (class, property, missing_id, query)  
✅ **Reproducible** - all results saved with timestamps  

## Tips

1. **Use consistent KG/Model names** - Affects folder organization
2. **Update config before each session** - Ensures correct folder placement
3. **Run reports after all sessions** - Consolidates all comparisons
4. **Keep track of question count** - Report shows "out of X evaluations"
5. **Use stage-wise data** - Identify bottleneck stages per KG/Model combo

## Example Final Report Structure

After running all evaluations and reports:

```
📊 FINAL EVALUATION REPORT

SUMMARY TABLE:
┌─────────────────────┬────────────┬──────┬───────────────────────────────┐
│ KG          Model   │ Questions  │ F1   │ Class    Property  MisID  Query │
├─────────────────────┼────────────┼──────┼───────────────────────────────┤
│ copypu      gemini  │ 50         │ 0.39 │ 0.35     0.38      0.41    0.42  │
│ copypu      mistral │ 50         │ 0.36 │ 0.32     0.34      0.38    0.39  │
│ dbpedia     gemini  │ 50         │ 0.42 │ 0.38     0.42      0.45    0.46  │
│ dbpedia     mistral │ 50         │ 0.38 │ 0.34     0.37      0.40    0.41  │
└─────────────────────┴────────────┴──────┴───────────────────────────────┘

BEST PERFORMERS:
🥇 Best Overall:    DBPedia + Gemini (F1=0.42)
🥈 Best on Copypu:  Gemini (F1=0.39 vs Mistral 0.36)
🥉 Best on DBPedia: Gemini (F1=0.42 vs Mistral 0.38)

GENERATED VISUALIZATIONS:
  📈 comparison_kg_model_matrix.png
  📊 comparison_per_kg_models.png
  📋 comparison_per_model_kgs.png
  🎯 comparison_stage_performance.png
```

This makes it easy to see which model/KG combination works best!
