"""结构化协作消息契约。

多 Agent 之间不自由对话，只交换受限的、可落库、可审计的结构化消息。
一条消息由三部分组成：语用行为（performative）、针对的主体（subject）、
载荷（payload）与证据（evidence）。

`evidence.locator` 与 `evidence.reproducible` 是“真协同”的载体：一条无法
被第三方用 locator 复现的证据，Adjudicator 有权不予采信。
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class Performative(str, Enum):
    """消息的语用行为。不同角色被授权发出的 performative 不同。"""

    REQUEST = "request"      # 请求执行任务（仅 Supervisor 可发）
    INFORM = "inform"        # 陈述事实/证据，不带主张
    PROPOSE = "propose"      # 主张某个值（仅生产者可发）
    CHALLENGE = "challenge"  # 反对，必须附反证（仅验证者/裁决者可发）
    VERDICT = "verdict"      # 裁决结论（仅 Adjudicator 可发）
    REFUSE = "refuse"        # 明确拒识/无法判断（允许“不知道”）
    ESCALATE = "escalate"    # 升级（预算耗尽/证据不可调和）


class EvidenceKind(str, Enum):
    SOURCE_SPAN = "source_span"    # 文档原文片段
    CELL_REF = "cell_ref"          # 单元格坐标（Excel）
    PAGE_REF = "page_ref"          # PDF 页码/区域
    CATALOG_ROW = "catalog_row"    # 标准物料库行
    RULE_ID = "rule_id"            # 确定性规则编号
    VECTOR_HIT = "vector_hit"      # 向量召回命中
    CLAIM_REF = "claim_ref"        # 引用另一条主张（用于反驳/裁决）


class Evidence(BaseModel):
    """可复现的证据。locator 必须是第三方能用来自行复现这条证据的定位信息。"""

    kind: str = Field(description="证据类型，见 EvidenceKind")
    locator: Dict[str, Any] = Field(default_factory=dict, description="可复现的定位信息")
    value: Any = Field(default=None, description="证据指向的值，无法确定时为 null")
    reproducible: bool = Field(default=True, description="第三方能否用 locator 复现这条证据")
    note: Optional[str] = Field(default=None, description="补充说明")


class Claim(BaseModel):
    """待裁决主张：某角色对某个主体（字段/SKU/动作）提出的值。"""

    subject: str = Field(description="主张针对的主体，如 item[0].quantity / order.action")
    value: Any = Field(default=None, description="主张的值")
    basis: str = Field(description="提出该主张的依据标识")
    confidence: Optional[float] = Field(default=None, description="提出方自报置信度，仅作参考，不得单独作为放行依据")
    disputed: bool = Field(default=False, description="该主张是否已被挑战且未解决")


class AgentMessage(BaseModel):
    """Agent 之间唯一的通信载体。所有消息落库，形成可审计轨迹。"""

    message_id: str = Field(default_factory=lambda: str(uuid4()))
    order_id: str
    task_id: str
    sender: str
    recipient: Optional[str] = Field(default=None, description="None 表示广播到黑板")
    performative: Performative
    in_reply_to: Optional[str] = Field(default=None, description="形成可追溯的对话链")
    subject: Dict[str, Any] = Field(default_factory=dict, description="消息针对哪个 item/field/region")
    payload: Dict[str, Any] = Field(default_factory=dict, description="领域模型序列化")
    evidence: List[Evidence] = Field(default_factory=list)
    cost: Dict[str, Any] = Field(default_factory=dict, description="tokens / latency_ms")

    def reproducible_evidence(self) -> List[Evidence]:
        return [item for item in self.evidence if item.reproducible]


def make_message(
    *,
    order_id: str,
    task_id: str,
    sender: str,
    performative: Performative,
    subject: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
    evidence: Optional[List[Evidence]] = None,
    recipient: Optional[str] = None,
    in_reply_to: Optional[str] = None,
    cost: Optional[Dict[str, Any]] = None,
) -> AgentMessage:
    return AgentMessage(
        order_id=order_id,
        task_id=task_id,
        sender=sender,
        recipient=recipient,
        performative=performative,
        in_reply_to=in_reply_to,
        subject=subject or {},
        payload=payload or {},
        evidence=evidence or [],
        cost=cost or {},
    )
