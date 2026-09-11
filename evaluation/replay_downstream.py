"""用已归档的 ParsedOrder 重放当前 Matching / Risk / 业务动作。

本脚本固定旧版解析结果，只重放 Parser 之后的下游阶段，用于定位下游改动收益并
复查“高分错 SKU”。它不经过 Parser、自纠错、HTTP、数据库，也不调用 Qwen，因此
输出必须标注为“下游重放”，不得当作端到端指标。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import Config
from domain.models import OrderStatus, ParsedOrder
from evaluation.metrics import (
    EvaluationAccumulator,
    build_summary_markdown,
    format_rate,
    safe_divide,
    values_match,
)
from evaluation.run_evaluation import (
    build_run_directory,
    create_evaluation_orchestrator,
    load_annotation,
    validate_material_index,
    write_json,
    write_jsonl,
)
from interfaces.http.serializers import to_jsonable


HIGH_SCORE_THRESHOLD = 0.8
REPLAY_PREDICTIONS_FILE = "replay_predictions.jsonl"
REPLAY_SUMMARY_FILE = "replay_summary.json"
REPLAY_SUMMARY_MARKDOWN_FILE = "replay_summary.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Replay the current Matching/Risk/business-action stages on archived "
            "ParsedOrders. This is a downstream replay, not an end-to-end run."
        )
    )
    parser.add_argument(
        "--predictions",
        required=True,
        help="Archived predictions.jsonl containing prediction.final_result.parsed_order.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "evaluation" / "results"),
        help="Directory where replay outputs will be written.",
    )
    parser.add_argument(
        "--dataset-name",
        help="Result name. Defaults to downstream_replay_<archived run dir name>.",
    )
    parser.add_argument("--limit", type=int, help="Optional max number of documents to replay.")
    parser.add_argument(
        "--evaluation-as-of",
        help=(
            "Fixed evaluation date (YYYY-MM-DD) used by the risk stage, e.g. the "
            "dataset_summary.validation.evaluation_as_of. Defaults to config/env."
        ),
    )
    return parser.parse_args()


def load_prediction_rows(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def reconstruct_parsed_order(row: Dict[str, Any]) -> Optional[ParsedOrder]:
    """从归档预测中恢复旧版 ParsedOrder；没有解析结果时返回 None。"""
    prediction = row.get("prediction") or {}
    final_result = prediction.get("final_result") or {}
    parsed = final_result.get("parsed_order")
    if not parsed:
        return None
    return ParsedOrder.model_validate(parsed)


def replay_order(orchestrator: Any, parsed_order: ParsedOrder, document_path: str) -> Tuple[Dict[str, Any], float]:
    """固定 ParsedOrder，只重放匹配、风控与业务动作。"""
    manager = orchestrator.order_manager
    order_id = manager.create_order(
        document_path=document_path,
        document_type=Path(document_path).suffix.lstrip(".").lower() or None,
        order_text="",
    )
    # 模拟解析阶段已完成，使状态机允许进入 matching（PENDING 不能直接跳 MATCHING）
    manager.update_order_status(order_id, OrderStatus.PARSING, reason="downstream_replay")
    manager.update_parsed_order(order_id, parsed_order)

    start = perf_counter()
    result = orchestrator._process_matching_phase(order_id, parsed_order)
    latency_ms = (perf_counter() - start) * 1000
    return to_jsonable(result), latency_ms


def classify_items(
    expected_items: List[Dict[str, Any]], predicted_items: List[Dict[str, Any]]
) -> Tuple[Dict[str, int], List[Dict[str, Any]]]:
    """按行对齐分类每条明细，区分正确匹配、正确拒识、错误接受与拒识。

    - 标注有金标 SKU：正确匹配 / 错误接受 / 拒识（安全但未交付正确 SKU）。
    - 标注无金标 SKU：正确拒识 / 错误接受（不应给出 SKU 却给出）。
    """
    counts = {
        "golden_items": 0,
        "correct_match": 0,
        "wrong_accept": 0,
        "rejected": 0,
        "no_golden_items": 0,
        "correct_reject": 0,
        "wrong_accept_no_golden": 0,
    }
    records: List[Dict[str, Any]] = []
    for index in range(max(len(expected_items), len(predicted_items))):
        expected = expected_items[index] if index < len(expected_items) else {}
        predicted = predicted_items[index] if index < len(predicted_items) else {}
        if not expected and not predicted:
            continue
        golden = expected.get("golden_sku_code")
        accepted = predicted.get("sku_code")
        has_golden = golden not in (None, "")

        if has_golden:
            counts["golden_items"] += 1
            if accepted in (None, ""):
                category = "rejected"
                counts["rejected"] += 1
            elif values_match(golden, accepted):
                category = "correct_match"
                counts["correct_match"] += 1
            else:
                category = "wrong_accept"
                counts["wrong_accept"] += 1
        else:
            counts["no_golden_items"] += 1
            if accepted in (None, ""):
                category = "correct_reject"
                counts["correct_reject"] += 1
            else:
                category = "wrong_accept_no_golden"
                counts["wrong_accept_no_golden"] += 1

        records.append(
            {
                "line_index": index + 1,
                "golden_sku": golden,
                "accepted_sku": accepted,
                "match_score": predicted.get("match_score"),
                "candidate_skus": predicted.get("candidate_skus") or [],
                "rejection_reason": predicted.get("rejection_reason"),
                "category": category,
            }
        )
    return counts, records


def coverage_summary(counts: Dict[str, int]) -> Dict[str, Any]:
    golden = counts["golden_items"]
    accepted = counts["correct_match"] + counts["wrong_accept"]
    return {
        "golden_items": golden,
        "no_golden_items": counts["no_golden_items"],
        "correct_match": counts["correct_match"],
        "wrong_accept": counts["wrong_accept"],
        "rejected": counts["rejected"],
        "correct_reject": counts["correct_reject"],
        "wrong_accept_no_golden": counts["wrong_accept_no_golden"],
        "accepted_sku_coverage": safe_divide(accepted, golden),
        "accepted_sku_precision": safe_divide(counts["correct_match"], accepted),
        "sku_accuracy": safe_divide(counts["correct_match"], golden),
    }


def analyze_high_score_wrong_skus(
    archived_final: Dict[str, Any],
    replayed_final: Dict[str, Any],
    annotation: Dict[str, Any],
    threshold: float = HIGH_SCORE_THRESHOLD,
) -> List[Dict[str, Any]]:
    """复查旧版“高分但 SKU 错误”的行，并按重放结果给出修复/拒识/仍错误。"""
    expected_items = annotation.get("items", [])
    old_items = (archived_final.get("matched_order") or {}).get("items") or []
    new_items = (replayed_final.get("matched_order") or {}).get("items") or []

    findings: List[Dict[str, Any]] = []
    for index, expected in enumerate(expected_items):
        golden = expected.get("golden_sku_code")
        if golden in (None, ""):
            continue
        old_item = old_items[index] if index < len(old_items) else None
        old_sku = old_item.get("sku_code") if old_item else None
        old_score = float((old_item or {}).get("match_score") or 0.0)
        if old_sku in (None, "") or values_match(golden, old_sku):
            continue
        if old_score < threshold:
            continue

        new_item = new_items[index] if index < len(new_items) else None
        new_sku = new_item.get("sku_code") if new_item else None
        if new_sku in (None, ""):
            outcome = "rejected"
        elif values_match(golden, new_sku):
            outcome = "fixed"
        else:
            outcome = "still_wrong"

        findings.append(
            {
                "line_index": index + 1,
                "golden_sku": golden,
                "old_sku": old_sku,
                "old_score": round(old_score, 4),
                "new_sku": new_sku,
                "outcome": outcome,
            }
        )
    return findings


def _merge_counts(total: Dict[str, int], counts: Dict[str, int]) -> None:
    for key, value in counts.items():
        total[key] = total.get(key, 0) + value


def replay_run() -> int:
    args = parse_args()
    predictions_path = Path(args.predictions).resolve()
    if not predictions_path.is_file():
        raise SystemExit(f"Predictions file does not exist: {predictions_path}")

    rows = load_prediction_rows(predictions_path)
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        raise SystemExit(f"No rows found in: {predictions_path}")

    config = Config()
    validate_material_index(config)
    dataset_name = args.dataset_name or f"downstream_replay_{predictions_path.parent.name}"
    output_dir = Path(args.output_dir).resolve()
    run_dir = build_run_directory(output_dir, dataset_name)

    orchestrator = create_evaluation_orchestrator(evaluation_as_of=args.evaluation_as_of)
    accumulator = EvaluationAccumulator()

    replay_rows: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []
    totals = {key: 0 for key in (
        "golden_items", "correct_match", "wrong_accept", "rejected",
        "no_golden_items", "correct_reject", "wrong_accept_no_golden",
    )}
    item_records: List[Dict[str, Any]] = []
    high_score_findings: List[Dict[str, Any]] = []

    for row in rows:
        document_id = row["document_id"]
        annotation_path = row.get("annotation_path")
        annotation = load_annotation(Path(annotation_path)) if annotation_path else None
        parsed_order = reconstruct_parsed_order(row)
        if parsed_order is None:
            failures.append({"document_id": document_id, "message": "缺少可重放的 ParsedOrder"})
            if annotation:
                accumulator.record_sample(
                    success=False, latency_ms=0.0, needs_confirmation=False,
                    parsed_item_count=0, matched_item_count=0, risk_issue_count=0,
                    annotation=annotation, prediction=None,
                )
            continue

        try:
            replayed, latency_ms = replay_order(
                orchestrator, parsed_order, row.get("file_path") or document_id
            )
        except Exception as exc:  # noqa: BLE001 - 需保留每条重放失败用于追溯
            failures.append({"document_id": document_id, "message": f"下游重放失败: {exc}"})
            if annotation:
                accumulator.record_sample(
                    success=False, latency_ms=0.0, needs_confirmation=False,
                    parsed_item_count=0, matched_item_count=0, risk_issue_count=0,
                    annotation=annotation, prediction=None,
                )
            continue

        success = bool(replayed.get("success"))
        final_result = replayed.get("final_result") or {}
        matched_items = (final_result.get("matched_order") or {}).get("items") or []
        parsed_items = (final_result.get("parsed_order") or {}).get("items") or []
        risk_issues = (final_result.get("risk_result") or {}).get("issues") or []
        if not success:
            failures.append({"document_id": document_id, "message": replayed.get("message")})

        replay_row = {
            "document_id": document_id,
            "file_path": row.get("file_path"),
            "annotation_path": annotation_path,
            "success": success,
            "latency_ms": latency_ms,
            "needs_confirmation": bool(replayed.get("needs_confirmation")),
            "parsed_item_count": len(parsed_items),
            "matched_item_count": len(matched_items),
            "risk_issue_count": len(risk_issues),
            "message": replayed.get("message"),
            "prediction": replayed,
        }
        replay_rows.append(replay_row)

        if annotation:
            accumulator.record_sample(
                success=success,
                latency_ms=latency_ms,
                needs_confirmation=replay_row["needs_confirmation"],
                parsed_item_count=len(parsed_items),
                matched_item_count=len(matched_items),
                risk_issue_count=len(risk_issues),
                annotation=annotation,
                prediction=replayed if success else None,
            )
            counts, records = classify_items(annotation.get("items", []), matched_items)
            _merge_counts(totals, counts)
            item_records.extend({"document_id": document_id, **record} for record in records)
            if success:
                high_score_findings.extend(
                    {
                        "document_id": document_id,
                        **finding,
                    }
                    for finding in analyze_high_score_wrong_skus(
                        (row.get("prediction") or {}).get("final_result") or {},
                        final_result,
                        annotation,
                    )
                )

    summary = accumulator.to_dict()
    coverage = coverage_summary(totals)
    high_score_outcome_counts = {
        outcome: sum(1 for finding in high_score_findings if finding["outcome"] == outcome)
        for outcome in ("fixed", "rejected", "still_wrong")
    }
    summary["replay"] = {
        "source_predictions": str(predictions_path),
        "source_run_dir": str(predictions_path.parent),
        "evaluation_as_of": args.evaluation_as_of or getattr(config.risk, "evaluation_as_of", None),
        "replayed_documents": len(replay_rows),
        "failed_documents": len(failures),
        "coverage": coverage,
        "high_score_wrong_sku": {
            "threshold": HIGH_SCORE_THRESHOLD,
            "count": len(high_score_findings),
            "outcomes": high_score_outcome_counts,
            "findings": high_score_findings,
        },
    }

    markdown = build_replay_markdown(
        dataset_name=dataset_name,
        predictions_path=predictions_path,
        summary=summary,
        failures=failures,
        item_records=item_records,
    )

    write_json(run_dir / REPLAY_SUMMARY_FILE, summary)
    write_jsonl(run_dir / REPLAY_PREDICTIONS_FILE, replay_rows)
    (run_dir / REPLAY_SUMMARY_MARKDOWN_FILE).write_text(markdown, encoding="utf-8")

    print(f"Downstream replay completed: {run_dir}")
    print(f"Report: {run_dir / REPLAY_SUMMARY_MARKDOWN_FILE}")
    print(
        "SKU accuracy (golden items): "
        f"{coverage['correct_match']}/{coverage['golden_items']} "
        f"({coverage['sku_accuracy']:.2%}); "
        f"accepted-SKU precision {coverage['accepted_sku_precision']:.2%}; "
        f"coverage {coverage['accepted_sku_coverage']:.2%}"
    )
    return 0


def build_replay_markdown(
    *,
    dataset_name: str,
    predictions_path: Path,
    summary: Dict[str, Any],
    failures: List[Dict[str, Any]],
    item_records: List[Dict[str, Any]],
) -> str:
    replay = summary["replay"]
    coverage = replay["coverage"]
    high_score = replay["high_score_wrong_sku"]

    banner = [
        f"# 下游重放报告（非端到端）: {dataset_name}",
        "",
        f"- 固定旧版解析结果来源: `{predictions_path}`",
        "- 本报告固定旧 ParsedOrder，只重放当前 Matching / Risk / 业务动作；",
        "  不经过 Parser、自纠错、HTTP、数据库，也不调用 Qwen。",
        "- 不得把本报告的数字当作新版端到端指标。",
        f"- 评测时点 (evaluation_as_of): {replay.get('evaluation_as_of') or 'config/env 默认'}",
        "",
    ]

    standard = build_summary_markdown(
        dataset_name=dataset_name,
        input_dir=replay["source_run_dir"],
        annotation_dir=None,
        summary=summary,
        failures=failures,
    )

    coverage_lines = [
        "",
        "## SKU Coverage & Accepted-SKU Accuracy",
        "",
        f"- Golden-SKU items: {coverage['golden_items']}",
        f"- Correct matches: {coverage['correct_match']}",
        f"- Wrong accepts: {coverage['wrong_accept']}",
        f"- Rejected (safe, no SKU delivered): {coverage['rejected']}",
        f"- Correct rejects (no golden SKU): {coverage['correct_reject']}",
        f"- Wrong accepts without golden SKU: {coverage['wrong_accept_no_golden']}",
        (
            "- Accepted-SKU coverage: "
            f"{format_rate(coverage['correct_match'] + coverage['wrong_accept'], coverage['golden_items'])}"
        ),
        (
            "- Accepted-SKU precision: "
            f"{format_rate(coverage['correct_match'], coverage['correct_match'] + coverage['wrong_accept'])}"
        ),
        f"- SKU accuracy: {format_rate(coverage['correct_match'], coverage['golden_items'])}",
    ]

    high_score_lines = [
        "",
        "## High-Score Wrong SKU Recheck",
        "",
        f"- 阈值: match_score >= {high_score['threshold']}",
        f"- 旧版高分错 SKU 行数: {high_score['count']}",
        f"- 重放后: fixed {high_score['outcomes']['fixed']}、"
        f"rejected {high_score['outcomes']['rejected']}、"
        f"still_wrong {high_score['outcomes']['still_wrong']}",
        "",
    ]
    if high_score["findings"]:
        high_score_lines.extend(
            [
                "| document | line | golden | old_sku | old_score | new_sku | outcome |",
                "| --- | ---: | --- | --- | ---: | --- | --- |",
            ]
        )
        for finding in high_score["findings"]:
            high_score_lines.append(
                f"| `{finding['document_id']}` | {finding['line_index']} | "
                f"{finding['golden_sku']} | {finding['old_sku']} | {finding['old_score']} | "
                f"{finding['new_sku'] or '-'} | {finding['outcome']} |"
            )
    else:
        high_score_lines.append("- 未发现旧版高分错 SKU。")

    rejected_records = [record for record in item_records if record["category"] == "rejected"]
    rejected_lines = ["", "## Rejected Detailed Items", ""]
    if rejected_records:
        rejected_lines.extend(
            [
                "| document | line | golden | candidate_skus | reason |",
                "| --- | ---: | --- | --- | --- |",
            ]
        )
        for record in rejected_records:
            candidates = ", ".join(record["candidate_skus"]) or "-"
            reason = (record.get("rejection_reason") or "-").replace("|", "/")
            rejected_lines.append(
                f"| `{record['document_id']}` | {record['line_index']} | "
                f"{record['golden_sku']} | {candidates} | {reason} |"
            )
    else:
        rejected_lines.append("- None")

    return "\n".join(banner + [standard] + coverage_lines + high_score_lines + rejected_lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(replay_run())
