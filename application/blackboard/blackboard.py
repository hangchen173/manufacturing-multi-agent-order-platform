"""三层黑板：多 Agent 的共享协作媒介。

```
Layer 3: Control State（控制层）      任务 DAG 状态 · 重试计数 · 预算消耗
                                      写入者：仅 Supervisor
Layer 2: Claims & Evidence（主张层）  待裁决主张 · 证据 · 异议 · 裁决记录 · 理由链
                                      写入者：所有业务 Agent（只能追加，不能改写他人主张）
Layer 1: Order Facts（事实层）        文档 IR · 已裁决字段值 · 已接受 SKU · 最终动作
                                      写入者：仅 Adjudicator
```

关键约束：

- **主张只追加**：同一 subject 的多条主张共存，由 Adjudicator 裁决；被推翻时追加
  一条 challenge，而不是覆盖。
- **事实只能由 Adjudicator 晋升**：其他 Agent 只能写主张与证据。
- **角色只能读自己的切片**：`slice_for()` 会按 `domain/agent_roles` 的白名单/黑名单
  裁剪视图，防止验证者被生产者的推理过程污染。
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from domain.agent_roles import (
    AgentRole,
    KEY_CLAIMS,
    KEY_DOCUMENT_IR,
    KEY_EVIDENCE,
    KEY_ORDER_FACTS,
    KEY_ITEMS,
    PermissionViolation,
    TERMINAL_STATE_AUTHORITY,
    is_forbidden,
)
from domain.messages import AgentMessage, Claim, Evidence, Performative


@dataclass
class ClaimRecord:
    """一条待裁决主张及其来源。"""

    subject: str
    claim: Claim
    sender: str
    message_id: str
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject": self.subject,
            "value": self.claim.value,
            "basis": self.claim.basis,
            "confidence": self.claim.confidence,
            "disputed": self.claim.disputed,
            "sender": self.sender,
            "message_id": self.message_id,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class DisputeRecord:
    """一条未解决的异议。"""

    subject: str
    reason: str
    challenger: str
    evidence: List[Evidence] = field(default_factory=list)
    resolved: bool = False
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject": self.subject,
            "reason": self.reason,
            "challenger": self.challenger,
            "evidence": [item.model_dump(mode="json") for item in self.evidence],
            "resolved": self.resolved,
            "created_at": self.created_at.isoformat(),
        }


class Blackboard:
    """单张订单的协作黑板。近似纯数据结构，可快照/恢复。"""

    LAYER_CONTROL = "control"
    LAYER_CLAIMS = "claims"
    LAYER_FACTS = "facts"

    def __init__(self, order_id: str, version: int = 0):
        self.order_id = order_id
        self.version = version
        self._control: Dict[str, Any] = {}
        self._facts: Dict[str, Any] = {}
        self._claims: List[ClaimRecord] = []
        self._disputes: List[DisputeRecord] = []
        self._verdicts: List[Dict[str, Any]] = []
        self._messages: List[AgentMessage] = []

    # ---------------------------------------------------------------- Layer 3
    def set_control(self, key: str, value: Any, actor: AgentRole = AgentRole.SUPERVISOR) -> None:
        if actor != AgentRole.SUPERVISOR:
            raise PermissionViolation(actor, "只有 Supervisor 可以写控制层")
        self._control[key] = value

    def control(self, key: str, default: Any = None) -> Any:
        return self._control.get(key, default)

    def control_state(self) -> Dict[str, Any]:
        return deepcopy(self._control)

    # ---------------------------------------------------------------- Layer 2
    def append_claim(self, message: AgentMessage) -> ClaimRecord:
        """只允许追加。同一 subject 的多条主张共存，由 Adjudicator 裁决。"""
        claim = Claim.model_validate(message.payload.get("claim") or {})
        record = ClaimRecord(
            subject=claim.subject,
            claim=claim,
            sender=message.sender,
            message_id=message.message_id,
        )
        self._claims.append(record)
        return record

    def append_evidence(self, message: AgentMessage) -> None:
        """证据不可删除；被推翻时追加一条 challenge 而非覆盖。"""
        if not message.evidence:
            return
        bucket = self._control.setdefault("_evidence", {})
        bucket.setdefault(message.sender, []).append({
            "message_id": message.message_id,
            "subject": message.subject,
            "evidence": [item.model_dump(mode="json") for item in message.evidence],
        })

    def add_dispute(self, message: AgentMessage, reason: str) -> DisputeRecord:
        record = DisputeRecord(
            subject=str(message.subject.get("claim_subject") or message.subject.get("subject") or ""),
            reason=reason,
            challenger=message.sender,
            evidence=list(message.evidence),
        )
        self._disputes.append(record)
        for claim_record in self._claims:
            if claim_record.subject == record.subject:
                claim_record.claim.disputed = True
        return record

    def resolve_dispute(self, subject: str) -> None:
        for record in self._disputes:
            if record.subject == subject:
                record.resolved = True
        for claim_record in self._claims:
            if claim_record.subject == subject:
                claim_record.claim.disputed = False

    def record_verdict(self, message: AgentMessage) -> None:
        self._verdicts.append({
            "message_id": message.message_id,
            "sender": message.sender,
            "payload": deepcopy(message.payload),
            "evidence": [item.model_dump(mode="json") for item in message.evidence],
            "created_at": datetime.now().isoformat(),
        })

    def claims(self, subject_prefix: Optional[str] = None) -> List[ClaimRecord]:
        if subject_prefix is None:
            return list(self._claims)
        return [record for record in self._claims if record.subject.startswith(subject_prefix)]

    def disputed_subjects(self) -> List[str]:
        return sorted({record.subject for record in self._disputes if not record.resolved})

    def disputes(self) -> List[DisputeRecord]:
        return list(self._disputes)

    def verdicts(self) -> List[Dict[str, Any]]:
        return deepcopy(self._verdicts)

    def record_message(self, message: AgentMessage) -> None:
        self._messages.append(message)

    def messages(self) -> List[AgentMessage]:
        return list(self._messages)

    def trace(self) -> List[Dict[str, Any]]:
        """协作轨迹：谁在什么时候对谁说了什么、依据是什么。"""
        return [
            {
                "message_id": message.message_id,
                "task_id": message.task_id,
                "sender": message.sender,
                "recipient": message.recipient,
                "performative": message.performative.value,
                "in_reply_to": message.in_reply_to,
                "subject": message.subject,
                "payload": message.payload,
                "evidence": [item.model_dump(mode="json") for item in message.evidence],
                "cost": message.cost,
            }
            for message in self._messages
        ]

    # ---------------------------------------------------------------- Layer 1
    def set_fact(self, key: str, value: Any, actor: AgentRole = TERMINAL_STATE_AUTHORITY) -> None:
        if actor != TERMINAL_STATE_AUTHORITY:
            raise PermissionViolation(actor, "只有 Adjudicator 可以把主张晋升为事实")
        self._facts[key] = value

    def fact(self, key: str, default: Any = None) -> Any:
        return self._facts.get(key, default)

    def facts(self) -> Dict[str, Any]:
        return deepcopy(self._facts)

    # ---------------------------------------------------------------- slices
    def slice_for(self, role: AgentRole, slice_key: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """按角色裁剪视图。被显式禁止的键不会出现在返回结果中。"""
        from application.blackboard.slices import build_slice

        return build_slice(self, role, slice_key or {})

    def visible_keys(self, role: AgentRole) -> List[str]:
        candidates = [
            KEY_DOCUMENT_IR, KEY_ORDER_FACTS, KEY_ITEMS, KEY_CLAIMS, KEY_EVIDENCE,
            "extractor.rationale", "extractor.confidence",
            "catalog_matcher.result", "catalog_matcher.rationale", "catalog_matcher.confidence",
            "semantic_matcher.candidates", "semantic_matcher.rationale", "semantic_matcher.confidence",
            "reference_prices", "reference_date", "candidates", "risk_issues", "catalog",
        ]
        return [key for key in candidates if not is_forbidden(role, key)]

    # ---------------------------------------------------------------- snapshot
    def to_snapshot(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "version": self.version,
            "control": deepcopy(self._control),
            "facts": deepcopy(self._facts),
            "claims": [record.to_dict() for record in self._claims],
            "disputes": [record.to_dict() for record in self._disputes],
            "verdicts": deepcopy(self._verdicts),
            "messages": [message.model_dump(mode="json") for message in self._messages],
        }

    @classmethod
    def from_snapshot(cls, payload: Dict[str, Any]) -> "Blackboard":
        board = cls(order_id=payload["order_id"], version=int(payload.get("version") or 0))
        board._control = deepcopy(payload.get("control") or {})
        board._facts = deepcopy(payload.get("facts") or {})
        for record in payload.get("claims") or []:
            board._claims.append(ClaimRecord(
                subject=record["subject"],
                claim=Claim(
                    subject=record["subject"],
                    value=record.get("value"),
                    basis=record.get("basis", ""),
                    confidence=record.get("confidence"),
                    disputed=bool(record.get("disputed")),
                ),
                sender=record.get("sender", ""),
                message_id=record.get("message_id", ""),
            ))
        for record in payload.get("disputes") or []:
            board._disputes.append(DisputeRecord(
                subject=record["subject"],
                reason=record["reason"],
                challenger=record["challenger"],
                evidence=[Evidence.model_validate(item) for item in record.get("evidence") or []],
                resolved=bool(record.get("resolved")),
            ))
        board._verdicts = deepcopy(payload.get("verdicts") or [])
        board._messages = [AgentMessage.model_validate(item) for item in payload.get("messages") or []]
        return board


def record(board: Blackboard, message: AgentMessage) -> None:
    """统一的消息落地：记录轨迹，并按 performative 分发到对应层。"""
    board.record_message(message)
    if message.performative == Performative.PROPOSE:
        board.append_claim(message)
    elif message.performative == Performative.CHALLENGE:
        board.append_evidence(message)
        board.add_dispute(message, reason=str(message.payload.get("reason") or "未说明理由"))
    elif message.performative in {Performative.INFORM, Performative.REFUSE}:
        board.append_evidence(message)
    elif message.performative == Performative.VERDICT:
        board.record_verdict(message)
