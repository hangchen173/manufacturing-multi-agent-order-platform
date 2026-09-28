"""协作 Agent 基类。

与旧的 `BaseAgent` 不同，协作 Agent 不接收任意 dict、不返回任意 dict，也不
持有其他 Agent 的引用。它的语义是**近似纯函数**：

```
handle(task) -> list[AgentMessage]
```

输入是黑板按角色裁剪后的切片，输出是结构化消息。这样才可重试、可重放、可单测。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from domain.agent_roles import (
    AgentRole,
    FORBIDDEN_KEYS,
    READABLE_KEYS,
    PermissionViolation,
    assert_performative_allowed,
)
from domain.messages import AgentMessage, Evidence, Performative, make_message
from domain.tasks import Task


class CollaborativeAgent(ABC):
    role: AgentRole

    def __init__(self, blackboard: Any = None, budget: Any = None, config: Any = None):
        self.blackboard = blackboard
        self.budget = budget
        self.config = config
        self.name = self.__class__.__name__
        self.logger = logging.getLogger(self.name)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    # ---------------------------------------------------------------- 权限声明
    @property
    def readable(self) -> frozenset:
        return READABLE_KEYS.get(self.role, frozenset())

    @property
    def forbidden(self) -> frozenset:
        return FORBIDDEN_KEYS.get(self.role, frozenset())

    # ---------------------------------------------------------------- 执行契约
    @abstractmethod
    def handle(self, task: Task) -> List[AgentMessage]:
        """纯函数语义：(上下文切片) -> (消息)。禁止调用其他 Agent。"""

    def read_slice(self, task: Task) -> Dict[str, Any]:
        if self.blackboard is None:
            return {}
        return self.blackboard.slice_for(self.role, task.slice_key)

    # ---------------------------------------------------------------- 消息构造
    def emit(
        self,
        task: Task,
        performative: Performative,
        *,
        subject: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        evidence: Optional[List[Evidence]] = None,
        recipient: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        cost: Optional[Dict[str, Any]] = None,
    ) -> AgentMessage:
        assert_performative_allowed(self.role, performative)
        return make_message(
            order_id=task.order_id,
            task_id=task.task_id,
            sender=self.role.value,
            performative=performative,
            subject=subject,
            payload=payload,
            evidence=evidence,
            recipient=recipient,
            in_reply_to=in_reply_to,
            cost=cost,
        )

    def claim_message(
        self,
        task: Task,
        *,
        subject: str,
        value: Any,
        basis: str,
        evidence: Optional[List[Evidence]] = None,
        confidence: Optional[float] = None,
    ) -> AgentMessage:
        return self.emit(
            task,
            Performative.PROPOSE,
            subject={"claim_subject": subject},
            payload={"claim": {
                "subject": subject,
                "value": value,
                "basis": basis,
                "confidence": confidence,
            }},
            evidence=evidence,
        )

    # ---------------------------------------------------------------- 日志
    def log_info(self, message: str) -> None:
        self.logger.info(message)

    def log_warning(self, message: str) -> None:
        self.logger.warning(message)

    def log_error(self, message: str) -> None:
        self.logger.error(message)


def assert_no_agent_references(module_globals: Dict[str, Any], role: AgentRole) -> None:
    """V1 拓扑断言的运行期辅助：确认本模块没有持有其他 Agent 实例。"""
    for name, value in module_globals.items():
        if name.startswith("_"):
            continue
        if isinstance(value, CollaborativeAgent) and getattr(value, "role", None) != role:
            raise PermissionViolation(role, f"模块持有其他 Agent 引用: {name}")
