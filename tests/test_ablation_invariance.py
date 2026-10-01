"""消融实验的「可测性」守卫。

背景（2026-10-02）：原计划的 E4 消融有三项，但其中两项在**当前实现上是恒等变换**——
无论怎么跑都不会产生差异。如果不先证明这一点，就会花掉两周实验预算去得到一个
「两臂完全相同」的空结果，然后误以为「该机制无效」。

本文件把两项「空洞消融」的证明固化为断言：

1. **去上下文隔离**：验证者是确定性比对器，从不读生产者置信度。
   把 `confidence` 放回切片或移出切片，判定结果逐字节相同。
   → 隔离是**设计不变量**（由断言守卫），不是**可消融的机制**。
2. **去预算熔断**：预算从未被触发（240 + 100 样本，0 次升级）。
   实测每单 3 次模型调用，预算上限 12。去掉熔断不会有任何行为差异。
   → 熔断是**安全网**，不是**性能机制**。

两个测试都**不调用任何模型**。
"""
import json
import unittest

from application.agents.grounding_verifier import GroundingVerifier
from application.protocol.budget import Budget
from config import Config
from tests.support import build_harness, excel_ir, excel_row, item, order_payload

#: 验证者模块源码。静态检查用。
VERIFIER_SOURCE = (
    __import__("pathlib").Path(__file__).resolve().parents[1]
    / "application/agents/grounding_verifier.py"
)


def _locator() -> dict:
    """一条最小可用的单元格定位：第 2 行、数量在第 4 列、原文值为 100。"""
    return {"sheet": "采购订单", "row": 2,
            "columns": {"quantity": 4}, "values": {"quantity": 100}}


def _order_ir(rows: int = 6):
    excel_rows = [excel_row(i + 1, f"物料{i + 1}", f"SPEC-{i + 1}", 100, "个", 10.0)
                  for i in range(rows)]
    return excel_ir(excel_rows)


def _payload(name_for_first: str, rows: int = 6):
    items = [item(name_for_first if i == 0 else f"物料{i + 1}",
                  f"SPEC-{i + 1}", 100, "个", 10.0) for i in range(rows)]
    return order_payload(items, order_number="PO-1", customer_name="客户01",
                         total_amount=6000.0)


class IsolationAblationIsIdentityTests(unittest.TestCase):
    """消融「去上下文隔离」在当前实现上不可能产生差异。"""

    def setUp(self):
        self.verifier = GroundingVerifier(config=Config())

    def test_challenge_decision_is_invariant_to_producer_confidence(self):
        """置信度从 0.0 拉到 1.0，错误值一律被挑战、正确值一律被放行。"""
        locator = _locator()

        for confidence in (0.0, 0.25, 0.5, 0.75, 0.99, 1.0):
            wrong = {"quantity": 1000, "confidence_score": confidence}
            right = {"quantity": 100, "confidence_score": confidence}

            self.assertEqual(
                len(self.verifier._verify_against_cells(0, wrong, locator)[0]), 1,
                f"置信度 {confidence} 时错误值未被挑战——隔离消融将不再是恒等变换",
            )
            self.assertEqual(
                len(self.verifier._verify_against_cells(0, right, locator)[0]), 0,
                f"置信度 {confidence} 时正确值被误挑战",
            )
            # 正确值同样必须留下可复现的正向证据，否则「通过」不可被第三方复核
            self.assertEqual(
                len(self.verifier._verify_against_cells(0, right, locator)[1]), 1,
                f"置信度 {confidence} 时正确值未外化证据链",
            )

    def test_verifier_never_references_confidence_or_rationale(self):
        """静态证明：验证者模块中根本不存在读取生产者内部状态的代码路径。"""
        source = VERIFIER_SOURCE.read_text(encoding="utf-8")

        self.assertNotIn("confidence", source,
                         "验证者开始引用 confidence —— 隔离不再是结构性不变量，"
                         "此时「去隔离」才成为一项可消融的机制")
        self.assertNotIn("rationale", source)

    def test_verifier_output_is_a_pure_function_of_document_and_value(self):
        """同一 (文档, 主张值, 定位符) 无论何时调用都给出同一结果。"""
        locator = _locator()
        value = {"quantity": 1000, "confidence_score": 0.99}

        first, first_checked = self.verifier._verify_against_cells(0, value, locator)
        second, second_checked = self.verifier._verify_against_cells(0, value, locator)

        self.assertEqual(
            [(field, reason) for field, reason, _ in first],
            [(field, reason) for field, reason, _ in second],
        )
        self.assertEqual(first_checked, second_checked)


class BudgetBreakerIsNeverTriggeredTests(unittest.TestCase):
    """消融「去预算熔断」在当前数据上不可能产生差异。"""

    def test_observed_call_count_is_far_below_the_budget(self):
        """实测每单模型调用数（含重抽的最坏路径）远低于 max_llm_calls。"""
        budget = Budget(order_id="probe")

        # 干净路径
        clean = build_harness(payloads=[_payload(f"物料{i + 1}") for i in range(6)])
        clean.supervisor.run(clean.manager.create_order(order_text=""), _order_ir())
        clean_calls = len(clean.prompts) + clean.review_llm.calls

        # 最坏路径：首轮物料名无法定位 → 触发挑战 → 带反证重抽
        retry = build_harness(payloads=[_payload("不存在的物料")]
                              + [_payload(f"物料{i + 1}") for i in range(6)])
        retry.supervisor.run(retry.manager.create_order(order_text=""), _order_ir())
        retry_calls = len(retry.prompts) + retry.review_llm.calls

        self.assertLessEqual(retry_calls, 4,
                             "重抽路径的调用数超出预期，预算可能开始变得紧约束")
        self.assertLess(max(clean_calls, retry_calls), budget.max_llm_calls,
                        "调用数已接近 max_llm_calls —— 熔断消融可能不再是恒等变换")

    def test_no_historical_run_ever_exhausted_the_budget(self):
        """历史运行的实证：240 + 100 个样本，0 次预算升级。"""
        results = __import__("pathlib").Path(__file__).resolve().parents[1] / "evaluation/results"
        checked = 0

        for run in sorted(results.glob("*/predictions.jsonl")):
            for line in run.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                checked += 1
                self.assertNotIn(
                    "预算耗尽", str(row.get("message") or ""),
                    f"{run.name} 出现了预算升级——熔断消融需要重新评估",
                )

        # 数据集被 git 忽略时这里会是 0，跳过而不是误报通过。
        if checked == 0:
            self.skipTest("未找到历史运行记录（evaluation/results 为空）")

    def test_budget_defaults_match_the_documented_values(self):
        """论文 §4.4 引用的三个默认值必须与代码一致。"""
        budget = Budget(order_id="probe")

        self.assertEqual(budget.max_tokens, 200_000)
        self.assertEqual(budget.max_llm_calls, 12)
        self.assertEqual(budget.max_wall_ms, 300_000.0)


if __name__ == "__main__":
    unittest.main()
