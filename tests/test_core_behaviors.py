import json
import tempfile
import unittest
from pathlib import Path

from langchain_core.messages import AIMessage

from application.agents.parser_agent import ParserAgent
from application.agents.risk_control_agent import RiskControlAgent
from application.pipeline.stages import AgentPipelineStage
from application.services import OrderManager, OrderProcessingContext
from config import Config
from domain.models import MatchedOrderItem, OrderStatus
from infrastructure.document_processing.document_loader import DocumentLoader
from tests.fakes import InMemoryOrderRepository


def _order_payload(specification):
    return {
        "order_number": "PO-1",
        "customer_name": "客户01",
        "items": [
            {
                "material_name": "螺丝",
                "specification": specification,
                "quantity": 10,
                "unit": "个",
                "unit_price": 1.0,
            }
        ],
        "total_amount": None,
        "parsing_confidence": 0.95,
    }


def _schema_invalid_payload():
    # material_name 仍为必填，置空可稳定触发 Pydantic 结构校验失败
    payload = _order_payload("M8")
    payload["items"][0]["material_name"] = None
    return payload


def _ungrounded_name_payload():
    payload = _order_payload("M8")
    payload["items"][0]["material_name"] = "不存在的物料"
    return payload


def _build_parser_agent(*payloads):
    responses = iter(payloads)
    prompts = []

    def fake_llm(prompt_value):
        prompts.append(prompt_value)
        return AIMessage(content=json.dumps(next(responses)))

    return ParserAgent(llm=fake_llm, config=Config()), prompts


ORDER_TEXT = "1 螺丝 M8 10 个 1.0 10.0"


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

            def record_stage(self, *_args, **_kwargs):
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

    def test_parser_skips_self_correction_when_extraction_is_clean(self):
        agent, prompts = _build_parser_agent(_order_payload("M8"))

        result = agent.run({"order_text": ORDER_TEXT})

        self.assertTrue(result["success"])
        self.assertEqual(len(prompts), 1)
        self.assertIsNone(agent.last_self_correction)

    def test_parser_retries_once_and_records_the_resolved_problem(self):
        agent, prompts = _build_parser_agent(
            _ungrounded_name_payload(),
            _order_payload("M8"),
        )

        result = agent.run({"order_text": ORDER_TEXT})

        self.assertEqual(len(prompts), 2)
        self.assertEqual(result["parsed_order"].items[0].specification, "M8")
        self.assertEqual(agent.last_self_correction["attempts"], 2)
        self.assertTrue(agent.last_self_correction["resolved"])
        self.assertEqual(len(agent.last_self_correction["initial_problems"]), 1)
        self.assertEqual(agent.last_self_correction["remaining_problems"], [])

    def test_parser_flags_unresolved_problems_for_manual_review(self):
        agent, prompts = _build_parser_agent(
            _ungrounded_name_payload(),
            _ungrounded_name_payload(),
        )

        result = agent.run({"order_text": ORDER_TEXT})

        self.assertEqual(len(prompts), ParserAgent.MAX_PARSING_ATTEMPTS)
        self.assertFalse(agent.last_self_correction["resolved"])
        self.assertEqual(len(agent.last_self_correction["remaining_problems"]), 1)

        parsed_order = result["parsed_order"]
        self.assertIsNone(parsed_order.items[0].confidence_score)
        self.assertEqual(parsed_order.parsing_confidence, 0.95)
        self.assertTrue(parsed_order.parsing_issues)

    def test_parser_exposes_unresolved_problems_as_structured_issues(self):
        agent, _ = _build_parser_agent(
            _ungrounded_name_payload(),
            _ungrounded_name_payload(),
        )

        result = agent.run({"order_text": ORDER_TEXT})

        parsed_order = result["parsed_order"]
        self.assertEqual(len(parsed_order.parsing_issues), 1)
        self.assertEqual(parsed_order.parsing_issues[0].item_index, 0)
        self.assertIn("无法在原文中定位", parsed_order.parsing_issues[0].description)

    def test_parser_records_order_level_problem_without_item_index(self):
        agent, _ = _build_parser_agent(
            _order_payload("M8"),
            _order_payload("M8"),
        )

        result = agent.run({"order_text": "1 螺丝 M8 10 个 1.0 10.0\n2 螺母 M8 5 个 2.0 10.0"})

        issues = result["parsed_order"].parsing_issues
        self.assertEqual(len(issues), 1)
        self.assertIsNone(issues[0].item_index)
        self.assertIn("明细数量不一致", issues[0].description)

    def test_resolved_parse_problem_leaves_no_structured_issue(self):
        agent, _ = _build_parser_agent(
            _ungrounded_name_payload(),
            _order_payload("M8"),
        )

        result = agent.run({"order_text": ORDER_TEXT})

        self.assertEqual(result["parsed_order"].parsing_issues, [])

    def test_parser_detects_row_count_mismatch(self):
        agent, prompts = _build_parser_agent(
            _order_payload("M8"),
            _order_payload("M8"),
        )

        agent.run({"order_text": "1 螺丝 M8 10 个 1.0 10.0\n2 螺母 M8 5 个 2.0 10.0"})

        self.assertEqual(len(prompts), 2)
        self.assertTrue(
            any("明细数量不一致" in problem for problem in agent.last_self_correction["remaining_problems"])
        )

    def test_parser_recovers_from_schema_validation_failure(self):
        agent, prompts = _build_parser_agent(
            _schema_invalid_payload(),
            _order_payload("M8"),
        )

        result = agent.run({"order_text": ORDER_TEXT})

        self.assertTrue(result["success"])
        self.assertEqual(len(prompts), 2)
        self.assertEqual(result["parsed_order"].items[0].specification, "M8")
        self.assertTrue(agent.last_self_correction["resolved"])
        self.assertTrue(
            any("结构校验" in problem for problem in agent.last_self_correction["initial_problems"])
        )

    def test_parser_fails_when_schema_validation_never_recovers(self):
        agent, prompts = _build_parser_agent(
            _schema_invalid_payload(),
            _schema_invalid_payload(),
        )

        result = agent.run({"order_text": ORDER_TEXT})

        self.assertFalse(result["success"])
        self.assertIn("结构校验", result["message"])
        self.assertEqual(len(prompts), ParserAgent.MAX_PARSING_ATTEMPTS)


if __name__ == "__main__":
    unittest.main()
