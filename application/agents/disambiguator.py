"""消歧裁决者 Agent（裁决者，对抗协议核心之二）。

输入是**两路结构化候选集**，不是两个 Matcher 的自然语言理由——避免被措辞说服。
它禁止提出新值，只能 INFORM / CHALLENGE / REFUSE。

裁决规则（与旧 `MatchingAgent._match_item` 行为等价，但拆成“两路取证 + 一路裁决”）：

```
两路一致且规格唯一 → INFORM(accepted=SKU)
规格冲突           → REFUSE(reason=规格缺少区分属性 / 规格冲突)
候选分差不足/多个候选 → REFUSE(reason=存在多个同规格候选)
```
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from application.agents.base_agent import CollaborativeAgent
from application.agents.match_keys import normalize_match_key
from domain.agent_roles import AgentRole
from domain.messages import AgentMessage, Evidence, Performative
from domain.tasks import Task


class Disambiguator(CollaborativeAgent):
    role = AgentRole.DISAMBIGUATOR

    def __init__(self, blackboard: Any = None, budget: Any = None, config: Any = None,
                 match_threshold: float = 0.8):
        super().__init__(blackboard, budget, config)
        self.match_threshold = match_threshold

    def handle(self, task: Task) -> List[AgentMessage]:
        view = self.read_slice(task)
        index = view.get("item_index")
        item = view.get("item") or {}
        candidates = view.get("candidates") or {}
        catalog = candidates.get("catalog") or {}
        semantic = candidates.get("semantic") or {}

        name_key = normalize_match_key(item.get("material_name"))
        spec_key = normalize_match_key(item.get("specification"))

        decision = self.decide(item, name_key, spec_key, catalog, semantic)
        performative = Performative.INFORM if decision["accepted"] else Performative.REFUSE
        return [self.emit(
            task,
            performative,
            subject={"item_index": index, "claim_subject": f"item[{index}].sku_code"},
            payload=decision,
            evidence=self._evidence(decision),
        )]

    # ------------------------------------------------------------------ decision
    def decide(self, item: Dict[str, Any], name_key: str, spec_key: str,
               catalog: Dict[str, Any], semantic: Dict[str, Any]) -> Dict[str, Any]:
        compatible_skus = catalog.get("compatible_skus") or []
        if len(compatible_skus) > 1:
            # 全目录存在多个同规格同名候选：不得任选其一
            return self._refuse(compatible_skus, 0.0,
                                f"全目录存在多个规格与名称一致的候选：{compatible_skus}")

        exact_row = catalog.get("exact_row")
        if exact_row and exact_row.get("sku_code"):
            return self._accept(
                sku_code=exact_row["sku_code"],
                basis=(catalog.get("candidate") or {}).get("basis") or "catalog_name_spec_exact",
                score=1.0,
                matched_material_name=exact_row.get("material_name"),
                matched_specification=exact_row.get("specification"),
                candidate_skus=[exact_row["sku_code"]],
            )

        scored = semantic.get("scored") or []
        candidate_skus = semantic.get("candidate_skus") or []
        if not scored:
            return self._refuse(candidate_skus, 0.0, "向量检索未召回任何候选物料")

        best = scored[0]
        best_score = float(best.get("score") or 0.0)
        best_sku = best.get("sku_code")

        if not name_key:
            return self._refuse(candidate_skus, best_score, "缺少物料名称，无法确认标准物料")
        if not spec_key:
            return self._refuse(candidate_skus, best_score, "缺少规格型号，无法唯一确认标准物料")
        if spec_key != best.get("spec_key"):
            # 高相似度不得覆盖规格硬冲突或缺失的区分属性
            return self._refuse(candidate_skus, best_score, self._spec_conflict_reason(item, best))
        if not best.get("name_compatible"):
            return self._refuse(
                candidate_skus, best_score,
                f"物料名称 '{item.get('material_name')}' 与最高相似候选 {best_sku}"
                f"（{best.get('material_name')}）不兼容",
            )

        acceptable_skus = list(dict.fromkeys(
            entry.get("sku_code") for entry in scored
            if entry.get("sku_code")
            and entry.get("spec_key") == spec_key
            and entry.get("name_compatible")
        ))
        if len(acceptable_skus) > 1:
            return self._refuse(candidate_skus, best_score,
                                f"存在多个规格与名称一致的候选：{acceptable_skus}")

        if best_score < self.match_threshold:
            return self._refuse(
                candidate_skus, best_score,
                f"最高相似度 {best_score:.2f} 低于阈值 {self.match_threshold:.2f}",
            )

        return self._accept(
            sku_code=best_sku,
            basis="vector_spec_exact",
            score=best_score,
            matched_material_name=best.get("material_name"),
            matched_specification=best.get("specification"),
            candidate_skus=candidate_skus,
        )

    @staticmethod
    def _spec_conflict_reason(item: Dict[str, Any], candidate: Dict[str, Any]) -> str:
        item_spec = normalize_match_key(item.get("specification"))
        candidate_spec = normalize_match_key(candidate.get("specification"))
        sku_code = candidate.get("sku_code")
        if item_spec and candidate_spec.startswith(item_spec):
            return (
                f"规格 '{item.get('specification')}' 缺少区分候选 {sku_code}"
                f"（{candidate.get('specification')}）的关键属性"
            )
        return (
            f"规格 '{item.get('specification')}' 与最高相似候选 {sku_code}"
            f"（{candidate.get('specification')}）存在冲突"
        )

    @staticmethod
    def _accept(*, sku_code: Optional[str], basis: str, score: float,
                matched_material_name: Any, matched_specification: Any,
                candidate_skus: List[str]) -> Dict[str, Any]:
        return {
            "accepted": {
                "sku_code": sku_code,
                "basis": basis,
                "score": score,
                "matched_material_name": matched_material_name,
                "matched_specification": matched_specification,
            },
            "match_score": score,
            "candidate_skus": candidate_skus,
            "rejection_reason": None,
        }

    @staticmethod
    def _refuse(candidate_skus: List[str], score: float, reason: str) -> Dict[str, Any]:
        return {
            "accepted": None,
            "match_score": score,
            "candidate_skus": candidate_skus,
            "rejection_reason": reason,
        }

    @staticmethod
    def _evidence(decision: Dict[str, Any]) -> List[Evidence]:
        accepted = decision.get("accepted")
        if accepted:
            return [Evidence(
                kind="rule_id",
                locator={"rule": "disambiguation", "basis": accepted["basis"]},
                value=accepted["sku_code"],
                reproducible=True,
            )]
        return [Evidence(
            kind="rule_id",
            locator={"rule": "disambiguation_reject"},
            value=decision.get("rejection_reason"),
            reproducible=True,
        )]
