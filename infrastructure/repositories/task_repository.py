"""任务队列持久化端口与 PostgreSQL 实现。

复用现有 PostgreSQL 实现一个有边界的任务队列，不引入新中间件。
支持租约（lease）与过期任务回收，使进程被杀后任务不会永久卡在 RUNNING。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from domain.tasks import TaskStatus


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


class PostgresTaskRepository(TaskRepository):
    _TABLE = "agent_tasks"

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
                    task_id TEXT PRIMARY KEY,
                    order_id UUID NOT NULL,
                    agent TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    slice_key JSONB NOT NULL,
                    status TEXT NOT NULL,
                    depends_on JSONB NOT NULL,
                    attempts INT NOT NULL,
                    max_attempts INT NOT NULL,
                    priority INT NOT NULL,
                    deadline_ms INT,
                    lease_owner TEXT,
                    lease_expires_at TIMESTAMPTZ,
                    last_error TEXT,
                    payload JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS {self._TABLE}_order_idx ON {self._TABLE} (order_id)"
            )
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS {self._TABLE}_lease_idx ON {self._TABLE} (lease_expires_at)"
            )

    def load(self, order_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"SELECT * FROM {self._TABLE} WHERE order_id = %s", (order_id,)
            )
            rows = cursor.fetchall()
        if not rows:
            return None
        tasks = {}
        for row in rows:
            tasks[row["task_id"]] = {
                "task_id": row["task_id"],
                "order_id": str(row["order_id"]),
                "agent": row["agent"],
                "stage": row["stage"],
                "slice_key": row["slice_key"],
                "depends_on": row["depends_on"],
                "priority": row["priority"],
                "attempts": row["attempts"],
                "max_attempts": row["max_attempts"],
                "deadline_ms": row["deadline_ms"],
                "status": row["status"],
                "lease_owner": row["lease_owner"],
                "lease_expires_at": row["lease_expires_at"].isoformat()
                if row["lease_expires_at"] else None,
                "last_error": row["last_error"],
                "payload": row["payload"],
            }
        return {"order_id": order_id, "tasks": tasks}

    def save(self, order_id: str, snapshot: Dict[str, Any]) -> bool:
        now = datetime.now()
        tasks = (snapshot.get("tasks") or {}).values()
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {self._TABLE} WHERE order_id = %s", (order_id,))
            for task in tasks:
                cursor.execute(
                    f"""
                    INSERT INTO {self._TABLE}
                    (task_id, order_id, agent, stage, slice_key, status, depends_on, attempts,
                     max_attempts, priority, deadline_ms, lease_owner, lease_expires_at,
                     last_error, payload, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        task["task_id"], task["order_id"], task["agent"], task["stage"],
                        Jsonb(task.get("slice_key") or {}), task["status"],
                        Jsonb(task.get("depends_on") or []), int(task.get("attempts") or 0),
                        int(task.get("max_attempts") or 2), int(task.get("priority") or 0),
                        task.get("deadline_ms"), task.get("lease_owner"),
                        _parse_dt(task.get("lease_expires_at")), task.get("last_error"),
                        Jsonb(task.get("payload") or {}), now,
                    ),
                )
        return True

    def claim_lease(self, task_id: str, owner: str, ttl_seconds: int) -> bool:
        """至少一次执行 + 租约：只有未持有有效租约时才能领取。"""
        now = datetime.now()
        expires = now + timedelta(seconds=ttl_seconds)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE {self._TABLE}
                SET lease_owner = %s, lease_expires_at = %s, status = %s, updated_at = %s
                WHERE task_id = %s
                  AND (lease_owner IS NULL OR lease_expires_at IS NULL OR lease_expires_at < %s)
                """,
                (owner, expires, TaskStatus.RUNNING.value, now, task_id, now),
            )
            return cursor.rowcount == 1

    def recover_expired(self, now: Optional[datetime] = None) -> List[str]:
        """把租约过期的 RUNNING 任务退回 READY，使进程重启后可恢复。"""
        now = now or datetime.now()
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE {self._TABLE}
                SET status = %s, lease_owner = NULL, lease_expires_at = NULL,
                    last_error = %s, updated_at = %s
                WHERE status = %s AND lease_expires_at IS NOT NULL AND lease_expires_at < %s
                RETURNING task_id, order_id::text
                """,
                (TaskStatus.READY.value, "租约过期，已重新入队", now,
                 TaskStatus.RUNNING.value, now),
            )
            return [row["order_id"] for row in cursor.fetchall()]


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))
