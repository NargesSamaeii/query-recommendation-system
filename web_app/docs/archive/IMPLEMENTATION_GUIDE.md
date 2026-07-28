# Implementation Guide: Professional KG-Based Folder Structure

## 🚀 Quick Implementation (Pick One Approach)

### Approach 1: Auto-Detection from Schema
The system detects which KG you're using by looking at what schema is loaded, then automatically creates the right folders.

### Approach 2: GUI Selection
Add a dropdown in GUI to select KG, system remembers it and uses it for folder organization.

---

## Step 1: Create Folder Structure

```bash
# PowerShell
mkdir config
mkdir data\input
mkdir data\output
mkdir results
mkdir prompts
mkdir ground_truth
mkdir evaluation_results
mkdir logs
mkdir cache\embeddings
mkdir tests
```

Result:
```
nl2sparql/
├── config/
├── data/
│   ├── input/              (put .ttl files here)
│   └── output/             (generated m_schema JSON files)
├── results/                (query results, auto-organized by KG)
├── prompts/                (generated prompts, auto-organized by KG)
├── ground_truth/           (Q&A pairs, auto-organized by KG)
├── evaluation_results/     (metrics, auto-organized by KG_Model)
├── logs/
├── cache/
├── tests/
├── nl2sparql/              (source code - already exists)
└── [docs, scripts, config]
```

---

## Step 2: Update ground_truth_manager.py

Add helper functions to detect KG and get KG-specific paths:

```python
# Add to ground_truth_manager.py (top of file)

import os
import glob
from pathlib import Path

def detect_kg_from_schema() -> str:
    """Auto-detect KG from available schema files."""
    
    # Look for generated m_schema files
    schema_files = glob.glob("data/output/*_mschema.json")
    if schema_files:
        # Get first schema found
        schema_name = os.path.basename(schema_files[0])
        kg_name = schema_name.replace("_mschema.json", "")
        return kg_name
    
    # If no schema found, look for input TTL files
    ttl_files = glob.glob("data/input/*.ttl")
    if ttl_files:
        ttl_name = os.path.basename(ttl_files[0])
        kg_name = ttl_name.replace(".ttl", "")
        return kg_name
    
    # Default fallback
    return "copypu"


def get_kg_paths(kg_name: str) -> dict:
    """Get all paths for a specific KG."""
    return {
        "results_dir": f"results/{kg_name}",
        "prompts_dir": f"prompts/{kg_name}",
        "ground_truth_dir": f"ground_truth/{kg_name}",
        "schema_dir": f"data/output/{kg_name}_mschema",
    }
```

---

## Step 3: Update GroundTruthManager Class

Modify the class to support KG-specific folders:

```python
# In ground_truth_manager.py - GroundTruthManager class

class GroundTruthManager:
    """Manages ground truth for a specific KG."""
    
    def __init__(self, kg_name: str = None):
        """
        Initialize ground truth manager for a KG.
        
        Args:
            kg_name: Knowledge Graph name (e.g., "copypu", "dbpedia").
                    If None, auto-detects from schema or TTL files.
        """
        self.kg_name = kg_name or detect_kg_from_schema()
        self.kg_paths = get_kg_paths(self.kg_name)
        self.ground_truth_dir = self.kg_paths["ground_truth_dir"]
        
        # Create KG-specific folders if they don't exist
        os.makedirs(self.ground_truth_dir, exist_ok=True)
        
        print(f"✅ GroundTruthManager initialized for: {self.kg_name}")
        print(f"   Ground truth folder: {self.ground_truth_dir}/")
```

---

## Step 4: Update EvaluationResultsManager Class

```python
# In ground_truth_manager.py - EvaluationResultsManager class

class EvaluationResultsManager:
    """Manages evaluation results, organized by KG and Model."""
    
    def __init__(self, kg_name: str = None, model_name: str = None):
        """
        Initialize evaluation manager.
        
        Args:
            kg_name: Knowledge Graph name. If None, auto-detects.
            model_name: LLM model name (e.g., "gemini", "mistral").
        """
        self.kg_name = kg_name or detect_kg_from_schema()
        self.model_name = model_name or "default"
        
        # Create KG_Model-specific folder
        self.eval_root = "evaluation_results"
        self.kg_model_dir = os.path.join(
            self.eval_root, 
            f"{self.kg_name}_{self.model_name}"
        )
        
        # Create subfolders
        os.makedirs(f"{self.kg_model_dir}/evaluation", exist_ok=True)
        os.makedirs(f"{self.kg_model_dir}/ground_truth", exist_ok=True)
        os.makedirs(f"{self.kg_model_dir}/results", exist_ok=True)
        
        # Old style for backward compatibility
        self.results_dir = "evaluation_results"
        os.makedirs(self.results_dir, exist_ok=True)
        
        print(f"✅ EvaluationResultsManager initialized")
        print(f"   Organization: {self.kg_name} + {self.model_name}")
        print(f"   Folder: {self.kg_model_dir}/")
    
    def save_evaluation(self, result_filename: str, evaluation: Dict) -> str:
        """Save evaluation to KG_Model-specific folder."""
        
        # Create filename
        eval_filename = result_filename.replace("result_", "eval_").replace(".json", "_eval.json")
        
        # Save to KG_Model-specific folder
        filepath = os.path.join(self.kg_model_dir, "evaluation", eval_filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(evaluation, f, indent=2, ensure_ascii=False)
        
        return filepath
```

---

## Step 5: Update pipeline.py

Add KG detection and pass KG name through the pipeline:

```python
# In pipeline.py - add at top after imports

from nl2sparql.ground_truth_manager import (
    detect_kg_from_schema, 
    get_kg_paths,
    GroundTruthManager,
    EvaluationResultsManager
)

# Then in NL2SPARQLPipeline.__init__()

class NL2SPARQLPipeline:
    def __init__(self, config=None, kg_name: str = None):
        """
        Initialize pipeline.
        
        Args:
            config: Configuration dict
            kg_name: Knowledge Graph name. If None, auto-detects.
        """
        self.config = config or self.load_config()
        self.kg_name = kg_name or detect_kg_from_schema()
        self.kg_paths = get_kg_paths(self.kg_name)
        
        # Create KG-specific folders
        for path in self.kg_paths.values():
            os.makedirs(path, exist_ok=True)
        
        self.logger.info(f"Pipeline initialized for KG: {self.kg_name}")
        
        # ... rest of init ...
```

---

## Step 6: Update GUI to Show KG Selector (Optional)

```python
# In gui_v2.py - add KG selector

def __init__(self):
    # ... existing init code ...
    
    # Add KG selector dropdown
    self.available_kgs = self._scan_available_kgs()
    self.kg_selector = tk.Combobox(
        master,
        values=self.available_kgs,
        state="readonly"
    )
    self.kg_selector.set(self.available_kgs[0] if self.available_kgs else "copypu")
    
    # ... rest of GUI ...

def _scan_available_kgs(self) -> list:
    """Scan for available KGs."""
    kgs = set()
    
    # Check input TTL files
    for ttl in glob.glob("data/input/*.ttl"):
        kg_name = os.path.basename(ttl).replace(".ttl", "")
        kgs.add(kg_name)
    
    # Check generated schemas
    for schema in glob.glob("data/output/*_mschema"):
        kg_name = os.path.basename(schema).replace("_mschema", "")
        kgs.add(kg_name)
    
    return sorted(list(kgs)) or ["copypu"]

def run_evaluation(self):
    """Run with selected KG."""
    kg_name = self.kg_selector.get()
    pipeline = NL2SPARQLPipeline(kg_name=kg_name)
    # ... run pipeline ...
```

---

## Step 7: Update Analysis Tools

**organized_evaluation.py** - Update paths:

```python
# At start of get_kg_model_combinations()

def get_kg_model_combinations() -> Dict:
    """Get all KG+Model combinations from new folder structure."""
    
    eval_root = "evaluation_results"
    combinations = {}
    
    if not os.path.exists(eval_root):
        print("No evaluations found yet")
        return combinations
    
    # Scan all folders like: copypu_gemini, copypu_mistral, etc.
    for folder in os.listdir(eval_root):
        folder_path = os.path.join(eval_root, folder)
        
        if not os.path.isdir(folder_path):
            continue
        
        # Parse folder name: "copypu_gemini" → kg="copypu", model="gemini"
        if "_" in folder:
            kg, model = folder.rsplit("_", 1)
            combinations[f"{kg}_{model}"] = folder_path
    
    return combinations
```

---

## Step 8: Example Usage

```python
# Before (manual config editing):
# Edit config.yaml: kg.name = "copypu"
# Run GUI
# Results go to: evaluation_results/eval_*.json (mixed)

# After (auto-detection):
# python run_gui.py
# Select: "copypu" from dropdown
# Results automatically go to:
#   /results/copypu/
#   /ground_truth/copypu/  (reference)
#   /evaluation_results/copypu_gemini/
# Next session: select "dbpedia" from dropdown
# Results automatically go to:
#   /results/dbpedia/
#   /evaluation_results/dbpedia_gemini/
```

---

## 🎯 What This Achieves

✅ **No Manual Config Edits** - Just select from GUI dropdown
✅ **Auto Folder Creation** - Creates KG-specific subfolders automatically  
✅ **Professional Structure** - Standard project layout
✅ **Easy Comparison** - Results organized by KG and Model
✅ **Scalable** - Add new KGs without changing code
✅ **Clean** - No messy folder mixing

---

## 📋 Checklist

- [ ] Create folder structure (Step 1)
- [ ] Add KG detection functions to ground_truth_manager.py (Step 2)
- [ ] Update GroundTruthManager class (Step 3)
- [ ] Update EvaluationResultsManager class (Step 4)
- [ ] Update pipeline.py (Step 5)
- [ ] Add GUI KG selector (Step 6 - optional)
- [ ] Update organized_evaluation.py paths (Step 7)
- [ ] Test end-to-end workflow

---

## 🧪 Test It

```python
# Quick test: Run this to see auto-detection

from nl2sparql.ground_truth_manager import detect_kg_from_schema, get_kg_paths

kg = detect_kg_from_schema()
print(f"Detected KG: {kg}")

paths = get_kg_paths(kg)
for name, path in paths.items():
    print(f"  {name}: {path}")
```

Expected output:
```
Detected KG: copypu
  results_dir: results/copypu
  prompts_dir: prompts/copypu
  ground_truth_dir: ground_truth/copypu
  schema_dir: data/output/copypu_mschema
```

---

This implementation makes the system completely **KG-aware** without needing manual config edits! 🚀
