# Final Professional Project Structure

## 🏗️ Optimized Structure

```
nl2sparql/
│
├── 📋 /config/                      ← Configuration
│   ├── config.yaml
│   └── logging.yaml
│
├── 📚 /data/                        ← Knowledge Graphs & Schemas
│   ├── /input/
│   │   ├── copypu.ttl
│   │   └── dbpedia.ttl
│   └── /output/
│       ├── copypu_mschema.json
│       └── dbpedia_mschema.json
│
├── 🧪 /tests/                       ← ALL Test-Related Files (GROUPED!)
│   │
│   ├── 📁 /prompts/                 ← Generated prompts (organized by KG)
│   │   ├── /copypu/
│   │   │   ├── prompt_class_extraction.txt
│   │   │   ├── prompt_property_extraction.txt
│   │   │   └── prompt_query_generation.txt
│   │   └── /dbpedia/
│   │       └── ...
│   │
│   ├── 📁 /results/                 ← Query execution results (organized by KG)
│   │   ├── /copypu/
│   │   │   ├── result_20260225_101530.json
│   │   │   └── ... (50+ files)
│   │   └── /dbpedia/
│   │       └── ...
│   │
│   ├── 📁 /ground_truth/            ← Q&A pairs (organized by KG)
│   │   ├── /copypu/
│   │   │   ├── gt_q001.json
│   │   │   └── ... (50+ files)
│   │   └── /dbpedia/
│   │       └── ...
│   │
│   ├── 📁 /extractions/             ← Extracted classes & properties (by KG)
│   │   ├── /copypu/
│   │   │   ├── classes_copypu.json
│   │   │   └── properties_copypu.json
│   │   └── /dbpedia/
│   │       └── ...
│   │
│   ├── 🐍 Python Test Files
│   │   ├── test_pipeline.py         ← Tests for pipeline
│   │   ├── test_evaluation_system.py ← Tests for evaluation
│   │   ├── test_gui_v2.py           ← Tests for GUI
│   │   └── __init__.py
│   │
│   └── 📖 README.md                 ← How to use /tests/ folder
│
├── 📊 /evaluation_results/          ← Evaluation Metrics (organized by KG_Model)
│   ├── /copypu_gemini/
│   │   ├── /ground_truth/ → (linked to tests/ground_truth/copypu/)
│   │   ├── /results/ → (linked to tests/results/copypu/)
│   │   ├── /evaluation/
│   │   │   └── eval_*.json (50+ files)
│   │   └── summary.json
│   ├── /copypu_mistral/
│   │   └── ...
│   └── (PNG comparison graphs)
│
├── 📜 /logs/                        ← Application logs
│   └── nl2sparql.log
│
├── ⚙️ /cache/                       ← Cache files
│   └── /embeddings/
│       └── embeddings_*.npz
│
├── 🐍 /nl2sparql/                   ← Source Code
│   ├── __init__.py
│   ├── pipeline.py
│   ├── gui_v2.py
│   ├── cli.py
│   ├── sparql_generator.py
│   ├── llm_interface.py
│   ├── ground_truth_manager.py
│   ├── schema_parser.py
│   ├── class_evaluator.py
│   ├── property_evaluator.py
│   └── __pycache__/
│
├── 📊 Analysis & Reporting Tools
│   ├── organized_evaluation.py
│   ├── generate_comparison_plots.py
│   ├── show_evaluation_structure.py
│   └── results_organizer.py
│
├── 📚 Documentation
│   ├── README.md
│   ├── QUICK_REFERENCE.md
│   ├── PROFESSIONAL_STRUCTURE.md
│   ├── BEFORE_VS_AFTER.md
│   ├── ACTION_PLAN.md
│   ├── IMPLEMENTATION_GUIDE.md
│   └── [other docs]
│
├── 🎯 Entry Points
│   ├── run_gui.py
│   ├── run_query.py
│   └── run_evaluation.py
│
├── 📦 Setup
│   ├── config.yaml (or move to config/)
│   ├── requirements.txt
│   ├── setup.py
│   ├── .gitignore
│   └── LICENSE
│
└── 📝 Other
    └── [CHANGELOG, README files, etc]
```

---

## 🎯 Key Improvements

### Before (Messy)
```
nl2sparql/
├── results/              ← Top level, mixed with everything
├── prompts/              ← Top level
├── ground_truth/         ← Top level
├── extractions/          ← Top level
├── test_pipeline.py      ← Top level scripts
├── test_gui_v2.py        ← Scattered around
└── [40+ other files]
```

### After (Clean & Professional)
```
nl2sparql/
├── tests/                ← All test stuff grouped
│   ├── /prompts/
│   ├── /results/
│   ├── /ground_truth/
│   ├── /extractions/
│   ├── test_pipeline.py
│   ├── test_gui_v2.py
│   └── README.md
├── evaluation_results/   ← Evaluation metrics (separate)
├── data/                 ← Input data
├── nl2sparql/            ← Source code
└── [root level scripts]
```

✅ **Organization is crystal clear**
✅ **All testing in one place**
✅ **Easy to .gitignore**
✅ **Professional structure**

---

## 📋 Implementation Steps

### STEP 1: Create /tests/ Folder Structure

```powershell
# Create main tests folder
mkdir tests
mkdir tests\prompts
mkdir tests\results
mkdir tests\ground_truth
mkdir tests\extractions

# Create subfolders for each KG (example)
mkdir tests\prompts\copypu
mkdir tests\results\copypu
mkdir tests\ground_truth\copypu
mkdir tests\extractions\copypu

Write-Host "✅ /tests/ folder structure created!"
```

### STEP 2: Move Test Data

```powershell
# Move prompts
Move-Item -Path "prompts\*" -Destination "tests\prompts\" -Force -ErrorAction SilentlyContinue

# Move results
Move-Item -Path "results\*" -Destination "tests\results\" -Force -ErrorAction SilentlyContinue

# Move ground truth
Move-Item -Path "ground_truth\*" -Destination "tests\ground_truth\" -Force -ErrorAction SilentlyContinue

# Move extractions
Move-Item -Path "extractions\*" -Destination "tests\extractions\" -Force -ErrorAction SilentlyContinue

# Remove old folders
Remove-Item -Path "prompts" -Force -Recurse -ErrorAction SilentlyContinue
Remove-Item -Path "results" -Force -Recurse -ErrorAction SilentlyContinue
Remove-Item -Path "ground_truth" -Force -Recurse -ErrorAction SilentlyContinue
Remove-Item -Path "extractions" -Force -Recurse -ErrorAction SilentlyContinue

Write-Host "✅ Data moved to /tests/"
```

### STEP 3: Move Test Python Files

```powershell
# Move test files to /tests/
Move-Item -Path "test_pipeline.py" -Destination "tests\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "test_gui_v2.py" -Destination "tests\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "test_evaluation_system.py" -Destination "tests\" -Force -ErrorAction SilentlyContinue

# Any other test files
Move-Item -Path "test_*.py" -Destination "tests\" -Force -ErrorAction SilentlyContinue

# Create __init__.py for tests module
New-Item -Path "tests\__init__.py" -Type File

Write-Host "✅ Test files moved to /tests/"
```

### STEP 4: Update Code to Use New Paths

Update all references in Python files:

**In ground_truth_manager.py:**
```python
# OLD:
self.ground_truth_dir = "ground_truth"

# NEW:
self.ground_truth_dir = "tests/ground_truth"
```

**In pipeline.py:**
```python
# OLD:
self.results_dir = "results"
self.prompts_dir = "prompts"
self.extractions_dir = "extractions"

# NEW:
self.results_dir = "tests/results"
self.prompts_dir = "tests/prompts"
self.extractions_dir = "tests/extractions"
```

**In other files:**
```python
# Search and replace:
"results/" → "tests/results/"
"prompts/" → "tests/prompts/"
"ground_truth/" → "tests/ground_truth/"
"extractions/" → "tests/extractions/"
```

### STEP 5: Update KG Path Detection

In ground_truth_manager.py:

```python
def get_kg_paths(kg_name: str) -> dict:
    """Get all paths for a specific KG."""
    return {
        "results_dir": f"tests/results/{kg_name}",           # Changed
        "prompts_dir": f"tests/prompts/{kg_name}",          # Changed
        "ground_truth_dir": f"tests/ground_truth/{kg_name}", # Changed
        "schema_dir": f"data/output/{kg_name}_mschema",
        "extractions_dir": f"tests/extractions/{kg_name}",  # Changed
    }
```

### STEP 6: Create tests/README.md

```markdown
# Tests Folder (/tests/)

This folder contains all test-related files and data.

## Structure

### Data Folders (organized by Knowledge Graph)

- **prompts/** - Generated prompts for each KG
- **results/** - Query execution results for each KG
- **ground_truth/** - Q&A reference pairs for each KG
- **extractions/** - Extracted classes/properties for each KG

### Test Files

- test_pipeline.py - Pipeline tests
- test_evaluation_system.py - Evaluation system tests
- test_gui_v2.py - GUI tests

## Usage

### Running Tests

```bash
cd tests
python -m pytest test_pipeline.py
python -m pytest test_evaluation_system.py
python -m pytest test_gui_v2.py
```

### Adding New Tests

1. Create test_*.py file in this folder
2. Use pytest conventions
3. Run with: python -m pytest test_*.py

### Organizing Data

Data is automatically organized by KG:
```
tests/
├── results/copypu/          ← Copypu results
├── results/dbpedia/         ← DBpedia results
├── ground_truth/copypu/     ← Copypu Q&A pairs
├── ground_truth/dbpedia/    ← DBpedia Q&A pairs
└── ...
```

## Related Folders

- **evaluation_results/** - Evaluation metrics (KG_Model combinations)
- **data/input/** - Input KG files
- **data/output/** - Generated schemas
```

### STEP 7: Update .gitignore

```
# Ignore test data (can be regenerated)
tests/results/**/*.json
tests/prompts/**/*.txt
tests/extractions/**/*.json

# But keep structure
!tests/results/.gitkeep
!tests/prompts/.gitkeep
!tests/extractions/.gitkeep
!tests/ground_truth/.gitkeep

# Keep test Python files
!tests/test_*.py
!tests/__init__.py
```

### STEP 8: Verify Everything Works

```powershell
# Check that old paths don't exist anymore
Test-Path "prompts"      # Should be False
Test-Path "results"      # Should be False
Test-Path "ground_truth" # Should be False
Test-Path "extractions"  # Should be False

# Check new paths exist
Test-Path "tests"        # Should be True
Test-Path "tests\results" # Should be True

# Run a test
cd tests
python test_pipeline.py
```

---

## 📁 Reference: All Path Changes

Update these patterns in your code:

| Old Path | New Path | Location |
|----------|----------|----------|
| `"results/"` | `"tests/results/"` | Everywhere |
| `"prompts/"` | `"tests/prompts/"` | Everywhere |
| `"ground_truth/"` | `"tests/ground_truth/"` | Everywhere |
| `"extractions/"` | `"tests/extractions/"` | Everywhere |
| `results_dir = "results"` | `results_dir = "tests/results"` | pipeline.py |
| `prompts_dir = "prompts"` | `prompts_dir = "tests/prompts"` | pipeline.py |
| `self.questions_dir = ...` | Update to use `tests/ground_truth/...` | ground_truth_manager.py |

---

## 🎯 Benefits

✅ **Professional** - Standard test directory structure
✅ **Organized** - Everything in one place
✅ **Clean root** - Uncluttered project root
✅ **Easy gitignore** - Can ignore all test data easily
✅ **Scalable** - Easy to add more KGs
✅ **Clear separation** - Tests separate from deployment

---

## 🔄 Data Flow (Updated)

```
Pipeline runs
    ↓
Detects KG: "copypu"
    ↓
Creates paths:
  - tests/results/copypu/
  - tests/prompts/copypu/
  - tests/ground_truth/copypu/
  - tests/extractions/copypu/
    ↓
Saves test data → tests/results/copypu/result_*.json
    ↓
Loads ground truth → tests/ground_truth/copypu/gt_*.json
    ↓
Evaluates and saves → evaluation_results/copypu_gemini/evaluation/
```

---

## ✅ Final Structure Checklist

After implementation:

- [ ] `/tests/` folder created
- [ ] `/tests/prompts/` with KG subfolders
- [ ] `/tests/results/` with KG subfolders
- [ ] `/tests/ground_truth/` with KG subfolders
- [ ] `/tests/extractions/` with KG subfolders
- [ ] Test Python files moved to `/tests/`
- [ ] `/tests/__init__.py` created
- [ ] `/tests/README.md` created
- [ ] Old folders (prompts, results, ground_truth, extractions) deleted
- [ ] Code paths updated
- [ ] .gitignore updated
- [ ] All tests pass
- [ ] Project root is clean

---

## 🚀 Why This Matters

**Before (Chaotic):**
```
nl2sparql/
├── test_pipeline.py          ← Where did this come from?
├── test_gui_v2.py            ← Why is this here?
├── prompts/                  ← Test data?
├── results/                  ← Test data?
├── ground_truth/             ← Test data?
├── extractions/              ← Test data?
├── [actual source code]
├── [documentation]
└── [config files]
```

**After (Professional):**
```
nl2sparql/
├── tests/                    ← All test stuff here
│   ├── prompts/
│   ├── results/
│   ├── ground_truth/
│   ├── extractions/
│   ├── test_pipeline.py
│   ├── test_gui_v2.py
│   └── README.md
├── evaluation_results/       ← Evaluation metrics
├── data/                     ← Input data
├── nl2sparql/                ← Source code
└── [clean root]              ← No test clutter
```

Crystal clear! ✨

---

## 🎯 Priority

1. **HIGH** - Create /tests/ structure
2. **HIGH** - Move files
3. **HIGH** - Update paths in code
4. **MEDIUM** - Update .gitignore
5. **LOW** - Create tests/README.md

---

## 💡 Pro Tip

After moving, keep your old folders backed up for 1 day, just in case:
```powershell
# Backup just in case
mkdir _backup_old_structure
Copy-Item -Path "tests" -Destination "_backup_old_structure" -Recurse

# After verifying everything works for a day:
Remove-Item -Path "_backup_old_structure" -Recurse
```

This is a **huge improvement** for project cleanliness! 🎉
