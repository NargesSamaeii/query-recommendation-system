"""
Evaluation Viewer Utilities

Utilities for viewing and analyzing evaluation results.

Uses consistent logic with GUI for aggregating evaluations by latest-per-question.
"""

import json
import os
import re
import statistics
from datetime import datetime
from typing import Dict, List, Optional, Set


# ============================================================================
# Question Normalization and Timestamp Parsing (GUI-Consistent)
# ============================================================================

def normalize_question_key(question_text: str) -> Optional[str]:
    """
    Normalize question text for consistent matching across punctuation variants.
    
    This matches the GUI logic in gui_v2.py to ensure consistent question grouping.
    
    Args:
        question_text: Raw question text
        
    Returns:
        Normalized key (lowercase, whitespace collapsed) or None if empty
    """
    if question_text is None:
        return None
    text = str(question_text).strip()
    if not text:
        return None
    return " ".join(text.split()).lower()


def parse_eval_timestamp(eval_data: Dict) -> datetime:
    """
    Parse timestamp from evaluation data safely.
    
    Args:
        eval_data: Evaluation JSON dict
        
    Returns:
        Parsed datetime or datetime.min if parsing fails
    """
    raw = eval_data.get('timestamp')
    if not raw:
        return datetime.min
    try:
        return datetime.fromisoformat(str(raw).replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return datetime.min


def extract_query_metrics(eval_data: Dict) -> Optional[Dict]:
    """
    Extract query_execution metrics from evaluation data.
    
    Used to filter evaluations that have query_execution results (consistent with GUI).
    
    Args:
        eval_data: Evaluation JSON dict
        
    Returns:
        Dict with f1, precision, recall, accuracy or None if not found
    """
    stages = eval_data.get('stages', {})
    q = stages.get('query_execution', {})
    
    if not q:
        return None
    
    f1 = q.get('f1')
    precision = q.get('precision')
    recall = q.get('recall')
    accuracy = q.get('accuracy')
    
    if f1 is None:
        f1 = q.get('set_f1')
    if precision is None:
        precision = q.get('set_precision')
    if recall is None:
        recall = q.get('set_recall')
    
    if all(v is None for v in [f1, precision, recall, accuracy]):
        return None
    
    return {
        'f1': float(f1) if f1 is not None else None,
        'precision': float(precision) if precision is not None else None,
        'recall': float(recall) if recall is not None else None,
        'accuracy': float(accuracy) if accuracy is not None else None,
    }


def get_normalized_examples_flag(eval_data: Dict) -> Optional[bool]:
    """
    Extract with_examples flag from evaluation data with multiple fallback paths.
    
    Matches GUI logic for detecting whether examples were used.
    
    Args:
        eval_data: Evaluation JSON dict
        
    Returns:
        True (with examples), False (without examples), or None (unknown)
    """
    candidates = [
        eval_data.get('with_examples'),
        eval_data.get('metadata', {}).get('with_examples'),
        eval_data.get('config', {}).get('pipeline', {}).get('schema', {}).get('query_generation', {}).get('include_examples'),
    ]
    
    for raw in candidates:
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, (int, float)):
            return bool(raw)
        if isinstance(raw, str):
            txt = raw.strip().lower()
            if txt in {"true", "1", "yes", "y", "with", "with examples", "with_examples"}:
                return True
            if txt in {"false", "0", "no", "n", "without", "without examples", "without_examples"}:
                return False
    
    return None


def average_metric(metric_rows: List[Dict], key: str) -> Optional[float]:
    """
    Average a metric across multiple evaluation rows.
    
    Args:
        metric_rows: List of metric dicts
        key: Key to average (e.g., 'f1', 'precision')
        
    Returns:
        Rounded average or None if no valid values
    """
    vals = [r[key] for r in metric_rows if r.get(key) is not None]
    return round(statistics.mean(vals), 4) if vals else None


def aggregate_evaluations_latest_per_question(
    eval_files: List[Dict],
    examples_filter: Optional[bool] = None
) -> Dict:
    """
    Aggregate evaluations keeping only the latest run per question.
    
    This mirrors the GUI logic for computing final aggregates:
    1. Group evaluations by normalized question text
    2. For each question, keep only the entry with the latest timestamp
    3. Average metrics across the kept entries
    
    Args:
        eval_files: List of loaded evaluation dicts
        examples_filter: Filter by with_examples flag 
                         (True=with, False=without, None=all)
    
    Returns:
        Dict with:
        - 'total_evaluations': count loaded
        - 'total_with_query_metrics': count with query_execution metrics
        - 'questions_included': count of unique questions kept
        - 'evaluations_processed': count after dedup
        - 'duplicates_dropped': count of older entries dropped
        - 'average_f1', 'average_precision', 'average_recall', 'average_accuracy'
        - 'question_entries': list of {question, timestamp, metrics} entries kept
    """
    if not eval_files:
        return {
            'total_evaluations': 0,
            'total_with_query_metrics': 0,
            'questions_included': 0,
            'evaluations_processed': 0,
            'duplicates_dropped': 0,
            'average_f1': None,
            'average_precision': None,
            'average_recall': None,
            'average_accuracy': None,
            'question_entries': []
        }
    
    # Track pools by (normalized_question_text, examples_flag)
    pools = {}  # (q_key, mode) -> [entry, ...]
    metrics_pool = []  # Final metrics to aggregate
    total_with_metrics = 0
    duplicates_dropped = 0
    
    for eval_data in eval_files:
        qm = extract_query_metrics(eval_data)
        if not qm:
            continue
        
        total_with_metrics += 1
        
        question_text = eval_data.get('question') or eval_data.get('metadata', {}).get('question')
        question_key = normalize_question_key(question_text)
        if not question_key:
            continue
        
        ts = parse_eval_timestamp(eval_data)
        flag = get_normalized_examples_flag(eval_data)
        
        # Determine mode label
        if examples_filter is None:
            # Include both modes
            mode_tuple = ("all", True)
        elif flag == examples_filter:
            # Include if matches filter
            mode_tuple = ("filtered", flag)
        else:
            # Skip if doesn't match filter
            continue
        
        # Get or create pool for this question+mode
        pool_key = (question_key, mode_tuple)
        if pool_key not in pools:
            pools[pool_key] = []
        
        # Check if we already have an entry for this question+mode
        existing_entry = None
        for entry in pools[pool_key]:
            if entry['timestamp'] < ts:
                # Replace with newer
                existing_entry = entry
                break
        
        if existing_entry:
            duplicates_dropped += 1
            pools[pool_key].remove(existing_entry)
        
        entry = {
            'question': question_text,
            'question_key': question_key,
            'timestamp': ts,
            'metrics': qm,
            'with_examples': flag
        }
        pools[pool_key].append(entry)
    
    # Flatten all pools and collect metrics
    all_question_entries = []
    for pool_entries in pools.values():
        for entry in pool_entries:
            all_question_entries.append(entry)
            if entry['metrics']:
                metrics_pool.append(entry['metrics'])
    
    # Calculate aggregates
    return {
        'total_evaluations': len(eval_files),
        'total_with_query_metrics': total_with_metrics,
        'questions_included': len(all_question_entries),
        'evaluations_processed': total_with_metrics,
        'duplicates_dropped': duplicates_dropped,
        'average_f1': average_metric(metrics_pool, 'f1'),
        'average_precision': average_metric(metrics_pool, 'precision'),
        'average_recall': average_metric(metrics_pool, 'recall'),
        'average_accuracy': average_metric(metrics_pool, 'accuracy'),
        'question_entries': all_question_entries
    }


def list_all_evaluations(eval_dir: str = "evaluation_results", limit: int = None) -> List[Dict]:
    """
    List all saved evaluations.
    
    Args:
        eval_dir: Directory containing evaluation results
        limit: Maximum number to return
        
    Returns:
        List of evaluation summaries
    """
    if not os.path.exists(eval_dir):
        return []
    
    evaluations = []
    files = sorted(
        [f for f in os.listdir(eval_dir) if f.endswith('_eval.json')],
        reverse=True
    )
    
    if limit:
        files = files[:limit]
    
    for filename in files:
        try:
            filepath = os.path.join(eval_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            overall = data.get("overall", {})
            stages = data.get("stages", {})
            
            summary = {
                "filename": filename,
                "question": data.get("question", ""),
                "timestamp": data.get("timestamp", ""),
                "average_f1": overall.get("average_f1", 0),
                "stages_evaluated": len(stages),
                "stage_details": {}
            }
            
            for stage, metrics in stages.items():
                if "f1" in metrics:
                    summary["stage_details"][stage] = {
                        "f1": metrics.get("f1", 0),
                        "precision": metrics.get("precision", 0),
                        "recall": metrics.get("recall", 0)
                    }
                elif "macro_average" in metrics:
                    macro = metrics["macro_average"]
                    summary["stage_details"][stage] = {
                        "f1": macro.get("f1", 0),
                        "precision": macro.get("precision", 0),
                        "recall": macro.get("recall", 0)
                    }
            
            evaluations.append(summary)
        except Exception as e:
            print(f"Error reading {filename}: {e}")
    
    return evaluations


def get_latest_evaluation(eval_dir: str = "evaluation_results") -> Optional[Dict]:
    """Get the newest evaluation."""
    evaluations = list_all_evaluations(eval_dir, limit=1)
    if evaluations:
        filepath = os.path.join(eval_dir, evaluations[0]["filename"])
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def get_evaluation_details(filename: str, eval_dir: str = "evaluation_results") -> Optional[Dict]:
    """
    Get full details of a specific evaluation.
    
    Args:
        filename: Evaluation filename
        eval_dir: Evaluation directory
        
    Returns:
        Full evaluation dictionary
    """
    filepath = os.path.join(eval_dir, filename)
    if not os.path.exists(filepath):
        return None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def format_evaluation_for_display(evaluation: Dict) -> str:
    """
    Format evaluation data for clean display.
    
    Args:
        evaluation: Evaluation dictionary
        
    Returns:
        Formatted string representation
    """
    if not evaluation:
        return "No evaluation found"
    
    lines = []
    lines.append("=" * 80)
    lines.append(f"EVALUATION REPORT")
    lines.append("=" * 80)
    
    lines.append(f"\nQUESTION: {evaluation.get('question', '')}")
    lines.append(f"TIMESTAMP: {evaluation.get('timestamp', '')}")
    
    # Overall metrics
    overall = evaluation.get("overall", {})
    if overall:
        lines.append(f"\n[OVERALL PERFORMANCE]")
        lines.append(f"  Average F1-Score: {overall.get('average_f1', 0):.4f}")
        lines.append(f"  Stages Evaluated: {overall.get('stages_evaluated', 0)}")
    
    # Stage-by-stage metrics
    stages = evaluation.get("stages", {})
    if stages:
        lines.append(f"\n[STAGE-BY-STAGE METRICS]")
        
        for stage_name, metrics in stages.items():
            lines.append(f"\n  {stage_name.upper()}")
            
            if "f1" in metrics:
                lines.append(f"    Precision: {metrics.get('precision', 0):.4f}")
                lines.append(f"    Recall:    {metrics.get('recall', 0):.4f}")
                lines.append(f"    F1-Score:  {metrics.get('f1', 0):.4f}")
                lines.append(f"    Accuracy:  {metrics.get('accuracy', 0):.4f}")
                
                if "true_positives" in metrics:
                    lines.append(f"    True Positives:  {metrics.get('tp_count', 0)}")
                    lines.append(f"    False Positives: {metrics.get('fp_count', 0)}")
                    lines.append(f"    False Negatives: {metrics.get('fn_count', 0)}")
            
            elif "macro_average" in metrics:
                macro = metrics["macro_average"]
                lines.append(f"    Macro Average:")
                lines.append(f"      Precision: {macro.get('precision', 0):.4f}")
                lines.append(f"      Recall:    {macro.get('recall', 0):.4f}")
                lines.append(f"      F1-Score:  {macro.get('f1', 0):.4f}")
                
                micro = metrics.get("micro_average", {})
                if micro:
                    lines.append(f"    Micro Average:")
                    lines.append(f"      Precision: {micro.get('precision', 0):.4f}")
                    lines.append(f"      Recall:    {micro.get('recall', 0):.4f}")
                    lines.append(f"      F1-Score:  {micro.get('f1', 0):.4f}")
                
                total = metrics.get("total_counts", {})
                if total:
                    lines.append(f"    Totals:")
                    lines.append(f"      True Positives:  {total.get('true_positives', 0)}")
                    lines.append(f"      False Positives: {total.get('false_positives', 0)}")
                    lines.append(f"      False Negatives: {total.get('false_negatives', 0)}")
    
    lines.append("\n" + "=" * 80)
    
    return "\n".join(lines)


def compare_evaluations(filename1: str, filename2: str, eval_dir: str = "evaluation_results") -> str:
    """
    Compare two evaluations side-by-side.
    
    Args:
        filename1, filename2: Evaluation filenames
        eval_dir: Evaluation directory
        
    Returns:
        Comparison string
    """
    e1 = get_evaluation_details(filename1, eval_dir)
    e2 = get_evaluation_details(filename2, eval_dir)
    
    if not e1 or not e2:
        return "One or both evaluations not found"
    
    lines = []
    lines.append("EVALUATION COMPARISON")
    lines.append(f"Evaluation 1: {filename1}")
    lines.append(f"Evaluation 2: {filename2}")
    lines.append("")
    
    q1 = e1.get("question", "")
    q2 = e2.get("question", "")
    lines.append(f"Question 1: {q1[:60]}...")
    lines.append(f"Question 2: {q2[:60]}...")
    lines.append("")
    
    # Compare overall F1
    o1_f1 = e1.get("overall", {}).get("average_f1", 0)
    o2_f1 = e2.get("overall", {}).get("average_f1", 0)
    improvement = ((o2_f1 - o1_f1) / o1_f1 * 100) if o1_f1 > 0 else 0
    
    lines.append(f"Overall F1-Score:")
    lines.append(f"  Eval 1: {o1_f1:.4f}")
    lines.append(f"  Eval 2: {o2_f1:.4f}")
    lines.append(f"  Change: {improvement:+.1f}%")
    lines.append("")
    
    # Compare stage results
    stages1 = e1.get("stages", {})
    stages2 = e2.get("stages", {})
    all_stages = set(stages1.keys()) | set(stages2.keys())
    
    lines.append("Stage Comparison:")
    for stage in sorted(all_stages):
        m1 = stages1.get(stage, {})
        m2 = stages2.get(stage, {})
        
        f1_1 = m1.get("f1", m1.get("macro_average", {}).get("f1", 0))
        f1_2 = m2.get("f1", m2.get("macro_average", {}).get("f1", 0))
        
        lines.append(f"  {stage}:")
        lines.append(f"    Eval 1 F1: {f1_1:.4f}")
        lines.append(f"    Eval 2 F1: {f1_2:.4f}")
        if f1_1 > 0:
            change = ((f1_2 - f1_1) / f1_1 * 100)
            lines.append(f"    Change:   {change:+.1f}%")
    
    return "\n".join(lines)


def get_evaluation_statistics(eval_dir: str = "evaluation_results", latest_per_question: bool = True) -> Dict:
    """
    Get statistics across all evaluations.
    
    Args:
        eval_dir: Evaluation directory
        latest_per_question: If True, aggregate using GUI logic (latest run per question).
                             If False, use all evaluations.
        
    Returns:
        Statistics dictionary
    """
    summaries = list_all_evaluations(eval_dir)
    
    if not summaries:
        return {
            "total_evaluations": 0,
            "average_f1": 0,
            "stage_averages": {},
            "aggregation_method": "latest_per_question" if latest_per_question else "all"
        }
    
    # If latest_per_question, load full eval files and aggregate
    if latest_per_question:
        all_evals = []
        for summary in summaries:
            eval_details = get_evaluation_details(summary["filename"], eval_dir)
            if eval_details:
                all_evals.append(eval_details)
        
        agg = aggregate_evaluations_latest_per_question(all_evals, examples_filter=None)
        
        return {
            "total_evaluations": agg["total_evaluations"],
            "total_with_query_metrics": agg["total_with_query_metrics"],
            "questions_included": agg["questions_included"],
            "duplicates_dropped": agg["duplicates_dropped"],
            "average_f1": agg["average_f1"],
            "average_precision": agg["average_precision"],
            "average_recall": agg["average_recall"],
            "average_accuracy": agg["average_accuracy"],
            "aggregation_method": "latest_per_question",
            "evaluations_summary": summaries
        }
    
    # Otherwise aggregate all (legacy behavior)
    avg_f1 = sum(e.get("average_f1", 0) for e in summaries) / len(summaries)
    
    # Calculate stage averages
    stage_scores = {}
    for eval_result in summaries:
        for stage, details in eval_result.get("stage_details", {}).items():
            if stage not in stage_scores:
                stage_scores[stage] = {
                    "f1": [],
                    "precision": [],
                    "recall": []
                }
            stage_scores[stage]["f1"].append(details.get("f1", 0))
            stage_scores[stage]["precision"].append(details.get("precision", 0))
            stage_scores[stage]["recall"].append(details.get("recall", 0))
    
    stage_averages = {}
    for stage, scores in stage_scores.items():
        stage_averages[stage] = {
            "avg_f1": round(sum(scores["f1"]) / len(scores["f1"]), 4),
            "avg_precision": round(sum(scores["precision"]) / len(scores["precision"]), 4),
            "avg_recall": round(sum(scores["recall"]) / len(scores["recall"]), 4)
        }
    
    return {
        "total_evaluations": len(summaries),
        "average_f1": round(avg_f1, 4),
        "stage_averages": stage_averages,
        "best_evaluation": max(summaries, key=lambda e: e.get("average_f1", 0))["filename"]
            if summaries else None,
        "best_f1": max((e.get("average_f1", 0) for e in summaries), default=0),
        "aggregation_method": "all",
        "evaluations_summary": summaries
    }


def print_evaluation_summary(eval_dir: str = "evaluation_results", latest_per_question: bool = True):
    """
    Print a summary of all evaluations.
    
    Args:
        eval_dir: Evaluation directory
        latest_per_question: Use latest-per-question aggregation logic (GUI-consistent)
    """
    stats = get_evaluation_statistics(eval_dir, latest_per_question=latest_per_question)
    
    print("\nEVALUATION SUMMARY")
    print("=" * 80)
    print(f"Aggregation Method: {stats.get('aggregation_method', 'unknown')}")
    print(f"Total Evaluations Loaded: {stats['total_evaluations']}")
    
    if stats.get('aggregation_method') == 'latest_per_question':
        print(f"Evaluations with Query Metrics: {stats.get('total_with_query_metrics', 0)}")
        print(f"Unique Questions (Latest Per Question): {stats.get('questions_included', 0)}")
        print(f"Duplicates Dropped: {stats.get('duplicates_dropped', 0)}")
    
    print(f"\nAggregate Query Execution Metrics:")
    print(f"  Average F1:        {stats['average_f1']:.4f}" if stats.get('average_f1') else f"  Average F1:        N/A")
    print(f"  Average Precision: {stats['average_precision']:.4f}" if stats.get('average_precision') else f"  Average Precision: N/A")
    print(f"  Average Recall:    {stats['average_recall']:.4f}" if stats.get('average_recall') else f"  Average Recall:    N/A")
    print(f"  Average Accuracy:  {stats['average_accuracy']:.4f}" if stats.get('average_accuracy') else f"  Average Accuracy:  N/A")
    
    if stats.get('stage_averages'):
        print(f"\nStage Averages:")
        for stage, avg in stats['stage_averages'].items():
            print(f"  {stage}:")
            print(f"    F1:        {avg['avg_f1']:.4f}")
            print(f"    Precision: {avg['avg_precision']:.4f}")
            print(f"    Recall:    {avg['avg_recall']:.4f}")
    
    if stats.get('best_evaluation'):
        print(f"\nBest Evaluation: {stats['best_evaluation']}")
        print(f"Best F1-Score: {stats['best_f1']:.4f}")
    
    print("=" * 80)


if __name__ == "__main__":
    print_evaluation_summary()
