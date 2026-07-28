# Evaluation System Quick Start Guide

## 5-Minute Setup

### 1. Create Your First Ground Truth

```python
from nl2sparql.ground_truth_manager import GroundTruthManager

gt_manager = GroundTruthManager()

# Define what the correct answer should be
ground_truth = {
    "expected_classes": ["Employee", "ProductCategory"],
    "expected_properties": [
        {"class_name": "Employee", "relevant_properties": ["name", "expertise"]},
        {"class_name": "ProductCategory", "relevant_properties": ["label"]}
    ],
    "expected_entities": {"Sensor": "http://ld.company.org/prod-cat-Sensor"},
    "expected_results": [{"name": "John", "expertise": "Sensors"}],
    "key_field": "name"
}

# Save it
gt_manager.save_ground_truth("Who is our Sensor expert?", ground_truth)
```

### 2. Run Your Question

```python
from nl2sparql.pipeline import NL2SPARQLPipeline

pipeline = NL2SPARQLPipeline()
results = pipeline.answer_question("Who is our Sensor expert?", "schema.json")

# If ground truth exists, evaluation runs automatically!
# results["evaluation"] will contain all metrics
```

### 3. View Results

```python
from nl2sparql.evaluation_viewer import get_latest_evaluation, format_evaluation_for_display

evaluation = get_latest_evaluation()
print(format_evaluation_for_display(evaluation))
```

## What Each Metric Means

| Metric | What It Measures | Good Value | Bad Value |
|--------|------------------|-----------|-----------|
| **F1** | Balance of precision & recall | 0.9+ | <0.6 |
| **Precision** | Accuracy of predictions | 0.9+ | <0.6 |
| **Recall** | Coverage of correct items | 0.9+ | <0.6 |

## Understanding Problem Areas

### Problem: "Low Precision, High Recall"
- **Means**: Finding all relevant items but including many wrong ones
- **Example**: F1=0.6, Precision=0.5, Recall=1.0
- **Action**: Filter more carefully, make selections more restrictive

```
Expected: [ClassA, ClassB]
Found:    [ClassA, ClassB, ClassC, ClassD]  ← Too many extras
```

### Problem: "High Precision, Low Recall"
- **Means**: All selections are correct but missing some
- **Example**: F1=0.6, Precision=1.0, Recall=0.4
- **Action**: Be less selective, include more items

```
Expected: [ClassA, ClassB, ClassC]
Found:    [ClassA, ClassB]  ← Missing one
```

### Problem: "Low F1 Across All Stages"
- **Means**: Multiple failures in the pipeline
- **Action**: Check each stage individually and fix worst performers first

## Common Workflow

### Week 1: Create Baseline

```python
from nl2sparql.ground_truth_manager import GroundTruthManager

questions = [
    "Who is our Sensor expert?",
    "What are the dimensions of all lightweight products?",
    "Which managers oversee product development teams?"
]

gt_manager = GroundTruthManager()
for q in questions:
    # Run through system once to see current performance
    # Then create accurate ground truth
    ground_truth = {...}
    gt_manager.save_ground_truth(q, ground_truth)
```

### Week 2: Identify Problem Areas

```python
from nl2sparql.evaluation_viewer import get_evaluation_statistics, print_evaluation_summary

stats = get_evaluation_statistics()
print_evaluation_summary()

# Identifies which stages have lowest F1 scores
```

### Week 3: Improve Worst Performer

- If class extraction (F1=0.65): Improve LLM prompt
- If property extraction (F1=0.70): Add more training examples
- If missing ID (F1=0.80): Check entity synonyms
- If query execution (F1=0.75): Debug generated query

```python
# After making improvements, re-run pipeline
pipeline = NL2SPARQLPipeline()
results = pipeline.answer_question("Your question?", "schema.json")

# View new metrics
evaluation = results["evaluation"]
print(f"Improvement: {old_f1:.2f} → {evaluation['overall']['average_f1']:.2f}")
```

### Week 4: Compare Progress

```python
from nl2sparql.evaluation_viewer import list_all_evaluations

evaluations = list_all_evaluations()
for eval_summary in evaluations:
    print(f"{eval_summary['timestamp']}: F1={eval_summary['average_f1']:.3f}")

# See if metrics are improving over time
```

## Advanced Usage

### Export for Analysis

```python
from nl2sparql.ground_truth_manager import EvaluationResultsManager

eval_manager = EvaluationResultsManager()
eval_manager.export_to_csv("my_evaluations.csv")

# Now analyze in Excel/Python/etc
```

### Compare Two Runs

```python
from nl2sparql.evaluation_viewer import compare_evaluations

# Before improvements
eval1 = "eval_20250223_120000_eval.json"

# After improvements
eval2 = "eval_20250223_150000_eval.json"

comparison = compare_evaluations(eval1, eval2)
print(comparison)
```

### Automate Batch Evaluation

```python
from nl2sparql.pipeline import NL2SPARQLPipeline
from nl2sparql.evaluation_viewer import get_evaluation_statistics

questions = [
    "Who is our Sensor expert?",
    "What are the dimensions of lightweight products?",
    "Which products are made in Germany?"
]

pipeline = NL2SPARQLPipeline()

for question in questions:
    results = pipeline.answer_question(question, "schema.json")
    if results.get("evaluation"):
        f1 = results["evaluation"]["overall"]["average_f1"]
        print(f"{question}: F1={f1:.3f}")

# View aggregate statistics
stats = get_evaluation_statistics()
print(f"\nAverage F1: {stats['average_f1']:.3f}")
```

## Interpreting Your Results

### Excellent (F1 > 0.85)
```
✅ Class extraction:   F1=0.90 (all correct classes found)
✅ Properties:         F1=0.88 (most properties correct)
✅ Entity resolution:  F1=0.95 (entities mostly correct)
✅ Query results:      F1=0.85 (some extra results)

Overall: System is production-ready
```

### Good (0.75 < F1 < 0.85)
```
✓ Class extraction:   F1=0.80 (missed some synonym classes)
✓ Properties:         F1=0.82 (mostly correct)
✓ Entity resolution:  F1=0.90 (good)
✓ Query results:      F1=0.72 (needs WHERE clause work)

Overall: System works well but has room for improvement
```

### Needs Work (F1 < 0.75)
```
✗ Class extraction:   F1=0.60 (missing important classes)
✗ Properties:         F1=0.65 (including too many incorrect)
✗ Entity resolution:  F1=0.75 (some wrong IRIs)
✗ Query results:      F1=0.70 (incorrect results)

Overall: System needs debugging
```

## Debugging Tips

### False Positives (Precision Issues)

**Class extraction**: Including unrelated classes
- Solution: Add negative examples to prompt
- Example: "Do NOT include Department when asking about Employees"

**Properties**: Including irrelevant properties
- Solution: Refine property relevance scoring
- Example: "salary is NOT relevant for product dimensions"

**Queries**: Returning wrong results
- Solution: Tighten WHERE clauses
- Example: Add filters for status=active

### False Negatives (Recall Issues)

**Class extraction**: Missing relevant classes
- Solution: Add synonyms to prompt
- Example: "Include Manager, Boss, Supervisor, Lead"

**Properties**: Missing important properties
- Solution: Check schema for synonyms
- Example: "weight_grams is same as weight_g"

**Queries**: Missing expected results
- Solution: Check if data exists
- Example: "Verify Sensor expert exists in database"

## Common Mistakes to Avoid

❌ **Don't**: Evaluate on the same data you trained on
- Ground truth should be separate validation set

❌ **Don't**: Ignore low recall if precision is high
- You might be too conservative (missing valid items)

❌ **Don't**: Focus only on overall F1
- Check each stage - one bad stage ruins everything

❌ **Don't**: Set unrealistic targets
- Different domains have different difficulty levels

✅ **Do**: Start with realistic ground truth
- Based on what data actually exists

✅ **Do**: Fix worst stage first
- Biggest improvement per effort

✅ **Do**: Track trends over time
- Is the system getting better?

✅ **Do**: Use macro AND micro averages
- Gives different perspectives on performance

## File Organization

After first evaluation run:
```
nl2sparql/
├── ground_truth/
│   ├── gt_a1b2c3d4.json          # Your ground truth
│   ├── gt_e5f6g7h8.json          # Another question
│   └── EXAMPLE_GROUND_TRUTH.md   # Documentation
├── evaluation_results/
│   ├── eval_20250223_120000_eval.json
│   ├── eval_20250223_130000_eval.json
│   └── EXAMPLE_EVALUATION_RESULT.json  # Example output
└── results/
    ├── result_20250223_120000.json     # Has evaluation field
    └── result_20250223_130000.json
```

## Getting Help

### Check the Logs

```python
import logging
logger = logging.getLogger('nl2sparql.pipeline')
logger.setLevel(logging.DEBUG)

# Now re-run pipeline
pipeline = NL2SPARQLPipeline()
results = pipeline.answer_question("Your question?", "schema.json")
```

### Inspect the Evaluation

```python
from nl2sparql.evaluation_viewer import get_latest_evaluation

eval = get_latest_evaluation()

# Check what went wrong in each stage
print("Class Extraction Issues:")
print(eval["stages"]["class_extraction"]["analysis"])

print("\nProperty Extraction Issues:")
print(eval["stages"]["property_extraction"]["macro_average"]["analysis"])
```

### Validate Your Ground Truth

```python
from nl2sparql.ground_truth_manager import GroundTruthManager

gtm = GroundTruthManager()
gt = gtm.load_ground_truth_by_question("Your question?")

# Verify it has all required fields
assert "expected_classes" in gt
assert "expected_properties" in gt
assert "expected_results" in gt
assert "key_field" in gt

print("Ground truth is valid!")
```

---

**Status**: ✅ Ready to Use
**Version**: 1.0
