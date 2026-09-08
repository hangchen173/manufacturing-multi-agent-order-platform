from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from infrastructure.repositories import OrderRepository


class InMemoryOrderRepository(OrderRepository):
    def __init__(self) -> None:
        self.active: Dict[str, Dict[str, Any]] = {}
        self.archived: Dict[str, Dict[str, Any]] = {}

    def load_all(self, archived: bool = False) -> Dict[str, Dict[str, Any]]:
        return deepcopy(self.archived if archived else self.active)

    def save_all(self, snapshots: Dict[str, Dict[str, Any]], archived: bool = False) -> None:
        if archived:
            self.archived = deepcopy(snapshots)
        else:
            self.active = deepcopy(snapshots)

    def load_index(self, archived: bool = False) -> Dict[str, Any]:
        snapshots = self.archived if archived else self.active
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

    def archive_orders(
        self,
        orders_to_archive: Dict[str, Dict[str, Any]],
        active_orders: Dict[str, Dict[str, Any]],
    ) -> None:
        self.archived.update(deepcopy(orders_to_archive))
        self.active = deepcopy(active_orders)
