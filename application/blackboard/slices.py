"""角色上下文切片。

Agent **不读整个黑板**，只读被授权的切片。这是防止上下文爆炸和
“验证者被生产者说服”的关键机制。

`build_slice()` 是唯一的构造入口；它同时应用 `domain/agent_roles` 里的
白名单（READABLE_KEYS）与黑名单（FORBIDDEN_KEYS）。任何被显式禁止的键
都不会出现在返回结果里——**不是被忽略，而是根本不进入切片**。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from domain.agent_roles import (
    AgentRole,
    FORBIDDEN_KEYS,
    KEY_CLAIMS,
    KEY_DOCUMENT_IR,
    KEY_ITEMS,
    KEY_ORDER_FACTS,
    is_forbidden,
)


def _items(board: Any) -> List[Dict[str, Any]]:
    return list(board.fact(KEY_ITEMS) or [])


def _item_at(board: Any, index: Optional[int]) -> Optional[Dict[str, Any]]:
    items = _items(board)
    if index is None or index < 0 or index >= len(items):
        return None
    return items[index]


def _claim_view(board: Any, subject: Optional[str]) -> List[Dict[str, Any]]:
    if subject is None:
        return []
    return [record.to_dict() for record in board.claims(subject)]


def build_slice(board: Any, role: AgentRole, slice_key: Dict[str, Any]) -> Dict[str, Any]:
    """按角色裁剪黑板视图。"""
    if role == AgentRole.ADJUDICATOR or role == AgentRole.SUPERVISOR:
        # 只有终裁者需要全局视图。
        return {
            KEY_DOCUMENT_IR: board.fact(KEY_DOCUMENT_IR),
            KEY_ORDER_FACTS: board.fact(KEY_ORDER_FACTS),
            KEY_ITEMS: _items(board),
            KEY_CLAIMS: [record.to_dict() for record in board.claims()],
            "disputes": [record.to_dict() for record in board.disputes()],
            "risk_issues": board.control("risk_issues") or [],
            "parsing_issues": board.control("parsing_issues") or [],
            "reference_prices": board.control("reference_prices") or {},
        }

    if role == AgentRole.STRUCTURE_SCOUT:
        # 只能看原始文档结构，不得看到任何业务主张。
        return {KEY_DOCUMENT_IR: board.fact(KEY_DOCUMENT_IR)}

    if role == AgentRole.EXTRACTOR:
        document_ir = board.fact(KEY_DOCUMENT_IR)
        region = slice_key.get("region")
        if region is not None and isinstance(document_ir, dict):
            document_ir = _narrow_region(document_ir, region)
        # 只给本区域文档与 schema；不提供其他区域的抽取结果。
        return {
            KEY_DOCUMENT_IR: document_ir,
            "region": region,
            "feedback": slice_key.get("feedback"),
            "schema": slice_key.get("schema"),
        }

    if role == AgentRole.GROUNDING_VERIFIER:
        index = slice_key.get("item_index")
        subject = slice_key.get("subject")
        claim_records = _claim_view(board, subject)
        view = {
            KEY_DOCUMENT_IR: board.fact(KEY_DOCUMENT_IR),
            "item_index": index,
            "item": _item_at(board, index),
            "claims": claim_records,
            "claim_subject": subject,
        }
        # 显式剥离生产者推理链与自报置信度：独立验证的前提。
        view.pop("extractor.rationale", None)
        view.pop("extractor.confidence", None)
        for claim_record in view["claims"]:
            claim_record.pop("confidence", None)
        return view

    if role == AgentRole.CATALOG_MATCHER:
        return {
            "item": _item_at(board, slice_key.get("item_index")),
            "item_index": slice_key.get("item_index"),
            "catalog": board.control("catalog"),
        }

    if role == AgentRole.SEMANTIC_MATCHER:
        return {
            "item": _item_at(board, slice_key.get("item_index")),
            "item_index": slice_key.get("item_index"),
            "catalog": board.control("catalog"),
        }

    if role == AgentRole.DISAMBIGUATOR:
        # 只接收两路结构化候选集，不接收两路的自然语言理由与置信度措辞。
        return {
            "item_index": slice_key.get("item_index"),
            "item": _item_at(board, slice_key.get("item_index")),
            "candidates": board.control(f"candidates:{slice_key.get('item_index')}") or {},
        }

    if role == AgentRole.POLICY_RISK:
        return {
            "item": _item_at(board, slice_key.get("item_index")),
            "item_index": slice_key.get("item_index"),
            "items": _items(board),
            "order_facts": board.fact(KEY_ORDER_FACTS),
            "catalog": board.control("catalog"),
            "reference_prices": board.control("reference_prices") or {},
        }

    if role == AgentRole.SCHEDULE_RISK:
        return {
            "item": _item_at(board, slice_key.get("item_index")),
            "item_index": slice_key.get("item_index"),
            "reference_date": board.control("reference_date"),
        }

    if role == AgentRole.REVIEW_ASSISTANT:
        return {
            "items": _items(board),
            "risk_issues": board.control("risk_issues") or [],
            "order_facts": board.fact(KEY_ORDER_FACTS),
            "catalog": board.control("catalog"),
        }

    return {}


def _narrow_region(document_ir: Dict[str, Any], region: Any) -> Dict[str, Any]:
    """把文档 IR 收窄到单个区域（sheet 或 page），避免抽取者看到其他区域。"""
    if not isinstance(region, dict):
        return document_ir
    kind = region.get("kind")
    if kind == "sheet":
        name = region.get("name")
        sheets = [sheet for sheet in document_ir.get("sheets", []) if sheet.get("name") == name]
        return {"document_type": "excel", "sheets": sheets}
    if kind == "page":
        number = region.get("page_number")
        pages = [page for page in document_ir.get("pages", []) if page.get("page_number") == number]
        return {"document_type": "pdf", "pages": pages}
    if kind == "pages":
        wanted = set(region.get("page_numbers") or [])
        pages = [page for page in document_ir.get("pages", []) if page.get("page_number") in wanted]
        return {"document_type": "pdf", "pages": pages}
    return document_ir


def forbidden_keys(role: AgentRole) -> List[str]:
    """暴露给测试与审计：某角色被显式禁止读取的键。"""
    return sorted(FORBIDDEN_KEYS.get(role, frozenset()))


def assert_slice_isolated(role: AgentRole, view: Dict[str, Any]) -> None:
    """断言切片中不含被禁止的键（供 V4 消融实验使用）。"""
    for key in view:
        if is_forbidden(role, key):
            raise AssertionError(f"{role.value} 切片中出现了被禁止的键: {key}")
