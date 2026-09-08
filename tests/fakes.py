from copy import deepcopy

from infrastructure.repositories import OrderRepository


class InMemoryOrderRepository(OrderRepository):
    def __init__(self):
        self.active = {}
        self.archived = {}

    def load_all(self, archived=False):
        return deepcopy(self.archived if archived else self.active)

    def save_all(self, snapshots, archived=False):
        if archived:
            self.archived = deepcopy(snapshots)
        else:
            self.active = deepcopy(snapshots)

    def load_index(self, archived=False):
        snapshots = self.archived if archived else self.active
        by_status = {}
        by_document_type = {}
        for snapshot in snapshots.values():
            by_status[snapshot["status"]] = by_status.get(snapshot["status"], 0) + 1
            document_type = snapshot.get("document_type") or "unknown"
            by_document_type[document_type] = by_document_type.get(document_type, 0) + 1
        return {
            "total_count": len(snapshots),
            "by_status": by_status,
            "by_document_type": by_document_type,
        }

    def archive_orders(self, orders_to_archive, active_orders):
        self.archived.update(deepcopy(orders_to_archive))
        self.active = deepcopy(active_orders)
