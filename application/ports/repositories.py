"""仓储端口：由 infrastructure 实现，application 只依赖这些抽象。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, NamedTuple, Optional

from domain.messages import AgentMessage


class BlackboardRepository(ABC):
    @abstractmethod
    def load(self, order_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def save(self, order_id: str, snapshot: Dict[str, Any]) -> bool:
        raise NotImplementedError


class TaskRepository(ABC):
    @abstractmethod
    def load(self, order_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def save(self, order_id: str, snapshot: Dict[str, Any]) -> bool:
        raise NotImplementedError

    @abstractmethod
    def claim_lease(self, task_id: str, owner: str, ttl_seconds: int) -> bool:
        raise NotImplementedError

    @abstractmethod
    def recover_expired(self, now: Optional[datetime] = None) -> List[str]:
        raise NotImplementedError


class MessageRepository(ABC):
    @abstractmethod
    def append(self, order_id: str, messages: List[AgentMessage]) -> int:
        raise NotImplementedError

    @abstractmethod
    def list_for_order(self, order_id: str) -> List[Dict[str, Any]]:
        raise NotImplementedError


class CollaborationRepositories(NamedTuple):
    """与某个 OrderRepository 同源的一组协作仓储。"""

    blackboard: BlackboardRepository
    tasks: TaskRepository
    messages: MessageRepository


class OrderRepository(ABC):
    @abstractmethod
    def load_all(self, archived: bool = False) -> Dict[str, Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get(self, order_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def create(self, snapshot: Dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def update(self, snapshot: Dict[str, Any], expected_updated_at: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def delete(self, order_id: str, expected_updated_at: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def load_index(self, archived: bool = False) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def archive(self, order_id: str, expected_updated_at: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def collaboration_repositories(self) -> CollaborationRepositories:
        """返回与本仓储同源（同后端、同连接目标）的协作仓储。

        由适配器自行实现，使「四个仓储必须同源」成为结构性保证，而不是
        调用方需要记住的约定。
        """
        raise NotImplementedError
