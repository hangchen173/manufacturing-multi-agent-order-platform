"""基线实现的离线守卫测试（**零模型调用**）。

钉死三件事：

1. **单变量控制**：基线的系统提示词、user 消息、输出模式与 VEAP 抽取器**逐字一致**，
   否则比的就是提示词而不是验证媒介。
2. **多数投票的确定性**：平票必须取「首次出现」，不能依赖字典顺序——
   否则同一份结果重跑会得到不同答案，实验不可复现。
3. **按位置对齐**：MAD 的共识合并必须按位置，不能按物料名。
"""
from __future__ import annotations

import unittest

from domain.models import OrderItem, ParsedOrder
from evaluation.baselines import BASELINES, DEFAULT_METHOD_ORDER
from evaluation.baselines.base import (
    BaselineResult,
    base_system_prompt,
    format_instructions,
    order_user_message,
)
from evaluation.baselines.mad import MADBaseline, _merge_items, majority
from evaluation.baselines.zero_shot import ZeroShotBaseline


def _item(name="轴承", spec="6200", quantity=100, unit="套", price=28.7):
    return OrderItem(material_name=name, specification=spec, quantity=quantity,
                     unit=unit, unit_price=price)


def _parsed(items, **order):
    return ParsedOrder(
        order_number=order.get("order_number"),
        customer_name=order.get("customer_name"),
        total_amount=order.get("total_amount"),
        items=items,
        parsing_confidence=order.get("confidence", 0.9),
    )


class SingleVariableControlTests(unittest.TestCase):
    """基线与 VEAP 抽取器必须共用同一套提示词与输出模式。"""

    def test_base_system_prompt_is_extractors_prompt(self):
        from application.agents.extractor import _TEXT_SYSTEM_PROMPT

        self.assertEqual(base_system_prompt(), _TEXT_SYSTEM_PROMPT)

    def test_base_system_prompt_exposes_format_placeholder(self):
        # 若上游把占位符改名，这里会失败，提醒实验脚本同步——
        # 否则 .format() 会抛 KeyError，整轮实验直接崩。
        self.assertIn("{format_instructions}", base_system_prompt())

    def test_format_instructions_are_parsed_orders_schema(self):
        text = format_instructions()
        self.assertIn("order_number", text)
        self.assertIn("items", text)

    def test_user_message_matches_extractors_template(self):
        self.assertEqual(order_user_message("X"), "订单文本如下：\nX")

    def test_registry_exposes_expected_methods(self):
        self.assertEqual(set(BASELINES), {"zero_shot", "mad"})
        self.assertEqual(set(DEFAULT_METHOD_ORDER), {"zero_shot", "mad"})


class MajorityTests(unittest.TestCase):
    def test_clear_majority_wins(self):
        self.assertEqual(majority([100, 100, 200]), 100)

    def test_numeric_equivalence_uses_value_not_text(self):
        # 100 与 "100" 与 100.0 必须算同一票，否则浮点/字符串差异会拆散多数。
        self.assertEqual(majority([100, "100", 200]), 100)

    def test_tie_breaks_on_first_occurrence(self):
        # 关键的可复现性保证：平票取首次出现，而不是依赖 Counter 的遍历顺序。
        self.assertEqual(majority([2, 1]), 2)
        self.assertEqual(majority([1, 2]), 1)

    def test_abstention_can_win(self):
        # 两个 agent 弃权、一个给了值 → 多数是「弃权」，结果应为 None。
        self.assertIsNone(majority([None, None, "x"]))

    def test_empty_input_is_none(self):
        self.assertIsNone(majority([]))

    def test_text_comparison_is_normalized(self):
        self.assertEqual(majority(["轴承 ", "轴承", "阀门"]), "轴承 ")


class MergeItemsTests(unittest.TestCase):
    def test_positional_alignment_across_agents(self):
        merged = _merge_items([
            [_item(quantity=100), _item(quantity=500)],
            [_item(quantity=100), _item(quantity=500)],
            [_item(quantity=100), _item(quantity=999)],
        ])
        self.assertEqual([item.quantity for item in merged], [100, 500])

    def test_uneven_row_counts_use_the_longest_list(self):
        # 某 agent 少抽一行 → 该位置只有两个候选，仍要投票而不是整体错位。
        merged = _merge_items([[_item(quantity=100)], [_item(quantity=100), _item(quantity=500)]])
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[1].quantity, 500)

    def test_empty_input_returns_empty_list(self):
        self.assertEqual(_merge_items([]), [])

    def test_missing_material_name_degrades_to_empty_string(self):
        # material_name 是必填 str；投票出 None 时必须降级为 ""，
        # 否则 pydantic 直接抛错，整份订单记成 error，掩盖真实结果。
        merged = _merge_items([
            [OrderItem(material_name="", quantity=1)],
            [OrderItem(material_name="", quantity=1)],
        ])
        self.assertEqual(merged[0].material_name, "")


class ConsensusTests(unittest.TestCase):
    def test_consensus_merges_three_answers(self):
        merged, error = MADBaseline._consensus([
            _parsed([_item(quantity=100)], order_number="PO-1"),
            _parsed([_item(quantity=100)], order_number="PO-1"),
            _parsed([_item(quantity=999)], order_number="PO-2"),
        ])
        self.assertIsNone(error)
        self.assertEqual(merged.order_number, "PO-1")
        self.assertEqual(merged.items[0].quantity, 100)

    def test_all_failed_returns_error_not_empty_order(self):
        merged, error = MADBaseline._consensus([None, None])
        self.assertIsNone(merged)
        self.assertIsNotNone(error)

    def test_confidence_is_clamped_into_unit_interval(self):
        merged, _ = MADBaseline._consensus([
            _parsed([_item()], confidence=1.0),
            _parsed([_item()], confidence=1.0),
        ])
        self.assertLessEqual(merged.parsing_confidence, 1.0)
        self.assertGreaterEqual(merged.parsing_confidence, 0.0)


class ConstructionTests(unittest.TestCase):
    def test_mad_rejects_degenerate_configurations(self):
        class _Config:
            def model_for(self, role):  # pragma: no cover - 不该被调用
                raise AssertionError("参数校验必须在建客户端之前完成")

        with self.assertRaises(ValueError):
            MADBaseline(_Config(), agents=1)
        with self.assertRaises(ValueError):
            MADBaseline(_Config(), rounds=0)

    def test_planned_calls_matches_agents_times_rounds(self):
        # 用 __new__ 绕过建客户端：这里只验算式，不碰网络。
        baseline = MADBaseline.__new__(MADBaseline)
        baseline.agents, baseline.rounds = 3, 2
        self.assertEqual(baseline.planned_calls, 9)

    def test_names_are_stable(self):
        # 方法名会进产物与论文表格，改名等于让历史结果不可比。
        self.assertEqual(ZeroShotBaseline.name, "zero_shot")
        self.assertEqual(MADBaseline.name, "mad")


class BaselineResultTests(unittest.TestCase):
    def test_total_tokens_reads_usage(self):
        result = BaselineResult(usage={"prompt_tokens": 10, "completion_tokens": 5,
                                       "total_tokens": 15})
        self.assertEqual(result.total_tokens, 15)

    def test_succeeded_requires_a_parsed_order(self):
        self.assertFalse(BaselineResult().succeeded)
        self.assertTrue(BaselineResult(parsed=_parsed([_item()])).succeeded)

    def test_evidence_chain_defaults_to_empty(self):
        # 基线的「不可审计」是**构造性的**：它从不产生证据链。
        # 比较脚本据此测量 auditable_rate，而不是靠论文里断言。
        self.assertEqual(BaselineResult().evidence_chain, [])


if __name__ == "__main__":
    unittest.main()
