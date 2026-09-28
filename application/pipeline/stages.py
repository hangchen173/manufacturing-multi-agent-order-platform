"""任务节点执行器。

从「线性阶段」升级为「节点执行器」：接受一个 `Task`，产出 `AgentMessage`，
并保留原有的诊断落库能力。

固定四步仍是核心语义：**状态前置校验（由 Supervisor 负责）→ 执行 → 诊断记录 →
结果落库**，但节点之间由依赖图而非硬编码顺序连接。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import Semaphore
from time import perf_counter
from typing import Any, Dict, List, Optional

from domain.agent_roles import AgentRole
from domain.exceptions import ExtractionSchemaException
from domain.messages import AgentMessage
from domain.tasks import Task, TaskStatus

LLM_ROLES = {AgentRole.EXTRACTOR, AgentRole.REVIEW_ASSISTANT}


@dataclass
class NodeExecutionResult:
    success: bool
    message: str
    messages: List[AgentMessage] = field(default_factory=list)
    error: Optional[BaseException] = None
    latency_ms: float = 0.0
    usage: Dict[str, int] = field(default_factory=dict)


class TaskNodeExecutor:
    def __init__(
        self,
        agents: Dict[AgentRole, Any],
        *,
        llm_semaphore: Optional[Semaphore] = None,
        order_manager: Any = None,
    ):
        self.agents = agents
        self.llm_semaphore = llm_semaphore or Semaphore(4)
        self.order_manager = order_manager

    def execute(self, task: Task, budget: Any = None) -> NodeExecutionResult:
        agent = self.agents[task.agent]
        is_llm = AgentRole(task.agent) in LLM_ROLES

        task.status = TaskStatus.RUNNING
        task.lease_owner = "supervisor"
        task.attempts += 1

        last_error: Optional[BaseException] = None
        start = perf_counter()

        while True:
            if budget is not None:
                budget.check(is_llm=is_llm)
            if is_llm:
                self.llm_semaphore.acquire()
            retry = False
            try:
                messages = agent.handle(task)
                if budget is not None:
                    budget.spend(tokens=self.tokens_of(messages), is_llm=is_llm)
                task.status = TaskStatus.DONE
                task.lease_owner = None
                result = NodeExecutionResult(
                    success=True,
                    message=f"{task.agent} 节点执行成功",
                    messages=messages,
                    latency_ms=round((perf_counter() - start) * 1000, 2),
                    usage=self.usage_of(messages),
                )
                self._record(task, result)
                return result
            except ExtractionSchemaException as exc:
                # 模型输出结构失败：有界可重试，带错误详情重抽
                last_error = exc
                retry = task.attempts < task.max_attempts
                if retry:
                    task.slice_key = dict(task.slice_key)
                    task.slice_key["feedback"] = str(exc)
                    task.attempts += 1
                else:
                    task.status = TaskStatus.FATAL
            except Exception as exc:  # noqa: BLE001 - 按可重试性分类
                last_error = exc
                retry = task.is_retryable(type(exc).__name__) and task.attempts < task.max_attempts
                if retry:
                    task.attempts += 1
                else:
                    task.status = TaskStatus.FATAL
            finally:
                if is_llm:
                    self.llm_semaphore.release()
            if not retry:
                break

        task.last_error = f"{type(last_error).__name__}: {last_error}"
        task.lease_owner = None
        result = NodeExecutionResult(
            success=False,
            message=f"{task.agent} 节点执行失败: {last_error}",
            error=last_error,
            latency_ms=round((perf_counter() - start) * 1000, 2),
        )
        self._record(task, result)
        return result

    def _record(self, task: Task, result: NodeExecutionResult) -> None:
        if self.order_manager is None:
            return
        self.order_manager.record_stage(task.order_id, f"node:{task.agent}", {
            "task_id": task.task_id,
            "stage": task.stage,
            "attempts": task.attempts,
            "success": result.success,
            "latency_ms": result.latency_ms,
            "usage": result.usage,
            "error": (f"{type(result.error).__name__}: {result.error}"
                      if result.error else None),
        })

    @staticmethod
    def tokens_of(messages: List[AgentMessage]) -> int:
        total = 0
        for message in messages:
            usage = (message.payload or {}).get("usage")
            if isinstance(usage, dict):
                total += int(usage.get("total_tokens") or 0)
        return total

    @staticmethod
    def usage_of(messages: List[AgentMessage]) -> Dict[str, int]:
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
                 "attempted_calls": 0, "reported_calls": 0}
        for message in messages:
            message_usage = (message.payload or {}).get("usage")
            if isinstance(message_usage, dict):
                for key in usage:
                    usage[key] += int(message_usage.get(key) or 0)
        return usage
