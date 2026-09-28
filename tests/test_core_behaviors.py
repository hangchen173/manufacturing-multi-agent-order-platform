import json
import tempfile
import unittest
from pathlib import Path

from langchain_core.messages import AIMessage

from application.pipeline.stages import TaskNodeExecutor
from application.services import OrderManager, OrderProcessingContext
from config import Config
from domain.agent_roles import AgentRole
from domain.exceptions import ExtractionSchemaException
from domain.models import OrderStatus
from domain.tasks import Task, TaskStatus
from infrastructure.document_processing.document_loader import DocumentLoader
from tests.fakes import InMemoryOrderRepository
from tests.support import build_harness, item, order_payload

ORDER_TEXT = "1 螺丝 M8 10 个 1.0"
TWO_ROW_TEXT = "1 螺丝 M8 10 个 1.0\n2 螺母 M8 5 个 2.0"


def _payload(name="螺丝", spec="M8", quantity=10, price=1.0):
    return order_payload([item(name, spec, quantity, "个", price)])


def _schema_invalid_payload():
    # material_name 为必填，置空可稳定触发 Pydantic 结构校验失败
    payload = _payload()
    payload["items"][0]["material_name"] = None
    return payload


class DocumentLoaderTests(unittest.TestCase):
    def test_text_documents_declared_as_supported_are_loaded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "order.txt"
            path.write_text("订单编号: ORD-1", encoding="utf-8")

            content, document_type = DocumentLoader().load_document(str(path))

        self.assertEqual(content, "订单编号: ORD-1")
        self.assertEqual(document_type, "text")


class GroundingEvidenceRiskTests(unittest.TestCase):
    def test_low_grounding_rate_is_a_medium_risk(self):
        from application.agents import PolicyRisk

        agent = PolicyRisk(config=Config())
        # 溯源证据通过率替代模型自报置信度：低于阈值必须送审
        issues = agent.check_grounding_evidence(
            {"material_name": "螺丝", "_grounding": {"rate": 0.0, "verified": 0, "total": 3}}, 0
        )

        self.assertEqual([issue["issue_type"] for issue in issues], ["low_confidence"])
        self.assertEqual(issues[0]["severity"], "medium")

    def test_sufficient_grounding_rate_is_not_a_risk(self):
        from application.agents import PolicyRisk

        agent = PolicyRisk(config=Config())
        issues = agent.check_grounding_evidence(
            {"material_name": "螺丝", "_grounding": {"rate": 1.0, "verified": 3, "total": 3}}, 0
        )

        self.assertEqual(issues, [])


class TaskNodeExecutorTests(unittest.TestCase):
    class _Agent:
        role = AgentRole.GROUNDING_VERIFIER

        def __init__(self, behaviour):
            self.behaviour = behaviour
            self.calls = 0

        def handle(self, task):
            self.calls += 1
            return self.behaviour(self.calls)

    def _execute(self, behaviour, *, max_attempts=2):
        agent = self._Agent(behaviour)
        executor = TaskNodeExecutor({AgentRole.GROUNDING_VERIFIER: agent})
        task = Task(order_id="order-1", agent=AgentRole.GROUNDING_VERIFIER.value,
                    stage="parse", max_attempts=max_attempts)
        return executor.execute(task), task, agent

    def test_non_retryable_error_marks_task_fatal_without_retry(self):
        def boom(_attempt):
            raise ValueError("bad input")

        result, task, agent = self._execute(boom)

        self.assertFalse(result.success)
        self.assertEqual(task.status, TaskStatus.FATAL)
        self.assertEqual(agent.calls, 1)

    def test_schema_error_is_retried_with_feedback(self):
        def schema_then_ok(attempt):
            if attempt == 1:
                raise ExtractionSchemaException("结构校验失败", agent_name="Extractor")
            return []

        result, task, agent = self._execute(schema_then_ok)

        self.assertTrue(result.success)
        self.assertEqual(task.attempts, 2)
        self.assertEqual(agent.calls, 2)

    def test_retryable_timeout_is_retried(self):
        def timeout_then_ok(attempt):
            if attempt == 1:
                raise TimeoutError("model timed out")
            return []

        result, task, agent = self._execute(timeout_then_ok)

        self.assertTrue(result.success)
        self.assertEqual(agent.calls, 2)

    def test_schema_error_never_recovering_is_fatal(self):
        def always_schema(_attempt):
            raise ExtractionSchemaException("结构校验失败", agent_name="Extractor")

        result, task, agent = self._execute(always_schema)

        self.assertFalse(result.success)
        self.assertEqual(task.status, TaskStatus.FATAL)
        self.assertEqual(agent.calls, 2)


class OrderStateTests(unittest.TestCase):
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


class ExtractionProtocolTests(unittest.TestCase):
    """抽取自检从"同一模型自问自答"改为"独立验证者挑战 + 带反证重抽"。"""

    def test_clean_extraction_uses_one_model_call(self):
        harness = build_harness(payloads=[_payload()])

        result = harness.orchestrator.process_order_from_text(ORDER_TEXT)

        self.assertTrue(result["success"])
        self.assertEqual(len(harness.prompts), 1)
        self.assertEqual(result["diagnostics"]["parse"]["attempts"], 1)
        self.assertEqual(result["diagnostics"]["parse"]["challenges"], [])

    def test_ungrounded_name_triggers_one_challenge_and_recovery(self):
        harness = build_harness(payloads=[_payload(name="不存在的物料"), _payload()])

        result = harness.orchestrator.process_order_from_text(ORDER_TEXT)

        self.assertTrue(result["success"])
        self.assertEqual(len(harness.prompts), 2)
        self.assertEqual(result["diagnostics"]["parse"]["attempts"], 2)
        self.assertTrue(result["diagnostics"]["parse"]["self_correction"]["resolved"])

    def test_counter_evidence_is_fed_back_into_the_retry_prompt(self):
        harness = build_harness(payloads=[_payload(name="不存在的物料"), _payload()])

        harness.orchestrator.process_order_from_text(ORDER_TEXT)

        self.assertIn("不存在的物料", harness.prompts[1].to_string())

    def test_unresolved_problem_blocks_auto_completion(self):
        harness = build_harness(payloads=[_payload(name="不存在的物料"),
                                          _payload(name="不存在的物料")])

        result = harness.orchestrator.process_order_from_text(ORDER_TEXT)

        self.assertTrue(result["success"])
        self.assertEqual(len(harness.prompts), 2)
        self.assertTrue(result["needs_confirmation"])
        self.assertEqual(result["business_decision"].action.value, "manual_review")
        self.assertFalse(result["diagnostics"]["parse"]["self_correction"]["resolved"])

    def test_unresolved_problem_is_exposed_as_a_structured_issue(self):
        harness = build_harness(payloads=[_payload(name="不存在的物料"),
                                          _payload(name="不存在的物料")])

        result = harness.orchestrator.process_order_from_text(ORDER_TEXT)

        issues = result["final_result"].parsed_order.parsing_issues
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].item_index, 0)
        self.assertIn("无法在原文中定位", issues[0].description)

    def test_order_level_problem_has_no_item_index(self):
        harness = build_harness(payloads=[_payload(), _payload()])

        result = harness.orchestrator.process_order_from_text(TWO_ROW_TEXT)

        issues = result["final_result"].parsed_order.parsing_issues
        self.assertEqual(len(issues), 1)
        self.assertIsNone(issues[0].item_index)
        self.assertIn("明细数量不一致", issues[0].description)

    def test_resolved_problem_leaves_no_structured_issue(self):
        harness = build_harness(payloads=[_payload(name="不存在的物料"), _payload()])

        result = harness.orchestrator.process_order_from_text(ORDER_TEXT)

        self.assertEqual(result["final_result"].parsed_order.parsing_issues, [])

    def test_row_count_mismatch_is_challenged(self):
        harness = build_harness(payloads=[_payload(), _payload()])

        result = harness.orchestrator.process_order_from_text(TWO_ROW_TEXT)

        self.assertEqual(len(harness.prompts), 2)
        challenges = result["diagnostics"]["parse"]["challenges"]
        self.assertTrue(any("明细数量不一致" in (challenge.get("reason") or "")
                            for challenge in challenges))

    def test_schema_validation_failure_recovers(self):
        harness = build_harness(payloads=[_schema_invalid_payload(), _payload()])

        result = harness.orchestrator.process_order_from_text(ORDER_TEXT)

        self.assertTrue(result["success"])
        self.assertEqual(len(harness.prompts), 2)
        self.assertEqual(result["final_result"].parsed_order.items[0].specification, "M8")

    def test_schema_validation_failure_never_recovering_fails(self):
        harness = build_harness(payloads=[_schema_invalid_payload(), _schema_invalid_payload()])

        result = harness.orchestrator.process_order_from_text(ORDER_TEXT)

        self.assertFalse(result["success"])
        self.assertIn("结构校验", result["message"])
        self.assertEqual(len(harness.prompts), 2)


if __name__ == "__main__":
    unittest.main()
