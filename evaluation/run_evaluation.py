from __future__ import annotations

import argparse
import csv
import json
import hashlib
import pickle
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Iterable, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from application.orchestrators import OrderProcessingOrchestrator
from application.services import OrderManager
from config import Config
from domain.constants import (
    SUPPORTED_EXCEL_EXTENSIONS,
    SUPPORTED_IMAGE_EXTENSIONS,
    SUPPORTED_PDF_EXTENSIONS,
)
from evaluation.metrics import EvaluationAccumulator, build_summary_markdown
from evaluation.contracts import normalize_annotation
from evaluation.repositories import InMemoryOrderRepository
from interfaces.http.serializers import to_jsonable


SUPPORTED_EVAL_EXTENSIONS = (
    SUPPORTED_PDF_EXTENSIONS | SUPPORTED_EXCEL_EXTENSIONS | SUPPORTED_IMAGE_EXTENSIONS
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run batch evaluation on a processed dataset directory.")
    parser.add_argument("--input-dir", required=True, help="Processed dataset directory containing documents.")
    parser.add_argument(
        "--annotation-dir",
        help="Optional directory containing annotation JSON files. If omitted, the runner will look for sidecar JSON files.",
    )
    parser.add_argument(
        "--manifest-csv",
        help="Optional manifest CSV mapping file_name to annotation_file.",
    )
    parser.add_argument(
        "--dataset-name",
        help="Dataset name used in result output. Defaults to input directory name.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "evaluation" / "results"),
        help="Directory where evaluation outputs will be written.",
    )
    parser.add_argument("--limit", type=int, help="Optional max number of files to evaluate.")
    parser.add_argument("--no-recursive", action="store_true", help="Disable recursive file discovery.")
    return parser.parse_args()


def discover_documents(input_dir: Path, recursive: bool = True) -> List[Path]:
    iterator: Iterable[Path]
    if recursive:
        iterator = input_dir.rglob("*")
    else:
        iterator = input_dir.glob("*")

    documents = [
        path for path in iterator
        if path.is_file() and path.suffix.lower() in SUPPORTED_EVAL_EXTENSIONS
    ]
    return sorted(documents)


def load_manifest_map(manifest_csv: Optional[Path]) -> Dict[str, str]:
    if manifest_csv is None or not manifest_csv.exists():
        return {}

    mapping: Dict[str, str] = {}
    with open(manifest_csv, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            file_name = row.get("file_name")
            annotation_file = row.get("annotation_file")
            if file_name and annotation_file:
                mapping[file_name] = annotation_file
    return mapping


def resolve_annotation_path(
    *,
    document_path: Path,
    annotation_dir: Optional[Path],
    manifest_map: Dict[str, str],
    manifest_base_dir: Optional[Path],
) -> Optional[Path]:
    manifest_annotation = manifest_map.get(document_path.name)
    if manifest_annotation:
        candidate = Path(manifest_annotation)
        if not candidate.is_absolute():
            if annotation_dir is not None:
                candidate = annotation_dir / candidate
            elif manifest_base_dir is not None:
                candidate = manifest_base_dir / candidate
        if candidate.exists():
            return candidate

    if annotation_dir is not None:
        candidate = annotation_dir / f"{document_path.stem}.json"
        if candidate.exists():
            return candidate

    sidecar = document_path.with_suffix(".json")
    if sidecar.exists():
        return sidecar

    return None


def load_annotation(annotation_path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if annotation_path is None:
        return None
    with open(annotation_path, "r", encoding="utf-8") as file:
        return normalize_annotation(json.load(file))


def count_risk_issues(prediction: Dict[str, Any]) -> int:
    final_result = prediction.get("final_result") or {}
    risk_result = final_result.get("risk_result") or {}
    issues = risk_result.get("issues") or []
    return len(issues)


def count_parsed_items(prediction: Dict[str, Any]) -> int:
    final_result = prediction.get("final_result") or {}
    parsed_order = final_result.get("parsed_order") or {}
    return len(parsed_order.get("items") or [])


def count_matched_items(prediction: Dict[str, Any]) -> int:
    final_result = prediction.get("final_result") or {}
    matched_order = final_result.get("matched_order") or {}
    return len(matched_order.get("items") or [])


def build_run_directory(base_output_dir: Path, dataset_name: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = base_output_dir / f"{dataset_name}_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def create_evaluation_orchestrator(run_dir: Path) -> OrderProcessingOrchestrator:
    config = Config()
    order_manager = OrderManager(repository=InMemoryOrderRepository(), config=config)
    return OrderProcessingOrchestrator(order_manager=order_manager, config=config)


def write_json(path: Path, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def sha256_file(path: Path) -> Optional[str]:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_material_index(config: Config) -> None:
    materials_path = Path(config.data.standard_materials_path)
    index_path = Path(config.data.faiss_index_path)
    metadata_path = index_path / "metadata.pkl"
    index_file = index_path / "index.faiss"
    required_paths = (materials_path, metadata_path, index_file)
    missing = [str(path) for path in required_paths if not path.is_file()]
    if missing:
        raise SystemExit(f"Material/index artifacts missing: {', '.join(missing)}")

    with materials_path.open("r", encoding="utf-8") as file:
        materials = list(csv.DictReader(file))
    with metadata_path.open("rb") as file:
        metadata = pickle.load(file)
    if not isinstance(metadata, list):
        raise SystemExit("FAISS metadata must be a list")

    material_by_sku = {row.get("sku_code"): row for row in materials}
    index_by_sku = {row.get("sku_code"): row for row in metadata}
    if len(material_by_sku) != len(materials) or len(index_by_sku) != len(metadata):
        raise SystemExit("Duplicate SKU found in material CSV or FAISS metadata")
    if set(material_by_sku) != set(index_by_sku):
        raise SystemExit("Material CSV and FAISS metadata SKU sets are inconsistent")
    for sku_code, material in material_by_sku.items():
        indexed = index_by_sku[sku_code]
        for field in ("material_name", "specification", "unit", "category"):
            if str(material.get(field, "")) != str(indexed.get(field, "")):
                raise SystemExit(f"Material/index mismatch for {sku_code}: {field}")
        if float(material["reference_price"]) != float(indexed["reference_price"]):
            raise SystemExit(f"Material/index mismatch for {sku_code}: reference_price")


def run() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir).resolve()
    annotation_dir = Path(args.annotation_dir).resolve() if args.annotation_dir else None
    manifest_csv = Path(args.manifest_csv).resolve() if args.manifest_csv else None
    dataset_name = args.dataset_name or input_dir.name
    output_dir = Path(args.output_dir).resolve()

    if not input_dir.exists():
        raise SystemExit(f"Input dir does not exist: {input_dir}")
    if annotation_dir is not None and not annotation_dir.exists():
        raise SystemExit(f"Annotation dir does not exist: {annotation_dir}")

    documents = discover_documents(input_dir, recursive=not args.no_recursive)
    if args.limit:
        documents = documents[: args.limit]
    if not documents:
        raise SystemExit(f"No supported documents found under: {input_dir}")

    manifest_map = load_manifest_map(manifest_csv)
    manifest_base_dir = manifest_csv.parent if manifest_csv else None
    run_dir = build_run_directory(output_dir, dataset_name)
    run_config = Config()
    validate_material_index(run_config)
    orchestrator = create_evaluation_orchestrator(run_dir)
    accumulator = EvaluationAccumulator()

    prediction_rows: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []

    for document_path in documents:
        annotation_path = resolve_annotation_path(
            document_path=document_path,
            annotation_dir=annotation_dir,
            manifest_map=manifest_map,
            manifest_base_dir=manifest_base_dir,
        )
        annotation = load_annotation(annotation_path)
        if annotation_dir is not None and annotation is None:
            raise SystemExit(f"Missing annotation for document: {document_path.name}")

        start = perf_counter()
        raw_result = orchestrator.process_order_from_document(str(document_path))
        latency_ms = (perf_counter() - start) * 1000
        result = to_jsonable(raw_result)

        success = bool(result.get("success"))
        document_id = document_path.stem
        parsed_item_count = count_parsed_items(result) if success else 0
        matched_item_count = count_matched_items(result) if success else 0
        risk_issue_count = count_risk_issues(result) if success else 0
        needs_confirmation = bool(result.get("needs_confirmation")) if success else False

        accumulator.record_sample(
            success=success,
            latency_ms=latency_ms,
            needs_confirmation=needs_confirmation,
            parsed_item_count=parsed_item_count,
            matched_item_count=matched_item_count,
            risk_issue_count=risk_issue_count,
            annotation=annotation,
            prediction=result if success else None,
        )

        row = {
            "document_id": document_id,
            "file_path": str(document_path),
            "annotation_path": str(annotation_path) if annotation_path else None,
            "success": success,
            "latency_ms": latency_ms,
            "needs_confirmation": needs_confirmation,
            "parsed_item_count": parsed_item_count,
            "matched_item_count": matched_item_count,
            "risk_issue_count": risk_issue_count,
            "message": result.get("message"),
            "prediction": result,
        }
        prediction_rows.append(row)

        if not success:
            failures.append(
                {
                    "document_id": document_id,
                    "file_path": str(document_path),
                    "message": result.get("message"),
                }
            )

    summary = accumulator.to_dict()
    markdown = build_summary_markdown(
        dataset_name=dataset_name,
        input_dir=str(input_dir),
        annotation_dir=str(annotation_dir) if annotation_dir else None,
        summary=summary,
        failures=failures,
    )

    write_json(run_dir / "summary.json", summary)
    write_jsonl(run_dir / "predictions.jsonl", prediction_rows)
    write_json(run_dir / "failures.json", failures)
    (run_dir / "summary.md").write_text(markdown, encoding="utf-8")

    manifest_payload = {
        "dataset_name": dataset_name,
        "input_dir": str(input_dir),
        "annotation_dir": str(annotation_dir) if annotation_dir else None,
        "manifest_csv": str(manifest_csv) if manifest_csv else None,
        "sample_count": len(documents),
        "generated_at": datetime.now().isoformat(),
        "run_dir": str(run_dir),
        "code_version": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True
        ).strip(),
        "artifacts": {
            "master_data_version": sha256_file(Path(run_config.data.standard_materials_path)),
            "index_version": sha256_file(Path(run_config.data.faiss_index_path) / "metadata.pkl"),
            "standard_materials_sha256": sha256_file(Path(run_config.data.standard_materials_path)),
            "faiss_index_sha256": sha256_file(Path(run_config.data.faiss_index_path) / "index.faiss"),
            "faiss_metadata_sha256": sha256_file(Path(run_config.data.faiss_index_path) / "metadata.pkl"),
            "embedding_model": "all-MiniLM-L6-v2",
            "model_config": {
                "model": run_config.model.model,
                "match_threshold": run_config.risk.match_threshold,
                "confidence_threshold": run_config.risk.confidence_threshold,
            },
        },
    }
    write_json(run_dir / "run_manifest.json", manifest_payload)

    print(f"Evaluation completed: {run_dir}")
    print(f"Summary: {run_dir / 'summary.md'}")
    print(f"Predictions: {run_dir / 'predictions.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
