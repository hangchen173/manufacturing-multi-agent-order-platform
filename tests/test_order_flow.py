import tempfile
import unittest

from application.agents import RiskControlAgent
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

    def test_low_match_score_yields_manual_review(self):
        risk_agent = RiskControlAgent(config=Config())
        result = self._run_with_matcher(LowScoreMatcher(), risk_agent=risk_agent)

        self.assertTrue(result["success"])
        self.assertTrue(result["needs_confirmation"])
        self.assertEqual(result["business_decision"].action, BusinessAction.MANUAL_REVIEW)
        self.assertIn("人工确认", result["business_decision"].reason)


if __name__ == "__main__":
    unittest.main()
