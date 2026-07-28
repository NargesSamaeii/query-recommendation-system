# How the Text2SPARQL Evaluation System Works

## 📊 Evaluation Overview

The evaluation system uses **Set-based precision, recall, and F1-score** metrics to compare generated SPARQL queries against expected results. Here's how it works:

```
Question (NL)
    ↓
[LLM + RAG] → Generated SPARQL Query
    ↓
Execute on SPARQL Endpoint → Generated Results
    ↓
Compare with Expected Results (Ground Truth)
    ↓
Calculate Metrics: Precision, Recall, F1-score
```

---

## 🎯 Core Metrics

### 1. **Set-based Evaluation**

Instead of exact query matching, the system evaluates **result sets**:

```python
Expected Results = {result1, result2, result3}
Generated Results = {result1, result2, result4}

True Positives (TP) = {result1, result2}  # Correctly returned
False Positives (FP) = {result4}  # Incorrectly returned
False Negatives (FN) = {result3}  # Should have been returned
```

### 2. **Precision** (Out of what we returned, how much is correct?)
```
Precision = TP / (TP + FP)
          = 2 / (2 + 1) 
          = 0.667 (66.7%)
```

### 3. **Recall** (Out of what should be returned, how much did we get?)
```
Recall = TP / (TP + FN)
       = 2 / (2 + 1)
       = 0.667 (66.7%)
```

### 4. **F1-Score** (Harmonic mean of Precision & Recall)
```
F1 = 2 × (Precision × Recall) / (Precision + Recall)
   = 2 × (0.667 × 0.667) / (0.667 + 0.667)
   = 0.667 (66.7%)
```

---

## 🔄 Evaluation Pipeline

### Step 1: **Question & Ground Truth Loading**
```yaml
questions.yml:
  - id: 1
    question: "In which department is Ms. Brant?"
    query:
      sparql: |
        PREFIX pv: <http://ld.company.org/prod-vocab/>
        SELECT DISTINCT ?result
        WHERE {
          <http://ld.company.org/prod-instances/empl-Karen.Brant%40company.org> 
          pv:memberOf ?result .
        }

ground_truth (gt_*.json):
  expected_results: [
    {"result": "http://ld.company.org/prod-instances/dept-73191"}
  ]
```

### Step 2: **Query Generation** (by LLM)
```
Input Question: "In which department is Ms. Brant?"
↓
[LLM with RAG context]
↓
Output SPARQL (varies based on LLM capability)
```

### Step 3: **Execution**
```bash
# Expected query execution
curl -X GET "http://localhost:8890/sparql" \
  --data-urlencode "query=PREFIX pv: <http://ld.company.org/prod-vocab/> ..."
  
# Returns:
{
  "results": {
    "bindings": [
      {"result": {"value": "http://ld.company.org/prod-instances/dept-73191"}}
    ]
  }
}
```

### Step 4: **Result Extraction**
```python
expected_results = {"http://ld.company.org/prod-instances/dept-73191"}
generated_results = {"http://ld.company.org/prod-instances/dept-73191"}

TP = 1, FP = 0, FN = 0
Precision = 1/1 = 1.0
Recall = 1/1 = 1.0
F1 = 1.0  ✓
```

### Step 5: **Aggregation**
```
For all 50 questions:
├─ Q1: F1 = 1.0
├─ Q2: F1 = 0.9
├─ Q3: F1 = 0.85
├─ ...
└─ Q50: F1 = 0.8

Average F1 = 0.87 (87%)
```

---

## 📋 Evaluation Data Structure

### Input: questions.yml
```yaml
questions:
  - id: 1
    question:
      en: "In which department is Ms. Brant?"
    features: [SELECT]
    classes: [:Department, :Employee]
    properties: [:memberOf]
    query:
      sparql: "PREFIX pv: ... SELECT DISTINCT ?result ..."
```

### Ground Truth: gt_*.json
```json
{
  "question": "In which department is Ms. Brant?",
  "question_id": 1,
  "expected_classes": ["Department", "Employee"],
  "expected_properties": [{...}],
  "expected_entities": {...},
  "expected_results": [
    {"result": "http://ld.company.org/prod-instances/dept-73191"}
  ],
  "key_field": "result",
  "query_type": "SELECT"
}
```

### Output: evaluation_results.json
```json
{
  "question_id": 1,
  "question": "In which department is Ms. Brant?",
  "expected_results_count": 1,
  "generated_results_count": 1,
  "true_positives": 1,
  "false_positives": 0,
  "false_negatives": 0,
  "precision": 1.0,
  "recall": 1.0,
  "f1_score": 1.0,
  "execution_time_ms": 234
}
```

---

## 🔧 Evaluation Workflow (from Text2SPARQL)

### 1. **Ask Phase** (Generate SPARQL)
```bash
text2sparql ask --answers-db cache.db \
  -o queries.json \
  questions_ck25.yaml \
  http://localhost:8765  # API endpoint
```

**Output:** `queries.json`
```json
{
  "questions": [
    {
      "id": 1,
      "question": "In which department is Ms. Brant?",
      "generated_sparql": "PREFIX pv: ... SELECT ...",
      "generation_time": 1.23
    }
  ]
}
```

### 2. **Evaluate Phase** (Compare Results)
```bash
text2sparql evaluate \
  -e http://localhost:8890/sparql \
  -o results.json \
  ExpasyGPT \
  questions_ck25.yaml \
  queries.json
```

**What happens:**
1. Load expected results from `questions_ck25.yaml` ground truth
2. Execute each generated SPARQL query against endpoint
3. Compare result sets using set-based metrics
4. Calculate Precision, Recall, F1-score
5. Aggregate across all questions

**Output:** `results.json`
```json
{
  "average": {
    "set_F": 0.87,
    "set_precision": 0.89,
    "set_recall": 0.85
  },
  "questions": [
    {
      "id": 1,
      "f1_score": 1.0,
      "precision": 1.0,
      "recall": 1.0
    }
  ]
}
```

---

## 🏆 Metric Interpretation

| F1 Score | Interpretation |
|----------|----------------|
| 0.90-1.0 | Excellent - Query generation is nearly perfect |
| 0.70-0.89 | Good - Most queries generate correct results |
| 0.50-0.69 | Fair - About half the queries are correct |
| 0.30-0.49 | Poor - Many queries fail or return wrong results |
| 0.00-0.29 | Very Poor - System is not working effectively |

---

## 🎚️ Multi-Level Evaluation

Your NL2SPARQL system evaluates at **4 stages**:

### Stage 1: Class Extraction
```
Question: "Who is our Sensor expert?"
↓
Expected Classes: [Employee, ProductCategory]
Generated Classes: [Employee, ProductCategory, Hardware]  ← Could be wrong
↓
F1_class = calculate_metrics(expected, generated)
```

### Stage 2: Property Extraction
```
Question: "Who is our Sensor expert?"
↓
Expected Properties: {Employee: [areaOfExpertise]}
Generated Properties: {Employee: [areaOfExpertise, department]}  ← Could be wrong
↓
F1_property = calculate_metrics(expected, generated)
```

### Stage 3: Entity Recognition
```
Question: "Who is our Sensor expert?"
↓
Expected Entities: {Sensor: IRI}
Generated Entities: {Sensor: IRI}  ← Could extract wrong IRI
↓
F1_entity = calculate_metrics(expected, generated)
```

### Stage 4: Query Execution
```
Question: "Who is our Sensor expert?"
Total Expected Results: 7 employees
↓
[Execute SPARQL Query]
↓
Generated Results: 7 employees
↓
Set-based F1 = calculate_metrics(expected, generated)
```

### Overall Score
```
Average F1 = Mean(F1_class, F1_property, F1_entity, F1_query)
```

---

## 📊 Example Evaluation Output

```
50 Questions Evaluated:
==============================================================================

Question 1: In which department is Ms. Brant?
├─ Class Extraction F1: 1.0 ✓
├─ Property Extraction F1: 1.0 ✓
├─ Entity Recognition F1: 1.0 ✓
├─ Query Execution F1: 1.0 ✓
└─ Overall F1: 1.0

Question 5: Who has expertise in Transistors?
├─ Class Extraction F1: 1.0 ✓
├─ Property Extraction F1: 1.0 ✓
├─ Entity Recognition F1: 1.0 ✓
├─ Query Execution F1: 0.85 (⚠️ returned 4, expected 4, but 1 false positive)
└─ Overall F1: 0.96

Question 12: Which suppliers available to deliver Compensators?
├─ Class Extraction F1: 0.8 ⚠️
├─ Property Extraction F1: 0.7 ⚠️
├─ Entity Recognition F1: 1.0 ✓
├─ Query Execution F1: 0.65 (returned 85, expected 90, recall issue)
└─ Overall F1: 0.79

==============================================================================

SUMMARY:
┌─────────────────────────────────┐
│ Average F1 Score: 0.87 (87%)   │
│ Min: 0.45  │  Max: 1.0         │
│ Std Dev: 0.14                   │
└─────────────────────────────────┘

BREAKDOWN BY STAGE:
├─ Class Extraction:    F1 = 0.92
├─ Property Extraction: F1 = 0.89
├─ Entity Recognition:  F1 = 0.95
└─ Query Execution:     F1 = 0.84

AREAS FOR IMPROVEMENT:
├─ Property Extraction (F1=0.89) - Focus on relationship properties
├─ Query Execution (F1=0.84) - Complex filters and aggregations
└─ Fallback handling - Only 2 failures, but critical questions
```

---

## 🔌 Integration with Your System

### Your NL2SPARQL Pipeline
```
Question (NL)
    ↓
[Class Extractor] → Classes (evaluated against ground truth)
    ↓
[Property Extractor] → Properties (evaluated)
    ↓
[Entity Recognizer] → Entities (evaluated)
    ↓
[Query Generator] → SPARQL Query
    ↓
[SPARQL Executor] → Results
    ↓
[Evaluator] → Compares with ground_truth/gt_*.json
    ↓
[Metrics Calculator] → Precision, Recall, F1-score
    ↓
Result with Evaluation Metrics
```

---

## ✅ What Your Ground Truth Files Enable

With the 50 ground truth files (gt_*.json) you've created, you can now:

1. ✅ **Automatic Evaluation** - Every pipeline run compares against ground truth
2. ✅ **Stage-by-Stage Metrics** - See which stage is underperforming
3. ✅ **Per-Question Analysis** - Identify problematic questions
4. ✅ **Regression Testing** - Track improvements over time
5. ✅ **Published Results** - Scientifically rigorous evaluation

---

## 🚀 Running Evaluation

### Command 1: Run Pipeline with Auto-Evaluation
```python
from nl2sparql.pipeline import NL2SPARQLPipeline

pipeline = NL2SPARQLPipeline()
result = pipeline.answer_question(
    question="Who is our Sensor expert?",
    schema_file="data/output/copypu_mschema.json"
)

# Evaluation automatic if ground truth exists
metrics = result["evaluation"]
print(f"Class F1: {metrics['stages']['class_extraction']['f1']:.3f}")
print(f"Overall F1: {metrics['overall']['average_f1']:.3f}")
```

### Command 2: Batch Evaluation on All 50 Questions
```bash
python evaluate_all_questions.py \
  --questions c:\Users\dhami\Downloads\questions.yml \
  --ground-truth c:\Users\dhami\nl2sparql\ground_truth \
  --schema data/output/copypu_mschema.json \
  --output results/evaluation_2026-02-23.json
```

**Output Summary:**
```
Evaluation Results:
═════════════════════════════════════
✓ Evaluated: 50 questions
✓ Passed (F1 ≥ 0.7): 42 questions
⚠️ Warning (F1 0.5-0.7): 6 questions
✗ Failed (F1 < 0.5): 2 questions

Average F1: 0.87
Average Precision: 0.89
Average Recall: 0.85
═════════════════════════════════════
```

---

## 📚 Key Takeaways

| Aspect | How It Works |
|--------|-------------|
| **Metrics** | Set-based Precision, Recall, F1-score on results |
| **Ground Truth** | JSON files with expected results per question |
| **Comparison** | Execute both expected & generated queries, compare result sets |
| **Aggregation** | Average F1 across all 50 questions |
| **Multi-stage** | Evaluate class, property, entity, and query separately |
| **Automatic** | Runs automatically if ground truth files exist |

---

**Status:** ✅ Your system is now ready for comprehensive evaluation!
