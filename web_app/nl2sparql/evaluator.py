"""
Evaluation Module

Provides comprehensive evaluation metrics (Precision, Recall, F1-score)
for assessing pipeline performance at each stage.

Supports two evaluation approaches:
1. Row-based evaluation (default): Compares SPARQL results row-by-row
2. Set-based evaluation (order-aware): Uses pytrec_eval for set comparison with optional order consideration
"""

import json
import os
import re
import statistics
from typing import Dict, List, Set, Tuple, Optional
from urllib.parse import unquote

try:
    import pytrec_eval
    PYTREC_AVAILABLE = True
except ImportError:
    PYTREC_AVAILABLE = False


# ============================================================================
# Helper Functions for Set-Based (Order-Aware) Evaluation
# ============================================================================

def filter_answer_dict(answer_dict: dict, order_required: list) -> dict:
    """Filter the questions where order is required for full evaluation"""
    return_dict = {}
    for question_id in order_required:
        if question_id in answer_dict:
            return_dict[question_id] = answer_dict[question_id]
    return return_dict


def non_destructive_update(results: dict, new_results: dict, new_metric: str) -> None:
    """Update the results with order_metric where necessary without touching other metrics"""
    for key in new_results:
        if key in results:
            results[key][new_metric] = new_results[key][new_metric]


def combine_averages(
    results: dict, new_metric: str, average_field: str = "average", old_metric: str = "set_F"
) -> None:
    """Create a new average value that combines set_F with order_metric"""
    combined_list = []
    for value in results.values():
        if isinstance(value, dict):
            if new_metric in value:
                combined_list.append(value[new_metric])
            else:
                combined_list.append(value.get(old_metric, 0.0))

    if combined_list and average_field in results:
        if isinstance(results[average_field], dict):
            results[average_field][f"{old_metric}_{new_metric}"] = statistics.fmean(combined_list)


class DBpediaDict2PytrecDict:
    """Transform SPARQL results into pytrec_eval compatible format"""

    def __init__(self, question: str) -> None:
        """Initialize the DBpediaDict2PytrecDict class.

        Args:
            question (str): The question that generated the sparql query.
        """
        self.question = question

    def transform(self, sparql_dict: dict) -> dict:
        """Transform a sparql dict into a dict to be evaluated through the pytrec library.

        Args:
            sparql_dict (dict): Dictionary of the URIs, returned by the endpoint

        Returns:
           dict: Dictionary of the predicted lists in which all items have the same weight
        """
        d: dict = {}
        if "boolean" in sparql_dict:
            bool_result = sparql_dict["boolean"]
            d[self.question] = {}
            d[self.question]["true"] = 1 if bool_result else 0
        else:
            list_results = sparql_dict.get("results", {}).get("bindings", [])
            list_vars = sparql_dict.get("head", {}).get("vars", [])
            d[self.question] = {}
            for var in list_vars:
                for value in list_results:
                    if var in value:
                        d[self.question][value[var]["value"]] = 1
        return d


class PytrecEvaluation:
    """Computes F1, Recall and Precision using the pytrec_eval library for set-based comparison.

    Provides metrics: set_P (set precision), set_recall (set recall), set_F (set F1)
    These metrics are order-agnostic (treat results as unordered sets).

    Requirements: pip install pytrec_eval numpy scipy
    """

    def __init__(self, model_name: str, metrics: set[str] | None = None) -> None:
        """Initialize the PytrecEvaluation class.

        Args:
            model_name (str): The name of the model that generates the predicted_dicts
            metrics (set): Name of the evaluated metrics. See pytrec_eval.supported_measures
        """
        if not PYTREC_AVAILABLE:
            raise ImportError("pytrec_eval is required for set-based evaluation. Install with: pip install pytrec_eval numpy scipy")
        
        if metrics is None:
            metrics = {"set_P", "set_recall", "set_F"}
        self.model_name = model_name
        self.metrics = metrics

    def evaluate(
        self,
        predicted_dict: dict[str, dict[str, int]],
        ground_truth_dict: dict[str, dict[str, int]],
    ) -> dict:
        """Evaluate the model considering a true dictionary and a predicted dictionary.

        Args:
            predicted_dict (dict): Dictionary of the predicted lists (question_id -> {value: weight})
            ground_truth_dict (dict): Dictionary of the ground truth lists (question_id -> {value: weight})

        Returns:
           dict: A dictionary with per-question metrics and averages
        """
        results = {}
        for question_id_key in predicted_dict:  # noqa: PLC0206
            if question_id_key not in ground_truth_dict:
                continue
                
            ground_truth = {question_id_key: ground_truth_dict[question_id_key]}
            prediction = {question_id_key: predicted_dict[question_id_key]}

            evaluator = pytrec_eval.RelevanceEvaluator(ground_truth, self.metrics)
            results_question = evaluator.evaluate(prediction)
            results.update(results_question)

        d: dict[str, float] = {}
        for measure in self.metrics:
            d[measure] = float(
                pytrec_eval.compute_aggregated_measure(
                    measure, [query_measures[measure] for query_measures in results.values()]
                )
            )
        results["average"] = d

        return results


class EvaluationMetrics:
    """Calculate and store evaluation metrics."""
    
    def __init__(self):
        """Initialize metrics storage."""
        self.metrics = {}
    
    @staticmethod
    def calculate_precision(predicted: Set, correct: Set) -> float:
        """
        Calculate Precision: proportion of correct predictions among those returned.
        
        Precision = (# correct predictions) / (# total predictions)
        
        Args:
            predicted: Set of predicted/extracted items
            correct: Set of correct items
            
        Returns:
            Precision score (0.0 to 1.0), or 0.0 if no predictions
        """
        if len(predicted) == 0:
            return 0.0
        true_positives = len(predicted & correct)
        return true_positives / len(predicted)
    
    @staticmethod
    def calculate_recall(predicted: Set, correct: Set) -> float:
        """
        Calculate Recall: proportion of correct items that were retrieved.
        
        Recall = (# correct predictions) / (# correct items)
        
        Args:
            predicted: Set of predicted/extracted items
            correct: Set of correct items
            
        Returns:
            Recall score (0.0 to 1.0), or 0.0 if no correct items
        """
        if len(correct) == 0:
            return 0.0
        true_positives = len(predicted & correct)
        return true_positives / len(correct)
    
    @staticmethod
    def calculate_f1(precision: float, recall: float) -> float:
        """
        Calculate F1-score: harmonic mean of Precision and Recall.
        
        F1 = 2 * (Precision * Recall) / (Precision + Recall)
        
        Args:
            precision: Precision score
            recall: Recall score
            
        Returns:
            F1-score (0.0 to 1.0), or 0.0 if both are 0
        """
        if precision + recall == 0:
            return 0.0
        return 2 * (precision * recall) / (precision + recall)
    
    @staticmethod
    def calculate_accuracy(predicted: Set, correct: Set) -> float:
        """
        Calculate Accuracy: exact match ratio.
        
        Args:
            predicted: Set of predicted items
            correct: Set of correct items
            
        Returns:
            1.0 if perfect match, 0.0 otherwise
        """
        return 1.0 if predicted == correct else 0.0


class ClassExtractionEvaluator:
    """Evaluate class extraction performance."""
    
    @staticmethod
    def evaluate(extracted_classes: List[str], ground_truth_classes: List[str]) -> Dict:
        """
        Evaluate class extraction.
        
        Args:
            extracted_classes: Classes extracted by the system
            ground_truth_classes: Correct classes (ground truth)
            
        Returns:
            Dictionary with evaluation metrics
        """
        extracted_set = set(extracted_classes)
        correct_set = set(ground_truth_classes)
        
        precision = EvaluationMetrics.calculate_precision(extracted_set, correct_set)
        recall = EvaluationMetrics.calculate_recall(extracted_set, correct_set)
        f1 = EvaluationMetrics.calculate_f1(precision, recall)
        accuracy = EvaluationMetrics.calculate_accuracy(extracted_set, correct_set)
        
        # Analyze errors
        false_positives = extracted_set - correct_set  # Should not have extracted
        false_negatives = correct_set - extracted_set  # Should have extracted
        true_positives = extracted_set & correct_set   # Correctly extracted
        
        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "accuracy": round(accuracy, 4),
            "true_positives": list(true_positives),
            "false_positives": list(false_positives),
            "false_negatives": list(false_negatives),
            "extracted_count": len(extracted_set),
            "correct_count": len(correct_set),
            "tp_count": len(true_positives),
            "fp_count": len(false_positives),
            "fn_count": len(false_negatives)
        }


class PropertyExtractionEvaluator:
    """Evaluate property extraction performance."""
    
    @staticmethod
    def _normalize_property_name(prop: str) -> str:
        """
        Normalize property name by extracting local name.
        Handles both 'memberOf' and 'prod_vocab:memberOf' formats.
        
        Args:
            prop: Property name (with or without prefix)
            
        Returns:
            Local name (after colon if present)
        """
        if ':' in prop:
            return prop.split(':')[-1]
        return prop
    
    @staticmethod
    def evaluate(
        extracted_properties: List[Dict],
        ground_truth_properties: List[Dict]
    ) -> Dict:
        """
        Evaluate property extraction ONLY for classes in ground truth.
        Ignores properties from false positive classes.
        
        Args:
            extracted_properties: Properties extracted by system
                [{class_name: str, relevant_properties: [str, ...]}, ...]
            ground_truth_properties: Correct properties
                [{class_name: str, relevant_properties: [str, ...]}, ...]
                
        Returns:
            Dictionary with evaluation metrics
        """
        # Create dictionaries with normalized property names
        extracted_dict = {}
        for p in extracted_properties:
            props = p.get('relevant_properties', [])
            normalized = set(PropertyExtractionEvaluator._normalize_property_name(prop) for prop in props)
            extracted_dict[p['class_name']] = normalized
        
        correct_dict = {}
        for p in ground_truth_properties:
            props = p.get('relevant_properties', [])
            normalized = set(PropertyExtractionEvaluator._normalize_property_name(prop) for prop in props)
            correct_dict[p['class_name']] = normalized
        
        # ONLY evaluate classes in ground truth (ignore false positive classes)
        all_classes = set(correct_dict.keys())
        
        # Calculate metrics per class
        per_class_metrics = {}
        total_precision_values = []
        total_recall_values = []
        total_f1_values = []
        
        total_tp = 0
        total_fp = 0
        total_fn = 0
        
        for class_name in all_classes:
            extracted = extracted_dict.get(class_name, set())
            correct = correct_dict.get(class_name, set())
            
            precision = EvaluationMetrics.calculate_precision(extracted, correct)
            recall = EvaluationMetrics.calculate_recall(extracted, correct)
            f1 = EvaluationMetrics.calculate_f1(precision, recall)
            
            # Count errors
            tp = len(extracted & correct)
            fp = len(extracted - correct)
            fn = len(correct - extracted)
            
            total_tp += tp
            total_fp += fp
            total_fn += fn
            
            total_precision_values.append(precision)
            total_recall_values.append(recall)
            total_f1_values.append(f1)
            
            per_class_metrics[class_name] = {
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
                "extracted_properties": list(extracted),
                "correct_properties": list(correct),
                "tp": tp,
                "fp": fp,
                "fn": fn
            }
        
        # Calculate macro averages (average of per-class scores)
        macro_precision = sum(total_precision_values) / len(total_precision_values) if total_precision_values else 0
        macro_recall = sum(total_recall_values) / len(total_recall_values) if total_recall_values else 0
        macro_f1 = sum(total_f1_values) / len(total_f1_values) if total_f1_values else 0
        
        # Calculate micro averages (based on total counts)
        micro_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
        micro_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
        micro_f1 = EvaluationMetrics.calculate_f1(micro_precision, micro_recall)
        
        return {
            "per_class": per_class_metrics,
            "macro_average": {
                "precision": round(macro_precision, 4),
                "recall": round(macro_recall, 4),
                "f1": round(macro_f1, 4)
            },
            "micro_average": {
                "precision": round(micro_precision, 4),
                "recall": round(micro_recall, 4),
                "f1": round(micro_f1, 4)
            },
            "total_counts": {
                "true_positives": total_tp,
                "false_positives": total_fp,
                "false_negatives": total_fn
            },
            "classes_evaluated": len(all_classes)
        }


class MissingIDEvaluator:
    """Evaluate missing ID (entity resolution) performance."""
    
    @staticmethod
    def evaluate(
        resolved_entities: Dict[str, str],
        ground_truth_entities: Dict[str, str]
    ) -> Dict:
        """
        Evaluate entity resolution performance based on IRI matching.
        
        Compares resolved IRIs regardless of entity names used.
        This allows matching even when entity is referred to differently
        (e.g., "Data Services" vs "department-dept-41622").
        
        Args:
            resolved_entities: {entity_name: iri, ...}
            ground_truth_entities: {entity_name: expected_iri, ...}
                
        Returns:
            Dictionary with evaluation metrics
        """
        # Special case: if no entities expected and none resolved → perfect match
        if len(ground_truth_entities) == 0 and len(resolved_entities) == 0:
            return {
                "precision": 1.0,
                "recall": 1.0,
                "f1": 1.0,
                "iri_accuracy": 1.0,
                "true_positives": [],
                "false_positives": [],
                "false_negatives": [],
                "correct_iris": 0,
                "found_entities": 0,
                "total_entities_resolved": 0,
                "total_expected": 0
            }
        
        # Extract IRI sets (compare by IRI, not entity name)
        resolved_iris = set(resolved_entities.values())
        expected_iris = set(ground_truth_entities.values())
        
        # Calculate metrics based on IRI matching
        matched_iris = resolved_iris & expected_iris
        precision = len(matched_iris) / len(resolved_iris) if len(resolved_iris) > 0 else 0.0
        recall = len(matched_iris) / len(expected_iris) if len(expected_iris) > 0 else 0.0
        f1 = EvaluationMetrics.calculate_f1(precision, recall)
        
        # Find entity names for matched/unmatched IRIs (for reporting)
        matched_entity_names = []
        for name, iri in resolved_entities.items():
            if iri in expected_iris:
                matched_entity_names.append(name)
        
        fp_entity_names = []
        for name, iri in resolved_entities.items():
            if iri not in expected_iris:
                fp_entity_names.append(name)
        
        fn_entity_names = []
        for name, iri in ground_truth_entities.items():
            if iri not in resolved_iris:
                fn_entity_names.append(name)
        
        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "iri_accuracy": round(precision, 4),  # For IRI-based comparison, precision = IRI accuracy
            "true_positives": matched_entity_names,
            "false_positives": fp_entity_names,
            "false_negatives": fn_entity_names,
            "correct_iris": len(matched_iris),
            "found_entities": len(matched_iris),
            "total_entities_resolved": len(resolved_entities),
            "total_expected": len(ground_truth_entities)
        }


class QueryExecutionEvaluator:
    """Evaluate query execution and results."""
    
    @staticmethod
    def evaluate(
        actual_results: List[Dict],
        expected_results: List[Dict],
        key_field: str = None,
        normalize_values: bool = True
    ) -> Dict:
        """
        Evaluate query execution results using row-by-row value comparison.
        
        Compares rows by matching their values (ignoring column names).
        Each expected row must find a matching actual row.
        
        Args:
            actual_results: Results returned by SPARQL query (SPARQL binding format)
                [{"field": {"type": "uri", "value": "..."}, ...}, ...]
            expected_results: Expected/correct results
                [{"field": "value", ...}, ...]
            key_field: Ignored (kept for backward compatibility)
            normalize_values: Whether to apply value normalization before matching
                
        Returns:
            Dictionary with evaluation metrics
        """
        def normalize_results_input(results):
            """Normalize supported result payloads to list-of-dict rows."""
            if results is None:
                return []
            if isinstance(results, list):
                return results
            if isinstance(results, dict):
                bindings = results.get("results", {}).get("bindings")
                if isinstance(bindings, list):
                    return bindings
            return []

        def extract_value(binding_value):
            """Extract scalar value from SPARQL binding format or passthrough value."""
            if isinstance(binding_value, dict) and "value" in binding_value:
                return binding_value["value"]
            return binding_value

        def canonical_forms(value) -> Set[str]:
            """Return normalized comparison forms for resilient row matching."""
            forms = set()
            if value is None:
                return forms

            text = str(value).strip()
            if not text:
                return forms

            if not normalize_values:
                forms.add(text)
                return forms

            forms.add(text)
            forms.add(text.lower())

            # URL decode (for labels with encoded characters)
            decoded = unquote(text)
            forms.add(decoded)
            forms.add(decoded.lower())

            # URI local-name fallback (common in expected ground-truth values)
            local_name = decoded
            if "#" in decoded:
                local_name = decoded.rsplit("#", 1)[-1]
            elif "/" in decoded:
                local_name = decoded.rsplit("/", 1)[-1]
            if local_name and local_name != decoded:
                forms.add(local_name)
                forms.add(local_name.lower())

                # Human-readable tokenization from common KG identifiers/emails
                # e.g., empl-Waldtraud.Kuttner@company.org -> "waldtraud kuttner"
                local_core = local_name
                if "-" in local_core:
                    local_core = local_core.split("-", 1)[-1]
                if "@" in local_core:
                    local_core = local_core.split("@", 1)[0]
                local_core = re.sub(r"[._-]+", " ", local_core)
                local_core = re.sub(r"\s+", " ", local_core).strip()
                if local_core:
                    forms.add(local_core)
                    forms.add(local_core.lower())

            # Numeric normalization (e.g., 42 vs 42.0)
            try:
                number = float(text)
                if number.is_integer():
                    forms.add(str(int(number)))
                forms.add(("%f" % number).rstrip("0").rstrip("."))

                # Add rounded variants to handle minor formatting differences
                forms.add(str(round(number, 1)).rstrip("0").rstrip("."))
                if abs(number - round(number)) <= 0.25:
                    forms.add(str(int(round(number))))
            except (TypeError, ValueError):
                pass

            return forms

        def extract_row_values(result: Dict) -> Set[str]:
            """Extract normalized scalar value forms from one result row."""
            values = set()
            if not isinstance(result, dict):
                return values
            for value in result.values():
                extracted = extract_value(value)
                values.update(canonical_forms(extracted))
            return values

        normalized_actual = normalize_results_input(actual_results)
        normalized_expected = normalize_results_input(expected_results)

        actual_row_sets = [extract_row_values(row) for row in normalized_actual]
        expected_row_sets = [extract_row_values(row) for row in normalized_expected]
        
        # For each expected row, check if its values are a subset of any actual row
        # (actual may have extra fields like IRI, so we check subset not equality)
        matched_expected = 0
        matched_actual = set()
        
        for exp_idx, exp_values in enumerate(expected_row_sets):
            for act_idx, act_values in enumerate(actual_row_sets):
                # Check if expected values are subset of actual values
                if exp_values.issubset(act_values):
                    matched_expected += 1
                    matched_actual.add(act_idx)
                    break  # Found a match for this expected row
        
        # Calculate metrics
        tp = matched_expected  # Expected rows that found a match
        fn = len(expected_row_sets) - matched_expected  # Expected rows with no match
        fp = len(actual_row_sets) - len(matched_actual)  # Actual rows that didn't match any expected
        
        precision = tp / len(actual_row_sets) if len(actual_row_sets) > 0 else 0.0
        recall = tp / len(expected_row_sets) if len(expected_row_sets) > 0 else 0.0
        f1 = EvaluationMetrics.calculate_f1(precision, recall)
        accuracy = 1.0 if (tp == len(actual_row_sets) and tp == len(expected_row_sets)) else 0.0
        
        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "accuracy": round(accuracy, 4),
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "actual_result_count": len(normalized_actual),
            "expected_result_count": len(normalized_expected),
            "match_type": "row_based"
        }

    @staticmethod
    def evaluate_set_based(
        actual_results: Dict,
        expected_results: List[Dict],
        question_id: str = "query",
        order_required: bool = False
    ) -> Dict:
        """
        Evaluate query execution results using set-based comparison with pytrec_eval.

        This treats results as unordered sets for evaluation.
        Option to evaluate with order sensitivity if needed.

        Args:
            actual_results: Results returned by SPARQL query (full SPARQL response dict)
                {"head": {"vars": [...]}, "results": {"bindings": [...]}, "boolean": ...}
            expected_results: Expected/correct results
                [{"field": "value", ...}, ...]
            question_id: Identifier for this query (for result tracking)
            order_required: If True, compute order-aware metrics in addition to set metrics

        Returns:
            Dictionary with set-based evaluation metrics
        """
        if not PYTREC_AVAILABLE:
            raise ImportError("pytrec_eval is required. Install with: pip install pytrec_eval numpy scipy")

        # Transform actual results to pytrec format
        transformer = DBpediaDict2PytrecDict(question_id)
        predicted_dict = transformer.transform(actual_results)

        # Transform expected results to pytrec format
        expected_dict = {question_id: {}}
        if isinstance(expected_results, list):
            for result in expected_results:
                if isinstance(result, dict):
                    for value in result.values():
                        expected_dict[question_id][str(value)] = 1
                else:
                    expected_dict[question_id][str(result)] = 1
        
        # Perform set-based evaluation
        evaluator = PytrecEvaluation("query_executor", metrics={"set_P", "set_recall", "set_F"})
        results = evaluator.evaluate(predicted_dict, expected_dict)

        # Extract metrics
        answer_metrics = results.get(question_id, {})
        average_metrics = results.get("average", {})

        output = {
            "set_precision": round(answer_metrics.get("set_P", 0.0), 4),
            "set_recall": round(answer_metrics.get("set_recall", 0.0), 4),
            "set_f1": round(answer_metrics.get("set_F", 0.0), 4),
            "average": {
                "set_precision": round(average_metrics.get("set_P", 0.0), 4),
                "set_recall": round(average_metrics.get("set_recall", 0.0), 4),
                "set_f1": round(average_metrics.get("set_F", 0.0), 4),
            },
            "match_type": "set_based"
        }

        if order_required:
            # Could add order-aware metrics here if needed
            output["order_required"] = True

        return output


class PipelineEvaluator:
    """
    Comprehensive pipeline evaluator that evaluates all stages.
    
    Supports two evaluation approaches for query execution:
    1. Row-based: Compares results row-by-row with value normalization
    2. Set-based: Uses pytrec_eval for set comparison (order-agnostic by default)
    """
    
    def __init__(
        self,
        normalize_query_execution_values: bool = True,
        evaluation_method: str = "row_based",
        order_matters: bool = False,
        order_required_questions: List[str] = None,
    ):
        """Initialize pipeline evaluator.
        
        Args:
            normalize_query_execution_values: Apply value normalization in row-based evaluation
            evaluation_method: "row_based" (default) or "set_based"
            order_matters: If True, consider result order in evaluation (requires set_based method)
            order_required_questions: Questions that require order-sensitive evaluation
        """
        self.logger = None  # Can be set externally
        self.normalize_query_execution_values = normalize_query_execution_values
        self.evaluation_method = evaluation_method.lower()
        self.order_matters = order_matters and self.evaluation_method == "set_based"
        self.order_required_questions = order_required_questions or []
        
        # Validate method selection
        if self.evaluation_method not in ("row_based", "set_based"):
            self.evaluation_method = "row_based"
            if self.logger:
                self.logger.warning(f"Unknown evaluation method, defaulting to 'row_based'")
    
    
    def evaluate_full_pipeline(
        self,
        result: Dict,
        ground_truth: Dict
    ) -> Dict:
        """
        Evaluate entire pipeline against ground truth.
        
        Args:
            result: Pipeline result (from ResultsManager)
            ground_truth: Ground truth data with keys:
                - question: str
                - expected_classes: [str, ...]
                - expected_properties: [{class_name, properties}, ...]
                - expected_entities: {entity_name: iri, ...}
                - expected_results: [{field: value, ...}, ...]
                
        Returns:
            Dictionary with evaluation metrics for all stages
        """
        evaluation = {
            "question": ground_truth.get("question", ""),
            "timestamp": result.get("metadata", {}).get("timestamp", ""),
            "stages": {},
            "settings": {
                "query_execution_normalization": bool(self.normalize_query_execution_values),
                "effective_evaluation_method": self.evaluation_method,
                "query_execution_fallback_reason": "",
            }
        }
        
        pipeline = result.get("pipeline", {})
        
        # Evaluate Class Extraction
        if "expected_classes" in ground_truth:
            extracted = pipeline.get("class_extraction", {}).get("extracted_classes", [])
            evaluation["stages"]["class_extraction"] = ClassExtractionEvaluator.evaluate(
                extracted,
                ground_truth["expected_classes"]
            )
        
        # Evaluate Property Extraction
        if "expected_properties" in ground_truth:
            extracted = pipeline.get("property_extraction", {}).get("property_selection", [])
            evaluation["stages"]["property_extraction"] = PropertyExtractionEvaluator.evaluate(
                extracted,
                ground_truth["expected_properties"]
            )
        
        # Evaluate Missing ID Extraction
        if "expected_entities" in ground_truth:
            resolved = pipeline.get("missing_id_extraction", {}).get("resolved_entities", {})
            evaluation["stages"]["missing_id_extraction"] = MissingIDEvaluator.evaluate(
                resolved,
                ground_truth["expected_entities"]
            )
        
        # Evaluate Query Execution
        if "expected_results" in ground_truth:
            # Check if this is an ASK query (boolean result)
            query_type = ground_truth.get("query_type", "SELECT")
            raw_results = pipeline.get("query_execution", {}).get("raw_results") or {}
            question_text = ground_truth.get("question", "")
            
            if query_type == "ASK":
                # For ASK queries, check the "boolean" field in raw_results
                actual_boolean = raw_results.get("boolean", False)
                
                # Get expected boolean from ground truth
                expected_value = ground_truth["expected_results"][0].get("result", "false")
                expected_boolean = str(expected_value).lower() == "true"
                
                # Simple boolean comparison
                match = actual_boolean == expected_boolean
                evaluation["stages"]["query_execution"] = {
                    "precision": 1.0 if match else 0.0,
                    "recall": 1.0 if match else 0.0,
                    "f1": 1.0 if match else 0.0,
                    "accuracy": 1.0 if match else 0.0,
                    "actual_value": actual_boolean,
                    "expected_value": expected_boolean,
                    "match": match,
                    "query_type": "ASK",
                    "evaluation_method": "boolean_comparison"
                }
            else:
                # SELECT query - use configured evaluation method
                actual_results = raw_results
                
                # Determine if order-aware evaluation should be used
                check_order = self.order_matters or (question_text in self.order_required_questions)
                
                if self.evaluation_method == "set_based":
                    try:
                        evaluation["stages"]["query_execution"] = QueryExecutionEvaluator.evaluate_set_based(
                            actual_results=actual_results,
                            expected_results=ground_truth["expected_results"],
                            question_id=question_text or "query",
                            order_required=check_order
                        )
                        evaluation["settings"]["effective_evaluation_method"] = "set_based"
                    except ImportError as e:
                        fallback_reason = (
                            "set_based requested but unavailable; falling back to row_based: "
                            f"{e}"
                        )
                        if self.logger:
                            self.logger.warning(
                                "Set-based evaluation requested but pytrec_eval not available. "
                                f"Falling back to row-based. Error: {e}"
                            )
                        # Fallback to row-based
                        actual_bindings = actual_results.get("results", {}).get("bindings", [])
                        evaluation["stages"]["query_execution"] = QueryExecutionEvaluator.evaluate(
                            actual_bindings,
                            ground_truth["expected_results"],
                            key_field=ground_truth.get("key_field", None),
                            normalize_values=self.normalize_query_execution_values,
                        )
                        evaluation["settings"]["effective_evaluation_method"] = "row_based"
                        evaluation["settings"]["query_execution_fallback_reason"] = fallback_reason
                else:
                    # Row-based evaluation (default)
                    actual_bindings = actual_results.get("results", {}).get("bindings", []) if isinstance(actual_results, dict) else actual_results
                    evaluation["stages"]["query_execution"] = QueryExecutionEvaluator.evaluate(
                        actual_bindings,
                        ground_truth["expected_results"],
                        key_field=ground_truth.get("key_field", None),
                        normalize_values=self.normalize_query_execution_values,
                    )
                    evaluation["settings"]["effective_evaluation_method"] = "row_based"
        
        # Update settings to reflect evaluation config
        evaluation["settings"]["evaluation_method"] = self.evaluation_method
        evaluation["settings"]["order_matters"] = self.order_matters
        
        
        # Calculate overall metrics
        evaluation["overall"] = self._calculate_overall_metrics(evaluation["stages"])
        
        return evaluation
    
    @staticmethod
    def _calculate_overall_metrics(stage_metrics: Dict) -> Dict:
        """Calculate overall pipeline metrics."""
        if not stage_metrics:
            return {}
        
        f1_scores = []
        stages_evaluated = []
        
        for stage_name, metrics in stage_metrics.items():
            if "f1" in metrics:
                f1_scores.append(metrics["f1"])
                stages_evaluated.append(stage_name)
            elif "set_f1" in metrics:
                f1_scores.append(metrics["set_f1"])
                stages_evaluated.append(stage_name)
            elif "macro_average" in metrics:
                f1_scores.append(metrics["macro_average"]["f1"])
                stages_evaluated.append(stage_name)
        
        if f1_scores:
            avg_f1 = sum(f1_scores) / len(f1_scores)
            return {
                "average_f1": round(avg_f1, 4),
                "stages_evaluated": len(stages_evaluated),
                "stages": stages_evaluated
            }
        
        return {}


def create_ground_truth_template(question: str) -> Dict:
    """
    Create a template for ground truth data.
    
    Args:
        question: The question being evaluated
        
    Returns:
        Dictionary template to fill in
    """
    return {
        "question": question,
        "expected_classes": [
            "Class1",
            "Class2"
        ],
        "expected_properties": [
            {
                "class_name": "Class1",
                "relevant_properties": ["property1", "property2"]
            },
            {
                "class_name": "Class2",
                "relevant_properties": ["property3"]
            }
        ],
        "expected_entities": {
            "EntityName": "http://example.com/entity"
        },
        "expected_results": [
            {"field1": "value1", "field2": "value2"},
            {"field1": "value3", "field2": "value4"}
        ],
        "key_field": "field1"  # Optional: which field to use for result comparison
    }
