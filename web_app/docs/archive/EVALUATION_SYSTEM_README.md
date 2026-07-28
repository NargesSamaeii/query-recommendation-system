# Evaluation System README

## Overview

The NL2SPARQL Evaluation System provides comprehensive metrics to assess pipeline quality at each processing stage. It measures **Precision**, **Recall**, and **F1-score** for:

1. **Class Extraction** - Are extracted classes relevant?
2. **Property Extraction** - Are selected properties appropriate for each class?
3. **Missing ID Resolution** - Are entities correctly identified and resolved to IRIs?
4. **Query Execution** - Are SPARQL results correct?

## Quick Start (30 seconds)

```python
# 1. Define what correct answer looks like
from nl2sparql.ground_truth_manager import GroundTruthManager
gt_manager = GroundTruthManager()
gt_manager.save_ground_truth("Your question?", {
    "expected_classes": ["Class1", "Class2"],
    "expected_properties": [{"class_name": "Class1", "relevant_properties": ["prop1"]}],
    "expected_entities": {"entity": "http://iri"},
    "expected_results": [{"field": "value"}],
    "key_field": "field"
})

# 2. Run question (evaluation auto-runs if ground truth exists)
from nl2sparql.pipeline import NL2SPARQLPipeline
pipeline = NL2SPARQLPipeline()
results = pipeline.answer_question("Your question?", "schema.json")

# 3. View results
from nl2sparql.evaluation_viewer import get_latest_evaluation, format_evaluation_for_display
evaluation = get_latest_evaluation()
print(format_evaluation_for_display(evaluation))
```

## Documentation Files

### 📚 User Guides

| File | Purpose | When to Read |
|------|---------|--------------|
| **EVALUATION_QUICK_START.md** | Quick reference (5 min) | Starting out with system |
| **EVALUATION_DOCUMENTATION.md** | Complete reference | Need detailed explanations |
| **ground_truth/EXAMPLE_GROUND_TRUTH.md** | Examples and templates | Creating your own ground truth |

### 📋 Example Files

| File | Purpose |
|------|---------|
| **evaluation_results/EXAMPLE_EVALUATION_RESULT.json** | Sample evaluation output (shows all metrics) |
| **test_evaluation_system.py** | Working demo of all components |

## Core Modules

### `nl2sparql/evaluator.py`
**Purpose**: Calculate metrics and run evaluations

**Key Classes**:
- `EvaluationMetrics` - Low-level metric calculations
- `ClassExtractionEvaluator` - Evaluate class extraction
- `PropertyExtractionEvaluator` - Evaluate property selection
- `MissingIDEvaluator` - Evaluate entity resolution
- `QueryExecutionEvaluator` - Evaluate query results
- `PipelineEvaluator` - Orchestrate full pipeline evaluation

**Usage**:
```python
from nl2sparql.evaluator import ClassExtractionEvaluator
metrics = ClassExtractionEvaluator.evaluate(extracted, ground_truth)
```

### `nl2sparql/ground_truth_manager.py`
**Purpose**: Store and manage ground truth and evaluation results

**Key Classes**:
- `GroundTruthManager` - Save/load ground truth by question
- `EvaluationResultsManager` - Store evaluation metrics and export to CSV

**Usage**:
```python
from nl2sparql.ground_truth_manager import GroundTruthManager
gt_manager = GroundTruthManager()
gt_manager.save_ground_truth("Your question?", ground_truth)
```

### `nl2sparql/evaluation_viewer.py`
**Purpose**: Display and analyze evaluation results

**Key Functions**:
- `list_all_evaluations()` - List all evaluations
- `get_latest_evaluation()` - Get newest evaluation
- `format_evaluation_for_display()` - Pretty-print results
- `compare_evaluations()` - Compare two evaluations
- `get_evaluation_statistics()` - Aggregate statistics

**Usage**:
```python
from nl2sparql.evaluation_viewer import get_latest_evaluation
evaluation = get_latest_evaluation()
```

## Metrics Glossary

### Precision
**Formula**: TP / (TP + FP)  
**Meaning**: Of the items we predicted, how many were correct?  
**Range**: 0.0 (all wrong) to 1.0 (all correct)

**Example**:
```
Predicted: [ClassA, ClassB, ClassC]
Correct:   [ClassA, ClassB]
Precision = 2 / 3 = 0.667 (one was wrong)
```

### Recall
**Formula**: TP / (TP + FN)  
**Meaning**: Of all correct items, how many did we find?  
**Range**: 0.0 (found none) to 1.0 (found all)

**Example**:
```
Predicted: [ClassA, ClassB]
Correct:   [ClassA, ClassB, ClassC]
Recall = 2 / 3 = 0.667 (missed one)
```

### F1-Score
**Formula**: 2 × (Precision × Recall) / (Precision + Recall)  
**Meaning**: Balanced metric combining precision and recall  
**Range**: 0.0 (worst) to 1.0 (perfect)

**Why F1?**
- Precision alone: Ignores what we missed
- Recall alone: Ignores what we incorrectly included
- F1: Punishes imbalance, rewards balance

## File Organization

```
nl2sparql/
├── evaluator.py                        # Core evaluation logic
├── ground_truth_manager.py             # Ground truth storage
├── evaluation_viewer.py                # Display utilities
├── pipeline.py                         # (MODIFIED - integration)
├── results_manager.py                  # (MODIFIED - evaluation field)
│
├── ground_truth/                       # Ground truth data
│   ├── EXAMPLE_GROUND_TRUTH.md        # Templates and examples
│   ├── gt_<hash>.json                 # Your ground truth files
│   └── ...
│
├── evaluation_results/                 # Evaluation metrics
│   ├── EXAMPLE_EVALUATION_RESULT.json  # Sample output
│   ├── eval_<timestamp>_eval.json     # Your evaluation files
│   └── ...
│
├── EVALUATION_DOCUMENTATION.md         # Complete reference (this reading)
├── EVALUATION_QUICK_START.md           # Quick start guide
└── test_evaluation_system.py           # Demo script
```

## Workflow Examples

### Example 1: Single Question Evaluation

```python
from nl2sparql.pipeline import NL2SPARQLPipeline
from nl2sparql.ground_truth_manager import GroundTruthManager
from nl2sparql.evaluation_viewer import get_latest_evaluation, format_evaluation_for_display

# 1. Create ground truth
gt_manager = GroundTruthManager()
ground_truth = {
    "expected_classes": ["Employee", "ProductCategory"],
    "expected_properties": [
        {"class_name": "Employee", "relevant_properties": ["name"]}
    ],
    "expected_entities": {"Sensor": "http://iri"},
    "expected_results": [{"name": "John"}],
    "key_field": "name"
}
gt_manager.save_ground_truth("Who is expert?", ground_truth)

# 2. Run question
pipeline = NL2SPARQLPipeline()
results = pipeline.answer_question("Who is expert?", "schema.json")

# 3. View evaluation (auto-ran if ground truth exists)
evaluation = get_latest_evaluation()
print(format_evaluation_for_display(evaluation))
```

### Example 2: Multiple Questions Evaluation

```python
from nl2sparql.pipeline import NL2SPARQLPipeline
from nl2sparql.evaluation_viewer import get_evaluation_statistics

questions = [
    "Who is our Sensor expert?",
    "What are lightweight products?",
    "Who manages development teams?"
]

# Assume ground truth exists for all questions
pipeline = NL2SPARQLPipeline()
for question in questions:
    results = pipeline.answer_question(question, "schema.json")

# View aggregate statistics
stats = get_evaluation_statistics()
print(f"Average F1: {stats['average_f1']:.3f}")
```

### Example 3: Tracking Improvements

```python
from nl2sparql.evaluation_viewer import compare_evaluations

# Before improvements
eval1 = "eval_20250223_120000_eval.json"

# After improvements
eval2 = "eval_20250223_150000_eval.json"

comparison = compare_evaluations(eval1, eval2)
# Shows improvement percentages
```

## Expected Performance

| Stage | Excellent | Good | Acceptable | Needs Work |
|-------|-----------|------|-----------|-----------|
| Class Extraction | > 0.88 | 0.80-0.88 | 0.70-0.80 | < 0.70 |
| Property Selection | > 0.85 | 0.75-0.85 | 0.65-0.75 | < 0.65 |
| Entity Resolution | > 0.95 | 0.85-0.95 | 0.75-0.85 | < 0.75 |
| Query Execution | > 0.80 | 0.65-0.80 | 0.50-0.65 | < 0.50 |

## Troubleshooting

### Issue: No evaluation results after running pipeline

**Cause**: Ground truth file doesn't exist  
**Solution**: Create ground truth first using `GroundTruthManager`

```python
from nl2sparql.ground_truth_manager import GroundTruthManager
gt_manager = GroundTruthManager()

# Check existing ground truths
all_gts = gt_manager.list_ground_truths()
print(f"Available ground truths: {len(all_gts)}")
```

### Issue: F1 score is too low

**Check each stage**:
```python
evaluation = get_latest_evaluation()
for stage_name, stage_metrics in evaluation['stages'].items():
    f1 = stage_metrics.get('f1') or stage_metrics.get('macro_average', {}).get('f1')
    print(f"{stage_name}: F1={f1:.3f}")
```

**Fix lowest performer first** - it's a bottleneck

### Issue: High precision but low recall

**Meaning**: Too conservative (including only certain items)  
**Solutions**:
- Lower filtering thresholds
- Add more examples to prompts
- Check for entity/synonym mismatches

### Issue: High recall but low precision

**Meaning**: Too aggressive (including many incorrect items)  
**Solutions**:
- Increase filtering thresholds
- Add negative examples to prompts
- Review WHERE clause generation

## Integration Points

### Pipeline Integration
When you run `pipeline.answer_question()`:
1. Pipeline checks if ground truth exists
2. If yes: Runs `PipelineEvaluator.evaluate_full_pipeline()`
3. Saves evaluation to `evaluation_results/`
4. Includes evaluation in result JSON

### Results Structure
Each result now has optional `evaluation` field:
```json
{
  "question": "...",
  "stages": {...},
  "evaluation": {
    "stages": {...},
    "overall": {...}
  }
}
```

## Development Reference

### Adding Custom Metrics

```python
from nl2sparql.evaluator import EvaluationMetrics

# Add to EvaluationMetrics class
@staticmethod
def calculate_specificity(predicted, correct):
    """True Negatives / (True Negatives + False Positives)"""
    # implementation
```

### Creating New Evaluators

```python
class MyEvaluator:
    @staticmethod
    def evaluate(predicted, ground_truth):
        # Implementation
        return {
            "precision": float,
            "recall": float,
            "f1": float,
            # ... other metrics
        }
```

## Performance Notes

- Ground truth lookup: O(1) via MD5 hash
- Evaluation calculation: O(n) where n = item count
- File I/O: Assume ~100ms per operation
- For 100+ evaluations: Consider batch processing

## Limitations

1. **Exact matching only**: Property extraction uses set comparison (order-insensitive but exact names)
2. **String matching**: Entity resolution requires exact IRI strings
3. **Result comparison**: Uses field-by-field comparison for key_field

## Future Enhancements

- [ ] Fuzzy string matching for entity resolution
- [ ] Confidence score weighting
- [ ] Multi-threshold analysis
- [ ] Performance visualization dashboards
- [ ] Automated ground truth generation (with validation)
- [ ] Real-time evaluation metrics display in GUI

## Testing

Run the demo script:
```bash
python test_evaluation_system.py
```

This demonstrates:
- Metric calculations
- Each evaluator type
- Ground truth management
- Results storage
- Viewing and comparison

## Support

For questions or issues:
1. Check **EVALUATION_QUICK_START.md** for common tasks
2. Check **EVALUATION_DOCUMENTATION.md** for detailed explanations
3. Review **test_evaluation_system.py** for working examples
4. Check **ground_truth/EXAMPLE_GROUND_TRUTH.md** for ground truth format

---

**Version**: 1.0  
**Status**: Production Ready  
**Last Updated**: 2025-02-23
