# Evaluation System Documentation Index

## 📚 Complete Navigation Guide

This index organizes all evaluation system documentation. Use it to find what you need quickly.

---

## 🚀 Getting Started (Choose Your Path)

### Path A: "I have 5 minutes"
→ Read: [EVALUATION_QUICK_START.md](EVALUATION_QUICK_START.md)

**Contains**: Code samples, common tasks, quick reference  
**Covers**: 
- How to create ground truth in 30 seconds
- How to run evaluation
- How to view results

### Path B: "I want to understand everything"
→ Read: [EVALUATION_INTEGRATION_GUIDE.md](EVALUATION_INTEGRATION_GUIDE.md)

**Contains**: Complete architecture, data flow, integration details  
**Covers**:
- How the system works end-to-end
- How components interact
- Integration with pipeline

### Path C: "I need detailed reference"
→ Read: [EVALUATION_DOCUMENTATION.md](EVALUATION_DOCUMENTATION.md)

**Contains**: Complete reference with examples  
**Covers**:
- Metrics explained (Precision, Recall, F1)
- Each stage explained
- Performance targets
- Troubleshooting

---

## 📖 Complete Documentation Map

### Core Documentation Files

| File | Purpose | Read Time | Audience |
|------|---------|-----------|----------|
| **[EVALUATION_SYSTEM_README.md](EVALUATION_SYSTEM_README.md)** | System overview & architecture | 5-10 min | Everyone |
| **[EVALUATION_QUICK_START.md](EVALUATION_QUICK_START.md)** | Quick reference & common tasks | 5 min | Users |
| **[EVALUATION_DOCUMENTATION.md](EVALUATION_DOCUMENTATION.md)** | Detailed reference | 20-30 min | Power users |
| **[EVALUATION_INTEGRATION_GUIDE.md](EVALUATION_INTEGRATION_GUIDE.md)** | How it all works together | 15-20 min | Developers |

### Ground Truth Documentation

| File | Purpose | When to Use |
|------|---------|------------|
| **[ground_truth/EXAMPLE_GROUND_TRUTH.md](ground_truth/EXAMPLE_GROUND_TRUTH.md)** | Templates & examples | Creating your first ground truth |
| **[ground_truth/README.md](ground_truth/README.md)** | Ground truth format | Understanding the format |

### Example Files

| File | Purpose | Contains |
|------|---------|----------|
| **[evaluation_results/EXAMPLE_EVALUATION_RESULT.json](evaluation_results/EXAMPLE_EVALUATION_RESULT.json)** | Sample evaluation output | All metrics for one evaluation |
| **[test_evaluation_system.py](test_evaluation_system.py)** | Working demo | 8 complete examples |

---

## 🎯 Find What You Need

### "How do I..."

#### Create Ground Truth?
→ [EVALUATION_QUICK_START.md](EVALUATION_QUICK_START.md#1-create-your-first-ground-truth)

#### Run Evaluation?
→ [EVALUATION_QUICK_START.md](EVALUATION_QUICK_START.md#2-run-your-question)

#### View Results?
→ [EVALUATION_QUICK_START.md](EVALUATION_QUICK_START.md#3-view-results)

#### Understand Precision vs Recall?
→ [EVALUATION_DOCUMENTATION.md](EVALUATION_DOCUMENTATION.md#metrics-explained)

#### Compare Two Evaluations?
→ [EVALUATION_QUICK_START.md](EVALUATION_QUICK_START.md#advanced-usage)

#### Export Results to CSV?
→ [EVALUATION_QUICK_START.md](EVALUATION_QUICK_START.md#export-for-analysis)

#### Debug Low F1 Score?
→ [EVALUATION_DOCUMENTATION.md](EVALUATION_DOCUMENTATION.md#interpreting-results)

#### See Example Ground Truth?
→ [ground_truth/EXAMPLE_GROUND_TRUTH.md](ground_truth/EXAMPLE_GROUND_TRUTH.md)

#### See Example Evaluation Output?
→ [evaluation_results/EXAMPLE_EVALUATION_RESULT.json](evaluation_results/EXAMPLE_EVALUATION_RESULT.json)

#### Run a Demo?
→ [test_evaluation_system.py](test_evaluation_system.py) (run with: `python test_evaluation_system.py`)

---

## 📊 Documentation by Topic

### Metrics & Scoring

| Metric | Explanation | File |
|--------|-------------|------|
| **Precision** | Accuracy of predictions | [EVALUATION_DOCUMENTATION.md](EVALUATION_DOCUMENTATION.md#precision) |
| **Recall** | Coverage of correct items | [EVALUATION_DOCUMENTATION.md](EVALUATION_DOCUMENTATION.md#recall) |
| **F1-Score** | Balanced metric | [EVALUATION_DOCUMENTATION.md](EVALUATION_DOCUMENTATION.md#f1-score) |
| **Macro Average** | Simple average per class | [EVALUATION_QUICK_START.md](EVALUATION_QUICK_START.md#advanced-usage) |
| **Micro Average** | Weighted average | [EVALUATION_QUICK_START.md](EVALUATION_QUICK_START.md#advanced-usage) |

### Pipeline Stages

| Stage | Evaluation | Ground Truth Format | File |
|-------|-----------|-------------------|------|
| **Class Extraction** | Precision/Recall/F1 | `expected_classes: []` | [EVALUATION_DOCUMENTATION.md](EVALUATION_DOCUMENTATION.md#1-class-extraction) |
| **Property Extraction** | Per-class + Macro/Micro | `expected_properties: [...]` | [EVALUATION_DOCUMENTATION.md](EVALUATION_DOCUMENTATION.md#2-property-extraction) |
| **Missing ID** | Precision/Recall/IRI Accuracy | `expected_entities: {}` | [EVALUATION_DOCUMENTATION.md](EVALUATION_DOCUMENTATION.md#3-missing-id-extraction) |
| **Query Execution** | Precision/Recall/F1 | `expected_results: []` | [EVALUATION_DOCUMENTATION.md](EVALUATION_DOCUMENTATION.md#4-query-execution) |

### Workflows

| Workflow | Link | Time |
|----------|------|------|
| **Single Question** | [EVALUATION_INTEGRATION_GUIDE.md](EVALUATION_INTEGRATION_GUIDE.md#workflow-1-test-single-question) | 5 min |
| **Batch Evaluation** | [EVALUATION_INTEGRATION_GUIDE.md](EVALUATION_INTEGRATION_GUIDE.md#workflow-2-batch-evaluation) | 10 min |
| **Track Improvements** | [EVALUATION_INTEGRATION_GUIDE.md](EVALUATION_INTEGRATION_GUIDE.md#workflow-3-track-improvements) | 15 min |

### Troubleshooting

| Problem | Solution | File |
|---------|----------|------|
| Low F1 score | Check each stage, fix worst first | [EVALUATION_DOCUMENTATION.md](EVALUATION_DOCUMENTATION.md#common-questions) |
| No evaluation results | Create ground truth | [EVALUATION_QUICK_START.md](EVALUATION_QUICK_START.md#debugging-tips) |
| High precision, low recall | Be less selective | [EVALUATION_QUICK_START.md](EVALUATION_QUICK_START.md#problem-high-precision-low-recall) |
| High recall, low precision | Filter more carefully | [EVALUATION_QUICK_START.md](EVALUATION_QUICK_START.md#problem-low-precision-high-recall) |

---

## 🔧 For Developers

### Code Reference

| Component | File | Purpose |
|-----------|------|---------|
| **EvaluationMetrics** | [nl2sparql/evaluator.py](../nl2sparql/evaluator.py) | Metric calculations |
| **ClassExtractionEvaluator** | [nl2sparql/evaluator.py](../nl2sparql/evaluator.py) | Class evaluation |
| **PropertyExtractionEvaluator** | [nl2sparql/evaluator.py](../nl2sparql/evaluator.py) | Property evaluation |
| **MissingIDEvaluator** | [nl2sparql/evaluator.py](../nl2sparql/evaluator.py) | Entity evaluation |
| **QueryExecutionEvaluator** | [nl2sparql/evaluator.py](../nl2sparql/evaluator.py) | Query result evaluation |
| **PipelineEvaluator** | [nl2sparql/evaluator.py](../nl2sparql/evaluator.py) | Orchestrator |
| **GroundTruthManager** | [nl2sparql/ground_truth_manager.py](../nl2sparql/ground_truth_manager.py) | Ground truth storage |
| **EvaluationResultsManager** | [nl2sparql/ground_truth_manager.py](../nl2sparql/ground_truth_manager.py) | Result storage |
| **evaluation_viewer** | [nl2sparql/evaluation_viewer.py](../nl2sparql/evaluation_viewer.py) | Display utilities |

### Integration Points

| Component | File | Details |
|-----------|------|---------|
| Pipeline Integration | [EVALUATION_INTEGRATION_GUIDE.md](EVALUATION_INTEGRATION_GUIDE.md#pipelinepy-integration) | How pipeline triggers evaluation |
| Results Structure | [EVALUATION_SYSTEM_README.md](EVALUATION_SYSTEM_README.md#integration-points) | Result field layout |
| API Reference | [EVALUATION_DOCUMENTATION.md](EVALUATION_DOCUMENTATION.md#api-reference) | All available functions |

### Testing

| Test | Location | Command |
|------|----------|---------|
| **Full Demo** | [test_evaluation_system.py](test_evaluation_system.py) | `python test_evaluation_system.py` |
| **Individual Tests** | [test_evaluation_system.py](test_evaluation_system.py) | See function names |

---

## 📋 Quick Reference Tables

### Metrics at a Glance

```
Precision  = TP / (TP + FP)  → Correct answers / All answers
Recall     = TP / (TP + FN)  → Correct answers / Correct answers in data
F1         = 2*(P*R)/(P+R)   → Harmonic mean of Precision & Recall

High Precision:  Few false positives (careful selection)
High Recall:     Few false negatives (comprehensive search)
High F1:         Good balance between both
```

### Ground Truth Fields

```json
{
  "expected_classes": ["Class1", "Class2"],
  "expected_properties": [
    {"class_name": "Class1", "relevant_properties": ["prop1", "prop2"]}
  ],
  "expected_entities": {"entity": "http://iri"},
  "expected_results": [{"field": "value"}],
  "key_field": "field"
}
```

### Performance Targets

```
Stage                  Excellent  Good    Acceptable  Needs Work
─────────────────────────────────────────────────────────────────
Class Extraction       > 0.88     0.80    0.70-0.80   < 0.70
Property Selection     > 0.85     0.75    0.65-0.75   < 0.65
Entity Resolution      > 0.95     0.85    0.75-0.85   < 0.75
Query Execution        > 0.80     0.65    0.50-0.65   < 0.50
```

---

## 🗂️ File Organization

```
nl2sparql/
│
├── Core Evaluation Modules
├── evaluator.py                          ← Metric calculations
├── ground_truth_manager.py               ← Storage management
├── evaluation_viewer.py                  ← Display utilities
├── [pipeline.py - MODIFIED]              ← Integration point
├── [results_manager.py - MODIFIED]       ← Evaluation field
│
├── Documentation
├── EVALUATION_SYSTEM_README.md            ← Overview
├── EVALUATION_QUICK_START.md              ← Quick reference
├── EVALUATION_DOCUMENTATION.md            ← Detailed reference
├── EVALUATION_INTEGRATION_GUIDE.md        ← Architecture & integration
├── EVALUATION_DOCUMENTATION_INDEX.md      ← This file
│
├── Data Directories
├── ground_truth/
│   ├── EXAMPLE_GROUND_TRUTH.md           ← Templates & examples
│   ├── gt_<hash>.json                    ← Your ground truth files
│   └── README.md
│
├── evaluation_results/
│   ├── EXAMPLE_EVALUATION_RESULT.json    ← Sample output
│   ├── eval_<timestamp>_eval.json        ← Your evaluation files
│   └── README.md
│
├── results/
│   ├── result_<timestamp>.json           ← Pipeline results
│   │   (with optional evaluation field)
│   └── README.md
│
└── Testing
    └── test_evaluation_system.py         ← Working demo (run this!)
```

---

## 📈 Learning Path (Recommended)

### Day 1: Basics (20 min)
1. Read: [EVALUATION_QUICK_START.md](EVALUATION_QUICK_START.md)
2. Run: `python test_evaluation_system.py`
3. Create ground truth for one question

### Day 2: Deep Dive (30 min)
1. Read: [EVALUATION_INTEGRATION_GUIDE.md](EVALUATION_INTEGRATION_GUIDE.md)
2. Read: [EVALUATION_DOCUMENTATION.md](EVALUATION_DOCUMENTATION.md)
3. Run pipeline with ground truth and check evaluation

### Day 3: Advanced (20 min)
1. Review: [EVALUATION_SYSTEM_README.md](EVALUATION_SYSTEM_README.md)
2. Create multiple ground truths
3. Compare evaluations across questions
4. Export to CSV for analysis

### Day 4+: Mastery
- Automate ground truth creation
- Build evaluation dashboards
- Integrate with CI/CD
- Create improvement tracking

---

## ❓ Still Need Help?

### Check These First

1. **"How do I use it?"**
   → [EVALUATION_QUICK_START.md](EVALUATION_QUICK_START.md)

2. **"What does this metric mean?"**
   → [EVALUATION_DOCUMENTATION.md](EVALUATION_DOCUMENTATION.md#metrics-explained)

3. **"How does it work?"**
   → [EVALUATION_INTEGRATION_GUIDE.md](EVALUATION_INTEGRATION_GUIDE.md)

4. **"I have a problem..."**
   → [EVALUATION_DOCUMENTATION.md](EVALUATION_DOCUMENTATION.md#common-questions)

5. **"Show me an example"**
   → [ground_truth/EXAMPLE_GROUND_TRUTH.md](ground_truth/EXAMPLE_GROUND_TRUTH.md) or `python test_evaluation_system.py`

### Still Stuck?

1. Review the relevant documentation
2. Check the GitHub examples
3. Run the test script: `python test_evaluation_system.py`
4. Enable debug logging (see EVALUATION_INTEGRATION_GUIDE.md)

---

## 📚 External References

### Metric Definitions
- **Precision & Recall**: Classic information retrieval metrics
- **F1-Score**: Harmonic mean, balances precision and recall
- **Accuracy**: Simple correctness measure

### Related Concepts
- Machine Learning evaluation
- Information Retrieval metrics
- A/B testing and comparison

---

## 📝 Document Summary Table

| Document | Purpose | Length | Level | When to Read |
|----------|---------|--------|-------|------------|
| EVALUATION_SYSTEM_README.md | Overview | 10 pages | Beginner | First |
| EVALUATION_QUICK_START.md | Quick ref | 8 pages | Beginner | Second |
| EVALUATION_DOCUMENTATION.md | Detailed | 15 pages | Advanced | As needed |
| EVALUATION_INTEGRATION_GUIDE.md | How it works | 20 pages | Advanced | When curious |
| ground_truth/EXAMPLE_GROUND_TRUTH.md | Examples | 8 pages | Beginner | Creating GT |
| test_evaluation_system.py | Code demo | 300 lines | Intermediate | Learning |

---

## 🎓 Knowledge Check

If you can answer these, you're ready:

1. **What do Precision and Recall measure?**
   - [Answer](EVALUATION_DOCUMENTATION.md#metrics-explained)

2. **How do I create ground truth?**
   - [Answer](EVALUATION_QUICK_START.md#1-create-your-first-ground-truth)

3. **What happens when I run the pipeline?**
   - [Answer](EVALUATION_INTEGRATION_GUIDE.md#step-by-step-integration)

4. **How is F1 calculated?**
   - [Answer](EVALUATION_DOCUMENTATION.md#f1-score)

5. **What files get created where?**
   - [Answer](EVALUATION_INTEGRATION_GUIDE.md#file-organization-after-running)

---

## 🚀 Next Steps

1. ✅ Read a documentation file above
2. ✅ Run the demo: `python test_evaluation_system.py`
3. ✅ Create ground truth for one question
4. ✅ Run pipeline and check evaluation
5. ✅ View results using evaluation_viewer
6. ✅ Track improvements over time

**You're ready to evaluate your pipeline!** 🎉

---

**Version**: 1.0  
**Status**: Complete  
**Last Updated**: 2025-02-23

---

**Questions?** Check the FAQ section in the relevant documentation file.
