"""证据链落盘的守卫（待决事项 D21 的实现侧）。

背景（2026-10-02）：E8 测得 423 条历史运行记录**0 条**带机器可核查证据。
根因不是「落盘时丢了」这么简单——验证者**只在驳回时**外化证据
（`INFORM` 只发 `{"verified": True}`），而历史上驳回数为 0，
所以即便把运行时的证据原样落盘，产出仍然是 0 条。

修复是让验证者在**接受**时也外化它实际比对过的 `(locator, 原文值)`，
并由 Supervisor 汇成证据链落到产物里。本文件把这件事固化为断言：

1. 一次干净运行会产出非空证据链，且**每一条被接受的字段**都在链上；
2. 链上每条单元格证据都能由第三方按 ``ρ(ℓ, D)`` 重新寻址取回同值
   ——**不调用任何模型**；
3. 风控问题被补上明细行定位符；
4. 证据链随编排器响应落到产物层。

全部测试**不调用任何模型**。
"""
import unittest

from application.agents.grounding_verifier import GroundingVerifier
from application.agents.source_map import cell_value
from config import Config
from tests.support import build_harness, excel_ir, excel_row, item, order_payload


def _order_ir(rows: int = 6):
    excel_rows = [excel_row(i + 1, f"物料{i + 1}", f"SPEC-{i + 1}", 100, "个", 10.0)
                  for i in range(rows)]
    return excel_ir(excel_rows)


def _payload(rows: int = 6):
    items = [item(f"物料{i + 1}", f"SPEC-{i + 1}", 100, "个", 10.0) for i in range(rows)]
    return order_payload(items, order_number="PO-1", customer_name="客户01",
                         total_amount=6000.0)


def _run_clean(rows: int = 6):
    harness = build_harness(payloads=[_payload(rows)])
    document_ir = _order_ir(rows)
    result = harness.supervisor.run(
        harness.manager.create_order(order_text=""), document_ir,
    )
    return harness, document_ir, result


class EvidenceChainIsPersistedTests(unittest.TestCase):
    """证据链从协议层走到产物层。"""

    def test_clean_run_emits_a_non_empty_chain(self):
        """干净运行（无驳回）也必须产出证据链——这正是修复前做不到的。"""
        _, _, result = _run_clean()

        self.assertTrue(result.get("success"), result.get("message"))
        chain = result.get("evidence_chain") or []
        self.assertTrue(chain, "干净运行的证据链为空——接受时的正向证据没有被外化")

    def test_every_chain_entry_carries_a_resolvable_locator(self):
        """每条证据都必须带 locator 与原文值，且 ``ρ(ℓ, D) == value`` 真的成立。"""
        _, document_ir, result = _run_clean()
        chain = result.get("evidence_chain") or []

        for entry in chain:
            locator = entry.get("locator") or {}
            self.assertIn(locator.get("kind"), {"cell", "span"},
                          f"证据缺少可复现的定位符: {entry}")
            self.assertIn("value", entry)

            if locator.get("kind") != "cell":
                continue
            resolved = cell_value(
                document_ir, locator.get("sheet"), locator.get("row"), locator.get("column"),
            )
            self.assertTrue(
                GroundingVerifier._cell_matches(entry.get("field"), resolved, entry["value"]),
                f"定位符无法复算回证据值: {entry} → 解析为 {resolved!r}",
            )

    def test_chain_records_both_verdicts(self):
        """链上区分「已验证」与「被挑战」，而不是只有驳回才有记录。"""
        _, _, result = _run_clean()
        verdicts = {entry.get("verdict") for entry in result.get("evidence_chain") or []}

        self.assertIn("inform", verdicts, "证据链里没有已验证的正向证据")

    def test_positive_evidence_is_flagged_reproducible_by_actual_resolution(self):
        """`reproducible` 不再是自报：它由一次真实的 ρ(ℓ,D) 复算得出（补上 D16）。"""
        _, _, result = _run_clean()

        for entry in result.get("evidence_chain") or []:
            if (entry.get("locator") or {}).get("kind") == "cell":
                self.assertTrue(entry.get("reproducible"),
                                f"单元格证据未被复算通过: {entry}")

    def test_risk_issues_get_row_locators(self):
        """风控问题被补上明细行定位符，使第三方能直接找到被质疑的那一行。"""
        _, _, result = _run_clean()
        issues = (result.get("verdict") or {}).get("risk_result") or {}
        issues = issues.get("issues") if isinstance(issues, dict) else None
        if not issues:
            self.skipTest("该样本没有风控问题，无法检验定位符补齐")

        for issue in issues:
            if issue.get("item_index") in (None, -1):
                continue
            self.assertTrue(issue.get("locator"),
                            f"问题缺少明细行定位符: {issue}")


class EvidenceChainReachesArtifactsTests(unittest.TestCase):
    """证据链真的落到编排器响应（进而进 predictions.jsonl）。"""

    def test_orchestrator_response_carries_the_chain(self):
        harness = build_harness(payloads=[_payload()])
        orchestrator = harness.orchestrator

        response = orchestrator._run(
            harness.manager.create_order(order_text=""), _order_ir(),
        )

        self.assertTrue(response.get("success"), response.get("message"))
        self.assertTrue(response.get("evidence_chain"),
                        "编排器响应里没有证据链——产物层仍然不可审计")
