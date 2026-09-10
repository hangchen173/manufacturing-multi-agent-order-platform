from __future__ import annotations

import argparse
import csv
import json
import hashlib
import pickle
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Number of documents processed in parallel. Defaults to 1 (serial).",
    )
    parser.add_argument("--no-recursive", action="store_true", help="Disable recursive file discovery.")
    parser.add_argument(
        "--resume-run",
        help=(
            "Existing run directory to resume. Only documents that failed or were never "
            "evaluated are re-run, and the merged results are written back into that directory."
        ),
    )
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


def load_prediction_rows(run_dir: Path) -> Dict[str, Dict[str, Any]]:
    path = run_dir / "predictions.jsonl"
    if not path.exists():
        return {}
    rows: Dict[str, Dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows[row["document_id"]] = row
    return rows


def load_manifest_payload(run_dir: Path) -> Dict[str, Any]:
    path = run_dir / "run_manifest.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def create_evaluation_orchestrator(
    faiss_manager: Optional[Any] = None,
) -> OrderProcessingOrchestrator:
    from application.agents import MatchingAgent

    config = Config()
    order_manager = OrderManager(repository=InMemoryOrderRepository(), config=config)
    matching_agent = MatchingAgent(config=config, faiss_manager=faiss_manager)
    return OrderProcessingOrchestrator(
        order_manager=order_manager,
        config=config,
        matching_agent=matching_agent,
    )


def evaluate_document(
    *,
    document_path: Path,
    annotation_dir: Optional[Path],
    manifest_map: Dict[str, str],
    manifest_base_dir: Optional[Path],
    orchestrator: OrderProcessingOrchestrator,
) -> Dict[str, Any]:
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
    return row


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

    all_documents = discover_documents(input_dir, recursive=not args.no_recursive)
    if args.limit:
        all_documents = all_documents[: args.limit]
    if not all_documents:
        raise SystemExit(f"No supported documents found under: {input_dir}")

    manifest_map = load_manifest_map(manifest_csv)
    manifest_base_dir = manifest_csv.parent if manifest_csv else None
    run_config = Config()
    validate_material_index(run_config)
    worker_count = max(1, args.concurrency)

    if args.resume_run:
        run_dir = Path(args.resume_run).resolve()
        if not run_dir.is_dir():
            raise SystemExit(f"Resume run dir does not exist: {run_dir}")
        prior_rows = load_prediction_rows(run_dir)
        dataset_name = args.dataset_name or load_manifest_payload(run_dir).get(
            "dataset_name"
        ) or input_dir.name
        documents = [
            path
            for path in all_documents
            if not (prior_rows.get(path.stem) or {}).get("success")
        ]
        if not documents:
            raise SystemExit(f"Nothing to resume: all {len(all_documents)} documents already succeeded")
        print(f"Resuming {run_dir.name}: re-evaluating {len(documents)} / {len(all_documents)} documents")
    else:
        run_dir = build_run_directory(output_dir, dataset_name)
        prior_rows = {}
        documents = all_documents

    accumulator = EvaluationAccumulator()

    def process(document_path: Path, orchestrator: OrderProcessingOrchestrator) -> Dict[str, Any]:
        return evaluate_document(
            document_path=document_path,
            annotation_dir=annotation_dir,
            manifest_map=manifest_map,
            manifest_base_dir=manifest_base_dir,
            orchestrator=orchestrator,
        )

    if worker_count == 1:
        serial_orchestrator = create_evaluation_orchestrator()
        outcomes = [process(document_path, serial_orchestrator) for document_path in documents]
    else:
        from infrastructure.vector_store.faiss_manager import FAISSManager

        shared_faiss_manager = FAISSManager(index_path=run_config.data.faiss_index_path)
        thread_state = threading.local()

        def get_orchestrator() -> OrderProcessingOrchestrator:
            if getattr(thread_state, "orchestrator", None) is None:
                thread_state.orchestrator = create_evaluation_orchestrator(shared_faiss_manager)
            return thread_state.orchestrator

        outcomes = [None] * len(documents)
        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            future_to_index = {
                pool.submit(process, document_path, get_orchestrator()): index
                for index, document_path in enumerate(documents)
            }
            for future in as_completed(future_to_index):
                outcomes[future_to_index[future]] = future.result()

    new_rows_by_id = {outcome["document_id"]: outcome for outcome in outcomes}

    final_rows: List[Dict[str, Any]] = []
    final_failures: List[Dict[str, Any]] = []
    for document_path in all_documents:
        document_id = document_path.stem
        prior = prior_rows.get(document_id)
        row = prior if (prior and prior.get("success")) else new_rows_by_id.get(document_id)
        if row is None:
            continue
        final_rows.append(row)
        if not row.get("success"):
            final_failures.append(
                {
                    "document_id": document_id,
                    "file_path": row.get("file_path", str(document_path)),
                    "message": row.get("message"),
                }
            )

    for row in final_rows:
        annotation = load_annotation(
            Path(row["annotation_path"]) if row.get("annotation_path") else None
        )
        accumulator.record_sample(
            success=bool(row["success"]),
            latency_ms=row["latency_ms"],
            needs_confirmation=bool(row.get("needs_confirmation")),
            parsed_item_count=row.get("parsed_item_count", 0),
            matched_item_count=row.get("matched_item_count", 0),
            risk_issue_count=row.get("risk_issue_count", 0),
            annotation=annotation,
            prediction=row.get("prediction") if row["success"] else None,
        )

    summary = accumulator.to_dict()
    markdown = build_summary_markdown(
        dataset_name=dataset_name,
        input_dir=str(input_dir),
        annotation_dir=str(annotation_dir) if annotation_dir else None,
        summary=summary,
        failures=final_failures,
    )

    write_json(run_dir / "summary.json", summary)
    write_jsonl(run_dir / "predictions.jsonl", final_rows)
    write_json(run_dir / "failures.json", final_failures)
    (run_dir / "summary.md").write_text(markdown, encoding="utf-8")

    manifest_payload = {
        "dataset_name": dataset_name,
        "input_dir": str(input_dir),
        "annotation_dir": str(annotation_dir) if annotation_dir else None,
        "manifest_csv": str(manifest_csv) if manifest_csv else None,
        "sample_count": len(all_documents),
        "evaluated_this_run": len(documents),
        "resumed": bool(args.resume_run),
        "concurrency": worker_count,
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
                "evaluation_as_of": run_config.risk.evaluation_as_of,
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
