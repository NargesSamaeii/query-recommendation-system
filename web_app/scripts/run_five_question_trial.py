import json
from pathlib import Path
from datetime import datetime

from nl2sparql.pipeline import NL2SPARQLPipeline


def load_five_questions(kg_name: str):
    gt_dir = Path("tests/ground_truth") / kg_name
    files = sorted(gt_dir.glob("gt_*.json"))[:5]
    questions = []
    for file_path in files:
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("question"):
                questions.append(data["question"])
            elif isinstance(data, list) and data:
                for item in data:
                    if isinstance(item, dict) and item.get("question"):
                        questions.append(item["question"])
                        break
        except Exception:
            continue
    return questions


def run_mode(kg_name: str, schema_path: str, with_examples: bool, questions: list[str]):
    pipeline = NL2SPARQLPipeline("config.yaml")

    # Core routing
    pipeline.config.config.setdefault("kg", {})["name"] = kg_name
    pipeline.config.config.setdefault("llm", {})["provider"] = "mistral"

    # Ensure recording + evaluation
    pipeline.config.config.setdefault("pipeline", {})["record_and_evaluate"] = True
    pipeline.config.config.setdefault("output", {})["save_intermediate"] = True

    # Fast/robust trial: focus on extraction quality for 5-question verification
    pipeline.config.config["pipeline"].setdefault("stages", {})["missing_id_extraction"] = False
    pipeline.config.config["pipeline"]["stages"]["query_generation"] = False
    pipeline.config.config["pipeline"]["stages"]["query_execution"] = False

    # Toggle examples in all relevant stages
    pipeline.config.config.setdefault("pipeline", {}).setdefault("schema", {})
    pipeline.config.config["pipeline"]["schema"].setdefault("class_extraction", {})["include_examples"] = with_examples
    pipeline.config.config["pipeline"]["schema"].setdefault("property_extraction", {})["include_examples"] = with_examples
    pipeline.config.config["pipeline"]["schema"].setdefault("query_generation", {})["include_examples"] = with_examples

    # Keep embedding settings aligned when extraction method is embedding
    pipeline.config.config["pipeline"].setdefault("extraction", {}).setdefault("embedding", {})["include_examples"] = with_examples

    summary = {
        "with_examples": with_examples,
        "attempted": len(questions),
        "success": 0,
        "failures": 0,
        "errors": [],
    }

    for question in questions:
        try:
            result = pipeline.answer_question(question, schema_path)
            if isinstance(result, dict):
                summary["success"] += 1
            else:
                summary["failures"] += 1
                summary["errors"].append({"question": question, "error": "non-dict result"})
        except Exception as exc:
            summary["failures"] += 1
            summary["errors"].append({"question": question, "error": str(exc)})

    return summary


def count_files(path: Path, pattern: str):
    if not path.exists():
        return 0
    return len(list(path.glob(pattern)))


def main():
    kg_name = "coporate"
    schema_path = "data/output/coporate_mschema.json"

    questions = load_five_questions(kg_name)
    if len(questions) < 5:
        raise RuntimeError(f"Need 5 questions, found {len(questions)}")

    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    report = {
        "kg": kg_name,
        "model": "mistral",
        "schema": schema_path,
        "questions": questions,
        "runs": []
    }

    report["runs"].append(run_mode(kg_name, schema_path, True, questions))
    report["runs"].append(run_mode(kg_name, schema_path, False, questions))

    # Folder verification
    result_dir = Path("tests/results") / kg_name / "mistral"
    extract_dir = Path("tests/extractions") / kg_name / "mistral"
    prompt_dir = Path("tests/prompts") / kg_name / "mistral"
    eval_dir = Path("tests/evaluation_results") / f"{kg_name}_mistral" / "evaluation"

    report["folder_verification"] = {
        "results_dir": str(result_dir),
        "results_json_count": count_files(result_dir, "*.json"),
        "extractions_dir": str(extract_dir),
        "extractions_json_count": count_files(extract_dir, "*.json"),
        "prompts_dir": str(prompt_dir),
        "prompts_files_count": count_files(prompt_dir, "*"),
        "evaluation_dir": str(eval_dir),
        "evaluation_json_count": count_files(eval_dir, "*.json"),
    }

    # with/without examples verification in evaluation files
    with_true = 0
    with_false = 0
    for jf in eval_dir.glob("*.json"):
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
            flag = data.get("with_examples")
            if flag is True:
                with_true += 1
            elif flag is False:
                with_false += 1
        except Exception:
            continue

    report["evaluation_filter_flags"] = {
        "with_examples_true_count": with_true,
        "with_examples_false_count": with_false,
    }

    out = Path("tests/evaluation_results") / f"trial_report_{run_ts}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nSaved report: {out}")


if __name__ == "__main__":
    main()
