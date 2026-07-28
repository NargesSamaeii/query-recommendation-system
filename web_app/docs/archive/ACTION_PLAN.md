# 🚀 Action Plan: Implement Professional KG-Based Structure

## ✅ What You Get

1. **No more config editing** - Just select from GUI dropdown
2. **Auto-organized folders** - Results automatically go to right place
3. **Professional structure** - Industry-standard project layout
4. **Easy comparison** - Results organized for comparison
5. **Scalable** - Add new KGs without changing code

---

## 📋 Step-by-Step Implementation

### STEP 1: Create Folder Structure (2 minutes)

**In PowerShell, run:**

```powershell
# Create folders
mkdir config
mkdir data\input data\output
mkdir results
mkdir prompts
mkdir ground_truth
mkdir evaluation_results
mkdir logs
mkdir cache\embeddings
mkdir tests

Write-Host "✅ Folder structure created!"
```

**Result:** You'll see these new folders in project root.

### STEP 2: Move Your Data (1 minute)

Organize your existing files:

```powershell
# Move your TTL files to data/input/
Move-Item -Path "copypu.ttl" -Destination "data/input/copypu.ttl" -Force
Move-Item -Path "*.ttl" -Destination "data/input/" -ErrorAction SilentlyContinue

# Move mschema files to data/output/
Move-Item -Path "*_mschema.json" -Destination "data/output/" -ErrorAction SilentlyContinue -Force

Write-Host "✅ Data files organized!"
```

### STEP 3: Add KG Detection to ground_truth_manager.py (5 minutes)

**Find this section in ground_truth_manager.py:**

```python
import os
import json
```

**Add after the imports:**

```python
import glob
from pathlib import Path
```

**Add these functions at the end of the file (before any class):**

```python
def detect_kg_from_schema() -> str:
    """Auto-detect KG from available schema files."""
    
    # Look for generated m_schema files
    schema_files = glob.glob("data/output/*_mschema.json")
    if schema_files:
        schema_name = os.path.basename(schema_files[0])
        kg_name = schema_name.replace("_mschema.json", "")
        return kg_name
    
    # If no schema found, look for input TTL files
    ttl_files = glob.glob("data/input/*.ttl")
    if ttl_files:
        ttl_name = os.path.basename(ttl_files[0])
        kg_name = ttl_name.replace(".ttl", "")
        return kg_name
    
    return "copypu"  # Default fallback


def get_kg_paths(kg_name: str) -> dict:
    """Get all paths for a specific KG."""
    return {
        "results_dir": f"results/{kg_name}",
        "prompts_dir": f"prompts/{kg_name}",
        "ground_truth_dir": f"ground_truth/{kg_name}",
        "schema_dir": f"data/output/{kg_name}_mschema",
    }
```

### STEP 4: Update GroundTruthManager Class (3 minutes)

**Find the `class GroundTruthManager:` section**

**Modify `__init__` method:**

```python
class GroundTruthManager:
    """Manages ground truth for a specific KG."""
    
    def __init__(self, kg_name: str = None):
        """
        Initialize ground truth manager.
        If kg_name not provided, auto-detects from schema.
        """
        # Auto-detect KG if not provided
        self.kg_name = kg_name or detect_kg_from_schema()
        self.kg_paths = get_kg_paths(self.kg_name)
        self.ground_truth_dir = self.kg_paths["ground_truth_dir"]
        
        # Create KG-specific folder if doesn't exist
        os.makedirs(self.ground_truth_dir, exist_ok=True)
        
        # For backward compatibility, also set old path
        self.questions_dir = self.ground_truth_dir
        
        print(f"✓ GroundTruthManager: {self.kg_name}")
        print(f"  Folder: {self.ground_truth_dir}/")
        
        # ... rest of existing __init__ code ...
```

### STEP 5: Update EvaluationResultsManager Class (5 minutes)

**Find the `class EvaluationResultsManager:` section**

**Modify `__init__` method:**

```python
class EvaluationResultsManager:
    """Manages evaluation results, organized by KG and Model."""
    
    def __init__(self, kg_name: str = None, model_name: str = None, results_dir: str = "evaluation_results"):
        """
        Initialize evaluation manager.
        """
        # Auto-detect if not provided
        self.kg_name = kg_name or detect_kg_from_schema()
        self.model_name = model_name or "default"
        
        # Create KG_Model-specific folder structure
        self.eval_root = results_dir
        self.kg_model_dir = os.path.join(
            self.eval_root, 
            f"{self.kg_name}_{self.model_name}"
        )
        
        # Create subfolders
        for subfolder in ["evaluation", "ground_truth", "results"]:
            os.makedirs(os.path.join(self.kg_model_dir, subfolder), exist_ok=True)
        
        # For backward compatibility
        self.results_dir = results_dir
        os.makedirs(self.results_dir, exist_ok=True)
        
        print(f"✓ EvaluationResultsManager: {self.kg_name} + {self.model_name}")
        print(f"  Folder: {self.kg_model_dir}/")
```

**Modify `save_evaluation` method:**

```python
    def save_evaluation(self, result_filename: str, evaluation: Dict) -> str:
        """
        Save evaluation results to KG_Model-specific folder.
        """
        # Create evaluation filename
        eval_filename = result_filename.replace("result_", "eval_").replace(".json", "_eval.json")
        
        # Save to KG_Model folder
        filepath = os.path.join(self.kg_model_dir, "evaluation", eval_filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(evaluation, f, indent=2, ensure_ascii=False)
        
        return filepath
```

### STEP 6: Update pipeline.py (5 minutes)

**At the top of pipeline.py, add to imports:**

```python
import glob  # Add this import
from nl2sparql.ground_truth_manager import (  # Update existing import
    detect_kg_from_schema,
    get_kg_paths,
    GroundTruthManager,
    EvaluationResultsManager
)
```

**Find `class NL2SPARQLPipeline:` - modify `__init__`:**

```python
class NL2SPARQLPipeline:
    def __init__(self, config=None, kg_name: str = None):
        """
        Initialize pipeline.
        
        Args:
            config: Configuration dict
            kg_name: KG name (if None, auto-detects)
        """
        self.config = config or self.load_config()
        
        # Auto-detect KG if not provided
        self.kg_name = kg_name or detect_kg_from_schema()
        self.kg_paths = get_kg_paths(self.kg_name)
        
        # Create KG-specific folders
        for path in self.kg_paths.values():
            os.makedirs(path, exist_ok=True)
        
        self.logger.info(f"Pipeline initialized for KG: {self.kg_name}")
        
        # ... rest of existing init code ...
```

### STEP 7: Test the System (5 minutes)

**Run this quick test:**

```python
# test_kg_detection.py

from nl2sparql.ground_truth_manager import detect_kg_from_schema, get_kg_paths

print("Testing KG detection...")
kg = detect_kg_from_schema()
print(f"✓ Detected KG: {kg}")

paths = get_kg_paths(kg)
print(f"\n✓ KG Paths for '{kg}':")
for name, path in paths.items():
    print(f"  {name}: {path}")
    import os
    if os.path.exists(path):
        print(f"    ✓ Exists")
    else:
        print(f"    ⚠️  Will be created on first use")
```

**Expected output:**
```
✓ Detected KG: copypu
✓ KG Paths for 'copypu':
  results_dir: results/copypu
    Will be created on first use
  prompts_dir: prompts/copypu
    Will be created on first use
  ground_truth_dir: ground_truth/copypu
    ✓ Exists
  schema_dir: data/output/copypu_mschema
    Will be created on first use
```

### STEP 8: Optional - Add GUI KG Selector (10 minutes)

**If you want to add a dropdown to GUI**, modify gui_v2.py to add:

```python
def _scan_available_kgs(self) -> list:
    """Scan for available KGs."""
    kgs = set()
    
    # Check TTL files
    for ttl in glob.glob("data/input/*.ttl"):
        kg_name = os.path.basename(ttl).replace(".ttl", "")
        kgs.add(kg_name)
    
    # Check schemas
    for schema in glob.glob("data/output/*_mschema"):
        kg_name = os.path.basename(schema).replace("_mschema", "")
        kgs.add(kg_name)
    
    return sorted(list(kgs)) or ["copypu"]
```

Then in GUI init:
```python
self.available_kgs = self._scan_available_kgs()
# Add dropdown for KG selection
```

### STEP 9: Test Full Workflow (10 minutes)

**Run one complete test:**

```bash
# Option A: Use GUI
python -m nl2sparql.gui_v2
# Select: copypu from dropdown
# Ask 5 test questions

# Option B: Use CLI
python run_query.py "What are all products?"
```

**Check folder organization:**

```powershell
# See what was created
Get-ChildItem -Path "results/" -Recurse
Get-ChildItem -Path "ground_truth/" -Recurse
Get-ChildItem -Path "evaluation_results/" -Recurse
```

**Expected:**
```
results/copypu/result_*.json
ground_truth/copypu/gt_*.json
evaluation_results/copypu_gemini/evaluation/eval_*.json
```

---

## 📊 Progress Checklist

- [ ] **STEP 1** - Create folder structure
- [ ] **STEP 2** - Move TTL and schema files
- [ ] **STEP 3** - Add KG detection functions
- [ ] **STEP 4** - Update GroundTruthManager
- [ ] **STEP 5** - Update EvaluationResultsManager
- [ ] **STEP 6** - Update pipeline.py
- [ ] **STEP 7** - Run test script
- [ ] **STEP 8** - (Optional) Add GUI selector
- [ ] **STEP 9** - Test full workflow

---

## 🐛 Troubleshooting

### "ImportError: cannot import detect_kg_from_schema"
→ Make sure you added the functions at END of ground_truth_manager.py (before any class definitions)

### "Folder not created"
→ Check your PowerShell path with `pwd`
→ Make sure you're in the nl2sparql root directory

### "Still can't find KG"
→ Verify data/input/ has your .ttl files
→ Run: `ls data/input/` to list them

### "Results still all mixed"
→ Delete evaluation_results/ folder and start fresh
→ Run pipeline again to create new structure

---

## 🎯 Next Steps (After Implementation)

1. **Run full evaluation** (50 questions per KG)
2. **Switch to different KG** by dropdown
3. **Run more evaluations**
4. **Generate reports**: `python organized_evaluation.py`
5. **Generate graphs**: `python generate_comparison_plots.py`

---

## ⏱️ Time Estimate

| Step | Time |
|------|------|
| Create structure | 2 min |
| Move files | 1 min |
| Update code (Pts 3-6) | 18 min |
| Test | 5 min |
| GUI enhancement (optional) | 10 min |
| **Total** | **~40 minutes** |

**Benefit:** Hours saved in future workflows! ⚡

---

## 📚 References

- **PROFESSIONAL_STRUCTURE.md** - Full explanation
- **IMPLEMENTATION_GUIDE.md** - Detailed code guide
- **BEFORE_VS_AFTER.md** - Visual comparison

**Ready?** Start with STEP 1! 🚀
