# 🚀 Multi-KG Multi-Model Evaluation - Quick Reference

## System Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER WORKFLOW                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  1️⃣  CONFIGURE                                                   │
│      edit config.yaml → set KG and Model                         │
│                                                                   │
│  2️⃣  RUN QUESTIONS                                              │
│      python -m nl2sparql.gui_v2 → 50 questions                  │
│                                                                   │
│  3️⃣  AUTO-EVALUATION                                            │
│      Pipeline runs evaluation automatically                      │
│      Results organized: evaluation_results/kg_model/             │
│                                                                   │
│  4️⃣  SWITCH CONFIG                                              │
│      Change config.yaml → different KG or Model                  │
│                                                                   │
│  5️⃣  REPEAT (Step 2-4)                                          │
│      Run 2+ combinations for comparisons                         │
│                                                                   │
│  6️⃣  ANALYZE                                                     │
│      python organized_evaluation.py → text reports               │
│      python generate_comparison_plots.py → visualizations        │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Configuration (config.yaml)

### Select Knowledge Graph
```yaml
kg:
  name: "copypu"                    # Change this to switch KGs
  source: "local_rdf"
  ttl_file: "data/input/copypu.ttl"
```

**Available KGs:**
- `copypu` - Product/supplier schema (default)
- `dbpedia` - General knowledge (if you add it)
- `freebase` - Factual data (if you add it)

### Select Model
```yaml
llm:
  provider: "gemini"                # Change this to switch models
  model_name: "gemini-1.5-pro"
```

**Available Models:**
- `gemini` - Google's Gemini API
- `mistral` - Mistral local model
- `gpt-4` - OpenAI GPT-4 (if configured)

---

## Folder Organization

### Root Structure
```
evaluation_results/
│
├── copypu_gemini/           ← Knowledge Graph_Model
│   ├── ground_truth/        ← Reference answers (Q&A pairs)
│   ├── results/             ← Execution results from queries
│   ├── evaluation/          ← Calculated metrics (F1, P, R)
│   └── summary.json         ← Overall performance (F1=0.35)
│
├── copypu_mistral/          ← Different model, same KG
│   ├── ground_truth/
│   ├── results/
│   ├── evaluation/
│   └── summary.json
│
├── dbpedia_gemini/          ← Different KG, same model
│   └── ...
│
└── comparison_*.png         ← Visualization graphs
```

### What Each Folder Contains

| Folder | Files | Purpose |
|--------|-------|---------|
| **ground_truth/** | `gt_*.json` | Expected answers (questions + correct outputs) |
| **results/** | `result_*.json` | Actual query results from execution |
| **evaluation/** | `eval_*_eval.json` | Computed metrics (precision, recall, F1) |
| **summary.json** | Single file | Overall F1 score and stage breakdown |

---

## Quick Commands

### 1. Check Evaluation Status
```bash
python show_evaluation_structure.py
```

**Output shows:**
- ✅ How many KG+Model combinations evaluated
- ✅ Number of questions per combination
- ✅ Overall F1 score per combination
- ✅ File counts per folder
- ✅ Folder sizes
- ✅ Recommendations for next steps

### 2. Generate Text Reports
```bash
python organized_evaluation.py
```

**Output shows:**
- Per combination: F1 + per-stage metrics
- Per KG: Which model is best?
- Per Model: Which KG is best?

### 3. Generate Visual Comparisons
```bash
python generate_comparison_plots.py
```

**Creates 4 PNG files:**
1. `comparison_kg_model_matrix.png` - Heatmap
2. `comparison_per_kg_models.png` - Bar charts per KG
3. `comparison_per_model_kgs.png` - Bar charts per model
4. `comparison_stage_performance.png` - Stage breakdown

### 4. View Folder Tree
```bash
tree /F evaluation_results           # Windows
# or
python show_evaluation_structure.py  # Any platform
```

---

## How Auto-Organization Works

### The Pipeline Tags Your Results

Every evaluation result is **automatically tagged** with:
```json
{
  "kg": "copypu",           ← From config.yaml
  "model": "gemini",        ← From config.yaml
  "question": "What are products?",
  "overall": { "average_f1": 0.35 },
  "stages": { ... }
}
```

### ResultsOrganizer Moves Files

After tagging, files are moved:
```
Step 1: Save
evaluation_results/eval_*.json

Step 2: Tag
evaluation["kg"] = "copypu"
evaluation["model"] = "gemini"

Step 3: Organize
evaluation_results/copypu_gemini/evaluation/eval_*.json
                   ↑            ↑            ↑
                   |            |            └─ Renamed evaluation file
                   |            └──────────────── Evaluation subfolder
                   └────────────────────────────── Auto-created folder
```

---

## Typical Usage Flow

### Session 1: Copypu + Gemini (50 questions)
```
1. config.yaml:
   kg.name: copypu
   llm.provider: gemini

2. Run: python -m nl2sparql.gui_v2
   Ask 50 questions

3. Results saved:
   evaluation_results/copypu_gemini/
   ├── ground_truth/ (50 Q&A pairs)
   ├── results/ (50 execution results)
   ├── evaluation/ (50 evaluation files)
   └── summary.json (F1=0.35)
```

### Session 2: Copypu + Mistral (50 questions)
```
1. config.yaml:
   kg.name: copypu
   llm.provider: mistral

2. Run: python -m nl2sparql.gui_v2
   Ask 50 questions

3. Results saved:
   evaluation_results/copypu_mistral/
   ├── ground_truth/ (50 Q&A pairs)
   ├── results/ (50 execution results)
   ├── evaluation/ (50 evaluation files)
   └── summary.json (F1=0.32)
```

### Analysis
```
python organized_evaluation.py
Output:
  copypu + gemini:   F1=0.35 ✅ BEST
  copypu + mistral:  F1=0.32

CONCLUSION: Gemini works better than Mistral on copypu

python generate_comparison_plots.py
Output:
  comparison_per_kg_models.png
  └─ Bar chart showing gemini > mistral on copypu
```

---

## Metrics Explained

### Overall F1 Score
```
F1 = 2 × (Precision × Recall) / (Precision + Recall)

Range: 0.0 (worst) to 1.0 (perfect)

Example: F1=0.35 means ~35% of answers were exactly correct
```

### Per-Stage Breakdown
```
Stage 1: Class Extraction
         "What entity type was recognized?"
         F1=0.85 (85% correct)

Stage 2: Property Extraction
         "What attributes were extracted?"
         F1=0.65 (65% correct)

Stage 3: Missing ID Extraction
         "Can we resolve entity references?"
         F1=0.25 (25% correct) ← Often lowest

Stage 4: Query Execution
         "Do query results match expected?"
         F1=0.28 (28% correct)

Average F1 = (0.85 + 0.65 + 0.25 + 0.28) / 4 ≈ 0.50
```

### What Precision & Recall Mean
```
Precision = "How many predicted answers were correct?"
           = Correct Predictions / Total Predictions

Recall    = "How many should-be-found answers did we find?"
           = Correct Predictions / Total Expected

Example:
  System predicted 10 entity classes
  Only 8 were actually correct
  But there were 14 actual classes total

  Precision = 8/10 = 0.80 (80% of our predictions were right)
  Recall = 8/14 = 0.57 (we found 57% of actual classes)
  F1 = 2 × (0.80 × 0.57) / (0.80 + 0.57) = 0.67
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **No folders created** | Run at least one evaluation first |
| **Empty ground_truth/** | Questions need correct answers marked in ground truth |
| **Empty evaluation/** | Check that auto-evaluation is enabled in pipeline |
| **summary.json missing** | Run `python organized_evaluation.py` once |
| **Charts look blank** | Need at least 2 KG+Model combinations |
| **Results in wrong folder** | Check config.yaml KG and Model values match |

---

## Key Files Reference

### Configuration
- **config.yaml** - Set KG and Model (USER EDITS THIS)

### Analysis Tools
- **show_evaluation_structure.py** - View folder structure & status
- **organized_evaluation.py** - Generate text comparison reports
- **generate_comparison_plots.py** - Create visualization graphs

### Core Pipeline
- **pipeline.py** - Runs evaluation & tags results automatically
- **results_organizer.py** - Moves files to KG+Model folders
- **ground_truth_manager.py** - Manages evaluation & results

### Documentation
- **MULTI_KG_MODEL_WORKFLOW.md** - Full detailed explanation (you are reading the summary)
- **This file** - Quick reference (what you're reading)

---

## 5-Minute Getting Started

```bash
# 1. Check current status
python show_evaluation_structure.py

# 2. Configure first KG+Model in config.yaml
# Edit: kg.name = "copypu", llm.provider = "gemini"

# 3. Run first evaluation (50 questions via GUI)
python -m nl2sparql.gui_v2

# 4. Change config for second model
# Edit: llm.provider = "mistral"

# 5. Run second evaluation (another 50 questions)
python -m nl2sparql.gui_v2

# 6. Generate report
python organized_evaluation.py

# 7. Generate graphs
python generate_comparison_plots.py

# 8. View results
ls evaluation_results/
# Should see: copypu_gemini/, copypu_mistral/, comparison_*.png
```

---

## Examples

### "Which model is best on copypu?"
```bash
python organized_evaluation.py

Output:
  copypu + gemini:   F1=0.3512
  copypu + mistral:  F1=0.3245
  
Answer: Gemini (0.3512 > 0.3245)
```

### "Which KG is easiest for gemini?"
```bash
python organized_evaluation.py

Output:
  copypu + gemini:   F1=0.3512
  dbpedia + gemini:  F1=0.2890
  
Answer: Copypu (0.3512 > 0.2890)
```

### "Visual comparison of all combinations"
```bash
python generate_comparison_plots.py

Creates:
  1. Heatmap showing F1 for all KG×Model
  2. Bar charts per KG (model comparison)
  3. Bar charts per model (KG comparison)
  4. Stage-wise F1 across all combos
```

---

## Next: Extend Your Evaluations

### Add a New Knowledge Graph
```yaml
# config.yaml
kg:
  name: "dbpedia"              # New KG
  source: "local_rdf"
  ttl_file: "data/input/dbpedia.ttl"
```

### Add a New Model
```yaml
# config.yaml
llm:
  provider: "gpt-4"            # New model
  model_name: "gpt-4"
```

### Create a Full Matrix (3 KGs × 2 Models = 6 combinations)
Run these 6 sessions (can be in any order):
- copypu + gemini
- copypu + mistral
- dbpedia + gemini
- dbpedia + mistral
- freebase + gemini
- freebase + mistral

Then: `python generate_comparison_plots.py` creates a 3×2 matrix showing all combinations!

---

## Remember

✅ **Config selects what you evaluate** - KG and Model determined by config.yaml
✅ **Results auto-organize** - You don't move files manually
✅ **Metrics auto-calculate** - Evaluation happens automatically
✅ **Comparisons auto-generate** - Just run the analysis scripts
✅ **Portable structure** - Same process works for any KG+Model combo

Happy evaluating! 🎯
