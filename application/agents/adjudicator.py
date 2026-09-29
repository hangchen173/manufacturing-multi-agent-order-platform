"""终裁者 Agent。

设计文档 §2.2：证据加权、理由链生成；**唯一有权改变订单终态的角色**。

它把 Layer 2 的主张与证据晋升为 Layer 1 的事实，并给出三分类动作。
规则保持保守：任何被证据支撑的 HIGH 风险、任何未决争议字段，都不得自动通过。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from application.agents.base_agent import CollaborativeAgent
from application.protocol.arbitration import build_reason_chain, weigh_evidence
from domain.agent_roles import AgentRole
from domain.constants import RISK_CHECK_ORDER, SeverityLevel
from domain.messages import AgentMessage, Evidence, Performative
from domain.models import (
    BusinessAction,
    BusinessDecision,
    MatchedOrder,
    MatchedOrderItem,
    NormalizationChange,
    OrderItem,
    ParsedOrder,
    ParsingIssue,
    RiskCheckResult,
    RiskIssue,
)
from domain.tasks import Task

ORDER_LEVEL_ITEM_INDEX = -1

_NAME_BASIS = {
    "catalog_alias_exact": "物料名称整串命中标准库已登记别名（别名内含规格）",
    "catalog_alias_joined_exact": "物料名称与规格拼合命中标准库已登记别名（别名内含规格）",
    "catalog_alias_spec_exact": "物料名称命中标准库已登记别名",
    "catalog_name_spec_exact": "物料名称为标准名的等价书写",
    "vector_spec_exact": "物料名称与标准库名称兼容且规格一致",
}


class Adjudicator(CollaborativeAgent):
    role = AgentRole.ADJUDICATOR

    def handle(self, task: Task) -> List[AgentMessage]:
        view = self.read_slice(task)
        items = view.get("items") or []
        order_facts = view.get("order_facts") or {}
        risk_issues = view.get("risk_issues") or []
        parsing_issues = view.get("parsing_issues") or []
        disputes = view.get("disputes") or []

        verdict = self.adjudicate(
            items=items,
            order_facts=order_facts,
            risk_issues=risk_issues,
            parsing_issues=parsing_issues,
            disputes=disputes,
        )

        if self.blackboard is not None:
            self.blackboard.set_fact("parsed_order", verdict["parsed_order"])
            self.blackboard.set_fact("matched_order", verdict["matched_order"])
            self.blackboard.set_fact("risk_result", verdict["risk_result"])
            self.blackboard.set_fact("business_decision", verdict["business_decision"])
            self.blackboard.set_fact("final_action", verdict["action"])

        return [self.emit(
            task,
            Performative.VERDICT,
            subject={"claim_subject": "order.action"},
            payload=verdict,
            evidence=[Evidence(
                kind="rule_id",
                locator={"rule": "adjudication", "action": verdict["action"],
                         "needs_confirmation": verdict["needs_confirmation"]},
                value=verdict["reason"],
                reproducible=True,
            )],
        )]

    # ------------------------------------------------------------------ core
    def adjudicate(self, *, items: List[Dict[str, Any]], order_facts: Dict[str, Any],
                   risk_issues: List[Dict[str, Any]], parsing_issues: List[Dict[str, Any]],
                   disputes: List[Dict[str, Any]]) -> Dict[str, Any]:
        parsed_order = self._build_parsed_order(items, order_facts, parsing_issues)
        matched_order = self._build_matched_order(items, order_facts, parsing_issues)
        ordered_issues = self._order_issues(risk_issues)
        disputed_subjects = sorted({
            dispute["subject"] for dispute in disputes if not dispute.get("resolved")
        })

        blocked_high = any(
            issue["severity"] == SeverityLevel.HIGH.value for issue in ordered_issues
        )
        needs_confirmation = blocked_high or bool(disputed_subjects)

        normalizations: List[NormalizationChange] = []
        if not needs_confirmation:
            for index, item in enumerate(items):
                normalizations.extend(self._collect_normalizations(item, index))

        action = self._decide_action(needs_confirmation, normalizations)
        reason = self._build_reason(action, ordered_issues, disputed_subjects, normalizations)

        risk_result = RiskCheckResult(
            needs_confirmation=needs_confirmation,
            issues=[RiskIssue(**issue) for issue in ordered_issues],
            overall_confidence=self._overall_confidence(ordered_issues, len(items)),
        )
        business_decision = BusinessDecision(
            action=action, reason=reason, normalizations=normalizations,
        )

        accepted_skus = [
            {
                "sku_code": item.get("sku_code"),
                "basis": item.get("match_basis"),
                "weight": round(weigh_evidence(self._item_evidence(item)), 2),
            }
            for item in items if item.get("sku_code")
        ]
        reason_chain = build_reason_chain(
            action=action.value,
            risk_issues=ordered_issues,
            disputed_subjects=disputed_subjects,
            normalizations=[change.model_dump(mode="json") for change in normalizations],
            accepted_skus=accepted_skus,
        )

        return {
            "needs_confirmation": needs_confirmation,
            "action": action.value,
            "reason": reason,
            "reason_chain": reason_chain,
            "disputed_subjects": disputed_subjects,
            "normalizations": [change.model_dump(mode="json") for change in normalizations],
            "parsed_order": parsed_order.model_dump(mode="json"),
            "matched_order": matched_order.model_dump(mode="json"),
            "risk_result": risk_result.model_dump(mode="json"),
            "business_decision": business_decision.model_dump(mode="json"),
        }

    # ------------------------------------------------------------------ builders
    @staticmethod
    def _build_parsed_order(items: List[Dict[str, Any]], order_facts: Dict[str, Any],
                            parsing_issues: List[Dict[str, Any]]) -> ParsedOrder:
        parsed_items = [
            OrderItem(
                material_name=item.get("material_name") or "",
                specification=item.get("specification"),
                quantity=item.get("quantity"),
                unit=item.get("unit"),
                unit_price=item.get("unit_price"),
                delivery_date=item.get("delivery_date"),
                confidence_score=item.get("confidence_score"),
            )
            for item in items
        ]
        return ParsedOrder(
            order_number=order_facts.get("order_number"),
            customer_name=order_facts.get("customer_name"),
            items=parsed_items,
            total_amount=order_facts.get("total_amount"),
            parsing_confidence=float(order_facts.get("parsing_confidence") or 0.0),
            parsing_issues=[ParsingIssue(**issue) for issue in parsing_issues],
        )

    @staticmethod
    def _build_matched_order(items: List[Dict[str, Any]], order_facts: Dict[str, Any],
                             parsing_issues: List[Dict[str, Any]]) -> MatchedOrder:
        matched_items = [
            MatchedOrderItem(
                material_name=item.get("material_name") or "",
                specification=item.get("specification"),
                quantity=item.get("quantity"),
                unit=item.get("unit"),
                unit_price=item.get("unit_price"),
                delivery_date=item.get("delivery_date"),
                confidence_score=item.get("confidence_score"),
                sku_code=item.get("sku_code"),
                matched_material_name=item.get("matched_material_name"),
                matched_specification=item.get("matched_specification"),
                match_score=float(item.get("match_score") or 0.0),
                candidate_skus=list(item.get("candidate_skus") or []),
                match_basis=item.get("match_basis"),
                rejection_reason=item.get("rejection_reason"),
            )
            for item in items
        ]
        return MatchedOrder(
            order_number=order_facts.get("order_number"),
            customer_name=order_facts.get("customer_name"),
            items=matched_items,
            total_amount=order_facts.get("total_amount"),
            parsing_issues=[ParsingIssue(**issue) for issue in parsing_issues],
        )

    @staticmethod
    def _order_issues(risk_issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """按规范顺序排序，保证两个风险 Agent 合并后顺序可复现。"""
        def sort_key(issue: Dict[str, Any]):
            try:
                rank = RISK_CHECK_ORDER.index(issue.get("issue_type"))
            except ValueError:
                rank = len(RISK_CHECK_ORDER)
            return (issue.get("item_index", ORDER_LEVEL_ITEM_INDEX), rank)

        item_level = [issue for issue in risk_issues if issue.get("item_index") != ORDER_LEVEL_ITEM_INDEX]
        order_level = [issue for issue in risk_issues if issue.get("item_index") == ORDER_LEVEL_ITEM_INDEX]
        return sorted(item_level, key=sort_key) + sorted(order_level, key=sort_key)

    @staticmethod
    def _item_evidence(item: Dict[str, Any]) -> List[Evidence]:
        evidence: List[Evidence] = []
        if item.get("sku_code"):
            evidence.append(Evidence(
                kind="catalog_row" if (item.get("match_basis") or "").startswith("catalog") else "vector_hit",
                locator={"kind": "catalog", "sku_code": item.get("sku_code")},
                value=item.get("sku_code"), reproducible=True,
            ))
        return evidence

    @staticmethod
    def _decide_action(needs_confirmation: bool,
                       normalizations: List[NormalizationChange]) -> BusinessAction:
        if needs_confirmation:
            return BusinessAction.MANUAL_REVIEW
        if normalizations:
            return BusinessAction.AUTO_CORRECT
        return BusinessAction.AUTO_APPROVE

    @staticmethod
    def _build_reason(action: BusinessAction, risk_issues: List[Dict[str, Any]],
                      disputed_subjects: List[str],
                      normalizations: List[NormalizationChange]) -> str:
        if action == BusinessAction.MANUAL_REVIEW:
            if disputed_subjects:
                return (f"存在 {len(disputed_subjects)} 个证据不可调和的争议字段"
                        f"（{'、'.join(disputed_subjects)}），需人工确认")
            return "风控发现高风险明细项，需人工确认"
        if action == BusinessAction.AUTO_CORRECT:
            fields = sorted({change.field for change in normalizations})
            return (f"{len(normalizations)} 处明细字段按标准物料库完成确定性归一化"
                    f"（{'、'.join(fields)}），未改变采购意图，未发现风险")
        return "全部明细与标准物料库一致，未发现风险"

    @staticmethod
    def _overall_confidence(issues: List[Dict[str, Any]], item_count: int) -> float:
        if item_count == 0:
            return 0.0
        high = sum(1 for issue in issues if issue["severity"] == SeverityLevel.HIGH.value)
        medium = sum(1 for issue in issues if issue["severity"] == SeverityLevel.MEDIUM.value)
        return max(0.0, min(1.0, 1.0 - (high * 0.2 + medium * 0.1)))

    # ------------------------------------------------------------------ normalizations
    def _collect_normalizations(self, item: Dict[str, Any],
                                item_index: int) -> List[NormalizationChange]:
        # 仅在接受标准 SKU 后才做归一化；未接受任何 SKU 时不得改写任何字段
        if not item.get("sku_code"):
            return []

        changes: List[NormalizationChange] = []
        if self._differs(item.get("material_name"), item.get("matched_material_name")):
            changes.append(NormalizationChange(
                item_index=item_index,
                field="material_name",
                original_value=item.get("material_name"),
                standard_value=item.get("matched_material_name"),
                basis=_NAME_BASIS.get(item.get("match_basis") or "", "名称归一化为标准物料名"),
            ))
        if self._differs(item.get("specification"), item.get("matched_specification")):
            changes.append(NormalizationChange(
                item_index=item_index,
                field="specification",
                original_value=item.get("specification"),
                standard_value=item.get("matched_specification"),
                basis="标准规格与原规格为等价书写",
            ))
        # 数量、单价、交期不参与自动纠正；单位换算无明确依据一律不自动执行
        return changes

    @staticmethod
    def _differs(original: Optional[str], standard: Optional[str]) -> bool:
        if not original or not standard:
            return False
        return original.strip() != standard.strip()
