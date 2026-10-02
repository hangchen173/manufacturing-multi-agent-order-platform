"""基线方法集合（对照实验用）。

**三条设计约束**（`paper/10_EXPERIMENTS.md` §3）：

- 基线**不得复用 VEAP 的验证逻辑**（`GroundingVerifier` / 对抗协议 / locator 回灌）；
- 基线**必须复用同一套输出模式与评测口径**（`ParsedOrder` / `values_match`）；
- 基线的**抽取提示词与模型必须与 VEAP 抽取器一致**（单变量控制）。

现有基线：

| name | 说明 | 调用次数 |
|---|---|---|
| ``zero_shot`` | 单次调用，无验证（**下界**） | 1 |
| ``mad`` | Du et al. 2023 多智能体自然语言辩论（**最强对手**） | N × (1 + R)，默认 9 |

> 尚未实现（按 `paper/08_SUBMISSION_PLAN.md` §10.3 排在 12 月）：CoT / Self-consistency / Self-refine。
"""
from evaluation.baselines.base import (
    BaselineLLM,
    BaselineResult,
    base_system_prompt,
    format_instructions,
    order_user_message,
    parse_order,
)
from evaluation.baselines.mad import MADBaseline, majority
from evaluation.baselines.zero_shot import ZeroShotBaseline

BASELINES = {
    ZeroShotBaseline.name: ZeroShotBaseline,
    MADBaseline.name: MADBaseline,
}

#: 比较脚本默认跑的方法顺序（由弱到强，便于阅读结果）。
DEFAULT_METHOD_ORDER = ("zero_shot", "mad")

__all__ = [
    "BASELINES",
    "DEFAULT_METHOD_ORDER",
    "BaselineLLM",
    "BaselineResult",
    "MADBaseline",
    "ZeroShotBaseline",
    "base_system_prompt",
    "format_instructions",
    "majority",
    "order_user_message",
    "parse_order",
]
