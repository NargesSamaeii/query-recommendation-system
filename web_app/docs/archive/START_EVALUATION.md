# 🚀 Start Using the Evaluation System - Today!

Welcome! This guide gets you using the evaluation system in **5 minutes**.

---

## What Is It?

The evaluation system measures **how good your pipeline is** by calculating:
- ✅ **Precision**: Are extracted items correct?
- ✅ **Recall**: Did we find all relevant items?
- ✅ **F1-Score**: Overall balance between both

For each stage:
1. Class extraction
2. Property extraction  
3. Entity resolution
4. Query results

---

## ⚡ Quick Start (5 Minutes)

### Step 1: See It In Action (1 min)

Run the demo:
```bash
python test_evaluation_system.py
```

You'll see:
- How metrics are calculated
- How evaluators work
- Example ground truth
- Sample evaluation results

### Step 2: Create Ground Truth (2 min)

Open Python and run:

```python
from nl2sparql.ground_truth_manager import GroundTruthManager

gt_manager = GroundTruthManager()

# What the CORRECT answer should be
ground_truth = {
    "expected_classes": ["Employee", "ProductCategory"],
    
    "expected_properties": [
        {"class_name": "Employee", "relevant_properties": ["name", "expertise"]},
        {"class_name": "ProductCategory", "relevant_properties": ["label"]}
    ],
    
    "expected_entities": {
        "Sensor": "http://ld.company.org/prod-cat-Sensor"
    },
    
    "expected_results": [
        {"name": "John Smith", "expertise": "Sensors"},
        {"name": "Jane Doe", "expertise": "Electronics"}
    ],
    
    "key_field": "name"
}

# Save it
gt_manager.save_ground_truth("Who is our Sensor expert?", ground_truth)
print("✓ Ground truth saved!")
```

### Step 3: Run Pipeline (1 min)

```python
from nl2sparql.pipeline import NL2SPARQLPipeline

pipeline = NL2SPARQLPipeline()

result = pipeline.answer_question(
    question="Who is our Sensor expert?",
    schema_file="data/output/copypu_mschema.json"
)

# That's it! Evaluation ran automatically!
```

### Step 4: View Results (1 min)

```python
from nl2sparql.evaluation_viewer import get_latest_evaluation, format_evaluation_for_display

evaluation = get_latest_evaluation()
print(format_evaluation_for_display(evaluation))
```

Output shows:
```
CLASS EXTRACTION: F1=0.80
  Precision: 0.80  Recall: 0.67

PROPERTY EXTRACTION: F1=0.91 (Macro) / 0.89 (Micro)
  Employee: F1=0.80
  ProductCategory: F1=1.00

ENTITY RESOLUTION: F1=1.00
  Sensor: CORRECT

QUERY EXECUTION: F1=0.80
  Found: 2/2 expected results
```

---

## 📊 Understanding Your Scores

### Precision
**What it means**: "Of what we extracted, how much was correct?"

```
Perfect (1.0)    → Everything was correct
Good (0.8)       → 80% was correct, 20% was wrong
Okay (0.6)       → 60% correct
Poor (< 0.5)     → More wrong than right
```

### Recall
**What it means**: "Did we find everything we should have?"

```
Perfect (1.0)    → Found everything
Good (0.8)       → Found 80%, missed 20%
Okay (0.6)       → Found 60%, missed 40%
Poor (< 0.5)     → Missed more than we found
```

### F1-Score
**What it means**: "Overall, how good is it?"

```
Excellent (0.9+) → Great performance
Good (0.8)       → Solid performance
Okay (0.7)       → Acceptable but could improve
Poor (< 0.7)     → Needs work
```

---

## 🎯 Common Problems & Solutions

### "My F1 is 0.5. What do I do?"

**Check which stage is worst**.

```python
evaluation = result["evaluation"]

for stage_name, stage_data in evaluation["stages"].items():
    f1 = stage_data.get("f1") or stage_data.get("macro_average", {}).get("f1", 0)
    print(f"{stage_name}: F1={f1:.3f}")
```

**Fix the worst stage first** - it's your bottleneck.

### "Precision is 1.0 but Recall is 0.5. What's wrong?"

**You're missing items.**

- You found everything you did find (perfect precision)
- But you missed 50% of what should be there (low recall)

**Solution**: Be less selective. Include more items.

### "Recall is 1.0 but Precision is 0.5. What's wrong?"

**You included too many wrong items.**

- You found everything (perfect recall)
- But 50% of what you found was wrong (low precision)

**Solution**: Filter more carefully. Exclude obviously wrong items.

---

## 📈 Track Your Progress

### Weekly Check-In

```python
from nl2sparql.evaluation_viewer import get_evaluation_statistics

stats = get_evaluation_statistics()

print(f"Average F1: {stats['average_f1']:.3f}")
print(f"Best: {stats['best_f1']:.3f}")
print(f"Worst: {stats['worst_f1']:.3f}")

# By stage
for stage, metrics in stats["stage_averages"].items():
    print(f"{stage}: F1={metrics['avg_f1']:.3f}")
```

### Export for Analysis

```python
from nl2sparql.ground_truth_manager import EvaluationResultsManager

eval_manager = EvaluationResultsManager()
eval_manager.export_to_csv("evaluation_progress.csv")

# Now open in Excel and make charts!
```

---

## 📚 Learn More

| Topic | Time | Guide |
|-------|------|-------|
| Quick reference | 5 min | [EVALUATION_QUICK_START.md](EVALUATION_QUICK_START.md) |
| Complete guide | 20 min | [EVALUATION_DOCUMENTATION.md](EVALUATION_DOCUMENTATION.md) |
| How it works | 15 min | [EVALUATION_INTEGRATION_GUIDE.md](EVALUATION_INTEGRATION_GUIDE.md) |
| Examples | 10 min | [ground_truth/EXAMPLE_GROUND_TRUTH.md](ground_truth/EXAMPLE_GROUND_TRUTH.md) |
| All docs | N/A | [EVALUATION_DOCUMENTATION_INDEX.md](EVALUATION_DOCUMENTATION_INDEX.md) |

---

## ❓ FAQ

### Q: Will my pipeline slow down?
**A**: No! Evaluation runs in ~50ms and only if ground truth exists.

### Q: Do I have to update all ground truth?
**A**: No! Only for questions you're testing. Others aren't evaluated.

### Q: Can I compare two evaluations?
**A**: Yes! 
```python
from nl2sparql.evaluation_viewer import compare_evaluations
compare_evaluations("eval1.json", "eval2.json")
```

### Q: How do I create good ground truth?
**A**: See [ground_truth/EXAMPLE_GROUND_TRUTH.md](ground_truth/EXAMPLE_GROUND_TRUTH.md) for templates.

### Q: What if ground truth is wrong?
**A**: Fix it and re-run. The evaluation is only as good as your ground truth.

### Q: Can I evaluate without ground truth?
**A**: You can manually compare results, but automatic evaluation needs ground truth.

### Q: How many ground truths should I create?
**A**: Start with 3-5 questions, then add more as needed. Each one ~2 min to create.

---

## 🎓 What You Learned

✅ Metrics measure quality (Precision, Recall, F1)  
✅ Ground truth defines the correct answer  
✅ Evaluation auto-runs with your pipeline  
✅ Results show what's working and what needs work  
✅ You can track improvements over time  

---

## 🚀 Next Steps

**Right now** (5 min):
1. ✅ Run `python test_evaluation_system.py`
2. ✅ Create ground truth for one question
3. ✅ Run pipeline
4. ✅ View evaluation

**This week** (daily):
1. Create ground truth for 3-5 questions
2. Check evaluation metrics
3. Note which stages need improvement
4. Make one improvement per day

**Next week** (tracking):
1. Compare evaluations week-over-week
2. Export to CSV
3. Calculate % improvement
4. Set targets for next week

---

## 🎉 You're Ready!

That's it! You now have everything you need to:
- ✅ Measure pipeline quality
- ✅ Identify problem areas
- ✅ Track improvements
- ✅ Compare performance

**Questions?** Check [EVALUATION_DOCUMENTATION_INDEX.md](EVALUATION_DOCUMENTATION_INDEX.md) for guides on specific topics.

**Happy evaluating!** 📊

---

**Version**: 1.0  
**Date**: 2025-02-23  
**Status**: Ready to Use ✨

---

## 📖 Documentation Map

```
START HERE → You are here!
    │
    ├─→ Want quick reference?
    │   └─→ [EVALUATION_QUICK_START.md](EVALUATION_QUICK_START.md)
    │
    ├─→ Want detailed guide?
    │   └─→ [EVALUATION_DOCUMENTATION.md](EVALUATION_DOCUMENTATION.md)
    │
    ├─→ Want to understand architecture?
    │   └─→ [EVALUATION_INTEGRATION_GUIDE.md](EVALUATION_INTEGRATION_GUIDE.md)
    │
    ├─→ Want examples?
    │   └─→ [ground_truth/EXAMPLE_GROUND_TRUTH.md](ground_truth/EXAMPLE_GROUND_TRUTH.md)
    │   └─→ run: python test_evaluation_system.py
    │
    ├─→ Want all documentation?
    │   └─→ [EVALUATION_DOCUMENTATION_INDEX.md](EVALUATION_DOCUMENTATION_INDEX.md)
    │
    └─→ Want overview?
        └─→ [EVALUATION_SYSTEM_README.md](EVALUATION_SYSTEM_README.md)
```

**Recommended**: Start with this file, then read EVALUATION_QUICK_START.md, then explore others as needed.
