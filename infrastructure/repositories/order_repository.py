from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


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


class PostgresOrderRepository(OrderRepository):
    """Persists complete order snapshots while keeping queryable order metadata."""

    _ACTIVE_TABLE = "orders"
    _ARCHIVE_TABLE = "archived_orders"

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._initialize_schema()

    def _connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def _initialize_schema(self) -> None:
        for table in (self._ACTIVE_TABLE, self._ARCHIVE_TABLE):
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                        order_id UUID PRIMARY KEY,
                        status TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL,
                        document_type TEXT,
                        snapshot JSONB NOT NULL
                    )
                    """
                )
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS {table}_created_at_idx ON {table} (created_at DESC)"
                )
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS {table}_status_idx ON {table} (status)"
                )

    def _table(self, archived: bool) -> str:
        return self._ARCHIVE_TABLE if archived else self._ACTIVE_TABLE

    def load_all(self, archived: bool = False) -> Dict[str, Dict[str, Any]]:
        table = self._table(archived)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(f"SELECT order_id::text, snapshot FROM {table}")
            return {row["order_id"]: row["snapshot"] for row in cursor.fetchall()}

    def get(self, order_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT snapshot FROM orders WHERE order_id = %s", (order_id,))
            row = cursor.fetchone()
            return row["snapshot"] if row else None

    def create(self, snapshot: Dict[str, Any]) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO orders
                   (order_id, status, created_at, updated_at, document_type, snapshot)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (snapshot["order_id"], snapshot["status"], snapshot["created_at"],
                 snapshot["updated_at"], snapshot.get("document_type"), Jsonb(snapshot)),
            )

    def update(self, snapshot: Dict[str, Any], expected_updated_at: str) -> bool:
        # Compare the exact snapshot token to avoid timezone conversion in the CAS check.
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """UPDATE orders SET status = %s, updated_at = %s, snapshot = %s
                   WHERE order_id = %s AND snapshot->>'updated_at' = %s""",
                (snapshot["status"], snapshot["updated_at"], Jsonb(snapshot),
                 snapshot["order_id"], expected_updated_at),
            )
            return cursor.rowcount == 1

    def delete(self, order_id: str, expected_updated_at: str) -> bool:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM orders WHERE order_id = %s AND snapshot->>'updated_at' = %s",
                (order_id, expected_updated_at),
            )
            return cursor.rowcount == 1

    def load_index(self, archived: bool = False) -> Dict[str, Any]:
        table = self._table(archived)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"SELECT status, COUNT(*) AS count FROM {table} GROUP BY status"
            )
            by_status = {row["status"]: row["count"] for row in cursor.fetchall()}
            cursor.execute(
                f"SELECT COALESCE(document_type, 'unknown') AS document_type, COUNT(*) AS count "
                f"FROM {table} GROUP BY document_type"
            )
            by_document_type = {row["document_type"]: row["count"] for row in cursor.fetchall()}
        return {
            "total_count": sum(by_status.values()),
            "by_status": by_status,
            "by_document_type": by_document_type,
        }

    def archive(self, order_id: str, expected_updated_at: str) -> bool:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """WITH moved AS (
                     DELETE FROM orders
                     WHERE order_id = %s AND snapshot->>'updated_at' = %s
                     RETURNING order_id, status, created_at, updated_at, document_type, snapshot
                   ) INSERT INTO archived_orders
                     (order_id, status, created_at, updated_at, document_type, snapshot)
                     SELECT * FROM moved""",
                (order_id, expected_updated_at),
            )
            return cursor.rowcount == 1
