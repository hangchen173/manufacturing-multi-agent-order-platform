"""基线对照实验：VEAP vs 零样本 vs MAD。

**要回答的问题**（`paper/08_SUBMISSION_PLAN.md` §10.5 的单基线决定性实验）：

在**同一模型、同一抽取提示词、同一评测口径**下——

1. VEAP 的字段准确率是否**不劣于**自然语言辩论（MAD）？
2. VEAP 的 token 成本是否**显著更低**？
3. 是否**只有 VEAP** 的产物带机器可核查证据链？

**判据**（写进 `paper/08_SUBMISSION_PLAN.md` §10.5）：

| 结果 | 含义 | 动作 |
|---|---|---|
| VEAP 等准确率下成本显著更低 **且** 唯一可审计 | 论文成立 | 按 ICDAR 计划推进 |
| VEAP 又贵又不准 | 论文不成立 | 降级目标 / 改叙事 |
| 准确率相当、成本相当 | 需重新定位贡献 | 回到 C2 叙事（可核查性） |

**为什么必须现在跑**：这是把「论文有没有贡献」这个最大不确定性
从 2027 年 1 月提前到 2026 年 10 月的唯一手段。

用法：

```
# 只看会跑哪些订单、不调模型
python scripts/baseline_comparison.py --limit 3 --dry-run

# 小规模实跑（先验证端到端可用）
python scripts/baseline_comparison.py --limit 3

# 只跑基线，跳过 VEAP（VEAP 已在主评测跑过时）
python scripts/baseline_comparison.py --limit 20 --methods zero_shot,mad

# 正式对照
python scripts/baseline_comparison.py --limit 20
```

**红线**：必须直连模型服务商官方端点。中转站会静默替换模型，
使「实际用了哪个模型」不可证明，整篇论文的可复现性主张随之失效。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from application.agents.extractor import Extractor  # noqa: E402
from application.agents.source_map import find_item_locators  # noqa: E402
from config import Config  # noqa: E402
from evaluation.baselines import BASELINES, DEFAULT_METHOD_ORDER  # noqa: E402
from evaluation.scoring import accuracy, merge_counts, score_order  # noqa: E402
from infrastructure.document_processing import DocumentLoader  # noqa: E402

ORDERS_DIR = PROJECT_ROOT / "datasets/generated_complex/orders/test"
ANNOTATIONS_DIR = PROJECT_ROOT / "datasets/generated_complex/annotations/test"
RESULTS_ROOT = PROJECT_ROOT / "evaluation/results"

#: 被测系统（VEAP）在结果表中的名字。它与 BASELINES 的键共同构成 method 列。
VEAP = "veap"

#: 固定评测时点，保证交期等日期判断可复现（与 `run_evaluation.py` 的重放口径一致）。
DEFAULT_AS_OF = "2026-10-01"


# --------------------------------------------------------------------- 订单装载

def _category(path: Path) -> str:
    """样本**业务场景档**：文件名去掉末尾 ``_数字`` 后的前缀。

    数据集三类各 80 份，**按下游业务处置动作划分，不是按抽取难度划分**
    （已核实 `business_decision` 字段）：

    | 类别 | `business_decision.action` | `scenario_tags` |
    |---|---|---|
    | `mfg_auto_approve` | `auto_approve` | 无（全部可唯一匹配且金额一致） |
    | `mfg_auto_correct` | `auto_correct` | 别名与格式归一化、单位与分隔符归一化 |
    | `mfg_manual_review` | `manual_review` | 价格超政策、行小计不符 |

    ⚠️ **不要把它当成「难度分档」**：`manual_review` 的订单之所以要人工复核，
    是因为**业务规则异常**（价格超政策等），而**不是**因为表格更难抽取。
    实测这三档对 `qwen3.7-plus` 的抽取难度**没有差别**（三档全部满分）。
    若在论文里写成「难度分档」会是一句站不住的表述。
    """
    stem = path.stem
    return stem.rsplit("_", 1)[0] if "_" in stem else stem


def select_order_paths(limit: int, strategy: str = "stratified") -> List[Path]:
    """挑选订单路径。

    **为什么默认分层而不是取前 N 份**：订单按文件名排序时 ``mfg_auto_approve``
    排在最前，取前 N 份等于**只取同一个业务场景**——样本单一，
    结论无法覆盖另外两类场景。分层策略按类别**轮转**取样本，
    使小规模抽样也覆盖全部业务场景；类内仍按文件名排序，
    保证**同一 limit 下样本集合完全确定**、可复现。

    ⚠️ **分层只保证「场景覆盖」，不保证「准确率维度有区分度」**：
    实测三档的抽取难度相同（全部满分），天花板效应依然存在。
    报告里的「按场景拆分」小节与天花板警告就是用来暴露这一点的。
    """
    if strategy == "head":
        return sorted(ORDERS_DIR.glob("*.xlsx"))[:limit]

    buckets: Dict[str, List[Path]] = {}
    for path in sorted(ORDERS_DIR.glob("*.xlsx")):
        buckets.setdefault(_category(path), []).append(path)

    selected: List[Path] = []
    cursors = {name: 0 for name in buckets}
    while len(selected) < limit:
        progressed = False
        for name in sorted(buckets):
            if len(selected) >= limit:
                break
            index = cursors[name]
            if index < len(buckets[name]):
                selected.append(buckets[name][index])
                cursors[name] += 1
                progressed = True
        if not progressed:  # 所有类别都取空
            break
    return selected


def load_cases(limit: int, strategy: str = "stratified") -> List[Dict[str, Any]]:
    """取 N 份订单，连同标注与「VEAP 抽取器实际看到的文本」。"""
    loader = DocumentLoader()
    cases: List[Dict[str, Any]] = []
    skipped = 0

    for order_path in select_order_paths(limit, strategy):
        annotation_path = ANNOTATIONS_DIR / f"{order_path.stem}.json"
        if not annotation_path.exists():
            skipped += 1
            continue

        document_ir, document_type = loader.load_ir(str(order_path))
        if document_type != "excel":
            skipped += 1
            continue
        locators = find_item_locators(document_ir, None)
        if not locators:
            skipped += 1
            continue

        region = {"kind": "sheet", "name": locators[0]["sheet"]}
        order_text = Extractor.region_source(document_ir, region)
        if not order_text.strip():
            skipped += 1
            continue

        cases.append({
            "document_id": order_path.stem,
            "order_path": order_path,
            "category": _category(order_path),
            "annotation": json.loads(annotation_path.read_text(encoding="utf-8")),
            "order_text": order_text,
            "region": region,
        })

    if skipped:
        print(f"[样本] 跳过 {skipped} 份订单（缺标注 / 非 excel / 无定位符）", file=sys.stderr)
    return cases


# --------------------------------------------------------------------- 各方法执行

def parsed_order_from_response(raw: Dict[str, Any]) -> Any:
    """从编排器响应中取出 `ParsedOrder`。

    **为什么要单独成函数**：编排器返回的 ``final_result`` 是 pydantic 对象
    （``FinalOrderResult``），**不是 dict**。写成 ``raw["final_result"].get(...)``
    会抛 ``AttributeError: 'FinalOrderResult' object has no attribute 'get'``——
    这个错误会把**所有** VEAP 结果记成失败，而准确率表仍然正常生成，
    表现为「VEAP 准确率 0」，极易被误读成「系统不行」。
    """
    from domain.models import ParsedOrder

    final_result = raw.get("final_result")
    if isinstance(final_result, dict):
        return ParsedOrder.model_validate(final_result.get("parsed_order"))
    if final_result is not None:
        return getattr(final_result, "parsed_order", None)
    return None


def run_veap(orchestrator: Any, case: Dict[str, Any]) -> Dict[str, Any]:
    """跑被测系统（完整编排器，含抽取 → 验证 → 匹配 → 风控 → 终裁）。

    ⚠️ **成本口径警告**：编排器返回的 ``usage`` 汇总自黑板上的 INFORM 消息，
    而 ``ReviewAssistant`` 发的 INFORM **不带 ``usage`` 字段**（见
    `application/agents/review_assistant.py:105`）——它的模型调用从不被计入。
    因此 **VEAP 的 token 数是下界**，成本优势是被**低估**的方向（保守）。
    论文必须如实声明这一点，不能把下界当实测值。
    """
    started = perf_counter()
    parsed, error = None, None
    usage: Dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    evidence_chain: List[Dict[str, Any]] = []

    try:
        raw = orchestrator.process_order_from_document(str(case["order_path"]))
        usage = dict(raw.get("usage") or usage)
        evidence_chain = list(raw.get("evidence_chain") or [])
        if not raw.get("success"):
            error = str(raw.get("message") or "未知失败")
        else:
            parsed = parsed_order_from_response(raw)
            if parsed is None:
                error = "编排器未返回 parsed_order"
    except Exception as exc:  # noqa: BLE001 - 失败样本必须记录，不能中断整轮
        error = f"{type(exc).__name__}: {exc}"

    return {
        "parsed": parsed,
        "usage": usage,
        # 编排器把「尝试过的模型调用次数」记在 usage 里，可直接用作成本口径。
        "calls": usage.get("attempted_calls"),
        "latency_ms": round((perf_counter() - started) * 1000, 2),
        "error": error,
        "evidence_chain": evidence_chain,
    }


def run_baseline(baseline: Any, case: Dict[str, Any]) -> Dict[str, Any]:
    result = baseline.run(case["order_text"])
    return {
        "parsed": result.parsed,
        "usage": dict(result.usage),
        "calls": result.calls,
        "latency_ms": result.latency_ms,
        "error": result.error,
        "evidence_chain": list(result.evidence_chain),
    }


# --------------------------------------------------------------------- 汇总

def aggregate(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """按方法聚合：字段准确率 + 成本 + 可审计性。"""
    methods = sorted({row["method"] for row in rows})
    summary: Dict[str, Any] = {}

    for method in methods:
        subset = [row for row in rows if row["method"] == method]
        order_counts: Dict[str, Dict[str, int]] = {}
        item_counts: Dict[str, Dict[str, int]] = {}
        for row in subset:
            merge_counts(order_counts, row["score"]["order_fields"])
            merge_counts(item_counts, row["score"]["item_fields"])

        order_acc = accuracy(order_counts)
        item_acc = accuracy(item_counts)
        combined_matched = order_acc["matched"] + item_acc["matched"]
        combined_total = order_acc["total"] + item_acc["total"]

        evidence_rows = [len(row["evidence_chain"]) for row in subset]
        summary[method] = {
            "orders": len(subset),
            "failures": sum(1 for row in subset if row["error"]),
            "per_category": _per_category(subset),
            "field_accuracy": (combined_matched / combined_total) if combined_total else 0.0,
            "field_matched": combined_matched,
            "field_total": combined_total,
            "order_level_accuracy": order_acc["accuracy"],
            "item_level_accuracy": item_acc["accuracy"],
            "per_field": item_acc["per_field"],
            "mean_total_tokens": _mean([row["usage"].get("total_tokens") or 0 for row in subset]),
            "mean_calls": _mean([row["calls"] for row in subset if row["calls"] is not None]),
            "mean_latency_ms": _mean([row["latency_ms"] for row in subset]),
            "mean_evidence_entries": _mean(evidence_rows),
            "orders_with_evidence": sum(1 for value in evidence_rows if value > 0),
            "auditable_rate": (sum(1 for value in evidence_rows if value > 0) / len(subset))
            if subset else 0.0,
        }
    return summary


def _per_category(subset: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """按**业务场景**拆分字段准确率。

    **为什么必须拆**：主表把三类样本混在一起，若整体接近满分，
    无法区分「方法都好」与「样本对该模型过易」——后者会让实验
    **看起来成立却毫无信息量**（G0 的天花板效应）。分场景后一眼可见：
    是否每一类场景下所有方法都满分。
    """
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for row in subset:
        buckets.setdefault(row.get("category") or "unknown", []).append(row)

    result: Dict[str, Dict[str, Any]] = {}
    for name, rows in sorted(buckets.items()):
        order_counts: Dict[str, Dict[str, int]] = {}
        item_counts: Dict[str, Dict[str, int]] = {}
        for row in rows:
            merge_counts(order_counts, row["score"]["order_fields"])
            merge_counts(item_counts, row["score"]["item_fields"])
        order_acc = accuracy(order_counts)
        item_acc = accuracy(item_counts)
        matched = order_acc["matched"] + item_acc["matched"]
        total = order_acc["total"] + item_acc["total"]
        result[name] = {
            "orders": len(rows),
            "field_accuracy": (matched / total) if total else 0.0,
            "field_matched": matched,
            "field_total": total,
            "failures": sum(1 for row in rows if row["error"]),
        }
    return result


def _mean(values: List[Any]) -> float:
    numbers = [float(value) for value in values if value is not None]
    return sum(numbers) / len(numbers) if numbers else 0.0


def verdict(summary: Dict[str, Any]) -> Dict[str, Any]:
    """按 `paper/08_SUBMISSION_PLAN.md` §10.5 的判据给出结论。"""
    veap = summary.get(VEAP)
    others = {name: value for name, value in summary.items() if name != VEAP}
    if veap is None or not others:
        return {"code": "INCOMPLETE", "reason": "缺少 VEAP 或任一基线结果"}

    strongest = max(others.items(), key=lambda item: item[1]["field_accuracy"])
    strongest_name, strongest_stats = strongest

    accuracy_gap = strongest_stats["field_accuracy"] - veap["field_accuracy"]
    cost_ratio = (strongest_stats["mean_total_tokens"] / veap["mean_total_tokens"]) \
        if veap["mean_total_tokens"] else 0.0

    # 容差 0.5 个百分点：字段级准确率在此量级上的差异不足以称为「更准」。
    accuracy_ok = accuracy_gap <= 0.005
    cost_ok = cost_ratio >= 1.5
    audit_ok = veap["auditable_rate"] > 0 and strongest_stats["auditable_rate"] == 0.0

    if accuracy_ok and cost_ok and audit_ok:
        code, reason = "SUPPORTED", (
            f"VEAP 与最强基线（{strongest_name}）准确率相当（差 {accuracy_gap:+.4f}），"
            f"token 成本低至 1/{cost_ratio:.1f}，且唯一可审计"
        )
    elif accuracy_ok and audit_ok:
        code, reason = "WEAK", (
            f"准确率相当且唯一可审计，但成本优势未达 1.5 倍"
            f"（{strongest_name} / VEAP = {cost_ratio:.2f}）→ 需回到 C2 可核查性叙事"
        )
    else:
        code, reason = "NOT_SUPPORTED", (
            f"准确率劣于 {strongest_name} {accuracy_gap:+.4f}，或成本优势不足"
            f"（比值 {cost_ratio:.2f}）→ 贡献不成立，需降级目标或改叙事"
        )
    return {
        "code": code,
        "reason": reason,
        "strongest_baseline": strongest_name,
        "accuracy_gap": accuracy_gap,
        "cost_ratio": cost_ratio,
        "accuracy_ok": accuracy_ok,
        "cost_ok": cost_ok,
        "audit_ok": audit_ok,
    }


# --------------------------------------------------------------------- 产物

def render_markdown(summary: Dict[str, Any], judgment: Dict[str, Any],
                    cases: List[Dict[str, Any]], model: str, as_of: str,
                    strategy: str = "stratified") -> str:
    methods = sorted(summary)
    header = "| 指标 | " + " | ".join(methods) + " |"
    divider = "|---" * (len(methods) + 1) + "|"

    def line(label: str, key: str, fmt: str = "{:.4f}") -> str:
        cells = [fmt.format(summary[name][key]) for name in methods]
        return f"| {label} | " + " | ".join(cells) + " |"

    categories = sorted({case.get("category") or "unknown" for case in cases})
    lines = [
        "# 基线对照实验：VEAP vs 零样本 vs MAD",
        "",
        f"- 订单数：{len(cases)}",
        f"- 抽样策略：`{strategy}`（分层＝按业务场景轮转）",
        f"- 业务场景：{categories}",
        f"- 模型：`{model}`",
        f"- 评测时点：{as_of}",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        "",
        "## 主表",
        "",
        header,
        divider,
        line("字段准确率（主指标）", "field_accuracy"),
        line("订单级字段准确率", "order_level_accuracy"),
        line("明细级字段准确率", "item_level_accuracy"),
        line("运行失败数", "failures", "{:.0f}"),
        line("平均 token / 单", "mean_total_tokens", "{:.0f}"),
        line("平均调用次数 / 单", "mean_calls", "{:.2f}"),
        line("平均延迟 ms / 单", "mean_latency_ms", "{:.0f}"),
        line("平均证据链条目 / 单", "mean_evidence_entries", "{:.2f}"),
        line("**可审计率**", "auditable_rate"),
        "",
        "## 判定",
        "",
        f"**{judgment['code']}** — {judgment['reason']}",
        "",
    ]
    if judgment["code"] == "SUPPORTED":
        lines += [
            "→ 论文的**成本 + 可核查性**主张成立，按 ICDAR 2027 计划推进。",
            "",
        ]
    else:
        lines += [
            "→ **不要投 ICDAR。** 按 `paper/08_SUBMISSION_PLAN.md` §10.6 改走"
            "「投出即止」的完整性策略，把资源转回考研。",
            "",
        ]

    # ---- 按业务场景拆分：判断本次实验是否真的「有区分度」
    if categories:
        lines += [
            "## 按业务场景拆分（判断实验是否有区分度）",
            "",
            "> 三个类别按**下游业务处置动作**划分（`auto_approve` / `auto_correct` /",
            "> `manual_review`），**不是按抽取难度划分**——`manual_review` 是因为业务规则异常",
            "> （价格超政策等）而需人工复核，其表格本身并不更难抽取。",
            "",
            "| 业务场景 | 订单数 | " + " | ".join(methods) + " |",
            "|---" * (len(methods) + 2) + "|",
        ]
        ceiling_hits: List[str] = []
        for category in categories:
            cells, values = [], []
            for name in methods:
                stats = summary[name]["per_category"].get(category)
                if not stats or not stats["field_total"]:
                    cells.append("—")
                    continue
                values.append(stats["field_accuracy"])
                cells.append(f"{stats['field_accuracy']:.4f} "
                             f"({stats['field_matched']}/{stats['field_total']})")
            count = summary[methods[0]]["per_category"].get(category, {}).get("orders", 0)
            lines.append(f"| {category} | {count} | " + " | ".join(cells) + " |")
            # 天花板：该档所有方法都 ≥ 0.99，差异被压扁，该档不提供区分度。
            if len(values) == len(methods) and all(value >= 0.99 for value in values):
                ceiling_hits.append(category)
        lines.append("")

        if ceiling_hits:
            lines += [
                f"⚠️ **天花板警告**：业务场景 {ceiling_hits} 上所有方法均 ≥ 0.99，",
                "该场景**不提供区分度**。若全部场景都如此，说明该数据集对被测模型过易，",
                "本实验只能支持「**成本 + 可审计性**」主张，",
                "**不能**支持任何准确率优势主张——**连「准确率相当」也只是「都没做错」，",
                "而非「难度下仍相当」**。写论文时必须如实说明，并补更难样本。",
                "",
            ]
        else:
            lines += [
                "✅ 至少一个业务场景存在方法间差异，本次实验对准确率维度**有区分度**。",
                "",
            ]

    lines += [
        "## 逐字段明细（明细级）",
        "",
        "| 字段 | " + " | ".join(methods) + " |",
        divider,
    ]
    fields = sorted({field for name in methods for field in summary[name]["per_field"]})
    for field in fields:
        cells = []
        for name in methods:
            stats = summary[name]["per_field"].get(field)
            cells.append(f"{stats['accuracy']:.4f} ({stats['matched']}/{stats['total']})"
                         if stats and stats["total"] else "—")
        lines.append(f"| {field} | " + " | ".join(cells) + " |")

    lines += [
        "",
        "## 成本口径（必读，论文必须如实声明）",
        "",
        "- **VEAP 的 token 数是下界**：编排器的 `usage` 汇总自黑板 INFORM 消息，而",
        "  `ReviewAssistant` 发的 INFORM **不带 `usage` 字段**，它的模型调用从未被计入。",
        "  即真实成本 ≥ 表中数值，**成本优势是被低估的方向（保守）**。",
        "- **MAD 的 token 数包含辩论轮次的全部 prompt**：每轮都把全部同伴输出塞进上下文，",
        "  因此单次调用长度也随 agent 数增长。",
        "- 两者的**抽取阶段提示词与模型完全一致**（单变量控制），成本差异只来自验证机制。",
        "",
        "> 复现实验前请核对 `run_manifest.json`：代码版本、提示词指纹、模型配置、"
        "样本指纹任一变化都会使本次结果不可比。",
        "",
        "> 判等口径复用 `evaluation.metrics.values_match`（数值容差 1e-3，文本规范化后比较），"
        "与主评测一致。明细行按**位置**对齐。",
        "",
    ]
    return "\n".join(lines)


def load_rows(rows_path: Path) -> List[Dict[str, Any]]:
    """从已落盘的 ``rows.jsonl`` 读回结果行。

    **为什么要这个**：整轮实验可能跑数十分钟（MAD 单份订单就要 9 次模型调用），
    中途被杀或被误停时，若汇总只能在全流程跑完后生成，**已消耗的模型调用全部作废**。
    ``rows.jsonl`` 是逐条 ``flush`` 的，因此它是唯一可靠的断点——
    有了它，任何一次部分完成的运行都能重新出报告。
    """
    rows: List[Dict[str, Any]] = []
    for line in rows_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def cases_from_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """从结果行反推「样本清单」，供分档拆分与表头使用（保持首次出现顺序）。"""
    seen: Dict[str, str] = {}
    for row in rows:
        seen.setdefault(row["document_id"], row.get("category") or "unknown")
    return [{"document_id": doc_id, "category": category}
            for doc_id, category in seen.items()]


def _fingerprint_cases(cases: List[Dict[str, Any]]) -> str:
    import hashlib

    payload = json.dumps(
        [{"document_id": case["document_id"], "region": case["region"]} for case in cases],
        sort_keys=True, ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_run_manifest(run_dir: Path, config: Config, cases: List[Dict[str, Any]],
                       methods: List[str], as_of: str, mad_config: Dict[str, int],
                       strategy: str = "stratified") -> None:
    from evaluation.run_evaluation import build_run_identity, identity_hash

    documents = [case["order_path"] for case in cases]
    try:
        identity = build_run_identity(
            config, documents=documents, annotation_dir=ANNOTATIONS_DIR,
            manifest_map={}, manifest_base_dir=None, manifest_csv=None,
        )
    except Exception as exc:  # noqa: BLE001 - 身份记录失败不应阻断实验，但必须留痕
        identity = {"identity_error": f"{type(exc).__name__}: {exc}"}

    identity["experiment"] = "baseline_comparison"
    identity["methods"] = methods
    identity["evaluation_as_of"] = as_of
    identity["mad_config"] = mad_config
    identity["sampling_strategy"] = strategy
    identity["case_count"] = len(cases)
    identity["case_categories"] = sorted({case.get("category") or "unknown" for case in cases})
    identity["case_fingerprint"] = _fingerprint_cases(cases)
    (run_dir / "run_manifest.json").write_text(
        json.dumps({"run_identity": identity, "identity_hash": identity_hash(identity)},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# --------------------------------------------------------------------- 主流程

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="基线对照实验：VEAP vs 零样本 vs MAD")
    parser.add_argument("--limit", type=int, default=20, help="订单数，默认 20")
    parser.add_argument("--methods", default=None,
                        help=f"逗号分隔的方法名，默认 {','.join((VEAP,) + DEFAULT_METHOD_ORDER)}")
    parser.add_argument("--strategy", default="stratified", choices=["stratified", "head"],
                        help="抽样策略：stratified（按业务场景轮转，默认）或 head（按文件名取前 N）")
    parser.add_argument("--dry-run", action="store_true", help="只列订单，不调用模型")
    parser.add_argument("--as-of", default=DEFAULT_AS_OF, help="固定评测时点")
    parser.add_argument("--mad-agents", type=int, default=3, help="MAD agent 数，默认 3")
    parser.add_argument("--mad-rounds", type=int, default=2, help="MAD 辩论轮数，默认 2")
    parser.add_argument("--output-dir", default=None, help="产物目录")
    parser.add_argument("--model", default=None, help="覆盖模型名")
    parser.add_argument("--from-rows", default=None,
                        help="不调模型，直接从已有 rows.jsonl 重算汇总（断点续算）")
    return parser.parse_args()


def rebuild_from_rows(rows_path: Path) -> int:
    """不调模型，从已落盘的结果行重算汇总与判定。"""
    if not rows_path.exists():
        print(f"[错误] 找不到 {rows_path}", file=sys.stderr)
        return 1
    rows = load_rows(rows_path)
    if not rows:
        print(f"[错误] {rows_path} 是空的", file=sys.stderr)
        return 1

    run_dir = rows_path.parent
    model, as_of, strategy = "unknown", DEFAULT_AS_OF, "unknown"
    manifest_path = run_dir / "run_manifest.json"
    if manifest_path.exists():
        identity = json.loads(manifest_path.read_text(encoding="utf-8")).get(
            "run_identity", {})
        # 模型名嵌在 `model_config` 里（不是顶层 `model`）——写错会静默显示 "unknown"。
        model = (identity.get("model_config") or {}).get("model") or "unknown"
        as_of = identity.get("evaluation_as_of") or as_of
        strategy = identity.get("sampling_strategy") or strategy

    cases = cases_from_rows(rows)
    summary = aggregate(rows)
    judgment = verdict(summary)

    # 结果行数与「方法 × 样本」的完整组合数不一致 → 本次是**部分完成**，
    # 必须显式声明，否则残缺的结果会被误当成完整实验读。
    expected = len(cases) * len({row["method"] for row in rows})
    (run_dir / "summary.json").write_text(
        json.dumps({"summary": summary, "judgment": judgment,
                    "partial": len(rows) < expected,
                    "rows": len(rows), "expected_rows": expected},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown = render_markdown(summary, judgment, cases, model, as_of, strategy=strategy)
    if len(rows) < expected:
        markdown = (f"> ⚠️ **本次为部分结果**：已完成 {len(rows)} / {expected} 行。"
                    f"判定仅基于已完成部分，**不可当作最终结论**。\n\n") + markdown
    (run_dir / "summary.md").write_text(markdown, encoding="utf-8")

    print(f"产物目录：{run_dir}")
    print(f"行数：{len(rows)} / {expected}")
    print(f"判定：{judgment['code']} — {judgment['reason']}")
    return 0


def main() -> int:
    args = parse_args()
    if args.from_rows:
        return rebuild_from_rows(Path(args.from_rows))

    methods = (
        [name.strip() for name in args.methods.split(",") if name.strip()]
        if args.methods else [VEAP, *DEFAULT_METHOD_ORDER]
    )
    unknown = [name for name in methods if name != VEAP and name not in BASELINES]
    if unknown:
        print(f"[错误] 未知方法 {unknown}；可选：{VEAP}、{list(BASELINES)}", file=sys.stderr)
        return 1

    cases = load_cases(args.limit, args.strategy)
    if not cases:
        print("[错误] 没有装载到任何订单，检查数据集路径。", file=sys.stderr)
        return 1

    category_counts: Dict[str, int] = {}
    for case in cases:
        category_counts[case["category"]] = category_counts.get(case["category"], 0) + 1
    print(f"[样本] 共 {len(cases)} 份订单（策略 {args.strategy}）：{category_counts}",
          file=sys.stderr)
    if args.dry_run:
        print(f"[dry-run] 方法：{methods}；未调用模型。")
        return 0

    config = Config()
    if args.model:
        config.model.model = args.model
    if not config.model.api_key:
        print("[错误] 未配置模型 API key（环境变量 QWEN_API_KEY）。"
              "请直连服务商官方端点，不要使用中转站。", file=sys.stderr)
        return 1
    config.risk.evaluation_as_of = args.as_of

    run_dir = Path(args.output_dir) if args.output_dir else (
        RESULTS_ROOT / f"baseline_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    mad_config = {"agents": args.mad_agents, "rounds": args.mad_rounds}
    write_run_manifest(run_dir, config, cases, methods, args.as_of, mad_config,
                       strategy=args.strategy)
    print(f"[产物] {run_dir}", file=sys.stderr)
    print(f"[模型] {config.model.model}；方法 {methods}", file=sys.stderr)

    # 增量落盘：MAD 单份订单约 9 次调用，整轮可能数小时；
    # 中途失败不应丢掉已完成的结果。
    rows_path = run_dir / "rows.jsonl"
    rows: List[Dict[str, Any]] = []
    orchestrator = None
    baselines: Dict[str, Any] = {}

    with rows_path.open("w", encoding="utf-8") as handle:
        for index, case in enumerate(cases, start=1):
            for method in methods:
                print(f"[{index}/{len(cases)}] {case['document_id']} · {method} …",
                      file=sys.stderr, end=" ")
                if method == VEAP:
                    if orchestrator is None:
                        from evaluation.run_evaluation import create_evaluation_orchestrator

                        orchestrator = create_evaluation_orchestrator(
                            evaluation_as_of=args.as_of)
                    outcome = run_veap(orchestrator, case)
                else:
                    if method not in baselines:
                        baselines[method] = BASELINES[method](config, **(
                            mad_config if method == "mad" else {}))
                    outcome = run_baseline(baselines[method], case)

                score = score_order(outcome["parsed"], case["annotation"])
                row = {
                    "document_id": case["document_id"],
                    "category": case["category"],
                    "method": method,
                    "error": outcome["error"],
                    "usage": outcome["usage"],
                    "calls": outcome["calls"],
                    "latency_ms": outcome["latency_ms"],
                    "evidence_chain": outcome["evidence_chain"],
                    "score": score,
                }
                rows.append(row)
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                handle.flush()
                status = "error" if outcome["error"] else "ok"
                print(f"{status}  tokens={outcome['usage'].get('total_tokens')}",
                      file=sys.stderr)

    summary = aggregate(rows)
    judgment = verdict(summary)
    (run_dir / "summary.json").write_text(
        json.dumps({"summary": summary, "judgment": judgment}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "summary.md").write_text(
        render_markdown(summary, judgment, cases, config.model.model, args.as_of,
                        strategy=args.strategy),
        encoding="utf-8",
    )

    print()
    print(f"产物目录：{run_dir}")
    print(f"判定：{judgment['code']} — {judgment['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
