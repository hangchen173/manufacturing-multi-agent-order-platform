"""对抗协议：PROPOSE / CHALLENGE / VERDICT。

这是把“自我确认”彻底修掉的核心机制：

```
① Extractor        PROPOSE(field=quantity, value=1000, evidence=[cell_ref: sheet1!C5])
② GroundingVerifier 读 source_span + claim（不含 Extractor 的推理过程）
     ├─ 能在 sheet1!C5 找到 "1000" → INFORM(verified)
     └─ 找不到 / 找到的是 "100"    → CHALLENGE(反证=[cell_ref: sheet1!C5 = "100"])
③ Supervisor 收到 CHALLENGE：
     ├─ 重试预算未尽 → 重新 REQUEST Extractor(带反证)
     └─ 预算耗尽     → 标记该字段为 disputed，交 Adjudicator
④ Adjudicator 面对 PROPOSE + CHALLENGE：必须显式裁决，并输出理由链；
   disputed 字段一律不得进入 AUTO_APPROVE
```
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from domain.messages import AgentMessage, Evidence, Performative


class AdversarialOutcome(str, Enum):
    ACCEPTED = "accepted"    # 验证通过，主张可晋升
    RETRY = "retry"          # 需要带反证重抽
    DISPUTED = "disputed"    # 无法调和，标记争议交终裁


def classify_verifier_response(response: Optional[AgentMessage]) -> AdversarialOutcome:
    if response is None:
        return AdversarialOutcome.ACCEPTED
    if response.performative == Performative.CHALLENGE:
        return AdversarialOutcome.DISPUTED
    if response.performative == Performative.REFUSE:
        return AdversarialOutcome.DISPUTED
    return AdversarialOutcome.ACCEPTED


def next_action(
    outcome: AdversarialOutcome,
    *,
    retries_left: int,
    disputed_already: bool,
) -> AdversarialOutcome:
    """根据重试预算决定下一步：能重试就重试，否则记为争议。"""
    if outcome == AdversarialOutcome.ACCEPTED:
        return AdversarialOutcome.ACCEPTED
    if retries_left > 0 and not disputed_already:
        return AdversarialOutcome.RETRY
    return AdversarialOutcome.DISPUTED


#: 反馈媒介。线上只使用 "locator"；"natural_language" 仅供新颖性判决实验的对照臂。
FEEDBACK_MODES = ("locator", "natural_language")


def build_counter_evidence_feedback(
    challenges: List[AgentMessage],
    *,
    mode: str = "locator",
) -> str:
    """把挑战的反证整理成可回灌给生产者的反馈。

    `mode="locator"`（默认，即线上行为）
        只回灌**可复现的证据**（locator + 反证值），不回灌验证者的措辞，
        避免生产者被自然语言说服而放弃对原文的核对。

    `mode="natural_language"`
        只回灌「哪一项的哪个字段不一致」这一层措辞，**剔除**单元格坐标、
        工作表名与原文真实值。它与 locator 模式的唯一差异就是反证媒介，
        因此两臂构成单变量对照（见 paper/06_NOVELTY_EXPERIMENT.md）。

    两种模式共用同一条消息列表，且 locator 模式与加入 mode 之前逐字节相同，
    所以 `paper-v1-baseline` 的语义不受影响。
    """
    if mode not in FEEDBACK_MODES:
        raise ValueError(f"未知的反馈模式 {mode!r}，可选 {FEEDBACK_MODES}")

    lines: List[str] = []
    for message in challenges:
        if mode == "natural_language":
            lines.append(f"- {_natural_language_reason(message)}")
            continue
        reason = message.payload.get("reason") or "未说明理由"
        lines.append(f"- {reason}")
        for evidence in message.evidence:
            if not evidence.reproducible:
                continue
            locator = evidence.locator or {}
            position = _describe_locator(locator)
            lines.append(
                f"  · 反证位置 {position}：原文为 {evidence.value!r}"
            )
    return "\n".join(lines)


def _natural_language_reason(message: AgentMessage) -> str:
    """把一条挑战改写成不含定位符与原文值的自然语言措辞。

    只保留「哪一项的哪个字段与原文不一致」——这正是纯自然语言对抗协议
    所能提供的全部信息。`item_index` 指向的是**主张列表**而不是源文档坐标，
    不构成 locator；工作表名、行列号与原文真实值一律不出现在输出中。
    """
    subject = message.subject or {}
    field = subject.get("field") or (message.payload or {}).get("field")
    item_index = subject.get("item_index")
    if item_index is not None and field:
        return f"第 {item_index + 1} 项的 {field} 与原文不一致，请重新核对原订单。"
    if field:
        return f"{field} 与原文不一致，请重新核对原订单。"
    return "上一次抽取结果与原文存在不一致，请重新核对原订单。"


def _describe_locator(locator: Dict[str, Any]) -> str:
    if not locator:
        return "未知位置"
    kind = locator.get("kind")
    if kind == "cell":
        return f"工作表 {locator.get('sheet')} 第 {locator.get('row')} 行第 {locator.get('column')} 列"
    if kind == "page":
        return f"第 {locator.get('page_number')} 页"
    if kind == "span":
        return f"原文片段 {locator.get('text')!r}"
    return str(locator)


def challenge_evidence(
    *,
    subject: str,
    locator: Dict[str, Any],
    expected: Any,
    actual: Any,
) -> List[Evidence]:
    """构造一条可复现的反证：locator 指向原文，value 是原文真实值。"""
    return [Evidence(
        kind="cell_ref" if locator.get("kind") == "cell" else "source_span",
        locator=locator,
        value=actual,
        reproducible=True,
        note=f"{subject} 主张为 {expected!r}，原文为 {actual!r}",
    )]
