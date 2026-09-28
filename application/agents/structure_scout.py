"""结构侦察 Agent。

职责：文档结构解析、sheet/页/区域探测、扫描页可用性判定。

它**只**输出“哪些区域是订单明细区”这一事实（INFORM/REFUSE），不提出任何业务
主张（P2 之外的准入理由：独立工具集——文档结构解析）。

多 Sheet 规则（对应目标文档阶段三）：

- 首 Sheet 是封面、后续 Sheet 才是明细：按表头识别，而不是按顺序取第一张。
- 隐藏工作表按明确规则排除，并记录排除原因。
- 缺少可用文本的 PDF 页路由到图像解析，而不是整份拒绝。
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from application.agents.base_agent import CollaborativeAgent
from domain.agent_roles import AgentRole
from domain.constants import (
    EXCEL_HEADER_ALIASES,
    EXCEL_NON_DETAIL_SHEET_HINTS,
    EXCEL_REQUIRED_DETAIL_FIELDS,
    EXCEL_SEQUENCE_HEADERS,
)
from domain.messages import AgentMessage, Evidence, Performative
from domain.tasks import Task

HEADER_SCAN_ROWS = 20


class StructureScout(CollaborativeAgent):
    role = AgentRole.STRUCTURE_SCOUT

    def handle(self, task: Task) -> List[AgentMessage]:
        view = self.read_slice(task)
        document_ir = view.get("document_ir") or {}
        document_type = document_ir.get("document_type")

        if document_type == "excel":
            regions, excluded = self._scout_excel(document_ir)
        elif document_type == "pdf":
            regions, excluded = self._scout_pdf(document_ir)
        elif document_type == "text":
            regions, excluded = [{"kind": "text"}], []
        else:
            regions, excluded = [], [{"reason": f"未知文档类型: {document_type}"}]

        if not regions:
            return [self.emit(
                task,
                Performative.REFUSE,
                payload={
                    "reason": "未探测到可抽取的订单明细区域",
                    "excluded": excluded,
                    "document_type": document_type,
                },
            )]

        self.log_info(f"探测到 {len(regions)} 个明细区域，排除 {len(excluded)} 个")
        return [self.emit(
            task,
            Performative.INFORM,
            payload={
                "regions": regions,
                "excluded": excluded,
                "document_type": document_type,
            },
            evidence=[Evidence(
                kind="source_span",
                locator={"kind": "document", "document_type": document_type},
                value=[region.get("name") or region.get("page_number") for region in regions],
                reproducible=True,
                note="区域由表头结构判定，可由第三方按同一表头词汇表复现",
            )],
        )]

    # ------------------------------------------------------------------ Excel
    def _scout_excel(self, document_ir: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        regions: List[Dict[str, Any]] = []
        excluded: List[Dict[str, Any]] = []

        for sheet in document_ir.get("sheets", []):
            name = sheet.get("name")
            if sheet.get("hidden"):
                excluded.append({"sheet": name, "reason": "hidden_sheet"})
                continue
            if any(hint in str(name) for hint in EXCEL_NON_DETAIL_SHEET_HINTS):
                excluded.append({"sheet": name, "reason": "non_detail_sheet_name"})
                continue
            header_row = self._find_header_row(sheet.get("rows") or [])
            if header_row is None:
                excluded.append({"sheet": name, "reason": "no_order_header"})
                continue
            regions.append({
                "kind": "sheet",
                "name": name,
                "index": sheet.get("index"),
                "header_row": header_row,
                "merged_regions": sheet.get("merged_regions") or [],
            })

        return regions, excluded

    @staticmethod
    def _find_header_row(rows: List[List[Any]]) -> Any:
        for index, row in enumerate(rows[:HEADER_SCAN_ROWS]):
            labels = [str(cell or "").strip() for cell in row]
            if not any(label in EXCEL_SEQUENCE_HEADERS for label in labels):
                continue
            matched = set()
            for field, aliases in EXCEL_HEADER_ALIASES.items():
                if any(label in aliases for label in labels):
                    matched.add(field)
            if all(field in matched for field in EXCEL_REQUIRED_DETAIL_FIELDS):
                return index
        return None

    # -------------------------------------------------------------------- PDF
    def _scout_pdf(self, document_ir: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        regions: List[Dict[str, Any]] = []
        excluded: List[Dict[str, Any]] = []
        text_pages: List[int] = []

        for page in document_ir.get("pages", []):
            number = page.get("page_number")
            has_text = bool((page.get("text") or "").strip()) or bool(page.get("tables"))
            if has_text:
                text_pages.append(number)
            else:
                # 缺少可用文本的页不拒绝整份文档，而是路由到图像解析。
                regions.append({"kind": "page", "page_number": number, "mode": "image"})
                excluded.append({"page_number": number, "reason": "no_extractable_text_routed_to_image"})

        if text_pages:
            # 明细可能跨页，文本页合并为一个区域，避免把同一张表拆成多次抽取。
            regions.insert(0, {"kind": "pages", "page_numbers": text_pages, "mode": "text"})

        return regions, excluded
