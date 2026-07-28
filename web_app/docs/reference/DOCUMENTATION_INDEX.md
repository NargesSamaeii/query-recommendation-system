# 📚 Multi-KG Multi-Model Evaluation System - Documentation Index

Welcome! This system allows you to evaluate your NL2SPARQL pipeline across multiple Knowledge Graphs (KGs) and Language Models (LLMs) with automatic organization, reporting, and visualization.

---

## 🚀 Quick Start (5 minutes)

**New to the system?** Start here:

1. **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** ← READ THIS FIRST
   - 5-minute overview of the entire system
   - Key concepts explained simply
   - Essential commands
   - Common scenarios

2. **[FOLDER_STRUCTURE_VISUAL.md](FOLDER_STRUCTURE_VISUAL.md)**
   - ASCII art folder structure
   - Data flow diagrams
   - How information moves through the system
   - File content examples

3. Run this command to see your evaluation status:
   ```bash
   python show_evaluation_structure.py
   ```

---

## 📖 Full Documentation

### Complete Workflow Guide
- **[MULTI_KG_MODEL_WORKFLOW.md](MULTI_KG_MODEL_WORKFLOW.md)** (Comprehensive)
  - Full step-by-step workflow
  - Detailed explanations
  - Multiple example scenarios
  - Troubleshooting guide
  - Advanced configurations

### Quick Reference & Cheat Sheet
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** (Quick lookup)
  - System architecture at a glance
  - Key commands reference
  - Folder structure summary
  - Metrics explained
  - Troubleshooting table

### Visual Guides
- **[FOLDER_STRUCTURE_VISUAL.md](FOLDER_STRUCTURE_VISUAL.md)** (Diagrams & ASCII art)
  - Folder tree visualization
  - Data flow diagrams
  - File structure examples
  - Process flow charts

---

## 🛠️ Essential Tools

### 1. Check Evaluation Status
```bash
python show_evaluation_structure.py
```

**What it does:**
- Shows all KG+Model combinations evaluated so far
- Displays file counts and sizes
- Shows current F1 scores
- Recommends next steps
- Displays folder tree

**When to use:** After each evaluation session or before generating reports

---

### 2. Generate Text Comparison Reports
```bash
python organized_evaluation.py
```

**What it does:**
- Creates 3 comparison tables:
  1. **Per KG+Model** - Overall F1 for each combination
  2. **Per KG** - Shows which model is best for each KG
  3. **Per Model** - Shows which KG is best for each model

**When to use:** After evaluating 2+ combinations

**Example output:**
```
copypu + gemini:   F1=0.3512 ✅ BEST
copypu + mistral:  F1=0.3245

COPYPU: WHICH MODEL IS BEST?
  Gemini wins (0.3512 > 0.3245)
```

---

### 3. Generate Visualization Graphs
```bash
python generate_comparison_plots.py
```

**What it does:**
Creates 4 PNG image files:
1. **comparison_kg_model_matrix.png** - Heatmap of all KG×Model combinations
2. **comparison_per_kg_models.png** - Bar charts per KG (model comparison)
3. **comparison_per_model_kgs.png** - Bar charts per model (KG comparison)
4. **comparison_stage_performance.png** - 4-subplot grid (stage-wise F1)

**When to use:** After evaluating 2+ combinations for visual analysis

**Location:** PNG files saved to `evaluation_results/` directory

---

## 🔄 Typical Workflow

### Step 1: Configure (Edit config.yaml)
```yaml
kg:
  name: "copypu"           # Change this to switch KGs
  source: "local_rdf"
  ttl_file: "data/input/copypu.ttl"

llm:
  provider: "gemini"       # Change this to switch models
  model_name: "gemini-1.5-pro"
```

### Step 2: Run Evaluation (Ask 50 questions)
```bash
python -m nl2sparql.gui_v2    # Interactive GUI
# or
python run_query.py "..."     # Single query
```

Results automatically saved to:
```
evaluation_results/copypu_gemini/
├── ground_truth/    ← Questions
├── results/         ← Execution results
├── evaluation/      ← Metrics (auto-calculated)
└── summary.json     ← Overall F1 (auto-generated)
```

### Step 3: Switch Configuration
```yaml
kg:
  name: "copypu"
  
llm:
  provider: "mistral"        ← Changed from gemini
```

### Step 4: Run Another Evaluation (50 more questions)
Results saved to `evaluation_results/copypu_mistral/`

### Step 5: Generate Reports
```bash
python organized_evaluation.py
python generate_comparison_plots.py
```

**Output:**
- Text reports showing metric comparison
- PNG graphs showing visual comparison
- Recommendation on best model/KG combo

---

## 📊 Understanding the Metrics

### Overall F1 Score
- **Range:** 0.0 (worst) to 1.0 (perfect)
- **Interpretation:** Percentage of questions answered correctly
- **Example:** F1=0.35 means ~35% of answers were completely correct

### Per-Stage F1 Scores
```
Stage 1: Class Extraction (F1=0.85)
         Can the system identify entity types?

Stage 2: Property Extraction (F1=0.65)
         Can the system extract relevant properties?

Stage 3: Missing ID Extraction (F1=0.25)
         Can the system resolve entity references?
         (Often lowest - challenging stage)

Stage 4: Query Execution (F1=0.28)
         Do execution results match expected?
```

### Precision vs Recall
- **Precision:** "How many predicted answers were correct?"
  - High precision = Few false positives
- **Recall:** "How many actual answers did we find?"
  - High recall = Few false negatives
- **F1:** Balanced combination of Precision & Recall

---

## 🎯 Common Scenarios

### Scenario 1: Which model works better on copypu?

```bash
# Step 1: Configure for copypu + gemini
# Edit config.yaml: kg.name = "copypu", llm.provider = "gemini"
# Step 2: Ask 50 questions via GUI
# Step 3: Configure for copypu + mistral
# Edit config.yaml: llm.provider = "mistral"
# Step 4: Ask 50 more questions
# Step 5: Generate report
python organized_evaluation.py

# Output will show:
# copypu + gemini:   F1=0.3512 ✅
# copypu + mistral:  F1=0.3245
```

---

### Scenario 2: Which KG is easier for gemini?

```bash
# Step 1: Configure for copypu + gemini
# Ask 50 questions
# Step 2: Configure for dbpedia + gemini
# Ask 50 questions
# Step 3: Generate report
python organized_evaluation.py

# Output will show:
# copypu + gemini:   F1=0.3512 ✅ (easier)
# dbpedia + gemini:  F1=0.2890
```

---

### Scenario 3: Full evaluation matrix (3 KGs × 2 models)

```bash
# Run these 6 evaluation sessions (in any order):
1. copypu + gemini (50 questions)
2. copypu + mistral (50 questions)
3. dbpedia + gemini (50 questions)
4. dbpedia + mistral (50 questions)
5. freebase + gemini (50 questions)
6. freebase + mistral (50 questions)

# Then generate comprehensive reports:
python organized_evaluation.py
python generate_comparison_plots.py

# Output:
# - Text reports comparing all 6 combinations
# - Heatmap showing 3×2 matrix of F1 scores
# - Bar charts for each KG and model
# - Stage-wise performance breakdown
```

---

## 📁 Folder Organization

### Root Level
```
evaluation_results/
├── copypu_gemini/
│   ├── ground_truth/
│   ├── results/
│   ├── evaluation/
│   └── summary.json
├── copypu_mistral/
│   └── ...
├── dbpedia_gemini/
│   └── ...
└── comparison_*.png
```

### Inside Each KG_Model Folder
```
copypu_gemini/
├── ground_truth/        ← Questions + expected answers
├── results/             ← Query execution results
├── evaluation/          ← Calculated metrics
└── summary.json         ← Overall F1 + per-stage scores
```

### What Each Folder Contains

| Folder | Purpose | File Count |
|--------|---------|-----------|
| **ground_truth/** | Reference Q&A pairs | 50-100+ JSON files |
| **results/** | Query outputs from system | 50-100+ JSON files |
| **evaluation/** | Calculated evaluation metrics | 50-100+ JSON files |
| **summary.json** | Aggregated metrics | 1 JSON file |

---

## 🔧 Configuration File (config.yaml)

### Select Knowledge Graph
```yaml
kg:
  name: "copypu"              # Change to: dbpedia, freebase, etc.
  source: "local_rdf"         # Where to load from
  ttl_file: "data/input/copypu.ttl"  # Path to RDF file
```

### Select Model
```yaml
llm:
  provider: "gemini"          # Change to: mistral, gpt-4, etc.
  model_name: "gemini-1.5-pro"
```

### How It Works
- Pipeline reads these values
- Pipeline tags all results with KG and Model
- ResultsOrganizer creates folder: `{kg}_{model}`
- Files move automatically to organized folder

---

## 🚨 Troubleshooting

### No folders created yet
- **Cause:** Haven't run any evaluations
- **Solution:** Follow "Typical Workflow" section above

### Folders created but empty
- **Cause:** Evaluation didn't complete or auto-tagging failed
- **Solution:** Check that evaluation is enabled in pipeline.py

### Missing summary.json files
- **Cause:** Haven't run analysis script
- **Solution:** Execute `python organized_evaluation.py`

### Charts show "No data"
- **Cause:** Only 1 KG+Model combination evaluated
- **Solution:** Run at least 2 combinations, then regenerate plots

### Wrong KG/Model in summary.json
- **Cause:** Config values don't match when questions were run
- **Solution:** Ensure config.yaml matches what was used during evaluation

---

## 📚 Documentation by Purpose

### Understanding the System
1. **QUICK_REFERENCE.md** - Overview & key concepts
2. **FOLDER_STRUCTURE_VISUAL.md** - Diagrams & ASCII art
3. **MULTI_KG_MODEL_WORKFLOW.md** - Deep dive explanation

### Running Evaluations
1. Update **config.yaml**
2. Run **python -m nl2sparql.gui_v2**
3. Check **python show_evaluation_structure.py**

### Analyzing Results
1. Run **python organized_evaluation.py** (text reports)
2. Run **python generate_comparison_plots.py** (graphs)
3. View PNG files in **evaluation_results/**

### Interpreting Results
1. Read "Understanding the Metrics" section above
2. Check QUICK_REFERENCE.md for examples
3. Review data flow in FOLDER_STRUCTURE_VISUAL.md

---

## 🎮 Command Reference

### View Status
```bash
python show_evaluation_structure.py
```

### Generate Reports
```bash
python organized_evaluation.py
```

### Generate Graphs
```bash
python generate_comparison_plots.py
```

### Run Evaluation (GUI)
```bash
python -m nl2sparql.gui_v2
```

### Run Single Query (CLI)
```bash
python run_query.py "What are all products?"
```

---

## 💡 Pro Tips

✅ **Always check config.yaml before running questions**
- Different KG/Model = Different folder

✅ **Run show_evaluation_structure.py between sessions**
- See what you've evaluated so far
- Get recommended next steps

✅ **Keep 50 questions per combination**
- Consistent sample size for fair comparison
- Easy to track and manage

✅ **Generate reports after 2+ combinations**
- 1 combo is baseline
- 2+ combos enable comparison

✅ **Use PNG visualizations for presentations**
- Graphs more intuitive than numbers
- Save to file for sharing

---

## 🔗 Quick Links

### Documentation
- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Start here!
- [MULTI_KG_MODEL_WORKFLOW.md](MULTI_KG_MODEL_WORKFLOW.md) - Full details
- [FOLDER_STRUCTURE_VISUAL.md](FOLDER_STRUCTURE_VISUAL.md) - Diagrams

### Tools
- [show_evaluation_structure.py](show_evaluation_structure.py) - View status
- [organized_evaluation.py](organized_evaluation.py) - Generate reports
- [generate_comparison_plots.py](generate_comparison_plots.py) - Create graphs

### Configuration
- [config.yaml](config.yaml) - Set KG and Model

### Code
- [pipeline.py](nl2sparql/pipeline.py) - Main pipeline
- [results_organizer.py](results_organizer.py) - Auto-organization
- [ground_truth_manager.py](nl2sparql/ground_truth_manager.py) - Evaluation

---

## ❓ Need Help?

1. **"How do I start?"**
   → Read [QUICK_REFERENCE.md](QUICK_REFERENCE.md)

2. **"What should I do next?"**
   → Run `python show_evaluation_structure.py`

3. **"How does it work?"**
   → Read [FOLDER_STRUCTURE_VISUAL.md](FOLDER_STRUCTURE_VISUAL.md)

4. **"What are all the options?"**
   → Read [MULTI_KG_MODEL_WORKFLOW.md](MULTI_KG_MODEL_WORKFLOW.md)

5. **"Where are my results?"**
   → Check `evaluation_results/` folder

6. **"Why is nothing showing up?"**
   → Check [Troubleshooting](#-troubleshooting) section above

---

## 🎯 Summary

Your multi-KG multi-model evaluation system is ready! Here's what it does:

✅ **Automatically** evaluates your pipeline
✅ **Automatically** organizes results by KG+Model
✅ **Automatically** calculates metrics (F1, Precision, Recall)
✅ **Automatically** tags results for comparison
✅ **Automatically** generates summaries for reporting

You just need to:
1. Configure KG and Model in config.yaml
2. Ask 50 questions via GUI
3. Repeat for different KGs/Models
4. Run analysis scripts
5. View reports and graphs

That's it! Happy evaluating! 🚀

---

**Last Updated:** February 25, 2026
**Status:** Ready for use
**Version:** 1.0
