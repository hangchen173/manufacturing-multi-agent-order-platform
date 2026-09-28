"""任务与依赖图模型。

订单处理被编译成一张 DAG，而不是固定顺序的线性阶段。每个 Task 是一个
近似纯函数调用的执行单元：`(context_slice) -> messages`。
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    BLOCKED = "blocked"      # 依赖未满足
    READY = "ready"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"        # 可重试
    FATAL = "fatal"          # 不可重试
    CANCELLED = "cancelled"


RETRYABLE_ERRORS = frozenset({
    "APITimeoutError",
    "APIConnectionError",
    "RateLimitError",
    "InternalServerError",
    "TimeoutError",
    "ConnectionError",
    "VectorStoreException",
    # 输出被 max_tokens 截断属容量问题：可重试，且重试时不带结构反馈。
    "ModelTruncationException",
})


class Task(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    order_id: str
    agent: str
    stage: str = Field(description="所属阶段分组：parse / match / risk / adjudicate / assist")
    slice_key: Dict[str, Any] = Field(default_factory=dict, description="上下文切片标识")
    depends_on: List[str] = Field(default_factory=list)
    priority: int = Field(default=0, description="数值越大越先执行")
    attempts: int = Field(default=0)
    max_attempts: int = Field(default=2)
    deadline_ms: Optional[int] = Field(default=None)
    status: TaskStatus = Field(default=TaskStatus.BLOCKED)
    lease_owner: Optional[str] = Field(default=None)
    lease_expires_at: Optional[datetime] = Field(default=None)
    last_error: Optional[str] = Field(default=None)
    payload: Dict[str, Any] = Field(default_factory=dict, description="任务输入（如重试反馈）")

    def is_retryable(self, error_type: str) -> bool:
        return error_type in RETRYABLE_ERRORS


class TaskGraph(BaseModel):
    """一张订单的任务依赖图。只有 Supervisor 能创建和修改。"""

    order_id: str
    tasks: Dict[str, Task] = Field(default_factory=dict)

    def add(self, task: Task) -> Task:
        self.tasks[task.task_id] = task
        return task

    def get(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def by_stage(self, stage: str) -> List[Task]:
        return [task for task in self.tasks.values() if task.stage == stage]

    def refresh_ready(self) -> List[Task]:
        """把依赖已满足的 BLOCKED 任务提升为 READY，返回就绪任务。"""
        ready: List[Task] = []
        for task in self.tasks.values():
            if task.status in {TaskStatus.READY, TaskStatus.RUNNING}:
                ready.append(task)
                continue
            if task.status != TaskStatus.BLOCKED:
                continue
            if all(
                self.tasks[dep].status == TaskStatus.DONE
                for dep in task.depends_on
                if dep in self.tasks
            ):
                task.status = TaskStatus.READY
                ready.append(task)
        return ready

    def has_unfinished(self) -> bool:
        return any(
            task.status in {TaskStatus.BLOCKED, TaskStatus.READY, TaskStatus.RUNNING, TaskStatus.FAILED}
            for task in self.tasks.values()
        )

    def failed_tasks(self) -> List[Task]:
        return [task for task in self.tasks.values() if task.status in {TaskStatus.FAILED, TaskStatus.FATAL}]

    def to_snapshot(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "tasks": {task_id: task.model_dump(mode="json") for task_id, task in self.tasks.items()},
        }

    @classmethod
    def from_snapshot(cls, payload: Dict[str, Any]) -> "TaskGraph":
        graph = cls(order_id=payload["order_id"])
        for task_id, task_payload in (payload.get("tasks") or {}).items():
            graph.tasks[task_id] = Task.model_validate(task_payload)
        return graph
