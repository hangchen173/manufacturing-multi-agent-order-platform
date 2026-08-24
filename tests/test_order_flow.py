import tempfile
import unittest

from application.orchestrators import OrderProcessingOrchestrator
from application.services import OrderManager
from config import Config
from domain.models import (
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
        self.assertEqual(status["status"], OrderStatus.COMPLETED.value)
        self.assertEqual(len(status["transition_history"]), 5)
        self.assertIsNotNone(restored_order)
        self.assertEqual(restored_order.status, OrderStatus.COMPLETED)
        self.assertEqual(restored_order.final_result.matched_order.items[0].sku_code, "SKU-001")


if __name__ == "__main__":
    unittest.main()
