# Evaluation System Documentation

## Overview

The NL2SPARQL evaluation system provides comprehensive metrics (Precision, Recall, F1-score) to assess pipeline performance at each stage. This allows you to measure system quality and track improvements over time.

## Metrics Explained

### Precision
**What it measures**: Accuracy - proportion of correct answers among those returned by the system.

Formula: `Precision = True Positives / (True Positives + False Positives)`

**Interpretation**:
- 1.0 = Perfect (no false positives)
- 0.5 = 50% of returned items were correct
- 0.0 = No correct items in results

**Use case**: "Of the classes we extracted, how many were actually relevant?"

### Recall
**What it measures**: Coverage - the system's ability to retrieve ALL relevant answers.

Formula: `Recall = True Positives / (True Positives + False Negatives)`

**Interpretation**:
- 1.0 = Perfect (all correct items retrieved)
- 0.5 = Retrieved only 50% of all relevant items
- 0.0 = Missed all correct items

**Use case**: "Did we find ALL the relevant classes or did we miss some?"

### F1-Score
**What it measures**: Balance between Precision and Recall.

Formula: `F1 = 2 * (Precision * Recall) / (Precision + Recall)`

**Interpretation**:
- 1.0 = Perfect balance
- 0.5 = Moderate performance
- 0.0 = Very poor

**Why it matters**: A system might have high precision but low recall (or vice versa). F1-score punishes such imbalances and rewards balanced systems.

## Evaluation Stages

### 1. Class Extraction
- **What's evaluated**: Which classes were extracted by the system
- **Ground truth needed**: `expected_classes: [list of correct class names]`
- **Metrics**: Precision, Recall, F1-score, Accuracy
- **Error analysis**: True Positives, False Positives, False Negatives

### 2. Property Extraction
- **What's evaluated**: Which properties were selected for each class
- **Ground truth needed**: `expected_properties: [{class_name, properties: [...]}, ...]`
- **Metrics**: Per-class F1, Macro-average (simple), Micro-average (weighted)
- **Why two averages?**
  - Macro: Treats each class equally
  - Micro: Weights by number of properties (large classes matter more)

### 3. Missing ID Extraction
- **What's evaluated**: Entity names and IRIs that were resolved
- **Ground truth needed**: `expected_entities: {entity_name: expected_iri, ...}`
- **Metrics**: Precision (entity found), Recall (all entities), IRI Accuracy (correct IRIs)

### 4. Query Execution
- **What's evaluated**: Results returned by SPARQL query
- **Ground truth needed**: `expected_results: [{field: value, ...}, ...]`
- **Metrics**: Precision, Recall, F1-score based on result comparison
- **Key field**: Optional - compare on specific field instead of full results

## Setting Up Ground Truth

### Step 1: Create Ground Truth File

Create a JSON file in the `ground_truth/` directory:

```json
{
  "question": "Who is our Sensor expert?",
  "expected_classes": [
    "prod_vocab:Employee",
    "prod_vocab:ProductCategory"
  ],
  "expected_properties": [
    {
      "class_name": "prod_vocab:Employee",
      "relevant_properties": ["ns_0_1:name", "prod_vocab:areaOfExpertise"]
    },
    {
      "class_name": "prod_vocab:ProductCategory",
      "relevant_properties": ["rdfs:label"]
    }
  ],
  "expected_entities": {
    "Sensor": "http://ld.company.org/prod-instances/prod-cat-Sensor"
  },
  "expected_results": [
    {
      "employeeName": "John Smith"
    }
  ],
  "key_field": "employeeName"
}
```

### Step 2: Save with GroundTruthManager

```python
from nl2sparql.ground_truth_manager import GroundTruthManager

gt_manager = GroundTruthManager()

ground_truth = {
    "expected_classes": ["Class1", "Class2"],
    "expected_properties": [...],
    "expected_entities": {...},
    "expected_results": [...]
}

gt_manager.save_ground_truth("Your question?", ground_truth)
```

The system automatically saves it with a filename based on the question hash.

## Running Evaluation

### Automatic Evaluation

After running a pipeline with ground truth available:

```python
from nl2sparql.pipeline import NL2SPARQLPipeline

pipeline = NL2SPARQLPipeline()
results = pipeline.answer_question(
    "Who is our Sensor expert?",
    "data/output/schema.json"
)

# If ground truth exists for this question,
# evaluation runs automatically and results include:
# results["evaluation"] = {
#     "stages": {...},
#     "overall": {...}
# }
```

### Manual Evaluation

```python
from nl2sparql.evaluator import PipelineEvaluator
from nl2sparql.ground_truth_manager import GroundTruthManager
from nl2sparql.results_viewer import get_latest_result

# Load result
result = get_latest_result()

# Load ground truth
gt_manager = GroundTruthManager()
ground_truth = gt_manager.load_ground_truth_by_question("Your question?")

# Evaluate
evaluator = PipelineEvaluator()
evaluation = evaluator.evaluate_full_pipeline(result, ground_truth)
```

## Viewing Evaluation Results

### List All Evaluations

```python
from nl2sparql.evaluation_viewer import list_all_evaluations

evaluations = list_all_evaluations(limit=10)
for eval_summary in evaluations:
    print(f"{eval_summary['question']}: F1={eval_summary['average_f1']:.4f}")
```

### View Latest Evaluation

```python
from nl2sparql.evaluation_viewer import get_latest_evaluation, format_evaluation_for_display

evaluation = get_latest_evaluation()
print(format_evaluation_for_display(evaluation))
```

### Get Evaluation Statistics

```python
from nl2sparql.evaluation_viewer import get_evaluation_statistics

stats = get_evaluation_statistics()
print(f"Average F1: {stats['average_f1']:.4f}")
print(f"Best Evaluation: {stats['best_evaluation']}")
print(f"Best F1: {stats['best_f1']:.4f}")

for stage, avg in stats['stage_averages'].items():
    print(f"{stage}:")
    print(f"  F1:        {avg['avg_f1']:.4f}")
    print(f"  Precision: {avg['avg_precision']:.4f}")
    print(f"  Recall:    {avg['avg_recall']:.4f}")
```

### Compare Two Evaluations

```python
from nl2sparql.evaluation_viewer import compare_evaluations

comparison = compare_evaluations(
    "eval_20260223_120000_eval.json",
    "eval_20260223_130000_eval.json"
)
print(comparison)
```

## Interpreting Results

### Class Extraction Example

```
Precision: 0.80    →  80% of extracted classes were correct
Recall: 0.67       →  We found 67% of all correct classes (missed 33%)
F1: 0.73           →  Balanced score between precision and recall

True Positives: 4  →  Correctly extracted
False Positives: 1 →  Extracted but shouldn't have
False Negatives: 2 →  Should have extracted but didn't
```

**Interpretation**: Good precision but lower recall - system is conservative (doesn't extract false items but misses some real ones).

### Property Extraction (Per-Class Analysis)

```
Employee class:
  Precision: 1.0   →  All extracted properties were correct
  Recall: 0.8      →  Missed one property
  F1: 0.889

Product class:
  Precision: 0.75  →  3 of 4 extracted were correct
  Recall: 1.0      →  Found all correct properties
  F1: 0.857

Macro Average F1: 0.873   →  Simple average of F1 scores
Micro Average F1: 0.864   →  Weighted average based on property counts
```

### Query Execution Results

```
Result Count: 5
Precision: 0.8  →  4 of 5 results were correct
Recall: 0.67    →  Found 4 of 6 expected results
F1: 0.73        →  Missing 2 expected results, had 1 extra result
```

## Setting Performance Targets

| Stage | Target | Why |
|-------|--------|-----|
| Class Extraction | F1 > 0.85 | Should find most relevant classes |
| Property Extraction | F1 > 0.80 | Properties are more specific than classes |
| Missing ID Resolution | F1 > 0.90 | Critical - wrong IRIs break queries |
| Query Execution | F1 > 0.80 | Final results are most important |

## Tracking Progress Over Time

### Export Evaluations to CSV

```python
from nl2sparql.ground_truth_manager import EvaluationResultsManager

eval_manager = EvaluationResultsManager()
eval_manager.export_to_csv("evaluation_progress.csv")
```

This creates a CSV with:
- timestamp
- question
- average_f1
- class_extraction_f1
- property_extraction_f1
- missing_id_f1
- query_execution_f1

### View Trends

```python
import pandas as pd

df = pd.read_csv("evaluation_progress.csv")

# Plot F1 scores over time
df['timestamp'] = pd.to_datetime(df['timestamp'])
df.set_index('timestamp')[['average_f1', 'class_extraction_f1']].plot()
plt.show()
```

## Common Questions

### Q: My Precision is 1.0 but Recall is 0.5. What does this mean?

A: You're not missing any wrong items (perfect precision), but you're only finding 50% of the relevant items (50% recall). You're being too conservative - you need to extract more items.

### Q: My Recall is 1.0 but Precision is 0.5. What does this mean?

A: You're finding all relevant items (perfect recall) but including 50% wrong items (low precision). You're being too aggressive - you're including things you shouldn't.

### Q: Should I optimize for Precision or Recall?

A: It depends on your application:
- **High Precision priority**: When false positives are costly (e.g., wrong diagnosis)
- **High Recall priority**: When missing items is costly (e.g., finding all suspects)
- **Balanced (F1)**: When both matter equally

### Q: Why compare macro vs micro averages?

A: 
- **Macro**: Equal weight to each class (treats small and large classes the same)
- **Micro**: Weight by class size (large classes influence score more)

Use macro if you care about consistency across all classes. Use micro if you care about overall performance.

## File Structure

```
ground_truth/
├── gt_a1b2c3d4.json       # Ground truth for one question
├── gt_e5f6g7h8.json       # Ground truth for another
└── ...

evaluation_results/
├── eval_20260223_120000_eval.json
├── eval_20260223_130000_eval.json
└── ...

results/
├── result_20260223_120000.json  # Contains evaluation if ground truth exists
├── result_20260223_130000.json
└── ...
```

## API Reference

### Evaluators

```python
# Class extraction
from nl2sparql.evaluator import ClassExtractionEvaluator
metrics = ClassExtractionEvaluator.evaluate(
    extracted_classes,
    ground_truth_classes
)

# Property extraction
from nl2sparql.evaluator import PropertyExtractionEvaluator
metrics = PropertyExtractionEvaluator.evaluate(
    extracted_properties,
    ground_truth_properties
)

# Missing ID
from nl2sparql.evaluator import MissingIDEvaluator
metrics = MissingIDEvaluator.evaluate(
    resolved_entities,
    ground_truth_entities
)

# Query execution
from nl2sparql.evaluator import QueryExecutionEvaluator
metrics = QueryExecutionEvaluator.evaluate(
    actual_results,
    expected_results,
    key_field="result_id"
)

# Full pipeline
from nl2sparql.evaluator import PipelineEvaluator
evaluation = PipelineEvaluator().evaluate_full_pipeline(result, ground_truth)
```

### Viewers

```python
from nl2sparql.evaluation_viewer import (
    list_all_evaluations,
    get_latest_evaluation,
    format_evaluation_for_display,
    compare_evaluations,
    get_evaluation_statistics,
    print_evaluation_summary
)
```

### Managers

```python
from nl2sparql.ground_truth_manager import (
    GroundTruthManager,
    EvaluationResultsManager
)

# Ground truth
gt_manager = GroundTruthManager()
gt_manager.save_ground_truth(question, ground_truth)
gt = gt_manager.load_ground_truth_by_question(question)
gt_manager.list_ground_truths()

# Evaluation results
eval_manager = EvaluationResultsManager()
eval_manager.save_evaluation(result_filename, evaluation)
eval_manager.list_evaluations()
eval_manager.export_to_csv("analysis.csv")
```

---

**Status**: ✅ Complete and Ready to Use

**Version**: 1.0
