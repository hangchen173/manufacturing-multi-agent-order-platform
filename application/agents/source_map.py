"""文档溯源工具（非 Agent，纯函数模块）。

Extractor 用它为抽取结果附加可复现的单元格定位（cell_ref），
GroundingVerifier 用同一套逻辑重新计算并比对——两边共用同一口径，
所以“抽取者给的定位”和“验证者校验的定位”必然指向同一个单元格。

放在这里而不是某个 Agent 里，是因为它是**共享库**而不是 Agent 之间的调用：
多 Agent 约束禁止的是 Agent 互相持有引用，不禁止共享纯函数。
"""
from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from domain.constants import EXCEL_HEADER_ALIASES, EXCEL_SEQUENCE_HEADERS

FIELD_ORDER = ("material_name", "specification", "quantity", "unit", "unit_price", "delivery_date")


def parse_document_ir(order_text: str) -> Optional[Dict[str, Any]]:
    """把文档文本还原成结构化 IR；纯文本订单返回 None。"""
    if not order_text:
        return None
    try:
        document = json.loads(order_text)
    except (ValueError, TypeError):
        return None
    if isinstance(document, dict) and document.get("document_type"):
        return document
    return None


def sheets_of(document_ir: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not document_ir or document_ir.get("document_type") != "excel":
        return []
    if document_ir.get("sheets"):
        return document_ir["sheets"]
    # 兼容只有单表信息的旧形态 IR
    if "rows" in document_ir:
        return [{"name": document_ir.get("sheet_name"), "index": 0,
                 "hidden": False, "rows": document_ir.get("rows") or []}]
    return []


def excel_source_items(sheet: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """从单个工作表还原明细行及其源单元格坐标。

    要求存在唯一「序号/行号」列，且序号恰为 1..N 连续整数；任一不满足即返回
    None（宁可不给定位，也不给出错误定位）。
    """
    headers = {
        field: set(aliases) for field, aliases in EXCEL_HEADER_ALIASES.items()
    }
    columns: Optional[Dict[str, int]] = None
    items: List[Dict[str, Any]] = []
    numbers: List[int] = []
    common_date = None
    sequence_column = None

    for source_row, row in enumerate(sheet.get("rows") or [], 1):
        if not isinstance(row, list):
            return None
        if columns is None:
            labels = [str(cell or "").strip() for cell in row]
            if labels and labels[0] in headers["delivery_date"] and len(row) > 1:
                common_date = row[1]
            sequence = [i for i, label in enumerate(labels) if label in EXCEL_SEQUENCE_HEADERS]
            if len(sequence) != 1:
                continue
            columns = {}
            for field, aliases in headers.items():
                matches = [i for i, label in enumerate(labels) if label in aliases]
                if len(matches) > 1:
                    return None
                if matches:
                    columns[field] = matches[0]
            if not {"material_name", "quantity"}.issubset(columns):
                return None
            sequence_column = sequence[0]
            continue
        if not any(cell is not None and cell != "" for cell in row):
            continue
        number = row[sequence_column] if sequence_column < len(row) else None
        try:
            number = Decimal(str(number))
        except InvalidOperation:
            break
        if not number.is_finite() or number != number.to_integral_value():
            return None
        numbers.append(int(number))
        item = {
            field: (row[index] if index < len(row) else None)
            for field, index in columns.items()
        }
        if item.get("delivery_date") in (None, "") and common_date not in (None, ""):
            item["delivery_date"] = common_date
        item["source_row"] = source_row
        item["_columns"] = dict(columns)
        item["_sequence_column"] = sequence_column
        item["_sheet"] = sheet.get("name")
        items.append(item)

    if not numbers or numbers != list(range(1, len(numbers) + 1)):
        return None
    return items


def count_source_rows(document_ir: Optional[Dict[str, Any]], raw_text: str = "") -> Optional[int]:
    """估算原文明细行数；无法可靠判断时返回 None（不猜）。"""
    if document_ir and document_ir.get("document_type") == "excel":
        for sheet in sheets_of(document_ir):
            items = excel_source_items(sheet)
            if items is not None:
                return len(items)
        return None

    if document_ir and document_ir.get("document_type") == "pdf":
        numbers: List[int] = []
        for page in document_ir.get("pages", []):
            for table in page.get("tables", []) or []:
                if not table or not table[0] or table[0][0] not in EXCEL_SEQUENCE_HEADERS:
                    continue
                for row in table[1:]:
                    if not row or not re.fullmatch(r"\d+", str(row[0] or "").strip()):
                        return None
                    numbers.append(int(row[0]))
        return len(numbers) if numbers and numbers == list(range(1, len(numbers) + 1)) else None

    source = raw_text
    if document_ir and document_ir.get("document_type") == "text":
        source = document_ir.get("text") or ""
    numbers = [
        int(match.group(1)) for line in source.splitlines()
        if (match := re.match(r"^\s*(\d+)\s+\S", line))
    ]
    # 材料牌号不是行号，必须是从 1 开始的完整序列。
    return len(numbers) if numbers and numbers == list(range(1, len(numbers) + 1)) else None


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", value or "").lower()


def find_item_locators(document_ir: Optional[Dict[str, Any]], region: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """为每个明细行索引给出可复现的单元格定位。无法定位时返回空列表。"""
    if not document_ir or document_ir.get("document_type") != "excel":
        return []
    target = None
    for sheet in sheets_of(document_ir):
        if region and region.get("kind") == "sheet" and sheet.get("name") != region.get("name"):
            continue
        items = excel_source_items(sheet)
        if items is not None:
            target = items
            break
    if target is None:
        return []

    locators: List[Dict[str, Any]] = []
    for item in target:
        columns = item["_columns"]
        locators.append({
            "sheet": item["_sheet"],
            "row": item["source_row"],
            "columns": {field: index + 1 for field, index in columns.items()},
            "values": {field: item.get(field) for field in columns},
        })
    return locators


def cell_value(document_ir: Optional[Dict[str, Any]], sheet_name: str, row: int, column: int) -> Any:
    """按 1-based 行列坐标读取单元格，用于反证定位。"""
    for sheet in sheets_of(document_ir):
        if sheet.get("name") != sheet_name:
            continue
        rows = sheet.get("rows") or []
        if 1 <= row <= len(rows):
            source_row = rows[row - 1]
            if isinstance(source_row, list) and 1 <= column <= len(source_row):
                return source_row[column - 1]
    return None
