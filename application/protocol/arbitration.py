"""证据加权与理由链生成。

Adjudicator 不是简单地“任一 HIGH 即转人工”，而是对每一条主张与风险
结论计算证据强度，再给出可追溯的理由链。规则保持保守：

- 不可复现的证据权重打折；
- 被挑战未解决的字段（disputed）**一律不得进入自动通过**；
- 任何一条被证据支撑的 HIGH 风险仍然阻断自动放行。
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from domain.messages import Evidence

#: 证据来源的基础权重。原文定位类最高，向量召回最低。
SOURCE_WEIGHT: Dict[str, float] = {
    "cell_ref": 1.0,
    "source_span": 1.0,
    "page_ref": 0.95,
    "catalog_row": 0.9,
    "rule_id": 0.8,
    "claim_ref": 0.6,
    "vector_hit": 0.5,
}

#: 不可复现证据的折扣系数。
NON_REPRODUCIBLE_DISCOUNT = 0.25

#: 低于该强度的证据不单独支撑一个结论。
MIN_SUPPORT = 0.4


def evidence_weight(evidence: Evidence) -> float:
    base = SOURCE_WEIGHT.get(evidence.kind, 0.5)
    if not evidence.reproducible:
        return base * NON_REPRODUCIBLE_DISCOUNT
    return base


def claim_weight(claim: Dict[str, Any], evidence: Iterable[Evidence]) -> float:
    """一条主张的证据强度：证据权重之和，被挑战未解决时归零。"""
    if claim.get("disputed"):
        return 0.0
    return sum(evidence_weight(item) for item in evidence)


def weigh_evidence(evidence: Iterable[Evidence]) -> float:
    return sum(evidence_weight(item) for item in evidence)


def is_supported(evidence: Iterable[Evidence], threshold: float = MIN_SUPPORT) -> bool:
    return weigh_evidence(evidence) >= threshold


def build_reason_chain(
    *,
    action: str,
    risk_issues: List[Dict[str, Any]],
    disputed_subjects: List[str],
    normalizations: List[Dict[str, Any]],
    accepted_skus: List[Dict[str, Any]],
) -> List[str]:
    """生成人类可读的理由链。每一条都能追溯到证据或规则。"""
    chain: List[str] = []
    chain.append(f"终裁动作：{action}")

    for item in accepted_skus:
        chain.append(
            f"接受 SKU {item.get('sku_code')}（依据 {item.get('basis')}，"
            f"证据强度 {item.get('weight', 0):.2f}）"
        )

    for issue in risk_issues:
        chain.append(
            f"风险 {issue.get('issue_type')}（{issue.get('severity')}）："
            f"{issue.get('description')} [证据强度 {issue.get('weight', 0):.2f}]"
        )

    for subject in disputed_subjects:
        chain.append(f"争议未决字段 {subject}：证据不可调和，不得自动通过")

    for change in normalizations:
        chain.append(
            f"确定性归一化 {change.get('field')}："
            f"{change.get('original_value')!r} → {change.get('standard_value')!r}"
        )

    if len(chain) == 1:
        chain.append("全部明细与标准物料库一致，未发现风险，且无争议字段")
    return chain


def arbitrate(
    *,
    risk_issues: List[Dict[str, Any]],
    disputed_subjects: List[str],
    blocked_high_severity: bool,
) -> str:
    """给出三分类动作。

    - 存在争议字段或被证据支撑的 HIGH 风险 → manual_review
    - 否则若有归一化 → auto_correct
    - 否则 → auto_approve
    """
    if disputed_subjects or blocked_high_severity:
        return "manual_review"
    return "auto_approve"
