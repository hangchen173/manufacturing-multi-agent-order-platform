"""协作消息的持久化端口与 PostgreSQL 实现（可审计轨迹，只追加）。

有了 `agent_messages`，才能回答“这个决策是谁提出的、谁反对过、依据是什么”。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from domain.messages import AgentMessage


class MessageRepository(ABC):
    @abstractmethod
    def append(self, order_id: str, messages: List[AgentMessage]) -> int:
        raise NotImplementedError

    @abstractmethod
    def list_for_order(self, order_id: str) -> List[Dict[str, Any]]:
        raise NotImplementedError


class PostgresMessageRepository(MessageRepository):
    _TABLE = "agent_messages"

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
                    message_id TEXT PRIMARY KEY,
                    order_id UUID NOT NULL,
                    task_id TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    recipient TEXT,
                    performative TEXT NOT NULL,
                    in_reply_to TEXT,
                    subject JSONB NOT NULL,
                    payload JSONB NOT NULL,
                    evidence JSONB NOT NULL,
                    cost JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS {self._TABLE}_order_idx "
                f"ON {self._TABLE} (order_id, created_at)"
            )

    def append(self, order_id: str, messages: List[AgentMessage]) -> int:
        if not messages:
            return 0
        now = datetime.now()
        written = 0
        with self._connect() as connection, connection.cursor() as cursor:
            for message in messages:
                cursor.execute(
                    f"""
                    INSERT INTO {self._TABLE}
                    (message_id, order_id, task_id, sender, recipient, performative,
                     in_reply_to, subject, payload, evidence, cost, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (message_id) DO NOTHING
                    """,
                    (
                        message.message_id, order_id, message.task_id, message.sender,
                        message.recipient, message.performative.value, message.in_reply_to,
                        Jsonb(message.subject), Jsonb(message.payload),
                        Jsonb([item.model_dump(mode="json") for item in message.evidence]),
                        Jsonb(message.cost), now,
                    ),
                )
                written += cursor.rowcount
        return written

    def list_for_order(self, order_id: str) -> List[Dict[str, Any]]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"SELECT * FROM {self._TABLE} WHERE order_id = %s ORDER BY created_at, message_id",
                (order_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
