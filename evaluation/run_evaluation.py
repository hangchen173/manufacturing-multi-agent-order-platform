from __future__ import annotations

import argparse
import csv
import json
import hashlib
import os
import pickle
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Dict, Iterable, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from application.agents.parser_agent import prompt_fingerprint
from application.orchestrators import OrderProcessingOrchestrator
from application.services import OrderManager
from config import Config
from domain.constants import (
    SUPPORTED_EXCEL_EXTENSIONS,
    SUPPORTED_IMAGE_EXTENSIONS,
    SUPPORTED_PDF_EXTENSIONS,
    SUPPORTED_TEXT_EXTENSIONS,
)
from evaluation.metrics import EvaluationAccumulator, build_summary_markdown, safe_divide
from evaluation.contracts import normalize_annotation
from evaluation.repositories import InMemoryOrderRepository
from interfaces.http.serializers import to_jsonable


SUPPORTED_EVAL_EXTENSIONS = (
    SUPPORTED_PDF_EXTENSIONS | SUPPORTED_EXCEL_EXTENSIONS | SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_TEXT_EXTENSIONS
)

MANIFEST_FILE = "run_manifest.json"
ATTEMPTS_FILE = "attempts.jsonl"
PREDICTIONS_FILE = "predictions.jsonl"
FAILURES_FILE = "failures.json"
SUMMARY_FILE = "summary.json"
SUMMARY_MARKDOWN_FILE = "summary.md"


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


def load_attempts(run_dir: Path) -> List[Dict[str, Any]]:
    path = run_dir / ATTEMPTS_FILE
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


class AttemptWriter:
    """逐条追加尝试记录并立即落盘，使评测中断后已完成的样本可被恢复。"""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def append(self, row: Dict[str, Any]) -> None:
        payload = json.dumps(row, ensure_ascii=False) + "\n"
        with self._lock:
            with self.path.open("a", encoding="utf-8") as file:
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())


def next_attempt_index(attempts: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    highest: Dict[str, int] = {}
    for row in attempts:
        document_id = row["document_id"]
        highest[document_id] = max(highest.get(document_id, 0), int(row.get("attempt", 0)))
    return highest


def select_final_rows(
    all_documents: List[Path], attempts: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """为每个样本选出最终预测：优先首次成功的尝试，否则取最后一次尝试。"""
    by_document: Dict[str, List[Dict[str, Any]]] = {}
    for row in attempts:
        by_document.setdefault(row["document_id"], []).append(row)

    final_rows: List[Dict[str, Any]] = []
    for document_path in all_documents:
        document_attempts = by_document.get(document_path.stem)
        if not document_attempts:
            continue
        document_attempts.sort(key=lambda row: int(row.get("attempt", 0)))
        successful = [row for row in document_attempts if row.get("success")]
        selected = successful[0] if successful else document_attempts[-1]
        final_row = dict(selected)
        final_row["attempt_count"] = len(document_attempts)
        final_rows.append(final_row)
    return final_rows


def summarize_attempts(attempts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """按文档汇总首次成功率、重试成功率以及累计耗时/tokens。"""
    by_document: Dict[str, List[Dict[str, Any]]] = {}
    for row in attempts:
        by_document.setdefault(row["document_id"], []).append(row)

    total_latency_ms = 0.0
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    usage_missing_attempts = 0
    usage_missing_calls = 0
    first_attempt_success = 0
    final_success = 0
    retried_documents = 0
    retry_success = 0

    for document_attempts in by_document.values():
        document_attempts.sort(key=lambda row: int(row.get("attempt", 0)))
        if document_attempts[0].get("success"):
            first_attempt_success += 1
        succeeded = any(row.get("success") for row in document_attempts)
        if succeeded:
            final_success += 1
        if len(document_attempts) > 1:
            retried_documents += 1
            if succeeded:
                retry_success += 1
        for row in document_attempts:
            total_latency_ms += float(row.get("latency_ms") or 0.0)
            usage = row.get("usage") or {}
            attempted_calls = usage.get("attempted_calls")
            missing_calls = max(0, attempted_calls - usage.get("reported_calls", 0)) if attempted_calls is not None else None
            if missing_calls is None or missing_calls > 0:
                usage_missing_attempts += 1
            usage_missing_calls += missing_calls or 0
            for key in total_usage:
                total_usage[key] += int(usage.get(key) or 0)

    total_documents = len(by_document)
    return {
        "total_documents": total_documents,
        "total_attempts": len(attempts),
        "first_attempt_success_count": first_attempt_success,
        "first_attempt_success_rate": safe_divide(first_attempt_success, total_documents),
        "final_success_count": final_success,
        "final_success_rate": safe_divide(final_success, total_documents),
        "retried_documents": retried_documents,
        "retry_success_count": retry_success,
        "retry_success_rate": safe_divide(retry_success, retried_documents),
        "total_latency_ms": total_latency_ms,
        "total_usage": total_usage,
        "usage_missing_attempts": usage_missing_attempts,
        "usage_missing_calls": usage_missing_calls,
    }


def load_manifest_payload(run_dir: Path) -> Dict[str, Any]:
    path = run_dir / MANIFEST_FILE
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def create_evaluation_orchestrator(
    faiss_manager: Optional[Any] = None,
    evaluation_as_of: Optional[str] = None,
) -> OrderProcessingOrchestrator:
    from application.agents import MatchingAgent

    config = Config()
    if evaluation_as_of:
        # 重放时固定评测时点，保证交期等日期判断可复现
        config.risk.evaluation_as_of = evaluation_as_of
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
    usage = result.get("usage") or {}
    if not usage:
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

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
        "usage": usage,
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


def fingerprint_files(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: str(item)):
        digest.update(str(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update((sha256_file(path) or "").encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _git_output(*args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""
    return completed.stdout.strip()


def build_run_identity(
    config: Config,
    *,
    documents: List[Path],
    annotation_dir: Optional[Path],
    manifest_map: Dict[str, str],
    manifest_base_dir: Optional[Path],
    manifest_csv: Optional[Path],
) -> Dict[str, Any]:
    """构建运行身份：代码/工作区、提示词、模型配置、数据/标注、索引与评测时点。"""
    resolved_annotations = [
        resolve_annotation_path(
            document_path=document,
            annotation_dir=annotation_dir,
            manifest_map=manifest_map,
            manifest_base_dir=manifest_base_dir,
        )
        for document in documents
    ]
    present_annotations = [path for path in resolved_annotations if path is not None]
    index_path = Path(config.data.faiss_index_path)
    return {
        "code_version": _git_output("rev-parse", "HEAD") or None,
        "workspace_state": fingerprint_files(
            [PROJECT_ROOT / "config.py", PROJECT_ROOT / "requirements.txt"]
            + [path for directory in ("application", "domain", "infrastructure", "interfaces", "evaluation")
               for path in (PROJECT_ROOT / directory).rglob("*.py")]
        ),
        "prompt_fingerprint": prompt_fingerprint(),
        "model_config": {
            "model": config.model.model,
            "base_url": config.model.base_url,
            "enable_thinking": False,
            "temperature": 0,
            "max_tokens": 4096,
            "timeout_seconds": 60,
            "sdk_retries": 0,
            "match_threshold": config.risk.match_threshold,
            "confidence_threshold": config.risk.confidence_threshold,
            "evaluation_as_of": config.risk.evaluation_as_of,
        },
        "artifacts": {
            "standard_materials_sha256": sha256_file(Path(config.data.standard_materials_path)),
            "faiss_index_sha256": sha256_file(index_path / "index.faiss"),
            "faiss_metadata_sha256": sha256_file(index_path / "metadata.pkl"),
            "embedding_model": "all-MiniLM-L6-v2",
        },
        "dataset_fingerprint": fingerprint_files(documents),
        "annotation_fingerprint": fingerprint_files(present_annotations),
        "annotation_missing": len(resolved_annotations) - len(present_annotations),
        "manifest_csv_sha256": sha256_file(manifest_csv) if manifest_csv else None,
    }


def identity_hash(identity: Dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def describe_identity_mismatch(
    prior_identity: Optional[Dict[str, Any]], current_identity: Dict[str, Any]
) -> Optional[str]:
    if not isinstance(prior_identity, dict) or not prior_identity:
        return "缺少运行身份记录"
    keys = sorted(set(prior_identity) | set(current_identity))
    changed = [key for key in keys if prior_identity.get(key) != current_identity.get(key)]
    if not changed:
        return None
    return "、".join(changed)


def validate_material_index(config: Config) -> None:
    import faiss
    from infrastructure.vector_store.catalog import load_material_catalog, validate_catalog_index

    index_path = Path(config.data.faiss_index_path)
    metadata_path = index_path / "metadata.pkl"
    index_file = index_path / "index.faiss"
    try:
        documents = load_material_catalog(config.data.standard_materials_path)
        with metadata_path.open("rb") as file:
            metadata = pickle.load(file)
        index = faiss.read_index(str(index_file))
        validate_catalog_index(documents, metadata, index)
    except Exception as exc:
        raise SystemExit(f"Material/index validation failed: {exc}") from exc


def run_concurrent_evaluation(
    documents: List[Path],
    worker_count: int,
    process: Callable[[Path, OrderProcessingOrchestrator], Dict[str, Any]],
    orchestrator_factory: Callable[[], OrderProcessingOrchestrator],
) -> List[Dict[str, Any]]:
    """在工作线程内获取线程本地 Orchestrator，使解析诊断与订单上下文逐线程隔离。

    Orchestrator 必须在线程内部构造：若在提交任务的主线程求值，所有工作线程会共享
    同一 Parser、订单字典与仓储。构造器中可复用的 FAISS 索引仅用于只读检索。
    """
    thread_state = threading.local()

    def get_orchestrator() -> OrderProcessingOrchestrator:
        if getattr(thread_state, "orchestrator", None) is None:
            thread_state.orchestrator = orchestrator_factory()
        return thread_state.orchestrator

    def worker(document_path: Path) -> Dict[str, Any]:
        return process(document_path, get_orchestrator())

    outcomes: List[Optional[Dict[str, Any]]] = [None] * len(documents)
    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        future_to_index = {
            pool.submit(worker, document_path): index
            for index, document_path in enumerate(documents)
        }
        for future in as_completed(future_to_index):
            outcomes[future_to_index[future]] = future.result()
    return outcomes


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

    identity = build_run_identity(
        run_config,
        documents=all_documents,
        annotation_dir=annotation_dir,
        manifest_map=manifest_map,
        manifest_base_dir=manifest_base_dir,
        manifest_csv=manifest_csv,
    )
    current_identity_hash = identity_hash(identity)

    if args.resume_run:
        resume_dir = Path(args.resume_run).resolve()
        if not resume_dir.is_dir():
            raise SystemExit(f"Resume run dir does not exist: {resume_dir}")
        prior_manifest = load_manifest_payload(resume_dir)
        dataset_name = args.dataset_name or prior_manifest.get("dataset_name") or dataset_name
        mismatch = describe_identity_mismatch(prior_manifest.get("run_identity"), identity)
        if mismatch:
            print(
                f"Run identity mismatch ({mismatch}); refusing to resume "
                f"{resume_dir.name} and starting a new run"
            )
            run_dir = build_run_directory(output_dir, dataset_name)
            resumed = False
            prior_attempts: List[Dict[str, Any]] = []
        else:
            run_dir = resume_dir
            resumed = True
            prior_attempts = load_attempts(run_dir)
    else:
        run_dir = build_run_directory(output_dir, dataset_name)
        resumed = False
        prior_attempts = []

    # 只有从未成功过的样本才需要重跑；已成功的样本保留历史尝试记录。
    successful_ids = {row["document_id"] for row in prior_attempts if row.get("success")}
    documents = [path for path in all_documents if path.stem not in successful_ids]
    if resumed:
        print(
            f"Resuming {run_dir.name}: re-evaluating "
            f"{len(documents)} / {len(all_documents)} documents"
        )

    manifest_payload = {
        "dataset_name": dataset_name,
        "input_dir": str(input_dir),
        "annotation_dir": str(annotation_dir) if annotation_dir else None,
        "manifest_csv": str(manifest_csv) if manifest_csv else None,
        "sample_count": len(all_documents),
        "evaluated_this_run": len(documents),
        "resumed": resumed,
        "concurrency": worker_count,
        "generated_at": datetime.now().isoformat(),
        "run_dir": str(run_dir),
        "run_identity": identity,
        "identity_hash": current_identity_hash,
    }
    write_json(run_dir / MANIFEST_FILE, manifest_payload)
    attempt_writer = AttemptWriter(run_dir / ATTEMPTS_FILE)
    attempt_counter = next_attempt_index(prior_attempts)
    counter_lock = threading.Lock()

    def process(document_path: Path, orchestrator: OrderProcessingOrchestrator) -> Dict[str, Any]:
        with counter_lock:
            attempt_index = attempt_counter.get(document_path.stem, 0) + 1
            attempt_counter[document_path.stem] = attempt_index
        row = evaluate_document(
            document_path=document_path,
            annotation_dir=annotation_dir,
            manifest_map=manifest_map,
            manifest_base_dir=manifest_base_dir,
            orchestrator=orchestrator,
        )
        row["attempt"] = attempt_index
        attempt_writer.append(row)
        return row

    if documents:
        if worker_count == 1:
            serial_orchestrator = create_evaluation_orchestrator()
            for document_path in documents:
                process(document_path, serial_orchestrator)
        else:
            from infrastructure.vector_store.faiss_manager import FAISSManager

            # FAISS 索引在工作线程间只读共享（仅 search 与 metadata 读取）；
            # Orchestrator 与订单上下文由 run_concurrent_evaluation 逐线程构造。
            shared_faiss_manager = FAISSManager(index_path=run_config.data.faiss_index_path)
            run_concurrent_evaluation(
                documents=documents,
                worker_count=worker_count,
                process=process,
                orchestrator_factory=lambda: create_evaluation_orchestrator(shared_faiss_manager),
            )

    all_attempts = load_attempts(run_dir)
    final_rows = select_final_rows(all_documents, all_attempts)
    attempt_summary = summarize_attempts(all_attempts)

    accumulator = EvaluationAccumulator()
    final_failures: List[Dict[str, Any]] = []
    for row in final_rows:
        if not row.get("success"):
            final_failures.append(
                {
                    "document_id": row["document_id"],
                    "file_path": row.get("file_path"),
                    "message": row.get("message"),
                    "attempt": row.get("attempt"),
                }
            )
        annotation = load_annotation(
            Path(row["annotation_path"]) if row.get("annotation_path") else None
        )
        accumulator.record_sample(
            success=bool(row.get("success")),
            latency_ms=row.get("latency_ms", 0.0),
            needs_confirmation=bool(row.get("needs_confirmation")),
            parsed_item_count=row.get("parsed_item_count", 0),
            matched_item_count=row.get("matched_item_count", 0),
            risk_issue_count=row.get("risk_issue_count", 0),
            annotation=annotation,
            prediction=row.get("prediction") if row.get("success") else None,
        )

    summary = accumulator.to_dict()
    summary["attempts"] = attempt_summary
    markdown = build_summary_markdown(
        dataset_name=dataset_name,
        input_dir=str(input_dir),
        annotation_dir=str(annotation_dir) if annotation_dir else None,
        summary=summary,
        failures=final_failures,
        attempts=attempt_summary,
    )

    write_json(run_dir / SUMMARY_FILE, summary)
    write_jsonl(run_dir / PREDICTIONS_FILE, final_rows)
    write_json(run_dir / FAILURES_FILE, final_failures)
    (run_dir / SUMMARY_MARKDOWN_FILE).write_text(markdown, encoding="utf-8")

    print(f"Evaluation completed: {run_dir}")
    print(f"Summary: {run_dir / SUMMARY_MARKDOWN_FILE}")
    print(f"Predictions: {run_dir / PREDICTIONS_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
