"""角色定义、能力声明与权限边界。

一个角色只有在满足下面至少一条时才允许存在（Agent 准入三条件）：

- P1 独立工具集：它拥有别人没有的工具（向量检索、原文定位、参考价查询……）。
- P2 目标冲突：它与其他角色的优化目标天然对立（“召回得全” vs “拒得准”）。
- P3 独立可验证：它能产出可被第三方复核的证据，而不是自然语言断言。

本模块同时固化两条关键边界：

1. **权限边界**：谁能改变订单终态、谁能创建任务、谁只能陈述。
2. **上下文切片边界**：每个角色能读什么、**明确不能读什么**。若验证者能看到
   生产者的推理过程，“独立验证”就是假的。
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, FrozenSet, Set

from domain.messages import Performative


class AgentRole(str, Enum):
    # 业务 Agent
    STRUCTURE_SCOUT = "structure_scout"
    EXTRACTOR = "extractor"
    GROUNDING_VERIFIER = "grounding_verifier"
    CATALOG_MATCHER = "catalog_matcher"
    SEMANTIC_MATCHER = "semantic_matcher"
    DISAMBIGUATOR = "disambiguator"
    POLICY_RISK = "policy_risk"
    SCHEDULE_RISK = "schedule_risk"
    ADJUDICATOR = "adjudicator"
    REVIEW_ASSISTANT = "review_assistant"
    # 编排 Agent
    SUPERVISOR = "supervisor"


#: 允许发出的 performative（权限边界之一：语用权限）
ROLE_PERFORMATIVES: Dict[AgentRole, FrozenSet[Performative]] = {
    AgentRole.STRUCTURE_SCOUT: frozenset({Performative.INFORM, Performative.REFUSE}),
    AgentRole.EXTRACTOR: frozenset({Performative.PROPOSE, Performative.REFUSE, Performative.INFORM}),
    AgentRole.GROUNDING_VERIFIER: frozenset({Performative.INFORM, Performative.CHALLENGE, Performative.REFUSE}),
    AgentRole.CATALOG_MATCHER: frozenset({Performative.PROPOSE, Performative.REFUSE, Performative.INFORM}),
    AgentRole.SEMANTIC_MATCHER: frozenset({Performative.PROPOSE, Performative.REFUSE, Performative.INFORM}),
    AgentRole.DISAMBIGUATOR: frozenset({Performative.INFORM, Performative.CHALLENGE, Performative.REFUSE}),
    AgentRole.POLICY_RISK: frozenset({Performative.INFORM, Performative.PROPOSE, Performative.REFUSE}),
    AgentRole.SCHEDULE_RISK: frozenset({Performative.INFORM, Performative.PROPOSE, Performative.REFUSE}),
    AgentRole.ADJUDICATOR: frozenset({Performative.VERDICT, Performative.ESCALATE, Performative.REFUSE}),
    AgentRole.REVIEW_ASSISTANT: frozenset({Performative.INFORM, Performative.REFUSE}),
    AgentRole.SUPERVISOR: frozenset({Performative.REQUEST, Performative.ESCALATE}),
}

#: 禁止提出新值的角色：防止“验证者变成第二个生产者”
NO_PROPOSAL_ROLES: FrozenSet[AgentRole] = frozenset({
    AgentRole.GROUNDING_VERIFIER,
    AgentRole.DISAMBIGUATOR,
    AgentRole.STRUCTURE_SCOUT,
})

#: 唯一有权改变订单终态的角色
TERMINAL_STATE_AUTHORITY: AgentRole = AgentRole.ADJUDICATOR
#: 唯一有权创建/取消任务的角色
TASK_AUTHORITY: AgentRole = AgentRole.SUPERVISOR

#: 全局黑板键（供上下文切片与黑板书读写使用）
KEY_DOCUMENT_IR = "document_ir"
KEY_ORDER_FACTS = "order_facts"
KEY_ITEMS = "items"
KEY_CLAIMS = "claims"
KEY_EVIDENCE = "evidence"
KEY_DISPUTES = "disputes"
KEY_TASK_STATE = "task_state"
KEY_BUDGET = "budget"

#: 每个角色显式禁止读取的键。用于防止角色污染（上下文隔离）。
#: 注意：`extractor.rationale` 与 `extractor.confidence` 是“独立验证”成立的前提，
#: 一旦 GroundingVerifier 读到它们，对抗协议就退化为自我确认。
FORBIDDEN_KEYS: Dict[AgentRole, FrozenSet[str]] = {
    AgentRole.STRUCTURE_SCOUT: frozenset({KEY_CLAIMS, KEY_EVIDENCE, KEY_ORDER_FACTS, KEY_ITEMS}),
    AgentRole.EXTRACTOR: frozenset({"extractor.other_regions", "claims.*.value"}),
    AgentRole.GROUNDING_VERIFIER: frozenset({"extractor.rationale", "extractor.confidence"}),
    AgentRole.CATALOG_MATCHER: frozenset({"semantic_matcher.candidates"}),
    AgentRole.SEMANTIC_MATCHER: frozenset({"catalog_matcher.result"}),
    AgentRole.DISAMBIGUATOR: frozenset({"catalog_matcher.rationale", "semantic_matcher.rationale",
                                        "catalog_matcher.confidence", "semantic_matcher.confidence"}),
    AgentRole.POLICY_RISK: frozenset({"extractor.confidence", "extractor.rationale"}),
    AgentRole.SCHEDULE_RISK: frozenset({"extractor.confidence", "extractor.rationale"}),
    AgentRole.ADJUDICATOR: frozenset(),
    AgentRole.REVIEW_ASSISTANT: frozenset({KEY_CLAIMS}),
    AgentRole.SUPERVISOR: frozenset(),
}

#: 每个角色允许读取的键前缀（白名单）。空集表示“只能读自己任务声明的切片”。
READABLE_KEYS: Dict[AgentRole, FrozenSet[str]] = {
    AgentRole.STRUCTURE_SCOUT: frozenset({KEY_DOCUMENT_IR}),
    AgentRole.EXTRACTOR: frozenset({KEY_DOCUMENT_IR}),
    AgentRole.GROUNDING_VERIFIER: frozenset({KEY_DOCUMENT_IR, "claims"}),
    AgentRole.CATALOG_MATCHER: frozenset({KEY_ITEMS, "catalog"}),
    AgentRole.SEMANTIC_MATCHER: frozenset({KEY_ITEMS, "catalog"}),
    AgentRole.DISAMBIGUATOR: frozenset({"candidates"}),
    AgentRole.POLICY_RISK: frozenset({KEY_ITEMS, "reference_prices"}),
    AgentRole.SCHEDULE_RISK: frozenset({KEY_ITEMS, "reference_date"}),
    AgentRole.ADJUDICATOR: frozenset({"*"}),
    AgentRole.REVIEW_ASSISTANT: frozenset({KEY_ITEMS, "risk_issues", "catalog"}),
    AgentRole.SUPERVISOR: frozenset({"*"}),
}


class PermissionViolation(Exception):
    """角色越权：发出未授权的 performative，或读取被显式禁止的键。"""

    def __init__(self, role: AgentRole, detail: str):
        self.role = role
        self.detail = detail
        super().__init__(f"[{role.value}] 权限违规: {detail}")


def assert_performative_allowed(role: AgentRole, performative: Performative) -> None:
    allowed = ROLE_PERFORMATIVES.get(role, frozenset())
    if performative not in allowed:
        raise PermissionViolation(role, f"不允许发出 {performative.value}（允许：{sorted(p.value for p in allowed)}）")


def is_forbidden(role: AgentRole, key: str) -> bool:
    forbidden: Set[str] = set(FORBIDDEN_KEYS.get(role, frozenset()))
    if key in forbidden:
        return True
    return any(
        entry.endswith(".*") and key.startswith(entry[:-1])
        for entry in forbidden
    )


def is_readable(role: AgentRole, key: str) -> bool:
    readable = READABLE_KEYS.get(role, frozenset())
    if "*" in readable:
        return not is_forbidden(role, key)
    if is_forbidden(role, key):
        return False
    return any(key == entry or key.startswith(f"{entry}.") for entry in readable)
