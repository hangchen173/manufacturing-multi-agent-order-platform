import tempfile
import unittest
from pathlib import Path

from application.agents.risk_control_agent import RiskControlAgent
from application.pipeline.stages import AgentPipelineStage
from application.services import OrderManager, OrderProcessingContext
from config import Config
from domain.models import MatchedOrderItem, OrderStatus
from infrastructure.document_processing.document_loader import DocumentLoader
from tests.fakes import InMemoryOrderRepository


class CoreBehaviorTests(unittest.TestCase):
    def test_text_documents_declared_as_supported_are_loaded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "order.txt"
            path.write_text("订单编号: ORD-1", encoding="utf-8")

            content, document_type = DocumentLoader().load_document(str(path))

        self.assertEqual(content, "订单编号: ORD-1")
        self.assertEqual(document_type, "text")

    def test_zero_confidence_is_a_risk(self):
        item = MatchedOrderItem(
            material_name="螺丝",
            specification="M8",
            quantity=1,
            unit="个",
            confidence_score=0,
            match_score=1,
        )
        result = RiskControlAgent(config=Config()).run({"matched_order": type("Order", (), {"items": [item]})()})

        self.assertTrue(result["risk_result"].needs_confirmation)
        self.assertEqual(result["risk_result"].issues[0].issue_type, "low_confidence")

    def test_pipeline_fails_when_result_cannot_be_persisted(self):
        stage = AgentPipelineStage(
            name="test",
            target_status=OrderStatus.PARSING,
            status_reason="test",
            runner=lambda _: {"success": True, "value": "ok"},
            payload_key="value",
            persist_callback=lambda *_: False,
        )

        class Manager:
            def __init__(self):
                self.statuses = []

            def update_order_status(self, *_args, **_kwargs):
                self.statuses.append("started")
                return True

            def set_error(self, *_args, **_kwargs):
                self.statuses.append("failed")
                return True

        manager = Manager()
        result = stage.execute(manager, "order-1", {})

        self.assertFalse(result.success)
        self.assertEqual(manager.statuses, ["started", "failed"])

    def test_snapshot_without_transition_history_is_rejected(self):
        snapshot = {
            "order_id": "order-1",
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
            "status": "pending",
            "transition_history": [],
        }

        with self.assertRaises(ValueError):
            OrderProcessingContext.from_snapshot(snapshot)

    def test_status_machine_rejects_a_shortcut_to_completion(self):
        with tempfile.TemporaryDirectory():
            config = Config()
            config.data.order_auto_archive_days = 0
            manager = OrderManager(repository=InMemoryOrderRepository(), config=config)
            order_id = manager.create_order(order_text="订单文本")

            updated = manager.update_order_status(order_id, OrderStatus.COMPLETED)

        self.assertFalse(updated)
        self.assertEqual(manager.get_order(order_id).status, OrderStatus.PENDING)


if __name__ == "__main__":
    unittest.main()
