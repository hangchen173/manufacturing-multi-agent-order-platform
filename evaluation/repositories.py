from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any, Dict

from infrastructure.repositories import OrderRepository


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
