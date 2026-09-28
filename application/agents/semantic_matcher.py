"""语义召回 Agent（生产者）。

独立工具集：FAISS 向量检索。它**不看**目录匹配的结果，只输出结构化的候选集与
分数——不做接受/拒识决策（那是 Disambiguator 的职责）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from application.agents.base_agent import CollaborativeAgent
from application.agents.match_keys import CatalogIndex, normalize_match_key
from domain.agent_roles import AgentRole
from domain.messages import AgentMessage, Evidence, Performative
from domain.tasks import Task

TOP_K = 3


class SemanticMatcher(CollaborativeAgent):
    role = AgentRole.SEMANTIC_MATCHER

    def __init__(self, faiss_manager: Any = None, blackboard: Any = None, budget: Any = None,
                 config: Any = None):
        super().__init__(blackboard, budget, config)
        self._faiss_manager = faiss_manager
        self._index: Optional[CatalogIndex] = None
        self._index_key: Optional[int] = None

    @property
    def faiss_manager(self):
        if self._faiss_manager is None and self.config is not None:
            from infrastructure.vector_store.faiss_manager import FAISSManager

            self._faiss_manager = FAISSManager(index_path=self.config.data.faiss_index_path)
        return self._faiss_manager

    def catalog_index(self, metadata: List[Dict[str, Any]]) -> CatalogIndex:
        if self._index is None or self._index_key != id(metadata):
            self._index = CatalogIndex(metadata)
            self._index_key = id(metadata)
        return self._index

    @staticmethod
    def calculate_match_score(distance: float) -> float:
        # 这是相似度映射，不是“正确概率”。
        return max(0.0, min(1.0, 1.0 - distance / 2.0))

    @staticmethod
    def build_query_text(item: Dict[str, Any]) -> str:
        parts = [item.get("material_name"), item.get("specification")]
        return " ".join(part for part in parts if part).strip()

    def handle(self, task: Task) -> List[AgentMessage]:
        view = self.read_slice(task)
        item = view.get("item") or {}
        index = view.get("item_index")
        metadata = view.get("catalog") or []

        query = self.build_query_text(item)
        if not query or self.faiss_manager is None:
            return [self.emit(task, Performative.INFORM, subject={"item_index": index},
                              payload={"scored": [], "candidate_skus": [], "query": query})]

        try:
            results = self.faiss_manager.search(query, k=TOP_K)
        except Exception as exc:  # noqa: BLE001 - 检索失败不得静默给出候选
            self.log_warning(f"向量检索失败 item_index={index} query='{query}': {exc}")
            return [self.emit(task, Performative.INFORM, subject={"item_index": index},
                              payload={"scored": [], "candidate_skus": [], "query": query,
                                       "error": str(exc)})]

        catalog = self.catalog_index(metadata)
        name_key = normalize_match_key(item.get("material_name"))
        scored: List[Dict[str, Any]] = []
        for doc, distance in results:
            score = self.calculate_match_score(distance)
            scored.append({
                "sku_code": doc.get("sku_code"),
                "score": score,
                "spec_key": normalize_match_key(doc.get("specification")),
                "name_compatible": catalog.name_compatible(name_key, doc),
                "specification": doc.get("specification"),
                "material_name": doc.get("material_name"),
            })
        scored.sort(key=lambda entry: entry["score"], reverse=True)
        candidate_skus = list(dict.fromkeys(
            entry["sku_code"] for entry in scored if entry.get("sku_code")
        ))

        evidence = [
            Evidence(kind="vector_hit",
                     locator={"kind": "vector", "sku_code": entry["sku_code"], "query": query},
                     value=round(entry["score"], 4), reproducible=True)
            for entry in scored if entry.get("sku_code")
        ]
        return [self.emit(task, Performative.PROPOSE,
                          subject={"item_index": index, "claim_subject": f"item[{index}].semantic_candidates"},
                          payload={
                              "claim": {
                                  "subject": f"item[{index}].semantic_candidates",
                                  "value": candidate_skus,
                                  "basis": "vector_recall",
                              },
                              "scored": scored, "candidate_skus": candidate_skus, "query": query,
                          },
                          evidence=evidence)]
