"""可核查性审计的离线守卫（D20 方案 α+γ 的实证基础）。

这些测试不调用任何模型、不依赖被 git 忽略的 `datasets/generated_complex`：
它们用临时 xlsx 与临时产物目录走**真实代码路径**，确认三件事：

1. ``ρ(ℓ, D)`` 真的能按定位符取回原单元格的值（这是「可核查」的形式化定义，
   也是待决事项 D16 要求补的校验）；
2. 「区域规模」这个分母算得对——它是自然语言体制下搜索空间 ``|D|`` 的依据；
3. 审计能把「只有最终值」与「带证据链」两种产物区分开——否则 C2b 的 0% 结论
   可能只是扫描逻辑写错了。
"""
import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from infrastructure.document_processing import DocumentLoader
from scripts import verifiability_audit as audit

HEADER = ["序号", "物料名称", "规格型号", "数量", "单位", "含税单价"]
ROWS = [
    [1, "深沟球轴承", "6200-OPEN", 100, "套", 28.7],
    [2, "不锈钢球阀", "Q11F-25P DN32", 500, "个", 124.5],
    [3, "硬质合金立铣刀", "D5×100 4刃", 50, "支", 83.94],
]


def _write_order(path: Path, rows=None) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "采购订单"
    sheet.append(HEADER)
    for row in rows or ROWS:
        sheet.append(row)
    workbook.save(str(path))


class ResolveLocatorTests(unittest.TestCase):
    """``ρ(ℓ, D)`` 必须是**一次直接寻址**，且取回的就是原值。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self._tmp.name)
        self.loader = DocumentLoader()
        self.path = self.directory / "order.xlsx"
        _write_order(self.path)
        self.ir, _ = self.loader.load_ir(str(self.path))

    def tearDown(self):
        self._tmp.cleanup()

    def test_locator_resolves_to_the_source_value(self):
        locator = {"sheet": "采购订单", "row": 2, "column": 4}

        self.assertEqual(audit.resolve_locator(self.ir, locator), 100)

    def test_locator_resolves_every_row_independently(self):
        for row_index, expected in ((2, 100), (3, 500), (4, 50)):
            self.assertEqual(
                audit.resolve_locator(self.ir, {"sheet": "采购订单",
                                                "row": row_index, "column": 4}),
                expected,
            )

    def test_unknown_sheet_or_out_of_range_resolves_to_none(self):
        self.assertIsNone(audit.resolve_locator(
            self.ir, {"sheet": "不存在的表", "row": 2, "column": 4}))
        self.assertIsNone(audit.resolve_locator(
            self.ir, {"sheet": "采购订单", "row": 999, "column": 4}))

    def test_region_cells_counts_the_whole_region(self):
        self.assertEqual(audit.region_cells(self.ir, "采购订单"), 4 * 6)
        self.assertEqual(audit.region_cells(self.ir, "不存在的表"), 0)


class AuditOrderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self._tmp.name)
        self.loader = DocumentLoader()

    def tearDown(self):
        self._tmp.cleanup()

    def test_every_checked_claim_resolves_on_a_clean_order(self):
        path = self.directory / "order.xlsx"
        _write_order(path)

        record = audit.audit_order(path, self.loader)

        self.assertIsNotNone(record)
        self.assertGreater(record["claims_checked"], 0)
        self.assertEqual(record["evidence_resolved"], record["claims_checked"])
        self.assertEqual(record["evidence_mismatched"], 0)

    def test_region_is_far_larger_than_one_cell(self):
        path = self.directory / "order.xlsx"
        _write_order(path)

        record = audit.audit_order(path, self.loader)

        self.assertGreater(record["region_cells"], 1,
                           "若区域只有 1 格，C2a 的成本比就没有意义")


class EvidenceChainDetectionTests(unittest.TestCase):
    """审计必须能把「只有最终值」与「带证据链」区分开。"""

    def test_final_values_alone_are_not_an_evidence_chain(self):
        final = {
            "status": "needs_confirmation",
            "parsed_order": {"order_number": "PO-1"},
            "risk_result": {"issues": [
                {"item_index": 23, "issue_type": "price_abnormal",
                 "description": "单价 23.36 相对于参考价格 4.16 异常",
                 "severity": "medium"},
            ]},
        }

        self.assertFalse(audit._has_evidence_chain(final),
                         "自然语言描述不是机器可核查的证据")

    def test_a_locator_on_any_issue_counts_as_an_evidence_chain(self):
        final = {"risk_result": {"issues": [
            {"item_index": 1, "issue_type": "price_abnormal",
             "locator": {"sheet": "采购订单", "row": 17, "column": 5}},
        ]}}

        self.assertTrue(audit._has_evidence_chain(final))

    def test_messages_or_evidence_blocks_also_count(self):
        self.assertTrue(audit._has_evidence_chain({"evidence": [{"kind": "cell"}]}))
        self.assertTrue(audit._has_evidence_chain({"messages": [{"performative": "CHALLENGE"}]}))


class AuditArtifactsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write_run(self, name, records):
        run = self.root / name
        run.mkdir(parents=True, exist_ok=True)
        (run / "predictions.jsonl").write_text(
            "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
            encoding="utf-8",
        )

    def test_counts_records_issues_and_locators(self):
        self._write_run("run_a", [
            {"prediction": {"final_result": {"risk_result": {"issues": [
                {"item_index": 1, "description": "自然语言描述"}]}}}},
            {"prediction": {"final_result": {"risk_result": {"issues": [
                {"item_index": 2, "locator": {"row": 3, "column": 4}}]}}}},
        ])
        self._write_run("run_b", [
            {"prediction": {"final_result": {"status": "auto_approved"}}},
        ])

        result = audit.audit_artifacts(self.root)

        self.assertEqual(result["records"], 3)
        self.assertEqual(result["records_with_evidence_chain"], 1)
        self.assertEqual(result["issues"], 2)
        self.assertEqual(result["issues_with_locator"], 1)

    def test_empty_root_yields_zeros(self):
        result = audit.audit_artifacts(self.root)

        self.assertEqual(result["records"], 0)
        self.assertEqual(result["records_with_evidence_chain"], 0)


class ReportTests(unittest.TestCase):
    def test_report_rates_are_ratios_not_percentages(self):
        orders = [{"region_cells": 300, "claims_checked": 10, "evidence_resolved": 10}]
        artifacts = {"runs": [], "records": 100, "records_with_evidence_chain": 0,
                     "issues": 50, "issues_with_locator": 0}

        report = audit.build_report(orders, artifacts)

        self.assertEqual(report["c2a_verification_cost"]["cost_ratio"], 300)
        self.assertEqual(report["c2b_audit_gap"]["audit_reproducibility"], 0.0)
        self.assertEqual(report["c2b_audit_gap"]["issue_verifiability"], 0.0)

    def test_markdown_renders_both_sections(self):
        orders = [{"region_cells": 300, "claims_checked": 10, "evidence_resolved": 10}]
        artifacts = {"runs": [{"run": "r", "records": 1, "records_with_evidence_chain": 0,
                               "issues": 0, "issues_with_locator": 0}],
                     "records": 1, "records_with_evidence_chain": 0,
                     "issues": 0, "issues_with_locator": 0}

        markdown = audit.render_markdown(audit.build_report(orders, artifacts))

        self.assertIn("C2a 核查成本", markdown)
        self.assertIn("C2b 审计可复现性缺口", markdown)


if __name__ == "__main__":
    unittest.main()
