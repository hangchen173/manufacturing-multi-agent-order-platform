"""输出截断（reasoning 耗尽 max_tokens）的识别与重试分类。

背景（真实接口实测，2026-09）：推理型模型把「思考」与「正文」计入同一个
max_tokens 预算。预算被思考耗尽时，API 仍返回 HTTP 200，但
`finish_reason == 'length'` 且 `content == ''`。

若把空正文直接送进结构校验，会被归类成 ExtractionSchemaException，
于是系统带着一份「字段级结构反馈」去重抽——那份反馈与真实故障无关，
既误导模型，又掩盖了「预算不足」这一根因。本模块锁定正确行为。
"""
import unittest

from langchain_core.messages import AIMessage

from application.agents.extractor import EXTRACTION_MAX_TOKENS, Extractor
from application.agents.review_assistant import REVIEW_MAX_TOKENS
from application.pipeline.stages import TaskNodeExecutor
from application.protocol.model_output import assert_not_truncated
from domain.agent_roles import AgentRole
from domain.exceptions import ExtractionSchemaException, ModelTruncationException
from domain.tasks import Task, TaskStatus


def _message(content: str, finish_reason: str = "stop") -> AIMessage:
    return AIMessage(content=content, response_metadata={"finish_reason": finish_reason})


class TruncationDetectionTests(unittest.TestCase):
    def test_length_finish_reason_is_rejected_even_with_content(self):
        # 正文被截断到一半：内容非空，但 JSON 必然不完整，同样不能当结构错误处理。
        with self.assertRaises(ModelTruncationException):
            assert_not_truncated(_message('{"items": [', "length"), agent_name="Extractor")

    def test_empty_content_with_stop_is_rejected(self):
        with self.assertRaises(ModelTruncationException):
            assert_not_truncated(_message("", "stop"), agent_name="Extractor")

    def test_whitespace_only_content_is_rejected(self):
        with self.assertRaises(ModelTruncationException):
            assert_not_truncated(_message("   \n  "), agent_name="Extractor")

    def test_missing_metadata_is_tolerated_when_content_exists(self):
        message = AIMessage(content='{"ok": true}')
        assert_not_truncated(message, agent_name="Extractor")

    def test_healthy_message_passes(self):
        assert_not_truncated(_message('{"ok": true}', "stop"), agent_name="Extractor")

    def test_exception_carries_finish_reason_for_diagnostics(self):
        with self.assertRaises(ModelTruncationException) as ctx:
            assert_not_truncated(_message("", "length"), agent_name="Extractor")

        self.assertEqual(ctx.exception.details["finish_reason"], "length")
        self.assertIn("max_tokens", ctx.exception.message)


class TruncationIsNotMisclassifiedAsSchemaFailureTests(unittest.TestCase):
    def test_truncation_is_retryable_but_schema_failure_keeps_its_own_type(self):
        self.assertTrue(Task(order_id="o", agent="x", stage="parse")
                        .is_retryable("ModelTruncationException"))
        # 结构错误不走 RETRYABLE_ERRORS，而是由 executor 的专用分支处理。
        self.assertFalse(Task(order_id="o", agent="x", stage="parse")
                         .is_retryable("ExtractionSchemaException"))


class _StubAgent:
    """最小 agent 桩：按尝试次数决定抛出什么。"""

    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.calls = 0

    def handle(self, task):
        self.calls += 1
        return self.behaviour(self.calls)


class TruncationRetryClassificationTests(unittest.TestCase):
    def _execute(self, behaviour, *, max_attempts=2):
        agent = _StubAgent(behaviour)
        executor = TaskNodeExecutor({AgentRole.EXTRACTOR: agent})
        task = Task(order_id="order-1", agent=AgentRole.EXTRACTOR.value,
                    stage="parse", max_attempts=max_attempts)
        return executor.execute(task), task, agent

    def test_truncation_is_retried_without_structural_feedback(self):
        def truncate_then_ok(attempt):
            if attempt == 1:
                raise ModelTruncationException("输出被截断", agent_name="Extractor")
            return []

        result, task, _agent = self._execute(truncate_then_ok)

        self.assertTrue(result.success)
        # execute() 入口先 +1，重试分支再 +1（与结构错误重试的计数语义一致）。
        self.assertEqual(task.attempts, 2)
        # 关键断言：截断重试不得把「结构反馈」塞进切片，否则模型会被错误引导。
        self.assertNotIn("feedback", task.slice_key)

    def test_schema_failure_still_carries_feedback(self):
        def schema_then_ok(attempt):
            if attempt == 1:
                raise ExtractionSchemaException("结构校验失败", agent_name="Extractor")
            return []

        result, task, _agent = self._execute(schema_then_ok)

        self.assertTrue(result.success)
        self.assertIn("feedback", task.slice_key)

    def test_persistent_truncation_becomes_fatal_not_silently_passed(self):
        def always_truncate(_attempt):
            raise ModelTruncationException("输出被截断", agent_name="Extractor")

        result, task, agent = self._execute(always_truncate)

        self.assertFalse(result.success)
        self.assertEqual(task.status, TaskStatus.FATAL)
        self.assertEqual(agent.calls, 2)
        self.assertIn("ModelTruncationException", task.last_error)


class ExtractorTruncationTests(unittest.TestCase):
    class _Runnable:
        def __init__(self, message):
            self.message = message

        def invoke(self, _payload):
            return self.message

    def _extractor(self):
        extractor = Extractor(llm=object(), blackboard=None, budget=None, config=None)
        return extractor

    def test_invoke_model_raises_truncation_instead_of_schema_error(self):
        extractor = self._extractor()
        runnable = self._Runnable(_message("", "length"))

        with self.assertRaises(ModelTruncationException):
            extractor._invoke_model(runnable, {})

    def test_truncation_is_recorded_in_call_diagnostics(self):
        extractor = self._extractor()

        with self.assertRaises(ModelTruncationException):
            extractor._invoke_model(self._Runnable(_message("", "length")), {})

        self.assertEqual(len(extractor.last_call_records), 1)
        self.assertEqual(extractor.last_call_records[0]["error_type"],
                         "ModelTruncationException")

    def test_healthy_response_is_returned_untouched(self):
        extractor = self._extractor()
        message = _message('{"items": []}', "stop")

        self.assertIs(extractor._invoke_model(self._Runnable(message), {}), message)


class OutputBudgetRegressionTests(unittest.TestCase):
    """输出上限必须显著高于「推理 + 正文」的实测消耗，否则会稳定截断。"""

    def test_extraction_budget_leaves_room_beyond_observed_reasoning(self):
        # 实测：单条简单提示的 reasoning_tokens 已达 1158~1982；
        # 复杂多行订单更高，故上限需留出充分余量。
        self.assertGreaterEqual(EXTRACTION_MAX_TOKENS, 8192)

    def test_review_budget_exceeds_the_old_truncating_value(self):
        # 旧值 1024 低于实测 reasoning 消耗，是真实的线上截断风险。
        self.assertGreater(REVIEW_MAX_TOKENS, 1024)


if __name__ == "__main__":
    unittest.main()
