"""溯源验证者 Agent（验证者，对抗协议核心）。

它读 `document_ir` + 主张的 locator，**不读** Extractor 的推理过程与自报置信度
（`domain/agent_roles.FORBIDDEN_KEYS` 强制隔离）。产出只能是 INFORM / CHALLENGE /
REFUSE，**禁止提出新值**——这是防止“验证者变成第二个生产者”的关键约束。

它替换了旧 `ParserAgent._parse_with_self_correction` 的自我确认：发现问题的人和
修问题的人不再是同一个模型。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from application.agents.base_agent import CollaborativeAgent
from application.agents.source_map import (
    cell_value,
    count_source_rows,
    find_item_locators,
    normalize_text,
    sheets_of,
)
from domain.agent_roles import AgentRole
from domain.messages import AgentMessage, Evidence, Performative
from domain.tasks import Task

TEXT_FIELDS = ("material_name", "specification", "unit")
NUMERIC_FIELDS = ("quantity", "unit_price")


class GroundingVerifier(CollaborativeAgent):
    role = AgentRole.GROUNDING_VERIFIER

    def handle(self, task: Task) -> List[AgentMessage]:
        view = self.read_slice(task)
        document_ir = view.get("document_ir") or {}
        index = view.get("item_index")
        claims = view.get("claims") or []
        region = task.slice_key.get("region")

        if index is None:
            return self._verify_order_level(task, document_ir, claims, region)

        if not claims:
            return [self.emit(
                task,
                Performative.REFUSE,
                subject={"claim_subject": f"item[{index}]"},
                payload={"reason": "没有可验证的主张"},
            )]

        claim = claims[-1]
        value = claim.get("value") or {}
        problems = self._verify_item(document_ir, index, value, region)

        if not problems:
            return [self.emit(
                task,
                Performative.INFORM,
                subject={"claim_subject": f"item[{index}]"},
                payload={"verified": True, "item_index": index},
                in_reply_to=claim.get("message_id"),
            )]

        messages: List[AgentMessage] = []
        for field, reason, evidence in problems:
            messages.append(self.emit(
                task,
                Performative.CHALLENGE,
                subject={"claim_subject": f"item[{index}].{field}", "item_index": index,
                         "field": field},
                payload={"reason": reason, "item_index": index, "field": field},
                evidence=evidence,
                in_reply_to=claim.get("message_id"),
            ))
        return messages

    # ------------------------------------------------------------------ item level
    def _verify_item(self, document_ir: Dict[str, Any], index: int, value: Dict[str, Any],
                     region: Optional[Dict[str, Any]]) -> List[Tuple[str, str, List[Evidence]]]:
        problems: List[Tuple[str, str, List[Evidence]]] = []

        name = (value.get("material_name") or "").strip()
        if not name:
            problems.append((
                "material_name",
                f"第 {index + 1} 行物料名称缺失",
                [Evidence(kind="rule_id", locator={"rule": "material_name_required"},
                          value=None, reproducible=True)],
            ))

        locators = find_item_locators(document_ir, region)
        if index < len(locators):
            problems.extend(self._verify_against_cells(index, value, locators[index]))
        else:
            problems.extend(self._verify_against_text(document_ir, index, value))
        return problems

    def _verify_against_cells(self, index: int, value: Dict[str, Any],
                              locator: Dict[str, Any]) -> List[Tuple[str, str, List[Evidence]]]:
        problems: List[Tuple[str, str, List[Evidence]]] = []
        columns = locator["columns"]
        source_values = locator["values"]

        for field, column in columns.items():
            expected = source_values.get(field)
            predicted = value.get(field)
            if self._cell_matches(field, expected, predicted):
                continue
            evidence = [Evidence(
                kind="cell_ref",
                locator={"kind": "cell", "sheet": locator["sheet"], "row": locator["row"],
                         "column": column},
                value=expected,
                reproducible=True,
                note=f"item[{index}].{field} 主张 {predicted!r}，原文单元格为 {expected!r}",
            )]
            problems.append((
                field,
                (f"第 {index + 1} 项 {field} 与工作表 {locator['sheet']} 第 {locator['row']} 行"
                 f"对应列不一致：原单元格为 {expected!r}，抽取为 {predicted!r}。"),
                evidence,
            ))
        return problems

    @staticmethod
    def _cell_matches(field: str, expected: Any, predicted: Any) -> bool:
        if expected in (None, ""):
            return predicted in (None, "")
        if field in NUMERIC_FIELDS:
            try:
                source_number = Decimal(str(expected).replace(",", ""))
            except InvalidOperation:
                return predicted is None
            try:
                return predicted is not None and source_number == Decimal(str(predicted))
            except InvalidOperation:
                return False
        if field == "delivery_date":
            try:
                return date.fromisoformat(str(expected).split("T")[0]).isoformat() == predicted
            except ValueError:
                return True  # 原文本身不是可解析日期，交给交期风控判定
        return normalize_text(str(expected)) == normalize_text(str(predicted or ""))

    def _verify_against_text(self, document_ir: Dict[str, Any], index: int,
                             value: Dict[str, Any]) -> List[Tuple[str, str, List[Evidence]]]:
        source = self._plain_text(document_ir)
        if not source:
            return []
        normalized_source = normalize_text(source)
        problems: List[Tuple[str, str, List[Evidence]]] = []
        name = value.get("material_name") or ""
        if normalize_text(name) and normalize_text(name) not in normalized_source:
            problems.append((
                "material_name",
                f"第 {index + 1} 行物料名称「{name}」无法在原文中定位",
                [Evidence(kind="source_span",
                          locator={"kind": "span", "text": name},
                          value=None, reproducible=True,
                          note="该名称在原文中不存在")],
            ))
        return problems

    @staticmethod
    def _plain_text(document_ir: Dict[str, Any]) -> str:
        document_type = document_ir.get("document_type")
        if document_type == "text":
            return document_ir.get("text") or ""
        if document_type == "pdf":
            # 加载层把表格单元格从 page.text 中剔除以避免重复；溯源时表格内容同样是
            # 「原文」，必须一并检索，否则表内物料名会被误判为无法定位。
            parts: List[str] = []
            for page in document_ir.get("pages", []):
                parts.append(page.get("text") or "")
                for table in page.get("tables") or []:
                    for row in table or []:
                        parts.append(" ".join(str(cell) for cell in row if cell is not None))
            return "\n".join(parts)
        return ""

    # ----------------------------------------------------------------- order level
    def _verify_order_level(self, task: Task, document_ir: Dict[str, Any],
                            claims: List[Dict[str, Any]], region: Optional[Dict[str, Any]]) -> List[AgentMessage]:
        claim = claims[-1] if claims else {}
        # 订单级核验需要完整明细；Supervisor 在切片里携带 {"items": [...]}，
        # 优先于仅含订单头字段的 order 主张值。
        parsed_order = task.slice_key.get("parsed_order") or (claim.get("value") or {})

        items = parsed_order.get("items") or []
        if not items:
            return [self.emit(
                task,
                Performative.CHALLENGE,
                subject={"claim_subject": "order.item_count"},
                payload={"reason": "未从订单中解析出任何物料明细", "field": "item_count"},
                evidence=[Evidence(kind="rule_id", locator={"rule": "non_empty_items"},
                                   value=0, reproducible=True)],
            )]

        expected_rows = count_source_rows(document_ir, self._plain_text(document_ir))
        if expected_rows is not None and expected_rows != len(items):
            return [self.emit(
                task,
                Performative.CHALLENGE,
                subject={"claim_subject": "order.item_count"},
                payload={
                    "reason": f"明细数量不一致：原文共 {expected_rows} 行明细，解析出 {len(items)} 行",
                    "field": "item_count",
                },
                evidence=[Evidence(
                    kind="rule_id",
                    locator={"rule": "row_count_match", "expected": expected_rows,
                             "actual": len(items)},
                    value=expected_rows,
                    reproducible=True,
                )],
            )]

        return [self.emit(
            task,
            Performative.INFORM,
            subject={"claim_subject": "order.item_count"},
            payload={"verified": True, "expected_rows": expected_rows, "item_count": len(items)},
        )]
