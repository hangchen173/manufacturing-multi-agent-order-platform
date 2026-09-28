import tempfile
import unittest

from application.orchestrators import OrderProcessingOrchestrator
from application.services import OrderManager
from config import Config
from domain.models import (
    BusinessAction,
    MatchedOrder,
    MatchedOrderItem,
    OrderStatus,
    ParsedOrder,
)
from tests.fakes import InMemoryOrderRepository
from tests.support import FakeFAISSManager, build_harness, item, order_payload

# 名称完全一致：不触发任何归一化
PLAIN_CATALOG = [
    {"sku_code": "SKU-001", "material_name": "螺丝", "specification": "M8",
     "unit": "个", "reference_price": 1.0, "category": "紧固件", "aliases": []},
]

# 别名 + 等价规格书写：用于验证确定性归一化记录
ALIAS_CATALOG = [
    {"sku_code": "SKU-001", "material_name": "304不锈钢内六角圆柱头螺钉",
     "specification": "M8x30", "unit": "个", "reference_price": 0.5,
     "category": "紧固件", "aliases": ["不锈钢螺丝"]},
]

SPEC_CATALOG = [
    {"sku_code": "CBL-003", "material_name": "屏蔽控制电缆",
     "specification": "RVVP 4×0.5mm² 普通屏蔽", "unit": "米", "reference_price": 4.16,
     "category": "线缆", "aliases": ["屏蔽电缆"]},
]

# 缺区分限定词：确定性路径拒识，向量召回低分候选 → 送审
SUFFIX_CATALOG = [
    {"sku_code": "ELC-025", "material_name": "交流接触器",
     "specification": "CJX2-0910 AC220V 01", "unit": "个", "reference_price": 215.60,
     "category": "电气", "aliases": ["CJX2 9A 220V"]},
]


class CompletedOrderTests(unittest.TestCase):
    def test_text_order_is_completed_and_restored_from_storage(self):
        with tempfile.TemporaryDirectory():
            repository = InMemoryOrderRepository()
            harness = build_harness(
                payloads=[order_payload([item("螺丝", "M8", 10, "个", 1.0)])],
                catalog=PLAIN_CATALOG, repository=repository,
            )

            result = harness.orchestrator.process_order_from_text("1 螺丝 M8 10 个 1.0")
            status = harness.orchestrator.get_order_status(result["order_id"])
            restored_manager = OrderManager(repository=repository, config=harness.config)
            restored_order = restored_manager.get_order(result["order_id"])

        self.assertTrue(result["success"])
        self.assertFalse(result["needs_confirmation"])
        self.assertEqual(result["business_decision"].action, BusinessAction.AUTO_APPROVE)
        self.assertEqual(status["status"], OrderStatus.COMPLETED.value)
        self.assertEqual(len(status["transition_history"]), 5)
        self.assertIsNotNone(restored_order)
        self.assertEqual(restored_order.status, OrderStatus.COMPLETED)
        self.assertEqual(restored_order.final_result.matched_order.items[0].sku_code, "SKU-001")


class EmptyOrderTests(unittest.TestCase):
    def test_empty_order_is_rejected_and_marked_failed(self):
        harness = build_harness(payloads=[
            order_payload([], parsing_confidence=0.1),
            order_payload([], parsing_confidence=0.1),
        ])

        result = harness.orchestrator.process_order_from_text("与订单无关的垃圾文本")
        status = harness.orchestrator.get_order_status(result["order_id"])

        self.assertFalse(result["success"])
        self.assertEqual(status["status"], OrderStatus.FAILED.value)


class EmptyMatchedOrderConfidenceTests(unittest.TestCase):
    def test_empty_item_set_does_not_report_full_confidence(self):
        from application.agents import Adjudicator

        self.assertEqual(Adjudicator()._overall_confidence([], 0), 0.0)


class BusinessDecisionTests(unittest.TestCase):
    def test_alias_normalization_yields_auto_correct(self):
        harness = build_harness(
            payloads=[order_payload([item("不锈钢螺丝", "M8x30", 10, "个", 0.5)])],
            catalog=ALIAS_CATALOG,
        )
        result = harness.orchestrator.process_order_from_text("1 不锈钢螺丝 M8x30 10 个 0.5")

        self.assertTrue(result["success"])
        self.assertFalse(result["needs_confirmation"])
        self.assertEqual(result["business_decision"].action, BusinessAction.AUTO_CORRECT)

    def test_auto_correct_records_explainable_name_change(self):
        harness = build_harness(
            payloads=[order_payload([item("不锈钢螺丝", "M8x30", 10, "个", 0.5)])],
            catalog=ALIAS_CATALOG,
        )
        result = harness.orchestrator.process_order_from_text("1 不锈钢螺丝 M8x30 10 个 0.5")
        decision = result["business_decision"]

        self.assertEqual(decision.action, BusinessAction.AUTO_CORRECT)
        self.assertEqual(len(decision.normalizations), 1)
        change = decision.normalizations[0]
        self.assertEqual(change.field, "material_name")
        self.assertEqual(change.original_value, "不锈钢螺丝")
        self.assertEqual(change.standard_value, "304不锈钢内六角圆柱头螺钉")
        self.assertEqual(change.basis, "物料名称命中标准库已登记别名")

    def test_equivalent_specification_writing_is_recorded(self):
        harness = build_harness(
            payloads=[order_payload([item("屏蔽控制电缆", "RVVP 4*0.5mm2 普通屏蔽", 100, "米", 4.0)])],
            catalog=SPEC_CATALOG,
        )
        result = harness.orchestrator.process_order_from_text(
            "1 屏蔽控制电缆 RVVP 4*0.5mm2 普通屏蔽 100 米 4.0"
        )
        decision = result["business_decision"]

        self.assertEqual(decision.action, BusinessAction.AUTO_CORRECT)
        self.assertEqual([c.field for c in decision.normalizations], ["specification"])
        self.assertEqual(decision.normalizations[0].original_value, "RVVP 4*0.5mm2 普通屏蔽")
        self.assertEqual(decision.normalizations[0].standard_value, "RVVP 4×0.5mm² 普通屏蔽")

    def test_auto_approve_has_no_normalization_records(self):
        harness = build_harness(
            payloads=[order_payload([item("螺丝", "M8", 10, "个", 1.0)])],
            catalog=PLAIN_CATALOG,
        )
        result = harness.orchestrator.process_order_from_text("1 螺丝 M8 10 个 1.0")
        decision = result["business_decision"]

        self.assertEqual(decision.action, BusinessAction.AUTO_APPROVE)
        self.assertEqual(decision.normalizations, [])

    def test_price_change_is_not_counted_as_auto_correction(self):
        # 改价不属于确定性归一化；无名称/规格等价书写变更时不得报 auto_correct
        harness = build_harness(
            payloads=[order_payload([item("螺丝", "M8", 10, "个", 1.2)])],
            catalog=PLAIN_CATALOG,
        )
        result = harness.orchestrator.process_order_from_text("1 螺丝 M8 10 个 1.2")
        decision = result["business_decision"]

        self.assertEqual(decision.action, BusinessAction.AUTO_APPROVE)
        self.assertEqual(decision.normalizations, [])

    def test_low_match_score_yields_manual_review(self):
        store = FakeFAISSManager(SUFFIX_CATALOG, search_results=[(SUFFIX_CATALOG[0], 0.5)])
        harness = build_harness(
            payloads=[order_payload([item("交流接触器", "CJX2-0910 AC220V", 10, "个", 200.0)])],
            faiss_manager=store,
        )
        result = harness.orchestrator.process_order_from_text(
            "1 交流接触器 CJX2-0910 AC220V 10 个 200.0"
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["needs_confirmation"])
        self.assertEqual(result["business_decision"].action, BusinessAction.MANUAL_REVIEW)
        self.assertIn("人工确认", result["business_decision"].reason)
        self.assertEqual(result["business_decision"].normalizations, [])


TWO_ROW_ORDER_TEXT = "1 螺丝 M8 10 个 1.0\n2 螺母 M8 5 个 2.0"

ROW_MISMATCH_PAYLOAD = order_payload([item("螺丝", "M8", 10, "个", 1.0)])


class UnresolvedParsingProblemTests(unittest.TestCase):
    def test_unresolved_row_mismatch_blocks_auto_completion(self):
        # 固定模型响应连续两次漏行，串联真实抽取、溯源、匹配、风控与状态机
        with tempfile.TemporaryDirectory():
            repository = InMemoryOrderRepository()
            harness = build_harness(
                payloads=[dict(ROW_MISMATCH_PAYLOAD), dict(ROW_MISMATCH_PAYLOAD)],
                catalog=PLAIN_CATALOG, repository=repository,
            )
            orchestrator = harness.orchestrator

            result = orchestrator.process_order_from_text(TWO_ROW_ORDER_TEXT)
            status = orchestrator.get_order_status(result["order_id"])
            detail = orchestrator.get_order_detail(result["order_id"])
            restored = OrderManager(repository=repository, config=harness.config).get_order(
                result["order_id"]
            )

        self.assertEqual(len(harness.prompts), 2)
        self.assertTrue(result["success"])
        self.assertTrue(result["needs_confirmation"])
        self.assertEqual(result["business_decision"].action, BusinessAction.MANUAL_REVIEW)
        self.assertEqual(status["status"], OrderStatus.NEEDS_CONFIRMATION.value)

        issue_types = [issue["issue_type"] for issue in detail["risk_result"]["issues"]]
        self.assertIn("unresolved_parsing_problem", issue_types)

        parsed_issues = restored.parsed_order.parsing_issues
        self.assertEqual(len(parsed_issues), 1)
        self.assertIn("明细数量不一致", parsed_issues[0].description)

        confirmation = restored.confirmation_requests[0]
        self.assertTrue(
            any(issue["issue_type"] == "unresolved_parsing_problem"
                for issue in confirmation["issues"])
        )


if __name__ == "__main__":
    unittest.main()
