"""三层黑板的持久化端口与 PostgreSQL 实现。

`version` 字段支持乐观并发，与订单快照的 `updated_at` CAS 同一套思路。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

LAYERS = ("control", "claims", "facts")


class BlackboardRepository(ABC):
    @abstractmethod
    def load(self, order_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def save(self, order_id: str, snapshot: Dict[str, Any]) -> bool:
        raise NotImplementedError


class PostgresBlackboardRepository(BlackboardRepository):
    _TABLE = "order_blackboard"

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._initialize_schema()

    def _connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def _initialize_schema(self) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._TABLE} (
                    order_id UUID NOT NULL,
                    layer TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value JSONB NOT NULL,
                    version BIGINT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (order_id, layer, key)
                )
                """
            )

    def load(self, order_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"SELECT layer, key, value, version FROM {self._TABLE} WHERE order_id = %s",
                (order_id,),
            )
            rows = cursor.fetchall()
        if not rows:
            return None

        snapshot: Dict[str, Any] = {
            "order_id": order_id,
            "version": max(int(row["version"]) for row in rows),
            "control": {},
            "facts": {},
            "claims": [],
            "disputes": [],
            "verdicts": [],
            "messages": [],
        }
        for row in rows:
            layer = row["layer"]
            value = row["value"]
            if layer == "control":
                snapshot["control"].update(value)
            elif layer == "facts":
                snapshot["facts"].update(value)
            elif layer == "claims":
                snapshot["claims"] = value.get("claims", [])
                snapshot["disputes"] = value.get("disputes", [])
                snapshot["verdicts"] = value.get("verdicts", [])
                snapshot["messages"] = value.get("messages", [])
        return snapshot

    def save(self, order_id: str, snapshot: Dict[str, Any]) -> bool:
        now = datetime.now()
        version = int(snapshot.get("version") or 0)
        payloads = {
            "control": snapshot.get("control") or {},
            "facts": snapshot.get("facts") or {},
            "claims": {
                "claims": snapshot.get("claims") or [],
                "disputes": snapshot.get("disputes") or [],
                "verdicts": snapshot.get("verdicts") or [],
                "messages": snapshot.get("messages") or [],
            },
        }
        with self._connect() as connection, connection.cursor() as cursor:
            for layer, value in payloads.items():
                cursor.execute(
                    f"""
                    INSERT INTO {self._TABLE} (order_id, layer, key, value, version, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (order_id, layer, key) DO UPDATE
                    SET value = EXCLUDED.value, version = EXCLUDED.version,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (order_id, layer, "*", Jsonb(value), version, now),
                )
        return True
