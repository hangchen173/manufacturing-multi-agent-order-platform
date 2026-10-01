"""可核查性审计（D20 方案 α+γ 的实证部分）。

**为什么有这个脚本**：原 C1 主张「locator 媒介能提升幻觉修正率」已被 G0 门禁证伪
（见 `paper/06_NOVELTY_EXPERIMENT.md` §12：50 次调用、0 个正向 discordant pair，
全部饱和）。根因是**任务本身太容易**——基线抽取准确率 0.998+，没有真实幻觉可修。

因此把因变量从「修正率」换成两个**不受基座模型能力影响**的确定性指标：

- **C2a 核查成本**：验证一条主张需要比对的单元格数。
  locator 体制 = ``ρ(ℓ, D)`` 一次直接寻址 → **1 格**；
  自然语言体制的消息**不携带任何结构信息**，要变成可执行核对必须先构造解析规则，
  在不假设文档结构的前提下搜索空间 = 区域全部单元格 = ``|D|`` 格。
- **C2b 审计可复现性**：仅凭**已落盘的产物**、不调用任何模型，能否复现一条历史驳回。

**零 LLM 调用**：全部是对既有产物与文档 IR 的确定性度量，成本 ¥0。

用法：

```
python scripts/verifiability_audit.py                    # 全部 240 个测试订单
python scripts/verifiability_audit.py --limit 20         # 小规模
python scripts/verifiability_audit.py --output-dir out/  # 指定产物目录
```
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from application.agents.grounding_verifier import GroundingVerifier  # noqa: E402
from application.agents.source_map import find_item_locators  # noqa: E402
from infrastructure.document_processing import DocumentLoader  # noqa: E402

ORDERS_DIR = PROJECT_ROOT / "datasets/generated_complex/orders/test"
RESULTS_ROOT = PROJECT_ROOT / "evaluation/results"

#: 参与度量的字段。与 `novelty_experiment.FIELD_ROTATION` 一致，便于两处结果互相对照。
AUDITED_FIELDS = ("quantity", "unit_price", "material_name", "specification")


# --------------------------------------------------------------------- C2a 核查成本

def region_cells(document_ir: Dict[str, Any], sheet_name: str) -> int:
    """该区域内**全部单元格**的个数——自然语言体制下的搜索空间 ``|D|``。"""
    for sheet in document_ir.get("sheets", []):
        if sheet.get("name") == sheet_name:
            return sum(len(row) for row in sheet.get("rows", []))
    return 0


def resolve_locator(document_ir: Dict[str, Any], locator: Dict[str, Any]) -> Any:
    """``ρ(ℓ, D)``：按定位符直接寻址取回源单元格的值。**恒定一次寻址**。"""
    for sheet in document_ir.get("sheets", []):
        if sheet.get("name") != locator.get("sheet"):
            continue
        rows = sheet.get("rows", [])
        row_index = locator.get("row")
        column_index = locator.get("column")
        if not row_index or not column_index:
            return None
        if row_index > len(rows) or column_index > len(rows[row_index - 1]):
            return None
        return rows[row_index - 1][column_index - 1]
    return None


def audit_order(path: Path, loader: DocumentLoader) -> Optional[Dict[str, Any]]:
    """度量单个订单：区域规模、主张数、以及定位符能否真的解析回原值。"""
    document_ir, document_type = loader.load_ir(str(path))
    if document_type != "excel":
        return None

    locators = find_item_locators(document_ir, None)
    if not locators:
        return None

    sheet_name = locators[0]["sheet"]
    cells = region_cells(document_ir, sheet_name)
    if not cells:
        return None

    resolved = checked = mismatched = 0
    for locator in locators:
        for field in AUDITED_FIELDS:
            column = locator["columns"].get(field)
            value = locator["values"].get(field)
            if column is None or value in (None, ""):
                continue
            checked += 1
            got = resolve_locator(
                document_ir,
                {"sheet": sheet_name, "row": locator["row"], "column": column},
            )
            if GroundingVerifier._cell_matches(field, value, got):
                resolved += 1
            else:
                mismatched += 1

    return {
        "order_id": path.stem,
        "sheet": sheet_name,
        "region_cells": cells,
        "item_count": len(locators),
        "claims_checked": checked,
        "evidence_resolved": resolved,
        "evidence_mismatched": mismatched,
    }


# --------------------------------------------------------------------- C2b 审计缺口

def audit_artifacts(results_root: Path) -> Dict[str, Any]:
    """扫描既有运行产物，看**证据链**有没有被落盘。

    一条驳回要能被第三方复现，产物里必须存在机器可核查的证据（locator + 原文值）。
    本函数统计：有多少记录带了这种证据，多少条问题描述只是自然语言。
    """
    records = 0
    with_evidence_chain = 0
    issues_total = 0
    issues_with_locator = 0
    runs = []

    for predictions in sorted(results_root.glob("*/predictions.jsonl")):
        run_records = run_with_chain = run_issues = run_issues_with_locator = 0
        for line in predictions.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            run_records += 1
            final = (row.get("prediction") or {}).get("final_result") or {}
            if _has_evidence_chain(final):
                run_with_chain += 1
            for issue in (final.get("risk_result") or {}).get("issues") or []:
                run_issues += 1
                if issue.get("locator"):
                    run_issues_with_locator += 1
        records += run_records
        with_evidence_chain += run_with_chain
        issues_total += run_issues
        issues_with_locator += run_issues_with_locator
        runs.append({
            "run": predictions.parent.name,
            "records": run_records,
            "records_with_evidence_chain": run_with_chain,
            "issues": run_issues,
            "issues_with_locator": run_issues_with_locator,
        })

    return {
        "runs": runs,
        "records": records,
        "records_with_evidence_chain": with_evidence_chain,
        "issues": issues_total,
        "issues_with_locator": issues_with_locator,
    }


def _has_evidence_chain(final_result: Dict[str, Any]) -> bool:
    """产物里是否留下了可机器核查的证据（而非只有最终值）。"""
    if final_result.get("evidence") or final_result.get("messages"):
        return True
    for issue in (final_result.get("risk_result") or {}).get("issues") or []:
        if issue.get("locator"):
            return True
    return False


# --------------------------------------------------------------------- 报告

def build_report(orders: List[Dict[str, Any]], artifacts: Dict[str, Any]) -> Dict[str, Any]:
    cells = [order["region_cells"] for order in orders]
    checked = sum(order["claims_checked"] for order in orders)
    resolved = sum(order["evidence_resolved"] for order in orders)

    return {
        "c2a_verification_cost": {
            "orders": len(orders),
            "region_cells_mean": round(statistics.fmean(cells), 1) if cells else 0.0,
            "region_cells_median": statistics.median(cells) if cells else 0,
            "region_cells_min": min(cells) if cells else 0,
            "region_cells_max": max(cells) if cells else 0,
            "cells_per_claim_locator": 1,
            "cells_per_claim_natural_language": round(statistics.fmean(cells), 1) if cells else 0.0,
            "cost_ratio": round(statistics.fmean(cells), 1) if cells else 0.0,
            "claims_checked": checked,
            "evidence_resolved": resolved,
            "evidence_resolution_rate": round(resolved / checked, 4) if checked else 0.0,
        },
        "c2b_audit_gap": {
            "records": artifacts["records"],
            "records_with_evidence_chain": artifacts["records_with_evidence_chain"],
            "audit_reproducibility": (
                round(artifacts["records_with_evidence_chain"] / artifacts["records"], 4)
                if artifacts["records"] else 0.0
            ),
            "issues": artifacts["issues"],
            "issues_with_locator": artifacts["issues_with_locator"],
            "issue_verifiability": (
                round(artifacts["issues_with_locator"] / artifacts["issues"], 4)
                if artifacts["issues"] else 0.0
            ),
        },
        "runs": artifacts["runs"],
    }


def render_markdown(report: Dict[str, Any]) -> str:
    a = report["c2a_verification_cost"]
    b = report["c2b_audit_gap"]
    lines = [
        "# 可核查性审计报告",
        "",
        "## C2a 核查成本",
        "",
        f"- 订单数：**{a['orders']}**",
        f"- 区域单元格数：均值 **{a['region_cells_mean']}**、中位数 {a['region_cells_median']}、"
        f"范围 [{a['region_cells_min']}, {a['region_cells_max']}]",
        f"- 每条主张的单元格比对：locator **{a['cells_per_claim_locator']}** 格 "
        f"vs 自然语言 **{a['cells_per_claim_natural_language']}** 格",
        f"- **成本比：{a['cost_ratio']} : 1**",
        f"- 定位符解析成功率：{a['evidence_resolved']}/{a['claims_checked']} "
        f"= **{a['evidence_resolution_rate']}**",
        "",
        "## C2b 审计可复现性缺口",
        "",
        f"- 历史运行记录：**{b['records']}** 条",
        f"- 带机器可核查证据链的：**{b['records_with_evidence_chain']}** 条",
        f"- **审计可复现性：{b['audit_reproducibility']}**",
        f"- 问题描述：**{b['issues']}** 条，其中带定位符的 **{b['issues_with_locator']}** 条",
        f"- **问题可核查率：{b['issue_verifiability']}**",
        "",
        "## 各运行明细",
        "",
        "| 运行 | 记录 | 带证据链 | 问题 | 带定位符 |",
        "|---|---|---|---|---|",
    ]
    for run in report["runs"]:
        lines.append(
            f"| {run['run']} | {run['records']} | {run['records_with_evidence_chain']} "
            f"| {run['issues']} | {run['issues_with_locator']} |"
        )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="可核查性审计（C2a + C2b）")
    parser.add_argument("--limit", type=int, default=None, help="只审计前 N 个订单")
    parser.add_argument("--output-dir", default=None, help="产物目录")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    loader = DocumentLoader()

    paths = sorted(ORDERS_DIR.glob("*.xlsx"))
    if args.limit is not None:
        paths = paths[: args.limit]
    print(f"[订单] 审计 {len(paths)} 个订单的区域规模与定位符可解析性…", file=sys.stderr)

    orders: List[Dict[str, Any]] = []
    for path in paths:
        record = audit_order(path, loader)
        if record is not None:
            orders.append(record)

    print(f"[产物] 扫描 {RESULTS_ROOT} 下的历史运行…", file=sys.stderr)
    artifacts = audit_artifacts(RESULTS_ROOT)

    report = build_report(orders, artifacts)

    if args.output_dir:
        out = Path(args.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "report.md").write_text(render_markdown(report), encoding="utf-8")
        print(f"\n产物目录：{out}")

    print()
    print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
