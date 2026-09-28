"""内存仓储实现：单元测试与评测使用，语义与 PostgreSQL 实现一致。"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from threading import RLock
from typing import Any, Dict, List, Optional

from domain.messages import AgentMessage
from domain.tasks import TaskStatus
from infrastructure.repositories.blackboard_repository import BlackboardRepository
from infrastructure.repositories.message_repository import MessageRepository
from infrastructure.repositories.order_repository import OrderRepository
from infrastructure.repositories.task_repository import TaskRepository


class InMemoryOrderRepository(OrderRepository):
    def __init__(self) -> None:
        self.active: Dict[str, Dict[str, Any]] = {}
        self.archived: Dict[str, Dict[str, Any]] = {}
        self._lock = RLock()

    def load_all(self, archived: bool = False) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return deepcopy(self.archived if archived else self.active)

    def get(self, order_id):
        with self._lock:
            return deepcopy(self.active.get(order_id))

    def create(self, snapshot):
        with self._lock:
            if snapshot["order_id"] in self.active:
                raise ValueError("Order already exists")
            self.active[snapshot["order_id"]] = deepcopy(snapshot)

    def update(self, snapshot, expected_updated_at):
        with self._lock:
            current = self.active.get(snapshot["order_id"])
            if current is None or current["updated_at"] != expected_updated_at:
                return False
            self.active[snapshot["order_id"]] = deepcopy(snapshot)
            return True

    def delete(self, order_id, expected_updated_at):
        with self._lock:
            current = self.active.get(order_id)
            if current is None or current["updated_at"] != expected_updated_at:
                return False
            del self.active[order_id]
            return True

    def load_index(self, archived: bool = False) -> Dict[str, Any]:
        snapshots = self.load_all(archived)
        by_status: Dict[str, int] = {}
        by_document_type: Dict[str, int] = {}
        for snapshot in snapshots.values():
            status = snapshot["status"]
            by_status[status] = by_status.get(status, 0) + 1
            document_type = snapshot.get("document_type") or "unknown"
            by_document_type[document_type] = by_document_type.get(document_type, 0) + 1
        return {
            "total_count": len(snapshots),
            "by_status": by_status,
            "by_document_type": by_document_type,
        }

    def archive(self, order_id, expected_updated_at):
        with self._lock:
            current = self.active.get(order_id)
            if current is None or current["updated_at"] != expected_updated_at:
                return False
            if order_id in self.archived:
                raise ValueError("Order already archived")
            self.archived[order_id] = self.active.pop(order_id)
            return True


class InMemoryBlackboardRepository(BlackboardRepository):
    def __init__(self) -> None:
        self.store: Dict[str, Dict[str, Any]] = {}
        self._lock = RLock()

    def load(self, order_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return deepcopy(self.store.get(order_id))

    def save(self, order_id: str, snapshot: Dict[str, Any]) -> bool:
        with self._lock:
            self.store[order_id] = deepcopy(snapshot)
            return True


class InMemoryTaskRepository(TaskRepository):
    def __init__(self) -> None:
        self.store: Dict[str, Dict[str, Any]] = {}
        self._lock = RLock()

    def load(self, order_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return deepcopy(self.store.get(order_id))

    def save(self, order_id: str, snapshot: Dict[str, Any]) -> bool:
        with self._lock:
            self.store[order_id] = deepcopy(snapshot)
            return True

    def claim_lease(self, task_id: str, owner: str, ttl_seconds: int) -> bool:
        now = datetime.now()
        with self._lock:
            for snapshot in self.store.values():
                task = (snapshot.get("tasks") or {}).get(task_id)
                if task is None:
                    continue
                expires = task.get("lease_expires_at")
                if expires and datetime.fromisoformat(expires) > now and task.get("lease_owner"):
                    return False
                task["lease_owner"] = owner
                task["lease_expires_at"] = (now + timedelta(seconds=ttl_seconds)).isoformat()
                task["status"] = TaskStatus.RUNNING.value
                return True
        return False

    def recover_expired(self, now: Optional[datetime] = None) -> List[str]:
        now = now or datetime.now()
        recovered: List[str] = []
        with self._lock:
            for order_id, snapshot in self.store.items():
                for task in (snapshot.get("tasks") or {}).values():
                    expires = task.get("lease_expires_at")
                    if task.get("status") != TaskStatus.RUNNING.value or not expires:
                        continue
                    if datetime.fromisoformat(expires) < now:
                        task["status"] = TaskStatus.READY.value
                        task["lease_owner"] = None
                        task["lease_expires_at"] = None
                        task["last_error"] = "租约过期，已重新入队"
                        recovered.append(order_id)
        return recovered


class InMemoryMessageRepository(MessageRepository):
    def __init__(self) -> None:
        self.rows: Dict[str, Dict[str, Any]] = {}
        self._lock = RLock()

    def append(self, order_id: str, messages: List[AgentMessage]) -> int:
        written = 0
        with self._lock:
            for message in messages:
                if message.message_id in self.rows:
                    continue
                self.rows[message.message_id] = {
                    "message_id": message.message_id,
                    "order_id": order_id,
                    "task_id": message.task_id,
                    "sender": message.sender,
                    "recipient": message.recipient,
                    "performative": message.performative.value,
                    "in_reply_to": message.in_reply_to,
                    "subject": deepcopy(message.subject),
                    "payload": deepcopy(message.payload),
                    "evidence": [item.model_dump(mode="json") for item in message.evidence],
                    "cost": deepcopy(message.cost),
                }
                written += 1
        return written

    def list_for_order(self, order_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                deepcopy(row) for row in self.rows.values() if row["order_id"] == order_id
            ]
