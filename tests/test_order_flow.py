import json
import tempfile
import unittest

from langchain_core.messages import AIMessage

from application.agents import MatchingAgent, ParserAgent, RiskControlAgent
from application.orchestrators import OrderProcessingOrchestrator
from application.services import OrderManager
from config import Config
from domain.models import (
    BusinessAction,
    MatchedOrder,
    MatchedOrderItem,
    OrderItem,
    OrderStatus,
    ParsedOrder,
    RiskCheckResult,
)
from tests.fakes import InMemoryOrderRepository
from tests.test_matching_ambiguity import FakeFAISSManager


class FixedParser:
    def run(self, _input_data):
        return {
            "success": True,
            "parsed_order": ParsedOrder(
                order_number="ORD-1",
                customer_name="测试客户",
                items=[
                    OrderItem(
                        material_name="不锈钢螺丝",
                        specification="M8x30",
                        quantity=10,
                        unit="个",
                        unit_price=0.5,
                        confidence_score=0.95,
                    )
                ],
                total_amount=5,
                parsing_confidence=0.95,
            ),
        }


class EmptyParser:
    def run(self, _input_data):
        return {
            "success": True,
            "parsed_order": ParsedOrder(items=[], parsing_confidence=0.1),
        }


class FixedMatcher:
    def run(self, input_data):
        parsed_order = input_data["parsed_order"]
        return {
            "success": True,
            "matched_order": MatchedOrder(
                order_number=parsed_order.order_number,
                customer_name=parsed_order.customer_name,
                items=[
                    MatchedOrderItem(
                        **parsed_order.items[0].model_dump(),
                        sku_code="SKU-001",
                        matched_material_name="不锈钢螺丝",
                        match_score=0.98,
                    )
                ],
                total_amount=parsed_order.total_amount,
            ),
        }

    def get_reference_prices(self, _matched_order):
        return {0: 0.5}


class FixedRiskControl:
    def run(self, _input_data):
        return {
            "success": True,
            "risk_result": RiskCheckResult(
                needs_confirmation=False,
                issues=[],
                overall_confidence=0.98,
            ),
        }


class NormalizingMatcher(FixedMatcher):
    def run(self, input_data):
        result = super().run(input_data)
        result["matched_order"].items[0].matched_material_name = "304不锈钢内六角圆柱头螺钉"
        result["matched_order"].items[0].match_basis = "catalog_alias_spec_exact"
        return result


class SpecNormalizingMatcher(FixedMatcher):
    def run(self, input_data):
        result = super().run(input_data)
        result["matched_order"].items[0].matched_specification = "M8×30"
        result["matched_order"].items[0].match_basis = "catalog_name_spec_exact"
        return result


class PriceOnlyMatcher(FixedMatcher):
    def run(self, input_data):
        result = super().run(input_data)
        result["matched_order"].items[0].unit_price = 99.0
        return result


class LowScoreMatcher(FixedMatcher):
    def run(self, input_data):
        result = super().run(input_data)
        result["matched_order"].items[0].match_score = 0.5
        return result


class OrderFlowTests(unittest.TestCase):
    def test_text_order_is_completed_and_restored_from_storage(self):
        with tempfile.TemporaryDirectory():
            config = Config()
            config.data.order_auto_archive_days = 0
            repository = InMemoryOrderRepository()
            manager = OrderManager(repository=repository, config=config)
            orchestrator = OrderProcessingOrchestrator(
                config=config,
                order_manager=manager,
                parser_agent_general=FixedParser(),
                matching_agent=FixedMatcher(),
                risk_agent=FixedRiskControl(),
            )

            result = orchestrator.process_order_from_text("订单文本")
            status = orchestrator.get_order_status(result["order_id"])
            restored_manager = OrderManager(repository=repository, config=config)
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
        config = Config()
        repository = InMemoryOrderRepository()
        manager = OrderManager(repository=repository, config=config)
        orchestrator = OrderProcessingOrchestrator(
            config=config,
            order_manager=manager,
            parser_agent_general=EmptyParser(),
            matching_agent=FixedMatcher(),
            risk_agent=FixedRiskControl(),
        )

        result = orchestrator.process_order_from_text("与订单无关的垃圾文本")
        status = orchestrator.get_order_status(result["order_id"])

        self.assertFalse(result["success"])
        self.assertEqual(status["status"], OrderStatus.FAILED.value)


class RiskControlEmptyOrderTests(unittest.TestCase):
    def test_empty_matched_order_does_not_report_full_confidence(self):
        agent = RiskControlAgent(config=Config())

        result = agent.run({"matched_order": MatchedOrder(items=[])})

        self.assertTrue(result["success"])
        risk_result = result["risk_result"]
        self.assertTrue(risk_result.needs_confirmation)
        self.assertEqual(risk_result.overall_confidence, 0.0)


class BusinessDecisionTests(unittest.TestCase):
    def _run_with_matcher(self, matcher, risk_agent=None):
        config = Config()
        manager = OrderManager(repository=InMemoryOrderRepository(), config=config)
        orchestrator = OrderProcessingOrchestrator(
            config=config,
            order_manager=manager,
            parser_agent_general=FixedParser(),
            matching_agent=matcher,
            risk_agent=risk_agent or FixedRiskControl(),
        )
        return orchestrator.process_order_from_text("订单文本")

    def test_alias_normalization_yields_auto_correct(self):
        result = self._run_with_matcher(NormalizingMatcher())

        self.assertTrue(result["success"])
        self.assertFalse(result["needs_confirmation"])
        self.assertEqual(result["business_decision"].action, BusinessAction.AUTO_CORRECT)

    def test_auto_correct_records_explainable_name_change(self):
        result = self._run_with_matcher(NormalizingMatcher())
        decision = result["business_decision"]

        self.assertEqual(decision.action, BusinessAction.AUTO_CORRECT)
        self.assertEqual(len(decision.normalizations), 1)
        change = decision.normalizations[0]
        self.assertEqual(change.field, "material_name")
        self.assertEqual(change.original_value, "不锈钢螺丝")
        self.assertEqual(change.standard_value, "304不锈钢内六角圆柱头螺钉")
        self.assertEqual(change.basis, "物料名称命中标准库已登记别名")

    def test_equivalent_specification_writing_is_recorded(self):
        result = self._run_with_matcher(SpecNormalizingMatcher())
        decision = result["business_decision"]

        self.assertEqual(decision.action, BusinessAction.AUTO_CORRECT)
        self.assertEqual([c.field for c in decision.normalizations], ["specification"])
        self.assertEqual(decision.normalizations[0].original_value, "M8x30")
        self.assertEqual(decision.normalizations[0].standard_value, "M8×30")

    def test_auto_approve_has_no_normalization_records(self):
        result = self._run_with_matcher(FixedMatcher())
        decision = result["business_decision"]

        self.assertEqual(decision.action, BusinessAction.AUTO_APPROVE)
        self.assertEqual(decision.normalizations, [])

    def test_price_change_is_not_counted_as_auto_correction(self):
        # 改价不属于确定性归一化；无名称/规格等价书写变更时不得报 auto_correct
        result = self._run_with_matcher(PriceOnlyMatcher())
        decision = result["business_decision"]

        self.assertEqual(decision.action, BusinessAction.AUTO_APPROVE)
        self.assertEqual(decision.normalizations, [])

    def test_low_match_score_yields_manual_review(self):
        risk_agent = RiskControlAgent(config=Config())
        result = self._run_with_matcher(LowScoreMatcher(), risk_agent=risk_agent)

        self.assertTrue(result["success"])
        self.assertTrue(result["needs_confirmation"])
        self.assertEqual(result["business_decision"].action, BusinessAction.MANUAL_REVIEW)
        self.assertIn("人工确认", result["business_decision"].reason)
        self.assertEqual(result["business_decision"].normalizations, [])


MATERIAL_CATALOG = [
    {
        "sku_code": "SCR-001",
        "material_name": "螺丝",
        "specification": "M8",
        "reference_price": 1.0,
    },
]

TWO_ROW_ORDER_TEXT = "1 螺丝 M8 10 个 1.0 10.0\n2 螺母 M8 5 个 2.0 10.0"

ROW_MISMATCH_PAYLOAD = {
    "order_number": "PO-1",
    "customer_name": "客户01",
    "items": [
        {
            "material_name": "螺丝",
            "specification": "M8",
            "quantity": 10,
            "unit": "个",
            "unit_price": 1.0,
        }
    ],
    "total_amount": None,
    "parsing_confidence": 0.95,
}


class UnresolvedParsingProblemTests(unittest.TestCase):
    def test_unresolved_row_mismatch_blocks_auto_completion(self):
        # 固定模型响应连续两次漏行，串联真实解析自检、匹配、风控和状态机
        responses = iter([dict(ROW_MISMATCH_PAYLOAD), dict(ROW_MISMATCH_PAYLOAD)])
        prompts = []

        def fake_llm(prompt_value):
            prompts.append(prompt_value)
            return AIMessage(content=json.dumps(next(responses)))

        with tempfile.TemporaryDirectory():
            config = Config()
            config.data.order_auto_archive_days = 0
            repository = InMemoryOrderRepository()
            manager = OrderManager(repository=repository, config=config)
            orchestrator = OrderProcessingOrchestrator(
                config=config,
                order_manager=manager,
                parser_agent_general=ParserAgent(llm=fake_llm, config=config),
                matching_agent=MatchingAgent(
                    faiss_manager=FakeFAISSManager(MATERIAL_CATALOG),
                    config=config,
                ),
                risk_agent=RiskControlAgent(config=config),
            )

            result = orchestrator.process_order_from_text(TWO_ROW_ORDER_TEXT)
            status = orchestrator.get_order_status(result["order_id"])
            detail = orchestrator.get_order_detail(result["order_id"])
            restored = OrderManager(
                repository=repository, config=config
            ).get_order(result["order_id"])

        self.assertEqual(len(prompts), ParserAgent.MAX_PARSING_ATTEMPTS)
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
            any(
                issue["issue_type"] == "unresolved_parsing_problem"
                for issue in confirmation["issues"]
            )
        )


if __name__ == "__main__":
    unittest.main()
