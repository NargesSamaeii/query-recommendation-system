# 🎯 Ground Truth Generation - Complete Guide

## ✅ What's Been Done for You

All **50 ground truth JSON files** have been automatically generated with the following information extracted from `questions.yml`:

✓ Natural language questions  
✓ Expected classes (from schema analysis)  
✓ Expected properties (from schema analysis)  
✓ Extracted entities with IRIs (from SPARQL queries)  
✓ Query type detection (SELECT vs ASK)  
✓ Pre-configured result field names  

---

## 📂 Generated Files Location

```
c:\Users\dhami\nl2sparql\ground_truth\
├── gt_0626d98c.json       ← Question 1
├── gt_d5ee34d4.json       ← Question 2
├── ...
└── gt_7bc9f3d1.json       ← Question 50
```

**Total**: 50 files ready to use

---

## ⏳ What Still Needs to Be Done

The `expected_results` field in each file contains a **placeholder value**:

```json
{
  "question": "Who is our Sensor expert?",
  "expected_results": [
    {
      "result": "value_to_be_filled"  ← NEEDS ACTUAL DATA
    }
  ]
}
```

## 🚀 How to Fill in Results

### Option A: Automatic Population (Recommended)

If you have a SPARQL endpoint running:

```bash
# First, install requests if needed
pip install requests

# Run the population script
C:\Users\dhami\nl2sparql\.venv\Scripts\python.exe populate_ground_truth_results.py ^
    c:\Users\dhami\Downloads\questions.yml ^
    http://localhost:8890/sparql
```

This will:
1. Execute each SPARQL query from questions.yml
2. Capture actual results from your endpoint
3. Automatically populate `expected_results` in all 50 files

**Trial Run** (to see what would happen):
```bash
python populate_ground_truth_results.py questions.yml --trial
```

### Option B: Manual Population

For each ground truth file:

```python
import json
from pathlib import Path

# Load the ground truth
gt_file = Path("ground_truth/gt_b908c380.json")
with open(gt_file, 'r') as f:
    gt = json.load(f)

# Update results
gt["expected_results"] = [
    {"result": "John Smith"},
    {"result": "Jane Doe"}
]

# Save
with open(gt_file, 'w') as f:
    json.dump(gt, f, indent=2)
```

### Option C: Batch Processing

```python
import json
import yaml
from pathlib import Path
from nl2sparql.sparql_executor import SPARQLExecutor

# Load SPARQL queries from questions.yml
with open("questions.yml") as f:
    data = yaml.safe_load(f)

executor = SPARQLExecutor()  # Your executor

for question in data['questions']:
    query = question['query']['sparql']
    results = executor.execute(query)
    
    # Find corresponding ground truth file
    question_text = question['question']['en']
    # ... find and update gt file ...
```

---

## 📋 File Structure Example

Here's what a complete ground truth file looks like:

```json
{
  "question": "Who is our Sensor expert?",
  "question_id": 6,
  "expected_classes": [
    "Employee",
    "ProductCategory"
  ],
  "expected_properties": [
    {
      "class_name": "Employee",
      "relevant_properties": ["areaOfExpertise"]
    },
    {
      "class_name": "ProductCategory",
      "relevant_properties": ["areaOfExpertise"]
    }
  ],
  "expected_entities": {
    "Sensor": "http://ld.company.org/prod-instances/prod-cat-Sensor"
  },
  "expected_results": [
    {"result": "John Smith"},
    {"result": "Jane Doe"},
    {"result": "Bob Johnson"}
  ],
  "key_field": "result",
  "query_type": "SELECT"
}
```

---

## 🔗 How to Use with Evaluation System

Once `expected_results` is filled, the evaluation will work automatically:

```python
from nl2sparql.pipeline import NL2SPARQLPipeline

# Initialize pipeline
pipeline = NL2SPARQLPipeline()

# Run question
result = pipeline.answer_question(
    question="Who is our Sensor expert?",
    schema_file="data/output/copypu_mschema.json"
)

# ✨ Evaluation runs automatically if ground truth exists!

# View metrics
evaluation = result["evaluation"]
print(f"Class extraction F1: {evaluation['stages']['class_extraction']['f1']:.3f}")
print(f"Property extraction F1: {evaluation['stages']['property_extraction']['macro_average']['f1']:.3f}")
print(f"Query execution F1: {evaluation['stages']['query_execution']['f1']:.3f}")
print(f"Overall: {evaluation['overall']['average_f1']:.3f}")
```

---

## 📊 Questions Summary

| # | Question | Classes | Properties | Type |
|---|----------|---------|-----------|------|
| 1 | In which department is Ms. Brant? | Department, Employee | memberOf | SELECT |
| 2 | What is the telephone of Baldwin Dirksen? | Employee | phone | SELECT |
| 3 | Who is the manager of Heinrich Hoch? | Employee, Manager | hasManager | SELECT |
| 4 | What is the email of Sabrina from Marketing? | Department, Employee | email, memberOf | SELECT |
| 5 | Who has expertise in Transistors? | Employee, ProductCategory | areaOfExpertise | SELECT |
| 6 | Who is our Sensor expert? | Employee, ProductCategory | areaOfExpertise | SELECT |
| 7 | Who is the manager of Data Services? | Department, Manager, Employee | memberOf, hasManager | SELECT |
| 8 | Department for Sensor Switch M558? | Department, Hardware | responsibleFor | SELECT |
| 9 | How many Sensor Switches? | Hardware, ProductCategory | hasCategory | SELECT + COUNT |
| 10 | Network expert from Marketing? | Department, ProductCategory, Employee | memberOf, areaOfExpertise | SELECT |
| ... | (40 more) | ... | ... | ... |
| 50 | Most responsible department? | Department, Product | responsibleFor | SELECT + COUNT |

**Key Statistics**:
- Total: 50 questions
- SELECT: 47 questions
- ASK: 3 questions (Q16, Q28, Q33)
- Average classes per question: 2-3
- Complexity range: Simple (1 query) to Complex (subqueries, aggregations)

---

## 🎯 Next Steps

### Immediate (Today)
1. ✅ Ground truth files created
2. **Next**: Execute SPARQL queries to get results
3. **Then**: Populate `expected_results`

### Quick Start (5 min)
```bash
# 1. Populate results automatically
python populate_ground_truth_results.py questions.yml

# 2. Validate all files are ready
python scripts/validate_ground_truth.py

# 3. Run evaluation
python -c "
from nl2sparql.pipeline import NL2SPARQLPipeline
pipeline = NL2SPARQLPipeline()
result = pipeline.answer_question('Who is our Sensor expert?', 'schema.json')
print(f\"F1: {result['evaluation']['overall']['average_f1']:.3f}\")
"
```

### Deep Dive (30 min)
1. Review ground truth files
2. Verify entities are correct
3. Test evaluation system
4. Review F1 scores per stage
5. Identify low-performing areas

---

## 📖 Related Documentation

| Document | Purpose |
|----------|---------|
| [GROUND_TRUTH_GENERATION_REPORT.md](GROUND_TRUTH_GENERATION_REPORT.md) | Detailed generation report |
| [EVALUATION_QUICK_START.md](../EVALUATION_QUICK_START.md) | How to use evaluation system |
| [EVALUATION_DOCUMENTATION.md](../EVALUATION_DOCUMENTATION.md) | Complete metrics reference |
| [START_EVALUATION.md](../START_EVALUATION.md) | 5-minute quick start |

---

## 🛠️ Scripts Reference

### generate_ground_truth.py
**Purpose**: Create ground truth JSON files from questions.yml  
**Status**: ✅ Already run  
**Output**: 50 ground truth files  

### populate_ground_truth_results.py
**Purpose**: Execute SPARQL queries and fill `expected_results`  
**Status**: Ready to run  
**Usage**:
```bash
python populate_ground_truth_results.py questions.yml [endpoint_url]

# Examples:
python populate_ground_truth_results.py questions.yml
python populate_ground_truth_results.py questions.yml http://localhost:8890/sparql
python populate_ground_truth_results.py questions.yml --trial  # Trial run
```

---

## ✨ Sample Ground Truth Files

### Simple Query (Question 2)
```json
{
  "question": "What is the telephone of Baldwin Dirksen?",
  "expected_classes": ["Employee"],
  "expected_properties": [{"class_name": "Employee", "relevant_properties": ["phone"]}],
  "expected_entities": {"Baldwin.Dirksen": "http://ld.company.org/prod-instances/empl-Baldwin.Dirksen%40company.org"},
  "expected_results": [{"result": "+1-555-0123"}],
  "query_type": "SELECT"
}
```

### Complex Query (Question 30)
```json
{
  "question": "Which department have more than 5 employees?",
  "expected_classes": ["Department", "Employee"],
  "expected_properties": [
    {"class_name": "Department", "relevant_properties": ["memberOf", "name"]},
    {"class_name": "Employee", "relevant_properties": ["memberOf", "name"]}
  ],
  "expected_results": [
    {"name": "Engineering", "numEmployees": 12},
    {"name": "Sales", "numEmployees": 8},
    {"name": "Marketing", "numEmployees": 6}
  ],
  "query_type": "SELECT"
}
```

### ASK Query (Question 16)
```json
{
  "question": "Do we have suppliers in Toulouse?",
  "expected_classes": ["Product", "Supplier"],
  "expected_results": [{"result": "true"}],
  "query_type": "ASK"
}
```

---

## ⚠️ Important Notes

### 1. Result Format
- **SELECT**: Returns `{"result": "value"}` or multiple variables like `{"name": "...", "count": "..."}`
- **ASK**: Returns `{"result": "true"}` or `{"result": "false"}`
- **COUNT**: Returns `{"result": "42"}`

### 2. Entity IRIs
- Verify that extracted IRIs match your actual database
- Some entities may need manual correction
- Use the format from your Virtuoso endpoint

### 3. Field Names
The `key_field` is pre-configured based on the SPARQL query:
- Usually `"result"` for single-value queries
- Can be `"name"`, `"count"`, `"email"`, etc. for complex queries

### 4. Multiple Results
For queries returning multiple rows, populate all of them:
```json
"expected_results": [
  {"result": "Value1"},
  {"result": "Value2"},
  {"result": "Value3"}
]
```

---

## 🔄 Workflow Summary

```
questions.yml (50 questions)
         ↓
[generate_ground_truth.py] ← Already done ✓
         ↓
ground_truth/ (50 skeleton files)
         ↓
[SPARQL Endpoint]
         ↓
[populate_ground_truth_results.py] ← Next step
         ↓
ground_truth/ (50 complete files with results)
         ↓
[NL2SPARQL Pipeline]
         ↓
[Automatic Evaluation] ← Results show quality!
         ↓
Precision/Recall/F1 Metrics
```

---

## 📝 Checklist

- [ ] Ground truth files generated (50 files) ✅
- [ ] Review a sample ground truth file
- [ ] Run SPARQL queries to get results
- [ ] Populate `expected_results` in all files
- [ ] Validate all files have real results (not "value_to_be_filled")
- [ ] Run pipeline with ground truth
- [ ] Check evaluation metrics
- [ ] Identify low-performing stages
- [ ] Plan improvements based on metrics

---

## 🎓 Learn More

- [Evaluation System Overview](../EVALUATION_SYSTEM_README.md)
- [Quick Start (5 min)](../EVALUATION_QUICK_START.md)
- [Complete Reference](../EVALUATION_DOCUMENTATION.md)
- [Integration Guide](../EVALUATION_INTEGRATION_GUIDE.md)

---

**Status**: ✅ Ground truth files generated, results pending  
**Generated**: 2025-02-23  
**Next**: Execute SPARQL queries and populate results

