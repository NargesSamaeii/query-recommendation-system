"""Ground truth and evaluation file management utilities."""

import json
import os
import re
from datetime import datetime
from pathlib import Path


class GroundTruthManager:
    """Handles loading and matching ground-truth files for evaluation."""

    def __init__(self, ground_truth_dir="tests/ground_truth"):
        self.ground_truth_dir = Path(ground_truth_dir)

    def _kg_folder(self, kg_name):
        return self.ground_truth_dir / (kg_name or "default")

    @staticmethod
    def _normalize_question(text):
        """Normalize question text for resilient matching across punctuation variants."""
        value = str(text or "").strip().lower()
        if not value:
            return ""

        # Normalize common typographic variations
        value = value.replace("\u2014", "-")  # em dash
        value = value.replace("\u2013", "-")  # en dash
        value = value.replace("\u2018", "'").replace("\u2019", "'")
        value = value.replace("\u201c", '"').replace("\u201d", '"')

        # Normalize spacing around hyphens and collapse whitespace
        value = re.sub(r"\s*-\s*", " - ", value)
        value = re.sub(r"\s+", " ", value).strip()
        return value

    def get_ground_truth_files(self, kg_name):
        folder = self._kg_folder(kg_name)
        if not folder.exists():
            return []
        return sorted(folder.glob("*.json"))

    def load_ground_truth(self, kg_name):
        """Load all ground-truth records for a KG from tests/ground_truth/<kg_name>."""
        all_records = []
        for file_path in self.get_ground_truth_files(kg_name):
            try:
                # Use utf-8-sig to handle UTF-8 BOM if present
                with open(file_path, "r", encoding="utf-8-sig") as file:
                    data = json.load(file)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            item.setdefault("__source_file", str(file_path))
                            all_records.append(item)
                elif isinstance(data, dict):
                    data.setdefault("__source_file", str(file_path))
                    all_records.append(data)
            except Exception:
                continue
        return all_records

    def load_ground_truth_by_question(self, question, kg_name=None, model_name=None):
        """Find a ground-truth record matching a question for a KG."""
        if not question:
            return None

        normalized_question = self._normalize_question(question)
        records = self.load_ground_truth(kg_name)
        for record in records:
            value = self._normalize_question(record.get("question", ""))
            if value and value == normalized_question:
                return record
        return None


class EvaluationResultsManager:
    """Handles saving and loading evaluation results in KG/model folders."""

    def __init__(self, eval_dir="tests/evaluation_results"):
        self.eval_dir = Path(eval_dir)

    def _folder(self, kg_name, model_name):
        folder = self.eval_dir / f"{kg_name}_{model_name}" / "evaluation"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def save_evaluation(self, *args):
        """
        Save evaluation with backward-compatible signatures.

        Supported:
        - save_evaluation(kg_name, model_name, eval_data)
        - save_evaluation(filename_tag, eval_data)  # infers kg/model from eval_data
        """
        if len(args) == 3:
            kg_name, model_name, eval_data = args
            filename_tag = None
        elif len(args) == 2:
            filename_tag, eval_data = args
            kg_name = eval_data.get("kg", "default")
            model_name = eval_data.get("model", "default")
        else:
            raise TypeError("save_evaluation expects 2 or 3 arguments")

        kg_name = kg_name or "default"
        model_name = model_name or "default"
        folder = self._folder(kg_name, model_name)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if filename_tag:
            stem = Path(str(filename_tag)).stem
            filename = f"eval_{stem}_{timestamp}.json"
        else:
            filename = f"eval_{kg_name}_{model_name}_{timestamp}.json"

        path = folder / filename
        with open(path, "w", encoding="utf-8") as file:
            json.dump(eval_data, file, indent=2, ensure_ascii=False)
        return str(path)

    def get_evaluation_path(self, filename, kg_name=None, model_name=None):
        """Get full path to an evaluation file in KG/model folder."""
        kg_name = kg_name or "default"
        model_name = model_name or "default"
        return str(self._folder(kg_name, model_name) / filename)

    def load_evaluations(self, kg_name, model_name):
        folder = self._folder(kg_name or "default", model_name or "default")
        evaluations = []
        for file_path in folder.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    evaluations.append(json.load(file))
            except Exception:
                continue
        return evaluations
