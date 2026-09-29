"""目录匹配 Agent（生产者）。

独立工具集：归一化、别名索引、规格精确约束。它**不看**语义召回的候选，
因此两路证据是独立的（P1 独立工具集 + P2 目标冲突）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from application.agents.base_agent import CollaborativeAgent
from application.agents.match_keys import CatalogIndex, normalize_match_key
from domain.agent_roles import AgentRole
from domain.messages import AgentMessage, Evidence, Performative
from domain.tasks import Task


class CatalogMatcher(CollaborativeAgent):
    role = AgentRole.CATALOG_MATCHER

    def __init__(self, blackboard: Any = None, budget: Any = None, config: Any = None):
        super().__init__(blackboard, budget, config)
        self._index: Optional[CatalogIndex] = None
        self._index_key: Optional[int] = None

    def catalog_index(self, metadata: List[Dict[str, Any]]) -> CatalogIndex:
        if self._index is None or self._index_key != id(metadata):
            self._index = CatalogIndex(metadata)
            self._index_key = id(metadata)
        return self._index

    def handle(self, task: Task) -> List[AgentMessage]:
        view = self.read_slice(task)
        item = view.get("item") or {}
        index = view.get("item_index")
        metadata = view.get("catalog") or []
        if not metadata:
            return [self.emit(task, Performative.REFUSE,
                              subject={"item_index": index},
                              payload={"reason": "标准物料库为空"})]

        catalog = self.catalog_index(metadata)
        name_key = normalize_match_key(item.get("material_name"))
        spec_key = normalize_match_key(item.get("specification"))

        # 已登记别名本身是「含规格的整串」。用户按别名书写时，抽取结果有两种形态：
        #   ① 整串留在物料名称、规格为空：`304内六角螺丝 M8*12` / None
        #   ② 规格被拆进规格字段：        `304内六角螺丝` / `M8*12`
        # 两种形态拼合后都等于同一条别名，因此统一用「拼合键」查别名索引。
        # 形态②若不拼合会双双落空：名称不含规格，规格又只是别名里的一段。
        joined_key = f"{name_key}{spec_key}" if spec_key else name_key

        compatible_skus = (
            catalog.compatible_skus(spec_key, name_key) if name_key and spec_key else []
        )
        alias_skus = catalog.alias_exact_skus(joined_key) if name_key else []

        # 两路各自至多命中一个、且指向同一个 SKU，才算唯一确定。
        agreed = set(compatible_skus) | set(alias_skus)
        exact_sku = None
        basis = None
        exact_row = None
        if len(compatible_skus) <= 1 and len(alias_skus) <= 1 and len(agreed) == 1:
            exact_sku = agreed.pop()
            row = catalog.by_sku(exact_sku) or {}
            exact_row = {
                "sku_code": exact_sku,
                "material_name": row.get("material_name"),
                "specification": row.get("specification"),
            }
            basis = self._basis(name_key, row, spec_key, via_alias=bool(alias_skus))

        payload = {
            "claim": {
                "subject": f"item[{index}].sku_code",
                "value": exact_sku,
                "basis": basis,
            },
            "candidate": {"exact_sku": exact_sku, "basis": basis},
            "exact_row": exact_row,
            "compatible_skus": compatible_skus,
            "alias_skus": alias_skus,
            "spec_key": spec_key,
            "name_key": name_key,
        }
        evidence: List[Evidence] = []
        if exact_sku:
            row = catalog.by_sku(exact_sku) or {}
            evidence.append(Evidence(
                kind="catalog_row",
                locator={"kind": "catalog", "sku_code": exact_sku,
                         "specification": row.get("specification")},
                value={"sku_code": exact_sku, "basis": basis},
                reproducible=True,
            ))
            return [self.emit(task, Performative.PROPOSE,
                              subject={"item_index": index, "claim_subject": f"item[{index}].sku_code"},
                              payload=payload, evidence=evidence)]

        return [self.emit(task, Performative.INFORM,
                          subject={"item_index": index}, payload=payload)]

    @staticmethod
    def _basis(item_name_key: str, row: Optional[Dict[str, Any]], spec_key: str,
               *, via_alias: bool) -> str:
        if via_alias:
            # 规格内嵌在已登记别名的整串里：规格字段可能为空（整串留在名称），
            # 也可能是别名里的那一段（规格被拆出来）。
            return "catalog_alias_exact" if not spec_key else "catalog_alias_joined_exact"
        if not row:
            return "catalog_name_spec_exact"
        canonical_key = normalize_match_key(row.get("material_name"))
        if item_name_key == canonical_key:
            return "catalog_name_spec_exact"
        return "catalog_alias_spec_exact"
