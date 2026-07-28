#!/usr/bin/env python3
"""
Results organizer for multi-KG multi-model evaluations.

Automatically organizes evaluation results into KG+Model folders.
"""

import os
import shutil
from pathlib import Path
import json


class ResultsOrganizer:
    """Organize evaluation results by KG and Model."""
    
    def __init__(self, base_eval_dir="tests/evaluation_results"):
        """Initialize organizer."""
        self.base_eval_dir = Path(base_eval_dir)
        self.base_eval_dir.mkdir(exist_ok=True)
    
    def get_kg_model_folder(self, kg_name, model_name):
        """Get path to KG+Model folder."""
        folder_name = f"{kg_name}_{model_name}"
        path = self.base_eval_dir / folder_name
        
        # Create subdirectories
        (path / "ground_truth").mkdir(parents=True, exist_ok=True)
        (path / "results").mkdir(parents=True, exist_ok=True)
        (path / "evaluation").mkdir(parents=True, exist_ok=True)
        
        return path
    
    def move_evaluation_and_related_files(self, eval_file_path, gt_file_path, result_file_path, kg_name, model_name):
        """Move evaluation, ground-truth, and result files to KG+Model subfolders."""
        eval_file = Path(eval_file_path) if eval_file_path else None
        gt_file = Path(gt_file_path) if gt_file_path else None
        result_file = Path(result_file_path) if result_file_path else None

        kg_model_dir = self.get_kg_model_folder(kg_name, model_name)
        moved_files = {}

        # Copy evaluation file
        if eval_file and eval_file.exists():
            target_eval = kg_model_dir / "evaluation" / eval_file.name
            try:
                shutil.copy(eval_file, target_eval)
                moved_files['evaluation'] = str(target_eval)
            except Exception as e:
                print(f"Error moving evaluation file: {e}")

        # Copy ground-truth file
        if gt_file and gt_file.exists():
            target_gt = kg_model_dir / "ground_truth" / gt_file.name
            try:
                shutil.copy(gt_file, target_gt)
                moved_files['ground_truth'] = str(target_gt)
            except Exception as e:
                print(f"Error moving ground-truth file: {e}")

        # Copy result file
        if result_file and result_file.exists():
            target_result = kg_model_dir / "results" / result_file.name
            try:
                shutil.copy(result_file, target_result)
                moved_files['result'] = str(target_result)
            except Exception as e:
                print(f"Error moving result file: {e}")

        return moved_files if moved_files else None
    
    def organize_from_config(self, config):
        """Organize results based on config KG and Model."""
        kg_name = config.get("kg", {}).get("name", "default")
        
        # Get model name
        llm_config = config.get("llm", {})
        model_name = llm_config.get("provider", "default")
        
        return kg_name, model_name
    
    def tag_evaluation_with_kg_model(self, eval_data, kg_name, model_name):
        """Add KG and Model tags to evaluation data."""
        eval_data["kg"] = kg_name
        eval_data["model"] = model_name
        return eval_data


if __name__ == "__main__":
    # Test
    organizer = ResultsOrganizer()
    kg_model_dir = organizer.get_kg_model_folder("copypu", "gemini")
    print(f"Created: {kg_model_dir}")
