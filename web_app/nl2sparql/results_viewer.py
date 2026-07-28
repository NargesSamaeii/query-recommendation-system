"""
Results Viewer Utility

Provides utilities for viewing and analyzing stored results.
"""

import json
import os
from pathlib import Path


def list_all_results(results_dir="tests/results", limit=None):
    """
    List all saved results with key information.
    
    Args:
        results_dir: Directory containing results
        limit: Maximum number of results to return (None = all)
        
    Returns:
        List of result summaries
    """
    if not os.path.exists(results_dir):
        return []
    
    results = []
    files = sorted(
        [f for f in os.listdir(results_dir) if f.endswith('.json')],
        reverse=True
    )
    
    if limit:
        files = files[:limit]
    
    for filename in files:
        try:
            filepath = os.path.join(results_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            summary = {
                "filename": filename,
                "timestamp": data.get("metadata", {}).get("timestamp", ""),
                "question": data.get("metadata", {}).get("question", ""),
                "classes_extracted": data.get("pipeline", {}).get("class_extraction", {}).get("class_count", 0),
                "properties_extracted": data.get("pipeline", {}).get("property_extraction", {}).get("total_properties", 0),
                "entities_resolved": data.get("pipeline", {}).get("missing_id_extraction", {}).get("resolved_count", 0),
                "query_type": data.get("pipeline", {}).get("query_execution", {}).get("query_type", ""),
                "result_count": data.get("pipeline", {}).get("query_execution", {}).get("result_count", 0),
                "stages_completed": data.get("statistics", {}).get("stages_completed", []),
                "has_errors": len(data.get("statistics", {}).get("errors", [])) > 0
            }
            results.append(summary)
        except Exception as e:
            print(f"Error reading {filename}: {e}")
    
    return results


def get_result_details(filename, results_dir="tests/results"):
    """
    Get full details of a specific result.
    
    Args:
        filename: Result filename
        results_dir: Directory containing results
        
    Returns:
        Full result dictionary
    """
    filepath = os.path.join(results_dir, filename)
    if not os.path.exists(filepath):
        return None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_result_by_index(index, results_dir="tests/results"):
    """
    Get result by index (0 = newest).
    
    Args:
        index: Result index
        results_dir: Directory containing results
        
    Returns:
        Full result dictionary
    """
    results = list_all_results(results_dir)
    if index < 0 or index >= len(results):
        return None
    
    return get_result_details(results[index]["filename"], results_dir)


def get_latest_result(results_dir="tests/results"):
    """Get the newest result."""
    result = get_result_by_index(0, results_dir)
    return result


def format_result_for_display(result):
    """
    Format result data for clean display.
    
    Args:
        result: Result dictionary
        
    Returns:
        Formatted string representation
    """
    if not result:
        return "No result found"
    
    lines = []
    lines.append("=" * 80)
    lines.append(f"QUESTION: {result.get('metadata', {}).get('question', '')}")
    lines.append(f"TIMESTAMP: {result.get('metadata', {}).get('timestamp', '')}")
    lines.append("=" * 80)
    
    pipeline = result.get("pipeline", {})
    
    # Class Extraction
    ce = pipeline.get("class_extraction", {})
    lines.append(f"\n[CLASS EXTRACTION]")
    lines.append(f"  Classes Found: {ce.get('class_count', 0)}")
    lines.append(f"  Config: include_examples={ce.get('config', {}).get('include_examples', False)}")
    if ce.get("extracted_classes"):
        lines.append(f"  Classes: {', '.join(ce['extracted_classes'][:5])}")
        if len(ce['extracted_classes']) > 5:
            lines.append(f"           ... and {len(ce['extracted_classes']) - 5} more")
    
    # Property Extraction
    pe = pipeline.get("property_extraction", {})
    lines.append(f"\n[PROPERTY EXTRACTION]")
    lines.append(f"  Total Properties: {pe.get('total_properties', 0)}")
    lines.append(f"  Config: include_examples={pe.get('config', {}).get('include_examples', False)}")
    
    # Missing ID
    mid = pipeline.get("missing_id_extraction", {})
    lines.append(f"\n[MISSING ID EXTRACTION]")
    lines.append(f"  Status: {'Enabled' if mid.get('config', {}).get('enabled') else 'Disabled'}")
    lines.append(f"  Entities Resolved: {mid.get('resolved_count', 0)}")
    if mid.get("resolved_entities"):
        for label, iri in list(mid["resolved_entities"].items())[:3]:
            lines.append(f"    - {label}: {iri[:50]}...")
        if len(mid["resolved_entities"]) > 3:
            lines.append(f"    ... and {len(mid['resolved_entities']) - 3} more")
    
    # Query Generation
    qg = pipeline.get("query_generation", {})
    lines.append(f"\n[QUERY GENERATION]")
    lines.append(f"  Config: include_examples={qg.get('config', {}).get('include_examples', False)}")
    if qg.get("generated_query"):
        query_preview = qg["generated_query"].split('\n')[0]
        lines.append(f"  Query: {query_preview}...")
    
    # Query Execution
    qe = pipeline.get("query_execution", {})
    lines.append(f"\n[QUERY EXECUTION]")
    lines.append(f"  Query Type: {qe.get('query_type', 'UNKNOWN')}")
    lines.append(f"  Results: {qe.get('result_count', 0)} rows")
    if qe.get("execution_error"):
        lines.append(f"  Error: {qe['execution_error']}")
    
    # Statistics
    stats = result.get("statistics", {})
    lines.append(f"\n[STATISTICS]")
    lines.append(f"  Stages Completed: {', '.join(stats.get('stages_completed', []))}")
    lines.append(f"  Errors: {len(stats.get('errors', []))}")
    
    lines.append("=" * 80)
    
    return "\n".join(lines)


def compare_results(filename1, filename2, results_dir="tests/results"):
    """
    Compare two results side-by-side.
    
    Args:
        filename1, filename2: Result filenames
        results_dir: Directory containing results
        
    Returns:
        Comparison string
    """
    r1 = get_result_details(filename1, results_dir)
    r2 = get_result_details(filename2, results_dir)
    
    if not r1 or not r2:
        return "One or both results not found"
    
    lines = []
    lines.append("COMPARISON")
    lines.append(f"Result 1: {filename1}")
    lines.append(f"Result 2: {filename2}")
    lines.append("")
    
    q1 = r1.get("metadata", {}).get("question", "")
    q2 = r2.get("metadata", {}).get("question", "")
    
    lines.append(f"Question 1: {q1}")
    lines.append(f"Question 2: {q2}")
    lines.append(f"Same Question: {q1 == q2}")
    lines.append("")
    
    # Compare pipeline results
    p1 = r1.get("pipeline", {})
    p2 = r2.get("pipeline", {})
    
    ce1 = p1.get("class_extraction", {}).get("class_count", 0)
    ce2 = p2.get("class_extraction", {}).get("class_count", 0)
    
    pe1 = p1.get("property_extraction", {}).get("total_properties", 0)
    pe2 = p2.get("property_extraction", {}).get("total_properties", 0)
    
    mid1 = p1.get("missing_id_extraction", {}).get("resolved_count", 0)
    mid2 = p2.get("missing_id_extraction", {}).get("resolved_count", 0)
    
    rc1 = p1.get("query_execution", {}).get("result_count", 0)
    rc2 = p2.get("query_execution", {}).get("result_count", 0)
    
    lines.append(f"Classes Extracted: {ce1} vs {ce2}")
    lines.append(f"Properties Extracted: {pe1} vs {pe2}")
    lines.append(f"Entities Resolved: {mid1} vs {mid2}")
    lines.append(f"Result Count: {rc1} vs {rc2}")
    
    return "\n".join(lines)


if __name__ == "__main__":
    # Example usage
    print("Latest Results:")
    results = list_all_results(limit=5)
    for i, r in enumerate(results):
        print(f"{i}. {r['timestamp']} - {r['question'][:50]}... ({r['classes_extracted']} classes, {r['result_count']} results)")
    
    if results:
        print("\n" + format_result_for_display(get_latest_result()))
