"""预算与熔断。

把“无限反思循环”从架构上排除：订单级 token/调用预算 + 任务级超时；
超限即 ESCALATE 转人工，而不是静默通过或继续重试。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Dict, Optional


class BudgetExhausted(Exception):
    def __init__(self, reason: str, snapshot: Dict[str, Any]):
        self.reason = reason
        self.snapshot = snapshot
        super().__init__(f"预算耗尽: {reason}")


@dataclass
class Budget:
    """订单级预算。Supervisor 持有，所有 LLM 任务在执行前后都要记账。"""

    order_id: str
    max_tokens: int = 200_000
    max_llm_calls: int = 12
    max_wall_ms: float = 300_000.0
    tokens_used: int = 0
    llm_calls: int = 0
    started_at: float = field(default_factory=perf_counter)
    escalations: int = 0

    def elapsed_ms(self) -> float:
        return (perf_counter() - self.started_at) * 1000.0

    def snapshot(self) -> Dict[str, Any]:
        return {
            "tokens_used": self.tokens_used,
            "max_tokens": self.max_tokens,
            "llm_calls": self.llm_calls,
            "max_llm_calls": self.max_llm_calls,
            "elapsed_ms": round(self.elapsed_ms(), 2),
            "max_wall_ms": self.max_wall_ms,
        }

    def check(self, *, is_llm: bool) -> None:
        if self.tokens_used > self.max_tokens:
            raise BudgetExhausted("token 预算耗尽", self.snapshot())
        if is_llm and self.llm_calls >= self.max_llm_calls:
            raise BudgetExhausted("模型调用次数预算耗尽", self.snapshot())
        if self.elapsed_ms() > self.max_wall_ms:
            raise BudgetExhausted("订单处理超时", self.snapshot())

    def spend(self, *, tokens: int = 0, is_llm: bool = False) -> None:
        self.tokens_used += max(0, int(tokens))
        if is_llm:
            self.llm_calls += 1

    @classmethod
    def from_snapshot(cls, payload: Dict[str, Any], order_id: str) -> "Budget":
        budget = cls(order_id=order_id)
        budget.tokens_used = int(payload.get("tokens_used") or 0)
        budget.llm_calls = int(payload.get("llm_calls") or 0)
        if payload.get("max_tokens"):
            budget.max_tokens = int(payload["max_tokens"])
        if payload.get("max_llm_calls"):
            budget.max_llm_calls = int(payload["max_llm_calls"])
        return budget


class RetryBudget:
    """任务级重试计数，避免无界重试。"""

    def __init__(self, default_max_attempts: int = 2):
        self.default_max_attempts = default_max_attempts
        self._attempts: Dict[str, int] = {}

    def attempts(self, task_id: str) -> int:
        return self._attempts.get(task_id, 0)

    def record(self, task_id: str) -> int:
        self._attempts[task_id] = self.attempts(task_id) + 1
        return self._attempts[task_id]

    def can_retry(self, task_id: str, max_attempts: Optional[int] = None) -> bool:
        limit = max_attempts or self.default_max_attempts
        return self.attempts(task_id) < limit
