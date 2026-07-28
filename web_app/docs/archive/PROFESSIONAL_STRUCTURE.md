# Professional Project Structure for Multi-KG Evaluation

## 🏗️ Proposed Structure

```
nl2sparql/
│
├── 📋 /config/                      ← Configuration files
│   ├── config.yaml                  ← Main configuration (optional: can be root-level)
│   └── logging.yaml                 ← Logging configuration
│
├── 📚 /data/                        ← Knowledge Graphs & Schemas
│   ├── /input/                      ← Input RDF/TTL files
│   │   ├── copypu.ttl               ← KG 1: Copypu (Products & Suppliers)
│   │   ├── dbpedia.ttl              ← KG 2: DBpedia (General Knowledge) [optional]
│   │   ├── freebase.ttl             ← KG 3: Freebase [optional]
│   │   └── README.md
│   │
│   └── /output/                     ← Generated schemas (m_schema JSON)
│       ├── /copypu_mschema/         ← Auto-generated from copypu.ttl
│       │   ├── copypu_mschema.json
│       │   ├── copypu_schema_info.json
│       │   └── copypu_classes.json
│       ├── /dbpedia_mschema/        ← Auto-generated from dbpedia.ttl
│       └── README.md
│
├── 💾 /results/                     ← Query Execution Results (organized by KG)
│   ├── /copypu/                     ← Results for Copypu KG
│   │   ├── result_20260225_101530.json
│   │   ├── result_20260225_101545.json
│   │   └── ... (all results for copypu)
│   ├── /dbpedia/                    ← Results for DBpedia KG
│   └── README.md
│
├── 📝 /prompts/                     ← Generated Prompts (organized by KG)
│   ├── /copypu/                     ← Prompts for Copypu KG
│   │   ├── prompt_class_extraction.txt
│   │   ├── prompt_property_extraction.txt
│   │   └── prompt_query_generation.txt
│   ├── /dbpedia/                    ← Prompts for DBpedia KG
│   └── README.md
│
├── ❓ /ground_truth/                ← Question & Answer Pairs (organized by KG)
│   ├── /copypu/                     ← Ground truth for Copypu KG
│   │   ├── gt_q001.json             ← {"question": "...", "expected": {...}}
│   │   ├── gt_q002.json
│   │   ├── gt_q003.json
│   │   └── ... (50-100 Q&A pairs)
│   ├── /dbpedia/                    ← Ground truth for DBpedia KG
│   │   ├── gt_q001.json
│   │   └── ... (50-100 Q&A pairs)
│   └── README.md
│
├── 📊 /evaluation_results/          ← Evaluation Metrics (organized by KG_Model)
│   ├── /copypu_gemini/              ← Copypu KG + Gemini Model
│   │   ├── /ground_truth/           ← Reference (links to /ground_truth/copypu/)
│   │   ├── /results/                ← Reference (links to /results/copypu/)
│   │   ├── /evaluation/
│   │   │   ├── eval_q001_eval.json  ← {"f1": 0.85, "stages": {...}}
│   │   │   ├── eval_q002_eval.json
│   │   │   └── ... (50 evaluation files)
│   │   ├── summary.json             ← {"kg": "copypu", "model": "gemini", "f1": 0.3512}
│   │   └── comparison_report.txt    ← Per-KG-Model report
│   │
│   ├── /copypu_mistral/             ← Copypu KG + Mistral Model
│   │   ├── /ground_truth/
│   │   ├── /results/
│   │   ├── /evaluation/
│   │   ├── summary.json
│   │   └── comparison_report.txt
│   │
│   ├── /dbpedia_gemini/             ← DBpedia KG + Gemini Model
│   ├── /dbpedia_mistral/
│   │
│   ├── comparison_kg_model_matrix.png      ← Visualizations
│   ├── comparison_per_kg_models.png
│   ├── comparison_per_model_kgs.png
│   ├── comparison_stage_performance.png
│   └── README.md
│
├── 📜 /logs/                        ← Application logs
│   ├── nl2sparql.log
│   └── README.md
│
├── ⚙️ /cache/                       ← Cache files
│   ├── /embeddings/                 ← Cached embeddings per schema
│   │   ├── embeddings_copypu_*.npz
│   │   ├── embeddings_dbpedia_*.npz
│   │   └── ...
│   └── README.md
│
├── 🐍 /nl2sparql/                   ← Source Code (already exists)
│   ├── __init__.py
│   ├── pipeline.py                  ← UPDATED: auto-detect KG
│   ├── gui_v2.py                    ← UPDATED: pass KG to pipeline
│   ├── cli.py                       ← UPDATED: pass KG to pipeline
│   ├── sparql_generator.py
│   ├── llm_interface.py
│   ├── ground_truth_manager.py      ← UPDATED: KG-based folders
│   ├── schema_parser.py
│   ├── class_evaluator.py
│   ├── property_evaluator.py
│   └── ...
│
├── 🧪 /tests/                       ← Unit Tests
│   ├── test_pipeline.py
│   ├── test_evaluation.py
│   └── README.md
│
├── 📊 Analysis & Reporting Tools (Root level)
│   ├── organized_evaluation.py       ← Generate comparison reports
│   ├── generate_comparison_plots.py  ← Generate visualizations
│   ├── show_evaluation_structure.py  ← Show current status
│   └── results_organizer.py          ← Auto-organize by KG+Model
│
├── 📚 Documentation (Root level)
│   ├── README.md                     ← Main documentation
│   ├── QUICK_REFERENCE.md
│   ├── MULTI_KG_MODEL_WORKFLOW.md
│   ├── FOLDER_STRUCTURE_VISUAL.md
│   ├── DOCUMENTATION_INDEX.md
│   ├── PROFESSIONAL_STRUCTURE.md     ← THIS FILE
│   └── ...
│
├── 📦 Setup & Config (Root level)
│   ├── config.yaml                   ← Main config (or move to /config/)
│   ├── requirements.txt
│   ├── setup.py
│   └── .gitignore
│
└── 🎯 Main Entry Points (Root level)
    ├── run_gui.py                    ← Start GUI: python run_gui.py
    ├── run_query.py                  ← Run single query: python run_query.py "question"
    └── run_evaluation.py             ← Run full evaluation: python run_evaluation.py
```

---

## 🔄 How Auto-Detection Works

### When User Runs GUI or Query

```python
# User selects schema in GUI
# Or user has copypu.ttl in /data/input/

┌─────────────────────────────────────┐
│ GUI / CLI receives user input       │
│ "What are all products?"            │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ System detects KG being used        │
│ (from available schema/database)    │
│ Detected: "copypu"                  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ Pipeline creates KG-specific paths: │
│ - /results/copypu/                  │
│ - /prompts/copypu/                  │
│ - Load ground_truth from:           │
│   /ground_truth/copypu/             │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ During evaluation:                  │
│ - Detect model (from LLM config)    │
│ - Create evaluation folder:         │
│   /evaluation_results/copypu_gemini/│
│ - Auto-tag results with:            │
│   {"kg": "copypu", "model": "gemini"}
└─────────────────────────────────────┘
```

---

## 🎯 Auto-Detection Implementation

### 1. Detect KG from Available Data

```python
# In pipeline.py or gui_v2.py

def detect_kg() -> str:
    """Auto-detect which KG is being used."""
    
    # Option A: From loaded schema
    schema_name = get_loaded_schema_name()  # e.g., "copypu_mschema.json"
    kg_name = schema_name.replace("_mschema.json", "")  # → "copypu"
    
    # Option B: From selected KG in GUI
    # (User selects from dropdown, system remembers)
    kg_name = gui.selected_kg  # e.g., "copypu"
    
    # Option C: From active database
    kg_name = get_active_database_name()  # e.g., "copypu"
    
    return kg_name  # Returns: "copypu", "dbpedia", etc.
```

### 2. Automatically Create KG-Based Folders

```python
# Helper function in ground_truth_manager.py

def get_kg_specific_paths(kg_name: str) -> Dict[str, str]:
    """Get all paths for a specific KG."""
    
    return {
        "results_dir": f"results/{kg_name}",
        "prompts_dir": f"prompts/{kg_name}",
        "ground_truth_dir": f"ground_truth/{kg_name}",
        "schema_dir": f"data/output/{kg_name}_mschema",
    }

# Usage in pipeline:
kg_name = detect_kg()  # → "copypu"
paths = get_kg_specific_paths(kg_name)

# Automatically create directories if they don't exist
for path in paths.values():
    os.makedirs(path, exist_ok=True)

# Use paths throughout:
results_file = os.path.join(paths["results_dir"], timestamp)
gt_folder = paths["ground_truth_dir"]
```

### 3. Auto-Create Evaluation Results Folders

```python
# In results_organizer.py

def organize_evaluation_result(kg_name: str, model_name: str, eval_data: dict):
    """Organize evaluation by KG+Model."""
    
    # Auto-create folder structure
    eval_root = "evaluation_results"
    eval_folder = os.path.join(eval_root, f"{kg_name}_{model_name}")
    
    os.makedirs(f"{eval_folder}/ground_truth", exist_ok=True)
    os.makedirs(f"{eval_folder}/results", exist_ok=True)
    os.makedirs(f"{eval_folder}/evaluation", exist_ok=True)
    
    # Create symbolic links (or copy) existing folders
    # This way evaluation_results/{kg}_{model}/ has all the data
    # without duplicating files
    
    # Option A: Copy files
    copy_tree(f"ground_truth/{kg_name}", f"{eval_folder}/ground_truth")
    copy_tree(f"results/{kg_name}", f"{eval_folder}/results")
    
    # Option B: Symbolic links (smarter - no duplication)
    os.symlink(
        os.path.abspath(f"ground_truth/{kg_name}"),
        f"{eval_folder}/ground_truth",
        target_is_directory=True
    )
    
    # Save evaluation results
    save_evaluation(f"{eval_folder}/evaluation", eval_data)
    
    # Generate summary
    generate_summary(f"{eval_folder}/summary.json", eval_data)
```

---

## 📂 Data Flow with New Structure

```
┌─────────────────────────────────────────────────┐
│ USER STARTS GUI (Without config change needed!)│
├─────────────────────────────────────────────────┤
│ "Select schema: Copypu [Dropdown]"              │
│ "Ask question: What are all products?"          │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
    System detects: KG="copypu", Model="gemini"
                 │
         ┌───────┴────────┐
         │                │
    Create folders:   Use existing folders:
    (If not exist)    (For data)
         │                │
         ▼                ▼
    /results/          /ground_truth/
    /copypu/           /copypu/
                       (Read questions)
         │                │
         └────────┬───────┘
                  │
        ▼─────────▼──────────▼
        Save results        Load GT
        /results/copypu/    /ground_truth/copypu/
        (new file)          (existing files)
                 │                  │
                 └────────┬─────────┘
                          │
                    ▼─────────▼──────────▼
                    Auto-evaluate
                    (Compare results vs GT)
                          │
                          ▼
                    /evaluation_results/
                    /copypu_gemini/
                    └── /evaluation/
                        ├── eval_q001_eval.json
                        ├── eval_q002_eval.json
                        └── summary.json
```

---

## 🎮 User Workflow (Simplified!)

### Before (Had to edit config.yaml each time)
```
1. Edit config.yaml
   kg.name = "copypu"
   llm.provider = "gemini"

2. Run GUI

3. Ask 50 questions

4. Go back to step 1, change config

5. Run GUI again for different model/KG
```

### After (Auto-detection!)
```
1. Run GUI (No config editing!)
   └─ Selects schema from dropdown (auto-detected)
   └─ LLM provider from last session (remembered)

2. Ask 50 questions
   └─ Results auto-saved to: /results/copypu/
   └─ Evaluation auto-saved to: /evaluation_results/copypu_gemini/

3. Run GUI again (Just ask different KG)
   └─ Select different schema from dropdown
   └─ Ask 50 questions
   └─ Results auto-saved to: /results/dbpedia/
   └─ Evaluation auto-saved to: /evaluation_results/dbpedia_gemini/

4. Analyze all at once!
   python organized_evaluation.py
   python generate_comparison_plots.py
```

---

## 🚀 Implementation Steps

### Step 1: Create Folder Structure
```bash
mkdir -p config/
mkdir -p data/input data/output
mkdir -p results/
mkdir -p prompts/
mkdir -p ground_truth/
mkdir -p evaluation_results/
mkdir -p logs/
mkdir -p cache/embeddings/
mkdir -p tests/
```

### Step 2: Update Ground Truth Manager
```python
# ground_truth_manager.py

class GroundTruthManager:
    def __init__(self, kg_name: str = None):
        """Initialize with optional kg_name for auto-folder detection."""
        self.kg_name = kg_name or self.detect_kg()
        self.kg_dir = f"ground_truth/{self.kg_name}"
        os.makedirs(self.kg_dir, exist_ok=True)
    
    @staticmethod
    def detect_kg() -> str:
        """Auto-detect KG from schema or config."""
        # Logic here
        pass
    
    def get_ground_truth_files(self):
        """Get all GT files for this KG."""
        return glob(f"{self.kg_dir}/*.json")
```

### Step 3: Update Pipeline
```python
# pipeline.py

class NL2SPARQLPipeline:
    def __init__(self, kg_name: str = None):
        """Initialize with auto-detected KG."""
        self.kg_name = kg_name or self.detect_kg()
        self.results_dir = f"results/{self.kg_name}"
        self.prompts_dir = f"prompts/{self.kg_name}"
        os.makedirs(self.results_dir, exist_ok=True)
        os.makedirs(self.prompts_dir, exist_ok=True)
```

### Step 4: Update GUI/CLI
```python
# gui_v2.py

class NL2SPARQLGUI:
    def __init__(self):
        self.available_kgs = self.scan_kgs()
        # Show dropdown: user selects from available KGs
    
    def scan_kgs(self) -> List[str]:
        """Scan /data/input/ and /data/output/ for available KGs."""
        kgs = []
        for ttl_file in glob("data/input/*.ttl"):
            kg_name = os.path.basename(ttl_file).replace(".ttl", "")
            kgs.append(kg_name)
        return kgs
    
    def run(self):
        kg_name = self.kg_dropdown.selectedItem()  # User selects
        pipeline = NL2SPARQLPipeline(kg_name=kg_name)
        # ... rest of pipeline
```

### Step 5: Move config.yaml (Optional)
```bash
# Option A: Keep at root (current)
mv config.yaml config.yaml

# Option B: Move to /config/ (cleaner)
mkdir -p config/
mv config.yaml config/config.yaml

# Then update references:
# config = load_config('config/config.yaml')
```

---

## 📊 Example: Running Full Evaluation

### Session 1: Copypu + Gemini
```bash
python run_gui.py

Select schema: copypu
LLM: gemini
Ask 50 questions...

Results created automatically:
├── /results/copypu/
│   ├── result_*.json (50 files)
├── /ground_truth/copypu/
│   ├── gt_*.json (50 files - reference)
└── /evaluation_results/copypu_gemini/
    ├── /ground_truth/ → (links to /ground_truth/copypu/)
    ├── /results/ → (links to /results/copypu/)
    ├── /evaluation/
    │   └── eval_*_eval.json (50 files)
    └── summary.json (F1=0.35)
```

### Session 2: Copypu + Mistral
```bash
python run_gui.py

Select schema: copypu
LLM: mistral (auto-remembered or dropdown)
Ask 50 questions...

Results created automatically:
└── /evaluation_results/copypu_mistral/
    ├── /ground_truth/ → (same as copypu_gemini)
    ├── /results/ → (new results for mistral)
    ├── /evaluation/ (new evaluations)
    └── summary.json (F1=0.32)
```

### Session 3: Analyze
```bash
python organized_evaluation.py

Output:
  copypu + gemini:   F1=0.3512 ✅ BEST
  copypu + mistral:  F1=0.3245

python generate_comparison_plots.py

Output:
  comparison_kg_model_matrix.png
  comparison_per_kg_models.png
  etc.
```

---

## ✅ Benefits of This Structure

✅ **Professional** - Industry-standard project layout
✅ **Auto-Detection** - No manual config changes needed
✅ **Clean Separation** - Each logical concern has its folder
✅ **Easy Scaling** - Add new KGs without changing code
✅ **Easy Comparison** - Results organized for comparison
✅ **No Duplication** - Symbolic links reduce storage
✅ **Documentation** - Structure is self-documenting
✅ **Easy Navigation** - Users know where everything is

---

## 🔧 Which Files Need Updates?

| File | Update | Reason |
|------|--------|--------|
| `pipeline.py` | Auto-detect KG, create KG-folders | Core change |
| `gui_v2.py` | Show KG selector dropdown | User interface |
| `cli.py` | Add --kg argument | CLI option |
| `ground_truth_manager.py` | Use KG-based paths | GT management |
| `results_organizer.py` | Update folder paths | Organization |
| `organized_evaluation.py` | Update to new paths | Analysis tool |
| `show_evaluation_structure.py` | Update to new paths | Status tool |
| `config.yaml` | Move to /config/ (optional) | Organization |

---

## 🎯 Implementation Priority

1. **HIGH**: Create folder structure manually
2. **HIGH**: Update pipeline.py to detect KG & create folders
3. **HIGH**: Update gui_v2.py to show KG selector
4. **MEDIUM**: Update ground_truth_manager.py for KG paths
5. **MEDIUM**: Test end-to-end workflow
6. **LOW**: Move config.yaml to /config/ subfolder
7. **LOW**: Update analysis tools for new paths

---

## Summary

**Before**: Manual config.yaml edits for each KG/Model combo
**After**: Auto-detection + automatic folder organization by KG

Structure becomes:
- `/results/copypu/` - All Copypu results
- `/ground_truth/copypu/` - All Copypu ground truth
- `/evaluation_results/copypu_gemini/` - All evaluations for copypu+gemini combo
- `/evaluation_results/copypu_mistral/` - All evaluations for copypu+mistral combo

Much cleaner, more professional, and way easier to use! 🚀
