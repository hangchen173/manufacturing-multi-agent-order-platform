"""MAD 基线：Du et al. 2023 的多智能体辩论（**自然语言媒介**）。

**为什么它是关键对照**：MAD 是「多智能体 + 交叉检验」这一族里最强的代表。
它的 agent 之间交换的是**完整抽取结果与文字理由**——没有任何可被程序化复核的
定位符。这正是 VEAP 的对照面：两者都有多轮交叉检验，**唯一差别是反证媒介**。

流程（忠实于原文 core loop）：

1. ``N`` 个 agent **独立**抽取（``temperature > 0``，制造分歧）；
2. 重复 ``R`` 轮：每个 agent 看到**其他 agent 的完整结果**，重新核对原订单并修订；
3. 共识：逐字段**多数投票**（平票取首次出现的取值，保证确定性）。

**与 VEAP 的成本差异是本质的**：MAD 需要 ``N × (1 + R)`` 次调用，
且每轮 prompt 都携带全部同伴输出（prompt 长度随 agent 数增长）；
VEAP 的验证者是确定性纯函数，**0 token**。
"""
from __future__ import annotations

import json
from collections import Counter
from time import perf_counter
from typing import Any, Dict, List, Optional, Sequence, Tuple

from config import Config
from evaluation.baselines.base import (
    BaselineLLM,
    BaselineResult,
    base_system_prompt,
    format_instructions,
    order_user_message,
    parse_order,
)

MAD_DEBATE_INSTRUCTION = """下面是其他抽取员对**同一份订单**的抽取结果（JSON）：

{peers}

请对照原订单原文逐字段核对，判断哪些字段存在错误，并输出你**修订后**的完整结果。

要求：
1. 只依据原订单原文判断，不要因为多数人这么写就跟着改；
2. 若你认为自己的原结果正确，原样输出；
3. 严格按上述格式输出完整 JSON。"""


def _key(value: Any) -> Tuple[str, Any]:
    """投票用的等价键。数值按数值比较，其余按规范化文本比较。"""
    from evaluation.metrics import normalize_float, normalize_text

    number = normalize_float(value)
    if number is not None:
        return ("n", round(number, 6))
    return ("s", normalize_text(value))


def majority(values: Sequence[Any]) -> Any:
    """多数投票。平票时取**首次出现**的取值，保证结果不依赖字典顺序。"""
    if not values:
        return None
    keys = [_key(value) for value in values]
    counts = Counter(keys)
    top = max(counts.values())
    for key in keys:
        if counts[key] == top:
            return values[keys.index(key)]
    return values[0]


def _mean_or_none(values: Sequence[Any]) -> Optional[float]:
    numbers = [float(value) for value in values if isinstance(value, (int, float))]
    if not numbers:
        return None
    return sum(numbers) / len(numbers)


class MADBaseline:
    name = "mad"
    label = "MAD（多智能体自然语言辩论）"

    def __init__(
        self,
        config: Config,
        *,
        agents: int = 3,
        rounds: int = 2,
        temperature: float = 0.7,
        **_: Any,
    ):
        if agents < 2:
            raise ValueError("MAD 至少需要 2 个 agent")
        if rounds < 1:
            raise ValueError("MAD 至少需要 1 轮辩论")
        self.agents = agents
        self.rounds = rounds
        self.llm = BaselineLLM(config, temperature=temperature)

    @property
    def model_name(self) -> str:
        return self.llm.model_name

    @property
    def planned_calls(self) -> int:
        """理论调用次数 = N × (1 + R)。实际值以 `BaselineResult.calls` 为准。"""
        return self.agents * (1 + self.rounds)

    # ------------------------------------------------------------------ run
    def run(self, order_text: str) -> BaselineResult:
        system = base_system_prompt().format(format_instructions=format_instructions())
        user = order_user_message(order_text)
        before = self.llm.snapshot()
        calls_before = self.llm.calls
        started = perf_counter()

        answers: List[Optional[Any]] = [self._sample(system, user) for _ in range(self.agents)]
        for _ in range(self.rounds):
            answers = [
                self._revise(system, user, answers, index=index)
                for index in range(self.agents)
            ]

        merged, error = self._consensus(answers)
        return BaselineResult(
            parsed=merged,
            usage=self.llm.delta(before),
            calls=self.llm.calls - calls_before,
            latency_ms=round((perf_counter() - started) * 1000, 2),
            error=error,
        )

    def _sample(self, system: str, user: str) -> Optional[Any]:
        try:
            return parse_order(self.llm.complete(system, user))
        except Exception:  # noqa: BLE001 - 单个 agent 失败不应终止整轮
            return None

    def _revise(
        self, system: str, user: str, answers: List[Optional[Any]], *, index: int
    ) -> Optional[Any]:
        peers = [
            answer.model_dump(mode="json")
            for position, answer in enumerate(answers)
            if position != index and answer is not None
        ]
        if not peers:
            return answers[index]
        prompt = user + "\n\n" + MAD_DEBATE_INSTRUCTION.format(
            peers=json.dumps(peers, ensure_ascii=False, indent=2)
        )
        revised = self._sample(system, prompt)
        # 修订失败时保留上一轮结果，而不是把该 agent 变成弃权——
        # 否则「辩论导致信息丢失」会被记成「辩论效果差」，混淆了两种失败。
        return revised if revised is not None else answers[index]

    # ------------------------------------------------------------------ consensus
    @staticmethod
    def _consensus(answers: List[Optional[Any]]) -> Tuple[Optional[Any], Optional[str]]:
        from domain.models import ParsedOrder

        valid = [answer for answer in answers if answer is not None]
        if not valid:
            return None, "全部 agent 抽取失败"

        items = _merge_items([list(answer.items) for answer in valid])
        confidence = _mean_or_none([answer.parsing_confidence for answer in valid])
        merged = ParsedOrder(
            order_number=majority([answer.order_number for answer in valid]),
            customer_name=majority([answer.customer_name for answer in valid]),
            total_amount=majority([answer.total_amount for answer in valid]),
            items=items,
            parsing_confidence=min(max(confidence if confidence is not None else 1.0, 0.0), 1.0),
            parsing_issues=[],
        )
        return merged, None


def _merge_items(items_lists: List[List[Any]]) -> List[Any]:
    """按**位置**对齐各 agent 的明细行，逐字段多数投票。

    位置对齐的合理性：所有 agent 读的是同一份订单原文，明细行的顺序由原文决定。
    agent 数多于行数或少于行数时，按「最长列表」补齐，缺失位置视为弃权。
    """
    from domain.models import OrderItem

    if not items_lists:
        return []
    longest = max(len(items) for items in items_lists)
    merged: List[Any] = []
    for index in range(longest):
        candidates = [items[index] for items in items_lists if index < len(items)]
        if not candidates:
            continue
        merged.append(
            OrderItem(
                material_name=majority([c.material_name for c in candidates]) or "",
                specification=majority([c.specification for c in candidates]),
                quantity=majority([c.quantity for c in candidates]),
                unit=majority([c.unit for c in candidates]),
                unit_price=majority([c.unit_price for c in candidates]),
                delivery_date=majority([c.delivery_date for c in candidates]),
                confidence_score=_mean_or_none([c.confidence_score for c in candidates]),
            )
        )
    return merged
