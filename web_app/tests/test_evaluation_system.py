#!/usr/bin/env python3
"""
Evaluation System Demo Script

Demonstrates how to use the evaluation system with sample data.
Run this to see how metrics are calculated and results displayed.

Usage:
    python test_evaluation_system.py
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path so we can import nl2sparql modules
sys.path.insert(0, str(Path(__file__).parent))

from nl2sparql.ground_truth_manager import GroundTruthManager, EvaluationResultsManager
from nl2sparql.evaluator import (
    EvaluationMetrics,
    ClassExtractionEvaluator,
    PropertyExtractionEvaluator,
    MissingIDEvaluator,
    QueryExecutionEvaluator,
    create_ground_truth_template
)
from nl2sparql.evaluation_viewer import (
    format_evaluation_for_display,
    get_evaluation_statistics,
    aggregate_evaluations_latest_per_question,
    normalize_question_key,
    get_normalized_examples_flag,
    extract_query_metrics
)


def demo_metrics_calculation():
    """Demonstrate basic metric calculations."""
    print("\n" + "="*60)
    print("DEMO 1: Basic Metrics Calculation")
    print("="*60)
    
    # Example: Class extraction
    predicted = {"class1", "class2"}
    correct = {"class1", "class2", "class3"}
    
    precision = EvaluationMetrics.calculate_precision(predicted, correct)
    recall = EvaluationMetrics.calculate_recall(predicted, correct)
    f1 = EvaluationMetrics.calculate_f1(precision, recall)
    
    print(f"\nPredicted classes: {predicted}")
    print(f"Correct classes:   {correct}")
    print(f"\nPrecision: {precision:.2%} (both predictions were correct)")
    print(f"Recall:    {recall:.2%} (but we missed 1 class)")
    print(f"F1-Score:  {f1:.4f} (balanced metric)")
    
    print("\nInterpretation:")
    print("- High precision (1.0) means no false positives")
    print("- Lower recall (0.67) means we missed one class")
    print("- F1-score (0.80) balances both metrics")


def demo_class_extraction():
    """Demonstrate class extraction evaluation."""
    print("\n" + "="*60)
    print("DEMO 2: Class Extraction Evaluation")
    print("="*60)
    
    # System extracted these classes
    extracted = ["Employee", "ProductCategory", "Department"]
    
    # Ground truth (what we expected)
    expected = ["Employee", "ProductCategory", "Manager"]
    
    metrics = ClassExtractionEvaluator.evaluate(extracted, expected)
    
    print(f"\nExtracted: {extracted}")
    print(f"Expected:  {expected}")
    
    print(f"\nMetrics:")
    print(f"  Precision:  {metrics['precision']:.2%}")
    print(f"  Recall:     {metrics['recall']:.2%}")
    print(f"  F1-Score:   {metrics['f1']:.4f}")
    print(f"  Accuracy:   {metrics['accuracy']:.2%}")
    
    print(f"\nAnalysis:")
    print(f"  ✓ Correct:      {metrics['true_positives']} (Employee, ProductCategory)")
    print(f"  ✗ Wrong:        {metrics['false_positives']} (Department)")
    print(f"  ✗ Missed:       {metrics['false_negatives']} (Manager)")


def demo_property_extraction():
    """Demonstrate property extraction evaluation."""
    print("\n" + "="*60)
    print("DEMO 3: Property Extraction Evaluation (Per-Class)")
    print("="*60)
    
    extracted = {
        "Employee": ["name", "email", "salary"],
        "Product": ["name", "weight", "category"]
    }
    
    expected = {
        "Employee": ["name", "email", "phone"],
        "Product": ["name", "weight"]
    }
    
    metrics = PropertyExtractionEvaluator.evaluate(extracted, expected)
    
    print(f"\nExtracted Properties:")
    for cls, props in extracted.items():
        print(f"  {cls}: {props}")
    
    print(f"\nExpected Properties:")
    for cls, props in expected.items():
        print(f"  {cls}: {props}")
    
    print(f"\nPer-Class Metrics:")
    for cls, cls_metrics in metrics['per_class'].items():
        print(f"  {cls}:")
        print(f"    Precision: {cls_metrics['precision']:.2%}")
        print(f"    Recall:    {cls_metrics['recall']:.2%}")
        print(f"    F1:        {cls_metrics['f1']:.4f}")
    
    print(f"\nAggregate Metrics:")
    print(f"  Macro-average F1:  {metrics['macro_average']['f1']:.4f} (equal weight to each class)")
    print(f"  Micro-average F1:  {metrics['micro_average']['f1']:.4f} (weighted by property count)")


def demo_entity_resolution():
    """Demonstrate entity resolution evaluation."""
    print("\n" + "="*60)
    print("DEMO 4: Entity Resolution (Missing ID)")
    print("="*60)
    
    resolved = {
        "Sensor": "http://ld.company.org/prod-cat-Sensor",
        "Widget": "http://ld.company.org/prod-cat-Widget"
    }
    
    expected = {
        "Sensor": "http://ld.company.org/prod-cat-Sensor",
        "Widget": "http://ld.company.org/prod-cat-Widget",
        "Gadget": "http://ld.company.org/prod-cat-Gadget"
    }
    
    metrics = MissingIDEvaluator.evaluate(resolved, expected)
    
    print(f"\nResolved Entities: {len(resolved)}")
    for entity, iri in resolved.items():
        print(f"  {entity}: {iri}")
    
    print(f"\nExpected Entities: {len(expected)}")
    for entity, iri in expected.items():
        print(f"  {entity}: {iri}")
    
    print(f"\nMetrics:")
    print(f"  Precision:    {metrics['precision']:.2%} (all resolved entities correct)")
    print(f"  Recall:       {metrics['recall']:.2%} (found 2 of 3 entities)")
    print(f"  F1-Score:     {metrics['f1']:.4f}")
    print(f"  IRI Accuracy: {metrics['iri_accuracy']:.2%} (100% of resolved IRIs correct)")


def demo_query_execution():
    """Demonstrate query execution evaluation."""
    print("\n" + "="*60)
    print("DEMO 5: Query Execution Evaluation")
    print("="*60)
    
    actual = [
        {"name": "John Smith", "expertise": "Sensors"},
        {"name": "Jane Doe", "expertise": "Electronics"},
        {"name": "Bob Johnson", "expertise": "Hardware"}
    ]
    
    expected = [
        {"name": "John Smith", "expertise": "Sensors"},
        {"name": "Jane Doe", "expertise": "Electronics"}
    ]
    
    metrics = QueryExecutionEvaluator.evaluate(actual, expected, key_field="name")
    
    print(f"\nExpected Results: {len(expected)}")
    for result in expected:
        print(f"  {result}")
    
    print(f"\nActual Results: {len(actual)}")
    for result in actual:
        print(f"  {result}")
    
    print(f"\nMetrics:")
    print(f"  Precision: {metrics['precision']:.2%} (2 of 3 results were correct)")
    print(f"  Recall:    {metrics['recall']:.2%} (found all 2 expected results)")
    print(f"  F1-Score:  {metrics['f1']:.4f}")
    print(f"  Accuracy:  {metrics['accuracy']:.2%}")
    
    print(f"\nAnalysis:")
    print(f"  ✓ Correct:  {metrics['true_positives']} (John, Jane)")
    print(f"  ✗ Extra:    {metrics['false_positives']} (Bob)")
    print(f"  ✗ Missing:  {metrics['false_negatives']} (none)")


def demo_ground_truth_management():
    """Demonstrate ground truth creation and management."""
    print("\n" + "="*60)
    print("DEMO 6: Ground Truth Management")
    print("="*60)
    
    gt_manager = GroundTruthManager()
    
    # Create ground truth
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
    
    print("\nCreating ground truth for: 'Who is our Sensor expert?'")
    gt_manager.save_ground_truth("Who is our Sensor expert?", ground_truth)
    
    print("✓ Ground truth saved successfully")
    
    # Load it back
    loaded_gt = gt_manager.load_ground_truth_by_question("Who is our Sensor expert?")
    
    print("\nLoaded ground truth back:")
    print(f"  Expected classes: {loaded_gt['expected_classes']}")
    print(f"  Expected entities: {loaded_gt['expected_entities']}")
    print(f"  Expected result count: {len(loaded_gt['expected_results'])}")
    
    # List all ground truths
    all_gts = gt_manager.list_ground_truths()
    print(f"\nTotal ground truth files: {len(all_gts)}")


def demo_evaluation_results():
    """Demonstrate evaluation results saving and viewing."""
    print("\n" + "="*60)
    print("DEMO 7: Evaluation Results Storage")
    print("="*60)
    
    # Create sample evaluation
    evaluation = {
        "question": "Who is our Sensor expert?",
        "timestamp": datetime.now().isoformat(),
        "stages": {
            "class_extraction": {
                "precision": 0.8,
                "recall": 0.67,
                "f1": 0.727,
                "true_positives": 2,
                "false_positives": 1,
                "false_negatives": 1
            },
            "property_extraction": {
                "macro_average": {
                    "precision": 1.0,
                    "recall": 0.83,
                    "f1": 0.909
                },
                "micro_average": {
                    "precision": 1.0,
                    "recall": 0.8,
                    "f1": 0.889
                }
            }
        },
        "overall": {
            "average_f1": 0.834,
            "by_stage": {
                "class_extraction": 0.727,
                "property_extraction_macro": 0.909,
                "property_extraction_micro": 0.889,
                "query_execution": 0.80
            }
        }
    }
    
    print("\nEvaluation created:")
    print(json.dumps(evaluation, indent=2))
    
    # Save it
    eval_manager = EvaluationResultsManager()
    eval_manager.save_evaluation("demo_result.json", evaluation)
    
    print("\n✓ Evaluation saved successfully")
    
    # Get statistics
    stats = eval_manager.get_evaluation_summary()
    print(f"\nEvaluation Statistics:")
    print(f"  Total evaluations: {stats['total_evaluations']}")


def demo_create_ground_truth_template():
    """Demonstrate ground truth template creation."""
    print("\n" + "="*60)
    print("DEMO 8: Ground Truth Template Creation")
    print("="*60)
    
    template = create_ground_truth_template("Your sample question?")
    
    print("\nGenerated Template:")
    print(json.dumps(template, indent=2))
    
    print("\nFields to fill:")
    print("  - expected_classes: Correct class names")
    print("  - expected_properties: Properties relevant to each class")
    print("  - expected_entities: Named entities and their IRIs")
    print("  - expected_results: Expected query results")
    print("  - key_field: Field to use for result comparison")


def demo_gui_consistent_aggregation():
    """Demonstrate GUI-consistent (latest-per-question) aggregation."""
    print("\n" + "="*60)
    print("DEMO 9: GUI-Consistent Aggregation (Latest Per Question)")
    print("="*60)
    
    # Sample evaluations for different runs of the same questions
    sample_evals = [
        {
            "question": "Who works in the sensor department?",
            "timestamp": "2026-05-18T10:00:00",
            "with_examples": True,
            "stages": {
                "query_execution": {
                    "f1": 0.75,
                    "precision": 0.80,
                    "recall": 0.70,
                    "accuracy": 0.75
                }
            }
        },
        {
            "question": "Who works in the Sensor Department?",  # Same question, different punctuation
            "timestamp": "2026-05-18T11:00:00",  # Newer run
            "with_examples": True,
            "stages": {
                "query_execution": {
                    "f1": 0.85,
                    "precision": 0.90,
                    "recall": 0.80,
                    "accuracy": 0.85
                }
            }
        },
        {
            "question": "What products are available?",
            "timestamp": "2026-05-18T10:30:00",
            "with_examples": False,
            "stages": {
                "query_execution": {
                    "f1": 0.65,
                    "precision": 0.70,
                    "recall": 0.60,
                    "accuracy": 0.65
                }
            }
        }
    ]
    
    print("\nSample evaluation data:")
    for i, ev in enumerate(sample_evals, 1):
        qm = extract_query_metrics(ev)
        examples = get_normalized_examples_flag(ev)
        print(f"  {i}. Q: {ev['question'][:40]}"
              f" | TS: {ev['timestamp']}"
              f" | Examples: {examples}"
              f" | F1: {qm['f1'] if qm else 'N/A'}")
    
    print("\nAggregating latest-per-question (GUI logic):")
    agg = aggregate_evaluations_latest_per_question(sample_evals, examples_filter=None)
    
    print(f"\nResults:")
    print(f"  Total evaluations loaded: {agg['total_evaluations']}")
    print(f"  With query metrics: {agg['total_with_query_metrics']}")
    print(f"  Unique questions (latest): {agg['questions_included']}")
    print(f"  Duplicates dropped: {agg['duplicates_dropped']}")
    print(f"\nAggregate Query Metrics (latest per question):")
    print(f"  Average F1:        {agg['average_f1']:.4f}")
    print(f"  Average Precision: {agg['average_precision']:.4f}")
    print(f"  Average Recall:    {agg['average_recall']:.4f}")
    print(f"  Average Accuracy:  {agg['average_accuracy']:.4f}")
    
    print("\nQuestion entries kept (latest per question):")
    for entry in agg["question_entries"]:
        print(f"  - {entry['question'][:40]} "
              f"| TS: {entry['timestamp'].strftime('%H:%M:%S')} "
              f"| F1: {entry['metrics']['f1']}")



def main():
    """Run all demos."""
    print("\n" + "="*60)
    print("NL2SPARQL Evaluation System Demo")
    print("="*60)
    print("\nThis script demonstrates each component of the evaluation system.")
    
    try:
        demo_metrics_calculation()
        demo_class_extraction()
        demo_property_extraction()
        demo_entity_resolution()
        demo_query_execution()
        demo_ground_truth_management()
        demo_evaluation_results()
        demo_create_ground_truth_template()
        demo_gui_consistent_aggregation()
        
        print("\n" + "="*60)
        print("✓ All Demos Completed Successfully!")
        print("="*60)
        
        print("\nNext Steps:")
        print("1. Read EVALUATION_QUICK_START.md for quick usage guide")
        print("2. Read EVALUATION_DOCUMENTATION.md for detailed reference")
        print("3. Check ground_truth/EXAMPLE_GROUND_TRUTH.md for ground truth examples")
        print("4. Create your own ground truth for your test questions")
        print("5. Run pipeline and check evaluation metrics")
        
    except Exception as e:
        print(f"\n✗ Error during demo: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
