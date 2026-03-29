import json
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict


class OrderRepository(ABC):
    @abstractmethod
    def load_all(self, archived: bool = False) -> Dict[str, Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def save_all(self, snapshots: Dict[str, Dict[str, Any]], archived: bool = False) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_index(self, archived: bool = False) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def archive_orders(
        self,
        orders_to_archive: Dict[str, Dict[str, Any]],
        active_orders: Dict[str, Dict[str, Any]],
    ) -> None:
        raise NotImplementedError


class JsonOrderRepository(OrderRepository):
    def __init__(self, store_path: str, archive_path: str):
        self.store_path = store_path
        self.archive_path = archive_path

    def load_all(self, archived: bool = False) -> Dict[str, Dict[str, Any]]:
        payload = self._load_payload(archived=archived)
        orders = payload.get("orders", {})
        return orders if isinstance(orders, dict) else {}

    def save_all(self, snapshots: Dict[str, Dict[str, Any]], archived: bool = False) -> None:
        payload = {
            "version": 2,
            "updated_at": datetime.now().isoformat(),
            "indexes": self._build_indexes(snapshots),
            "orders": snapshots,
        }
        self._write_payload(payload, archived=archived)

    def load_index(self, archived: bool = False) -> Dict[str, Any]:
        payload = self._load_payload(archived=archived)
        indexes = payload.get("indexes")
        if isinstance(indexes, dict):
            return indexes
        return self._build_indexes(payload.get("orders", {}))

    def archive_orders(
        self,
        orders_to_archive: Dict[str, Dict[str, Any]],
        active_orders: Dict[str, Dict[str, Any]],
    ) -> None:
        archived_orders = self.load_all(archived=True)
        archived_orders.update(orders_to_archive)
        self.save_all(active_orders, archived=False)
        self.save_all(archived_orders, archived=True)

    def _target_path(self, archived: bool = False) -> str:
        return self.archive_path if archived else self.store_path

    def _load_payload(self, archived: bool = False) -> Dict[str, Any]:
        target_path = self._target_path(archived=archived)
        if not os.path.exists(target_path):
            return {}

        try:
            with open(target_path, "r", encoding="utf-8") as file:
                payload = json.load(file)
        except json.JSONDecodeError:
            return {}

        if not isinstance(payload, dict):
            return {}

        if "orders" in payload:
            return payload

        # Backward compatibility with older plain order-map format.
        return {
            "version": 1,
            "updated_at": None,
            "indexes": self._build_indexes(payload),
            "orders": payload,
        }

    def _write_payload(self, payload: Dict[str, Any], archived: bool = False) -> None:
        target_path = self._target_path(archived=archived)
        directory = os.path.dirname(target_path)
        if directory:
            os.makedirs(directory, exist_ok=True)

        temp_path = f"{target_path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)

        os.replace(temp_path, target_path)

    def _build_indexes(self, snapshots: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        by_status: Dict[str, list] = {}
        by_document_type: Dict[str, list] = {}

        for order_id, snapshot in snapshots.items():
            status = snapshot.get("status", "unknown")
            document_type = snapshot.get("document_type") or "unknown"

            by_status.setdefault(status, []).append(order_id)
            by_document_type.setdefault(document_type, []).append(order_id)

        for values in by_status.values():
            values.sort()
        for values in by_document_type.values():
            values.sort()

        return {
            "total_count": len(snapshots),
            "by_status": by_status,
            "by_document_type": by_document_type,
            "generated_at": datetime.now().isoformat(),
        }
