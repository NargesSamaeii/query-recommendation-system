# Evaluation System Integration Guide

## How It All Works Together

The evaluation system seamlessly integrates with the existing NL2SPARQL pipeline. Here's a complete walkthrough.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      NL2SPARQL Pipeline                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Question → [5 Stages] → Results                              │
│              ├─ Class Extraction                              │
│              ├─ Property Extraction                           │
│              ├─ Missing ID Resolution                         │
│              ├─ Query Generation                              │
│              └─ Query Execution                               │
│                        ↓                                       │
│              Results Manager (saves results)                  │
│                        ↓                                       │
│         ┌─────────────────────────────────────┐              │
│         │ Check: Ground Truth Available?      │              │
│         └────────┬───────────────────────┬────┘              │
│                  │ YES                    │ NO               │
│                  ↓                        ↓                  │
│         ┌────────────────────┐      (evaluation = null)     │
│         │ PipelineEvaluator  │                               │
│         │  - Evaluate each   │                               │
│         │    stage           │                               │
│         │  - Calc metrics    │                               │
│         │  - Save results    │                               │
│         └────────┬───────────┘                               │
│                  ↓                                           │
│         Evaluation Results Manager                           │
│         (saves to evaluation_results/)                       │
│                                                              │
└─────────────────────────────────────────────────────────────────┘
                          ↓
             Evaluation Viewer (display & analyze)
```

## Data Flow

### 1. Question Execution
```
Question: "Who is our Sensor expert?"
           ↓
    ┌──────────────────────┐
    │ pipeline.answer()    │
    └──────────┬───────────┘
               ↓
    ┌──────────────────────────────────┐
    │ Stage 1: Class Extraction        │
    │ Output: [Employee, Category]     │
    └──────────┬───────────────────────┘
               ↓
    ┌──────────────────────────────────┐
    │ Stage 2: Property Extraction     │
    │ Output: Employee[name, expertise]│
    └──────────┬───────────────────────┘
               ↓
    ┌──────────────────────────────────┐
    │ Stage 3: Missing ID Resolution   │
    │ Output: Sensor → http://oid...   │
    └──────────┬───────────────────────┘
               ↓
    ┌──────────────────────────────────┐
    │ Stage 4: Query Generation        │
    │ Output: SPARQL query             │
    └──────────┬───────────────────────┘
               ↓
    ┌──────────────────────────────────┐
    │ Stage 5: Query Execution         │
    │ Output: [[John, Sensors], ...]   │
    └──────────┬───────────────────────┘
               ↓
    Result: {stages: {...}, evaluation: null}
```

### 2. Ground Truth Check & Evaluation
```
Results saved
       ↓
Load Ground Truth by Question
       ├─ No GT found → evaluation = null
       │
       └─ GT found → Evaluate
              ↓
    ┌──────────────────────────────────┐
    │ PipelineEvaluator                │
    ├──────────────────────────────────┤
    │ ClassExtractionEvaluator         │
    │ Compare: [Employee, Category]    │
    │ vs GT: [Employee, Category]      │
    │ Result: {precision:1.0, ...}     │
    │                                   │
    │ PropertyExtractionEvaluator      │
    │ Compare: Employee[name, exp]     │
    │ vs GT: Employee[name, exp, id]   │
    │ Result: {F1: 0.89, ...}          │
    │                                   │
    │ MissingIDEvaluator               │
    │ Compare: {Sensor: http://...}    │
    │ vs GT: {Sensor: http://...}      │
    │ Result: {accuracy: 1.0, ...}     │
    │                                   │
    │ QueryExecutionEvaluator          │
    │ Compare: [[John, ...]]           │
    │ vs GT: [[John, ...]]             │
    │ Result: {F1: 0.8, ...}           │
    └──────────┬───────────────────────┘
               ↓
    evaluation = {
      stages: {...all metrics...},
      overall: {average_f1: 0.89}
    }
               ↓
    Save to evaluation_results/
    Update result with evaluation field
```

## Step-by-Step Integration

### Phase 1: Create Ground Truth (One-time setup)

```python
from nl2sparql.ground_truth_manager import GroundTruthManager

gt_manager = GroundTruthManager()

# Define ground truth for your question
ground_truth = {
    "expected_classes": ["prod_vocab:Employee", "prod_vocab:ProductCategory"],
    
    "expected_properties": [
        {
            "class_name": "prod_vocab:Employee",
            "relevant_properties": ["ns_0_1:name", "prod_vocab:areaOfExpertise", "prod_vocab:employeeID"]
        },
        {
            "class_name": "prod_vocab:ProductCategory",
            "relevant_properties": ["rdfs:label", "rdf:type"]
        }
    ],
    
    "expected_entities": {
        "Sensor": "http://ld.company.org/prod-instances/prod-cat-Sensor"
    },
    
    "expected_results": [
        {"employeeName": "John Smith", "expertise": "Sensor Technology"},
        {"employeeName": "Jane Doe", "expertise": "Sensor Design"}
    ],
    
    "key_field": "employeeName"
}

# Save it
gt_manager.save_ground_truth("Who is our Sensor expert?", ground_truth)
print("✓ Ground truth saved")
```

**Important**: Ground truth is saved with question hash, not filename.

### Phase 2: Run Pipeline (Automatic evaluation)

```python
from nl2sparql.pipeline import NL2SPARQLPipeline

# Initialize pipeline
pipeline = NL2SPARQLPipeline()

# Run question
result = pipeline.answer_question(
    question="Who is our Sensor expert?",
    schema_file="data/output/copypu_mschema.json"
)

# Behind the scenes:
# 1. Pipeline runs all 5 stages
# 2. Saves results
# 3. Checks for ground truth (found!)
# 4. Runs PipelineEvaluator
# 5. Saves evaluation results
# 6. Returns result with evaluation field

# Check if evaluation was run
if result.get("evaluation"):
    print("✓ Evaluation completed")
    print(f"Overall F1: {result['evaluation']['overall']['average_f1']:.3f}")
else:
    print("✗ No evaluation (no ground truth)")
```

### Phase 3: View Results

```python
from nl2sparql.evaluation_viewer import (
    get_latest_evaluation,
    format_evaluation_for_display
)

# Get the evaluation
evaluation = get_latest_evaluation()

# Display it nicely
print(format_evaluation_for_display(evaluation))

# Output:
# ============================================================
# Question: Who is our Sensor expert?
# ============================================================
#
# CLASS EXTRACTION: F1=0.727 (Precision=0.80 Recall=0.67)
#   ✓ Correct: 2 (Employee, ProductCategory)
#   ✗ Wrong: 1 (Department)
#   ✗ Missed: 1 (Manager)
#
# PROPERTY EXTRACTION: F1=0.909 (Macro) / 0.889 (Micro)
#   Employee: F1=0.80 (2/3 properties)
#   ProductCategory: F1=1.00 (2/2 properties)
#
# ... etc
```

## Integration Points

### Pipeline.py Integration

**Location**: `nl2sparql/pipeline.py` lines ~700-730

```python
# After saving results
if result is not None:
    results_manager = ResultsManager()
    results_manager.save_result(result)
    
    # NEW: Evaluation integration
    try:
        gt_manager = GroundTruthManager()
        ground_truth = gt_manager.load_ground_truth_by_question(question)
        
        if ground_truth:
            # Run evaluation
            evaluator = PipelineEvaluator()
            evaluation = evaluator.evaluate_full_pipeline(result, ground_truth)
            
            # Save evaluation
            eval_manager = EvaluationResultsManager()
            eval_manager.save_evaluation(result_filename, evaluation)
            
            # Update result
            result["evaluation"] = evaluation
            results_manager.save_result(result)
            
            logger.info(f"Evaluation complete: F1={evaluation['overall']['average_f1']:.3f}")
    except Exception as e:
        logger.warning(f"Evaluation failed: {e}")
        # Pipeline continues even if evaluation fails
```

**Key Features**:
- ✅ Automatic check for ground truth
- ✅ Silent skip if no ground truth
- ✅ Error handling (doesn't break pipeline)
- ✅ Logs results for debugging

### ResultsManager.py Integration

**Location**: `nl2sparql/results_manager.py`

```python
# Result structure updated to include evaluation field

result = {
    "question": str,
    "timestamp": str,
    "stages": {
        "class_extraction": {...},
        "property_extraction": {...},
        "missing_id_extraction": {...},
        "query_generation": {...},
        "query_execution": {...}
    },
    "evaluation": None  # ← NEW FIELD
    # Can be filled by pipeline if ground truth exists
}
```

## File Organization After Running

After first evaluation run:

```
nl2sparql/
├── ground_truth/
│   ├── gt_a1b2c3d4.json          # Your first ground truth
│   ├── gt_e5f6g7h8.json          # Another ground truth
│   ├── EXAMPLE_GROUND_TRUTH.md
│   └── README.md
│
├── evaluation_results/
│   ├── eval_20250223_120000_eval.json
│   │   └── Full evaluation with all metrics
│   ├── eval_20250223_130000_eval.json
│   │   └── Another evaluation
│   ├── EXAMPLE_EVALUATION_RESULT.json
│   └── README.md
│
├── results/
│   ├── result_20250223_120000.json
│   │   └── {stages: {...}, evaluation: {...}}
│   │   └── Has evaluation field if GT existed
│   └── result_20250223_130000.json
│       └── {stages: {...}, evaluation: null}
│       └── No evaluation if no GT
│
└── [evaluation system files]
```

## Common Workflows

### Workflow 1: Test Single Question

```python
# Setup (one-time)
gt_manager.save_ground_truth("Question?", {...})

# Test loop
pipeline = NL2SPARQLPipeline()
for i in range(3):  # Run 3 times
    result = pipeline.answer_question("Question?", "schema.json")
    eval = result["evaluation"]
    print(f"Run {i+1}: F1={eval['overall']['average_f1']:.3f}")
```

### Workflow 2: Batch Evaluation

```python
from nl2sparql.evaluation_viewer import get_evaluation_statistics

questions = [
    "Question 1?",
    "Question 2?",
    "Question 3?"
]

# Setup ground truth for all
for q in questions:
    gt_manager.save_ground_truth(q, {...})

# Run all
for q in questions:
    result = pipeline.answer_question(q, "schema.json")
    print(f"{q}: F1={result['evaluation']['overall']['average_f1']:.3f}")

# Aggregate statistics
stats = get_evaluation_statistics()
print(f"Average: {stats['average_f1']:.3f}")
```

### Workflow 3: Track Improvements

```python
# Before improvements
eval_before = get_latest_evaluation()

# Make improvements (e.g., to prompts or logic)
# ... modify code ...

# Test again
result = pipeline.answer_question("Question?", "schema.json")
eval_after = result["evaluation"]

# Compare
compare = compare_evaluations(
    eval_before["timestamp"],
    eval_after["timestamp"]
)

# Shows % improvement per stage
```

## Metrics Calculation Details

### Class Extraction

```
Extracted: {Employee, Department, Category}
Ground Truth: {Employee, Category, Manager}

TP (Correct): {Employee, Category}         # 2
FP (Wrong):   {Department}                 # 1
FN (Missed):  {Manager}                    # 1

Precision = TP / (TP + FP) = 2/3 = 0.667
Recall = TP / (TP + FN) = 2/3 = 0.667
F1 = 2 * (0.667 * 0.667) / (0.667 + 0.667) = 0.667
```

### Property Extraction (Per-Class)

```
Employee properties:
  Extracted: {name, email, salary}
  Ground Truth: {name, email, phone}
  
  TP: {name, email}
  FP: {salary}
  FN: {phone}
  
  Precision: 2/3 = 0.667
  Recall: 2/3 = 0.667
  F1: 0.667

Product properties:
  Extracted: {name, weight, category}
  Ground Truth: {name, weight, color}
  
  TP: {name, weight}
  FP: {category}
  FN: {color}
  
  Precision: 2/3 = 0.667
  Recall: 2/3 = 0.667
  F1: 0.667

Macro Average: (0.667 + 0.667) / 2 = 0.667
  (Simple average - each class counts equally)

Micro Average: (2+2) / (3+3) = 4/6 = 0.667
  (Weighted by class size)
```

### Entity Resolution

```
Resolved: {Sensor: http://iri1, Widget: http://iri2}
Ground Truth: {Sensor: http://iri1, Widget: http://iri2, Gadget: http://iri3}

TP: {Sensor, Widget}           # 2
FP: {}                         # 0 (all resolved were correct)
FN: {Gadget}                   # 1

Precision: 2/2 = 1.0
Recall: 2/3 = 0.667
F1: 2 * (1.0 * 0.667) / (1.0 + 0.667) = 0.8

IRI Accuracy: 100% (all resolved IRIs match ground truth)
```

### Query Execution

```
Expected: [[John, Sensors], [Jane, Electronics]]
Actual: [[John, Sensors], [Jane, Electronics], [Bob, Hardware]]

By key_field (name):
  TP: {John, Jane}              # 2 found
  FP: {Bob}                     # 1 extra
  FN: {}                        # 0 missed

Precision: 2/3 = 0.667
Recall: 2/2 = 1.0
F1: 2 * (0.667 * 1.0) / (0.667 + 1.0) = 0.8
```

## Error Handling

### Scenario 1: Ground Truth File Missing

```python
try:
    ground_truth = gt_manager.load_ground_truth_by_question("Question?")
except FileNotFoundError:
    print("Ground truth not found - skipping evaluation")
    result["evaluation"] = None
```

### Scenario 2: Evaluation Calculation Error

```python
try:
    evaluation = evaluator.evaluate_full_pipeline(result, ground_truth)
except Exception as e:
    logger.warning(f"Evaluation failed: {e}")
    # Pipeline continues without evaluation
    result["evaluation"] = None
```

### Scenario 3: Missing Fields in Results

```python
try:
    # If result is malformed
    if not result.get("stages"):
        raise ValueError("Invalid result structure")
    
    evaluation = evaluator.evaluate_full_pipeline(result, ground_truth)
except ValueError as e:
    logger.error(f"Cannot evaluate malformed result: {e}")
```

## Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Load ground truth | ~1ms | MD5 hash lookup |
| Load result | ~10ms | JSON file read |
| Evaluate class extraction | ~5ms | Set comparison |
| Evaluate properties | ~10ms | Per-class comparison |
| Evaluate entities | ~5ms | Dict lookup |
| Evaluate query results | ~20ms | List comparison + key matching |
| Total evaluation | ~50ms | Usually < 100ms |
| Save evaluation | ~20ms | JSON file write |

For performance-critical applications, consider:
- Batch evaluation off-cycle
- Caching ground truth
- Async evaluation

## Testing Integration

Run the test script to verify integration:

```bash
python test_evaluation_system.py
```

This verifies:
- ✓ All evaluators work
- ✓ Ground truth storage works
- ✓ Evaluation results storage works
- ✓ Viewers display correctly

## Debugging

### Enable Debug Logging

```python
import logging

# Set pipeline logger to DEBUG
logging.getLogger('nl2sparql.pipeline').setLevel(logging.DEBUG)

# Now run pipeline
pipeline = NL2SPARQLPipeline()
result = pipeline.answer_question("Question?", "schema.json")

# Log output will show:
# - Ground truth lookup result
# - Evaluation start/completion
# - Metric calculations
```

### Inspect Evaluation Structure

```python
import json
evaluation = get_latest_evaluation()

print(json.dumps(evaluation, indent=2))

# Shows complete structure with:
# - stages: {...all stage metrics...}
# - overall: {...aggregate metrics...}
# - recommendations: [...improvement suggestions...]
```

## Next Steps

1. **Create ground truth** for your test questions (see phase 1)
2. **Run pipeline** with questions (see phase 2)
3. **View results** (see phase 3)
4. **Track improvements** over time

## References

- [EVALUATION_SYSTEM_README.md](EVALUATION_SYSTEM_README.md) - System overview
- [EVALUATION_QUICK_START.md](EVALUATION_QUICK_START.md) - Quick reference
- [EVALUATION_DOCUMENTATION.md](EVALUATION_DOCUMENTATION.md) - Detailed reference
- [ground_truth/EXAMPLE_GROUND_TRUTH.md](ground_truth/EXAMPLE_GROUND_TRUTH.md) - Examples
- [test_evaluation_system.py](test_evaluation_system.py) - Working demo

---

**Version**: 1.0  
**Status**: Complete  
**Date**: 2025-02-23
