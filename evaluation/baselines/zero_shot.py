"""零样本基线：单次调用，无任何验证环节。

它是**下界**——若被测系统连它都赢不了，说明整个对抗验证机制没有价值。
它同时定义了成本基准：**1 次调用**。
"""
from __future__ import annotations

from time import perf_counter
from typing import Any

from config import Config
from evaluation.baselines.base import (
    BaselineLLM,
    BaselineResult,
    base_system_prompt,
    format_instructions,
    order_user_message,
    parse_order,
)


class ZeroShotBaseline:
    name = "zero_shot"
    label = "零样本（单次调用，无验证）"

    def __init__(self, config: Config, *, temperature: float = 0.0, **_: Any):
        self.llm = BaselineLLM(config, temperature=temperature)

    @property
    def model_name(self) -> str:
        return self.llm.model_name

    def run(self, order_text: str) -> BaselineResult:
        system = base_system_prompt().format(format_instructions=format_instructions())
        before = self.llm.snapshot()
        calls_before = self.llm.calls
        started = perf_counter()

        parsed, error = None, None
        try:
            content = self.llm.complete(system, order_user_message(order_text))
            parsed = parse_order(content)
        except Exception as exc:  # noqa: BLE001 - 失败样本必须记录，不能中断整轮
            error = f"{type(exc).__name__}: {exc}"

        return BaselineResult(
            parsed=parsed,
            usage=self.llm.delta(before),
            calls=self.llm.calls - calls_before,
            latency_ms=round((perf_counter() - started) * 1000, 2),
            error=error,
        )
