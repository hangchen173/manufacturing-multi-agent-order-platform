"""交期风险 Agent。

独立工具集：时点基准、交期解析与时效判定。与 PolicyRisk 目标不同（时间 vs 价格），
因此必须独立成角色（P1 独立工具集）。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from application.agents.base_agent import CollaborativeAgent
from domain.agent_roles import AgentRole
from domain.constants import IssueType, SeverityLevel
from domain.messages import AgentMessage, Evidence, Performative
from domain.tasks import Task


class ScheduleRisk(CollaborativeAgent):
    role = AgentRole.SCHEDULE_RISK

    def __init__(self, blackboard: Any = None, budget: Any = None, config: Any = None):
        super().__init__(blackboard, budget, config)
        self.evaluation_as_of = getattr(getattr(config, "risk", None), "evaluation_as_of", None)

    def handle(self, task: Task) -> List[AgentMessage]:
        view = self.read_slice(task)
        index = view.get("item_index")
        item = view.get("item") or {}
        reference_date = view.get("reference_date")
        reference_date = self._parse_reference_date(reference_date)
        issues = self.check_delivery_date(item, index, reference_date)
        return [self.emit(
            task,
            Performative.INFORM,
            subject={"item_index": index, "claim_subject": f"item[{index}].risk.schedule"},
            payload={"issues": issues, "item_index": index,
                     "reference_date": reference_date.isoformat() if reference_date else None},
            evidence=[Evidence(
                kind="rule_id",
                locator={"rule": issue["issue_type"], "item_index": index,
                         "reference_date": reference_date.isoformat() if reference_date else None},
                value=issue["description"],
                reproducible=True,
            ) for issue in issues],
        )]

    def _parse_reference_date(self, value: Any) -> date:
        if value:
            try:
                return datetime.strptime(str(value), "%Y-%m-%d").date()
            except ValueError:
                pass
        if self.evaluation_as_of:
            return datetime.strptime(self.evaluation_as_of, "%Y-%m-%d").date()
        return datetime.now().date()

    def check_delivery_date(self, item: Dict[str, Any], item_index: int,
                            reference_date: Optional[date] = None) -> List[Dict[str, Any]]:
        delivery_date = item.get("delivery_date")
        if not delivery_date:
            return []
        try:
            parsed = datetime.strptime(str(delivery_date), "%Y-%m-%d").date()
        except ValueError:
            return [self._issue(
                item_index, IssueType.INVALID_DATE_FORMAT,
                f"交期格式 {delivery_date} 无效，应为 YYYY-MM-DD",
                SeverityLevel.MEDIUM,
            )]
        reference = reference_date or self._parse_reference_date(None)
        # 按日期语义比较：当日交期不算过去
        if parsed < reference:
            return [self._issue(
                item_index, IssueType.PAST_DELIVERY,
                f"交期 {delivery_date} 早于评估日期 {reference:%Y-%m-%d}",
                SeverityLevel.HIGH,
            )]
        return []

    @staticmethod
    def _issue(item_index: int, issue_type: Any, description: str, severity: Any) -> Dict[str, Any]:
        issue_type_value = issue_type.value if hasattr(issue_type, "value") else str(issue_type)
        severity_value = severity.value if hasattr(severity, "value") else str(severity)
        return {
            "item_index": item_index,
            "issue_type": issue_type_value,
            "description": description,
            "severity": severity_value,
        }
