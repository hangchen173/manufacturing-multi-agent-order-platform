"""物料匹配的共享键归一化与目录索引（非 Agent，纯函数/纯数据结构）。

CatalogMatcher 与 SemanticMatcher 用同一套归一化与名称兼容判据，
Disambiguator 用同一套键做结构化裁决——保证两路候选“可比较”。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

UNIT_ALIASES = (
    ("平方米", "m2"),
    ("立方米", "m3"),
    ("毫米", "mm"),
    ("微米", "um"),
    ("厘米", "cm"),
    ("分米", "dm"),
    ("千米", "km"),
    ("米", "m"),
    ("²", "2"),
    ("μ", "u"),
    ("µ", "u"),
)


def normalize_match_key(value: Optional[str]) -> str:
    if not value:
        return ""
    normalized = value.replace("×", "*").replace("✖", "*").replace("ｘ", "*")
    for alias, canonical in UNIT_ALIASES:
        normalized = normalized.replace(alias, canonical)
    return "".join(normalized.lower().split())


class CatalogIndex:
    """标准物料库的确定性索引：名称兼容 + 规格索引 + SKU 反查。"""

    def __init__(self, metadata: List[Dict[str, Any]]):
        self.metadata = metadata
        self._spec_index: Dict[str, List[Dict[str, Any]]] = {}
        self._name_spec_index: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        self._row_name_keys: Dict[str, Set[str]] = {}
        self._by_sku: Dict[str, Dict[str, Any]] = {}
        self._build()

    def _build(self) -> None:
        for row in self.metadata:
            name_key = normalize_match_key(row.get("material_name"))
            spec_key = normalize_match_key(row.get("specification"))
            row_keys: Set[str] = set()
            if name_key:
                row_keys.add(name_key)
            for alias in row.get("aliases") or []:
                alias_key = normalize_match_key(alias)
                if alias_key:
                    row_keys.add(alias_key)
            sku_code = row.get("sku_code")
            if sku_code:
                self._row_name_keys.setdefault(sku_code, set()).update(row_keys)
                self._by_sku[sku_code] = row
            if name_key and spec_key:
                self._name_spec_index.setdefault((name_key, spec_key), []).append(row)
            if spec_key:
                self._spec_index.setdefault(spec_key, []).append(row)

    def name_compatible(self, name_key: str, row: Dict[str, Any]) -> bool:
        if not name_key:
            return False
        row_keys = self._row_name_keys.get(row.get("sku_code"))
        if not row_keys:
            row_keys = {normalize_match_key(row.get("material_name"))}
        return name_key in row_keys

    def compatible_rows(self, spec_key: str, name_key: str) -> List[Dict[str, Any]]:
        """全目录中规格一致且名称兼容的行（不依赖召回，避免召回掩盖歧义）。"""
        return [
            row for row in self._spec_index.get(spec_key, [])
            if self.name_compatible(name_key, row)
        ]

    def compatible_skus(self, spec_key: str, name_key: str) -> List[str]:
        return list(dict.fromkeys(
            row["sku_code"] for row in self.compatible_rows(spec_key, name_key)
            if row.get("sku_code")
        ))

    def spec_rows(self, spec_key: str) -> List[Dict[str, Any]]:
        return list(self._spec_index.get(spec_key, []))

    def by_sku(self, sku_code: Optional[str]) -> Optional[Dict[str, Any]]:
        if not sku_code:
            return None
        return self._by_sku.get(sku_code)

    def reference_price(self, sku_code: Optional[str]) -> Optional[float]:
        row = self.by_sku(sku_code)
        if not row:
            return None
        price = row.get("reference_price")
        return float(price) if price is not None else None
