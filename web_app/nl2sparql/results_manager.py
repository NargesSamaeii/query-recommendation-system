"""
Results Manager

Manages comprehensive result storage with clean JSON formatting.
"""

import json
import os
from datetime import datetime
from pathlib import Path


class ResultsManager:
    """Stores and manages pipeline results in a structured JSON format."""
    
    def __init__(self, results_dir="tests/results"):
        """
        Initialize results manager.
        
        Args:
            results_dir: Directory to save results
        """
        self.results_dir = results_dir
        os.makedirs(results_dir, exist_ok=True)
    
    def create_result_entry(self, question):
        """
        Create a new result entry structure.
        
        Args:
            question: The user's natural language question
            
        Returns:
            Dictionary with result structure
        """
        return {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "question": question
            },
            "pipeline": {
                "query_routing": {
                    "config": {"enabled": None},
                    "route": None,
                    "confidence": None,
                    "reason": None,
                    "schema_summary": None
                },
                "class_extraction": {
                    "config": {"include_examples": None},
                    "extracted_classes": [],
                    "class_count": 0,
                    "schema_with_examples": None,
                    "schema_without_examples": None
                },
                "property_extraction": {
                    "config": {"include_examples": None},
                    "property_selection": [],
                    "total_properties": 0,
                    "schema_with_examples": None,
                    "schema_without_examples": None
                },
                "missing_id_extraction": {
                    "config": {"enabled": False, "max_iris": None},
                    "missing_id_query": None,
                    "resolved_entities": {},
                    "resolved_count": 0,
                    "schema_passed_to_llm": None
                },
                "query_generation": {
                    "config": {"include_examples": None},
                    "schema_with_examples": None,
                    "schema_without_examples": None,
                    "generated_query": None
                },
                "query_execution": {
                    "config": {},
                    "executed_query": None,
                    "query_type": None,  # SELECT, ASK, CONSTRUCT, DESCRIBE
                    "raw_results": None,
                    "formatted_results": None,
                    "result_count": 0,
                    "execution_error": None
                }
            },
            "prompts": {
                "query_routing_prompt": None,
                "class_extraction_prompts": [],
                "property_extraction_prompts": [],
                "missing_id_query_prompt": None,
                "final_query_generation_prompt": None
            },
            "statistics": {
                "stages_completed": [],
                "total_time_ms": None,
                "errors": []
            },
            "evaluation": None
        }
    
    def update_class_extraction(self, result, extracted_classes, config, schema_with, schema_without, prompts):
        """Update class extraction results."""
        result["pipeline"]["class_extraction"]["extracted_classes"] = extracted_classes
        result["pipeline"]["class_extraction"]["class_count"] = len(extracted_classes)
        result["pipeline"]["class_extraction"]["config"] = config
        result["pipeline"]["class_extraction"]["schema_with_examples"] = schema_with
        result["pipeline"]["class_extraction"]["schema_without_examples"] = schema_without
        result["prompts"]["class_extraction_prompts"] = prompts if isinstance(prompts, list) else [prompts]
        if "class_extraction" not in result["statistics"]["stages_completed"]:
            result["statistics"]["stages_completed"].append("class_extraction")

    def update_query_routing(self, result, route, confidence, reason, config, schema_summary, prompt):
        """Update routing decision results."""
        result["pipeline"]["query_routing"]["route"] = route
        result["pipeline"]["query_routing"]["confidence"] = confidence
        result["pipeline"]["query_routing"]["reason"] = reason
        result["pipeline"]["query_routing"]["config"] = config
        result["pipeline"]["query_routing"]["schema_summary"] = schema_summary
        result["prompts"]["query_routing_prompt"] = prompt
        if "query_routing" not in result["statistics"]["stages_completed"]:
            result["statistics"]["stages_completed"].append("query_routing")
    
    def update_property_extraction(self, result, property_selection, config, schema_with, schema_without, prompts):
        """Update property extraction results."""
        result["pipeline"]["property_extraction"]["property_selection"] = property_selection
        result["pipeline"]["property_extraction"]["total_properties"] = sum(
            len(p.get("relevant_properties", [])) for p in property_selection
        )
        result["pipeline"]["property_extraction"]["config"] = config
        result["pipeline"]["property_extraction"]["schema_with_examples"] = schema_with
        result["pipeline"]["property_extraction"]["schema_without_examples"] = schema_without
        result["prompts"]["property_extraction_prompts"] = prompts if isinstance(prompts, list) else [prompts]
        if "property_extraction" not in result["statistics"]["stages_completed"]:
            result["statistics"]["stages_completed"].append("property_extraction")
    
    def update_missing_id(self, result, query, resolved_entities, config, schema_passed, prompt):
        """Update missing ID extraction results."""
        result["pipeline"]["missing_id_extraction"]["missing_id_query"] = query
        result["pipeline"]["missing_id_extraction"]["resolved_entities"] = resolved_entities
        result["pipeline"]["missing_id_extraction"]["resolved_count"] = len(resolved_entities)
        result["pipeline"]["missing_id_extraction"]["config"] = config
        result["pipeline"]["missing_id_extraction"]["schema_passed_to_llm"] = schema_passed
        result["prompts"]["missing_id_query_prompt"] = prompt
        if "missing_id_extraction" not in result["statistics"]["stages_completed"]:
            result["statistics"]["stages_completed"].append("missing_id_extraction")
    
    def update_query_generation(self, result, generated_query, config, schema_with, schema_without, prompt):
        """Update final query generation results."""
        result["pipeline"]["query_generation"]["generated_query"] = generated_query
        result["pipeline"]["query_generation"]["config"] = config
        result["pipeline"]["query_generation"]["schema_with_examples"] = schema_with
        result["pipeline"]["query_generation"]["schema_without_examples"] = schema_without
        result["prompts"]["final_query_generation_prompt"] = prompt
        if "query_generation" not in result["statistics"]["stages_completed"]:
            result["statistics"]["stages_completed"].append("query_generation")
    
    def update_query_execution(self, result, executed_query, query_type, raw_results, formatted_results, error=None):
        """Update query execution results."""
        result["pipeline"]["query_execution"]["executed_query"] = executed_query
        result["pipeline"]["query_execution"]["query_type"] = query_type
        result["pipeline"]["query_execution"]["raw_results"] = raw_results
        result["pipeline"]["query_execution"]["formatted_results"] = formatted_results
        result["pipeline"]["query_execution"]["execution_error"] = error
        
        # Count results
        if raw_results and "results" in raw_results and "bindings" in raw_results["results"]:
            result["pipeline"]["query_execution"]["result_count"] = len(raw_results["results"]["bindings"])
        elif raw_results and "boolean" in raw_results:
            result["pipeline"]["query_execution"]["result_count"] = 1  # Boolean result
        
        if "query_execution" not in result["statistics"]["stages_completed"]:
            result["statistics"]["stages_completed"].append("query_execution")
    
    def add_error(self, result, stage, error_message):
        """Add error to results."""
        result["statistics"]["errors"].append({
            "stage": stage,
            "message": str(error_message),
            "timestamp": datetime.now().isoformat()
        })
    
    def save_result(self, result, filename_prefix="result"):
        """
        Save result to JSON file.
        
        Args:
            result: Result dictionary
            filename_prefix: Prefix for filename (default: "result")
            
        Returns:
            Path to saved file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_prefix}_{timestamp}.json"
        filepath = os.path.join(self.results_dir, filename)
        
        # Ensure results directory exists
        os.makedirs(self.results_dir, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def save_result_with_custom_name(self, result, custom_name):
        """
        Save result with a custom filename (without timestamp).
        
        Args:
            result: Result dictionary
            custom_name: Custom filename (without .json extension)
            
        Returns:
            Path to saved file
        """
        filename = f"{custom_name}.json"
        filepath = os.path.join(self.results_dir, filename)
        
        os.makedirs(self.results_dir, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def load_result(self, filepath):
        """
        Load result from JSON file.
        
        Args:
            filepath: Path to result file
            
        Returns:
            Result dictionary
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_latest_results(self, limit=5):
        """
        Get the latest saved results.
        
        Args:
            limit: Number of latest results to retrieve
            
        Returns:
            List of (filename, result) tuples sorted by timestamp
        """
        if not os.path.exists(self.results_dir):
            return []
        
        files = sorted(
            [(f, os.path.getmtime(os.path.join(self.results_dir, f))) 
             for f in os.listdir(self.results_dir) if f.endswith('.json')],
            key=lambda x: x[1],
            reverse=True
        )[:limit]
        
        results = []
        for filename, _ in files:
            try:
                filepath = os.path.join(self.results_dir, filename)
                data = self.load_result(filepath)
                results.append((filename, data))
            except Exception as e:
                print(f"Error loading {filename}: {e}")
        
        return results
    
    def get_summary_stats(self):
        """
        Get summary statistics of all saved results.
        
        Returns:
            Dictionary with overall statistics
        """
        if not os.path.exists(self.results_dir):
            return {"total_results": 0, "files": []}
        
        files = [f for f in os.listdir(self.results_dir) if f.endswith('.json')]
        
        stats = {
            "total_results": len(files),
            "files": sorted(files, reverse=True),
            "oldest": None,
            "newest": None,
            "average_queries_per_result": 0
        }
        
        if files:
            modify_times = [(f, os.path.getmtime(os.path.join(self.results_dir, f))) for f in files]
            modify_times.sort(key=lambda x: x[1])
            stats["oldest"] = modify_times[0][0]
            stats["newest"] = modify_times[-1][0]
        
        return stats
    
    def export_to_csv(self, filepath):
        """
        Export all results to a CSV file for analysis.
        
        Args:
            filepath: Path to save CSV file
        """
        import csv
        
        if not os.path.exists(self.results_dir):
            return
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'timestamp', 'question', 'classes_extracted', 'properties_extracted',
                'entities_resolved', 'query_type', 'result_count', 'stages_completed', 'errors'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            files = [f for f in os.listdir(self.results_dir) if f.endswith('.json')]
            for filename in sorted(files, reverse=True):
                try:
                    filepath_full = os.path.join(self.results_dir, filename)
                    data = self.load_result(filepath_full)
                    
                    row = {
                        'timestamp': data['metadata'].get('timestamp', ''),
                        'question': data['metadata'].get('question', ''),
                        'classes_extracted': data['pipeline']['class_extraction'].get('class_count', 0),
                        'properties_extracted': data['pipeline']['property_extraction'].get('total_properties', 0),
                        'entities_resolved': data['pipeline']['missing_id_extraction'].get('resolved_count', 0),
                        'query_type': data['pipeline']['query_execution'].get('query_type', ''),
                        'result_count': data['pipeline']['query_execution'].get('result_count', 0),
                        'stages_completed': ', '.join(data['statistics'].get('stages_completed', [])),
                        'errors': len(data['statistics'].get('errors', []))
                    }
                    writer.writerow(row)
                except Exception as e:
                    print(f"Error processing {filename}: {e}")
