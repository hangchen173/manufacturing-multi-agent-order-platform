"""infrastructure 的仓储适配器。

端口（ABC）定义在 `application/ports/repositories.py`，本包只提供实现。
"""
from infrastructure.repositories.blackboard_repository import PostgresBlackboardRepository
from infrastructure.repositories.message_repository import PostgresMessageRepository
from infrastructure.repositories.order_repository import PostgresOrderRepository
from infrastructure.repositories.task_repository import PostgresTaskRepository

__all__ = [
    "PostgresOrderRepository",
    "PostgresBlackboardRepository",
    "PostgresTaskRepository",
    "PostgresMessageRepository",
]
