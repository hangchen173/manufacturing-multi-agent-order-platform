from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

from application.agents.base_agent import BaseAgent
from config import Config
from domain.models import MatchedOrder, MatchedOrderItem, ParsedOrder

if TYPE_CHECKING:
    from infrastructure.vector_store.faiss_manager import FAISSManager

class MatchingAgent(BaseAgent):
    def __init__(
        self, 
        llm=None, 
        faiss_manager: Optional["FAISSManager"] = None,
        config: Optional[Config] = None
    ):
        super().__init__(llm, config)
        self.match_threshold = self.config.risk.match_threshold
        self._faiss_manager = faiss_manager
        self._name_spec_index: Optional[Dict[Tuple[str, str], List[Dict[str, Any]]]] = None
        self._spec_index: Optional[Dict[str, List[Dict[str, Any]]]] = None
        self._row_name_keys: Optional[Dict[str, Set[str]]] = None

    @property
    def faiss_manager(self):
        if self._faiss_manager is None:
            from infrastructure.vector_store.faiss_manager import FAISSManager

            self._faiss_manager = FAISSManager(
                index_path=self.config.data.faiss_index_path
            )
        return self._faiss_manager
    
    def _calculate_match_score(self, distance: float) -> float:
        return max(0.0, min(1.0, 1.0 - distance / 2.0))
    
    def _build_query_text(self, item: Any) -> str:
        parts = []
        if item.material_name:
            parts.append(item.material_name)
        if item.specification:
            parts.append(item.specification)
        return " ".join(parts).strip()
    
    _UNIT_ALIASES = (
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

    @classmethod
    def _normalize_match_key(cls, value: Optional[str]) -> str:
        if not value:
            return ""
        normalized = value.replace("×", "*").replace("✖", "*").replace("ｘ", "*")
        for alias, canonical in cls._UNIT_ALIASES:
            normalized = normalized.replace(alias, canonical)
        return "".join(normalized.lower().split())

    def _build_key_index(self) -> None:
        if self._name_spec_index is not None:
            return

        name_spec_index: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        spec_index: Dict[str, List[Dict[str, Any]]] = {}
        row_name_keys: Dict[str, Set[str]] = {}
        for row in self.faiss_manager.metadata:
            name_key = self._normalize_match_key(row.get("material_name"))
            spec_key = self._normalize_match_key(row.get("specification"))

            # 标准名称与已登记别名共同构成名称兼容性依据
            row_keys: Set[str] = set()
            if name_key:
                row_keys.add(name_key)
            for alias in row.get("aliases") or []:
                alias_key = self._normalize_match_key(alias)
                if alias_key:
                    row_keys.add(alias_key)
            sku_code = row.get("sku_code")
            if sku_code:
                row_name_keys.setdefault(sku_code, set()).update(row_keys)

            if name_key and spec_key:
                name_spec_index.setdefault((name_key, spec_key), []).append(row)
            if spec_key:
                spec_index.setdefault(spec_key, []).append(row)

        self._name_spec_index = name_spec_index
        self._spec_index = spec_index
        self._row_name_keys = row_name_keys

    def _name_compatible(self, name_key: str, row: Dict[str, Any]) -> bool:
        if not name_key:
            return False
        row_keys = None
        if self._row_name_keys is not None:
            row_keys = self._row_name_keys.get(row.get("sku_code"))
        if not row_keys:
            row_keys = {self._normalize_match_key(row.get("material_name"))}
        return name_key in row_keys

    def _match_by_catalog_key(self, item: Any) -> Optional[Dict[str, Any]]:
        self._build_key_index()

        name_key = self._normalize_match_key(item.material_name)
        spec_key = self._normalize_match_key(item.specification)

        if not name_key or not spec_key:
            return None

        # 全目录验证标准名和别名，避免精确名称路径掩盖另一 SKU 的别名冲突。
        compatible_rows = [
            row
            for row in self._spec_index.get(spec_key, [])
            if self._name_compatible(name_key, row)
        ]
        if len(compatible_rows) == 1:
            return compatible_rows[0]
        return None

    def _catalog_basis(self, item: Any, row: Dict[str, Any]) -> str:
        item_name_key = self._normalize_match_key(item.material_name)
        canonical_key = self._normalize_match_key(row.get("material_name"))
        if item_name_key == canonical_key:
            return "catalog_name_spec_exact"
        return "catalog_alias_spec_exact"

    def _spec_conflict_reason(self, item: Any, candidate: Dict[str, Any]) -> str:
        item_spec = self._normalize_match_key(item.specification)
        candidate_spec = self._normalize_match_key(candidate.get("specification"))
        sku_code = candidate.get("sku_code")
        if item_spec and candidate_spec.startswith(item_spec):
            return (
                f"规格 '{item.specification}' 缺少区分候选 {sku_code}"
                f"（{candidate.get('specification')}）的关键属性"
            )
        return (
            f"规格 '{item.specification}' 与最高相似候选 {sku_code}"
            f"（{candidate.get('specification')}）存在冲突"
        )

    def _accept_vector_candidate(
        self, item: Any, scored: List[Tuple[Dict[str, Any], float]]
    ) -> Tuple[Optional[Dict[str, Any]], float, Optional[str]]:
        if not scored:
            return None, 0.0, "向量检索未召回任何候选物料"

        best_match, best_score = scored[0]
        name_key = self._normalize_match_key(item.material_name)
        spec_key = self._normalize_match_key(item.specification)

        if not name_key:
            return None, best_score, "缺少物料名称，无法确认标准物料"
        if not spec_key:
            return None, best_score, "缺少规格型号，无法唯一确认标准物料"

        best_spec_key = self._normalize_match_key(best_match.get("specification"))
        if spec_key != best_spec_key:
            # 高相似度不得覆盖规格硬冲突或缺失的区分属性
            return None, best_score, self._spec_conflict_reason(item, best_match)

        if not self._name_compatible(name_key, best_match):
            return None, best_score, (
                f"物料名称 '{item.material_name}' 与最高相似候选 "
                f"{best_match.get('sku_code')}（{best_match.get('material_name')}）不兼容"
            )

        # 多个候选同时满足规格一致与名称兼容时属于歧义，不得任选其一
        acceptable_skus = list(
            dict.fromkeys(
                doc.get("sku_code")
                for doc, _ in scored
                if doc.get("sku_code")
                and self._normalize_match_key(doc.get("specification")) == spec_key
                and self._name_compatible(name_key, doc)
            )
        )
        if len(acceptable_skus) > 1:
            return None, best_score, (
                f"存在多个规格与名称一致的候选：{acceptable_skus}"
            )

        if best_score < self.match_threshold:
            return None, best_score, (
                f"最高相似度 {best_score:.2f} 低于阈值 {self.match_threshold:.2f}"
            )

        return best_match, best_score, None

    def _build_matched_item(
        self,
        item: Any,
        match: Optional[Dict[str, Any]],
        score: float,
        match_basis: Optional[str] = None,
        candidate_skus: Optional[List[str]] = None,
        rejection_reason: Optional[str] = None,
    ) -> MatchedOrderItem:
        return MatchedOrderItem(
            material_name=item.material_name,
            specification=item.specification,
            quantity=item.quantity,
            unit=item.unit,
            unit_price=item.unit_price,
            delivery_date=item.delivery_date,
            confidence_score=item.confidence_score,
            sku_code=match.get('sku_code') if match else None,
            matched_material_name=match.get('material_name') if match else None,
            matched_specification=match.get('specification') if match else None,
            match_score=score,
            candidate_skus=candidate_skus or [],
            match_basis=match_basis,
            rejection_reason=rejection_reason,
        )

    def _match_item(self, item: Any) -> MatchedOrderItem:
        self._build_key_index()
        name_key = self._normalize_match_key(item.material_name)
        spec_key = self._normalize_match_key(item.specification)
        compatible_skus = list(dict.fromkeys(
            row["sku_code"] for row in self._spec_index.get(spec_key, [])
            if self._name_compatible(name_key, row)
        ))
        if len(compatible_skus) > 1:
            return self._build_matched_item(
                item, None, 0.0, candidate_skus=compatible_skus,
                rejection_reason=f"全目录存在多个规格与名称一致的候选：{compatible_skus}",
            )
        deterministic_match = self._match_by_catalog_key(item)
        if deterministic_match is not None:
            return self._build_matched_item(
                item,
                deterministic_match,
                1.0,
                match_basis=self._catalog_basis(item, deterministic_match),
                candidate_skus=[deterministic_match.get("sku_code")],
            )

        query_text = self._build_query_text(item)
        search_results: List[Tuple[Dict[str, Any], float]] = []
        if query_text:
            try:
                search_results = self.faiss_manager.search(query_text, k=3)
            except Exception as e:
                self.log_error(f"FAISS search failed for '{query_text}': {str(e)}")
        else:
            self.log_warning(f"Empty query for item: {item.material_name}")

        scored = sorted(
            (
                (doc, self._calculate_match_score(distance))
                for doc, distance in search_results
            ),
            key=lambda pair: pair[1],
            reverse=True,
        )

        candidate_skus = list(
            dict.fromkeys(
                doc.get("sku_code") for doc, _ in scored if doc.get("sku_code")
            )
        )

        accepted_match, best_score, rejection_reason = self._accept_vector_candidate(
            item, scored
        )

        if accepted_match is not None:
            self.log_info(
                f"物料 '{item.material_name}' 向量接受 SKU "
                f"{accepted_match.get('sku_code')}，得分 {best_score:.2f}"
            )
        else:
            self.log_warning(
                f"物料 '{item.material_name}' 未接受候选 SKU：{rejection_reason}"
            )

        return self._build_matched_item(
            item,
            accepted_match,
            best_score,
            match_basis="vector_spec_exact" if accepted_match is not None else None,
            candidate_skus=candidate_skus,
            rejection_reason=rejection_reason,
        )

    def get_reference_prices(self, matched_order: MatchedOrder) -> Dict[int, float]:
        reference_prices: Dict[int, float] = {}

        for idx, item in enumerate(matched_order.items):
            if not getattr(item, "sku_code", None):
                continue

            try:
                doc = next((row for row in self.faiss_manager.metadata if row.get("sku_code") == item.sku_code), None)
                reference_price = doc.get("reference_price") if doc else None
                if reference_price is not None:
                    reference_prices[idx] = float(reference_price)
            except Exception as exc:
                self.log_warning(
                    f"参考价查询失败，item_index={idx}, sku={item.sku_code}: {exc}"
                )

        return reference_prices
    
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.log_info("开始物料匹配")
        
        try:
            self.validate_input(input_data, required_keys=["parsed_order"])
            
            parsed_order: ParsedOrder = input_data.get("parsed_order")
            
            matched_items: List[MatchedOrderItem] = []
            for item in parsed_order.items:
                matched_item = self._match_item(item)
                matched_items.append(matched_item)
                self.log_info(
                    f"物料 '{item.material_name}' 匹配完成，得分: {matched_item.match_score:.2f}"
                )
            
            matched_order = MatchedOrder(
                order_number=parsed_order.order_number,
                customer_name=parsed_order.customer_name,
                items=matched_items,
                total_amount=parsed_order.total_amount,
                parsing_issues=parsed_order.parsing_issues,
            )
            
            self.log_info(f"物料匹配完成，共匹配 {len(matched_items)} 项")
            
            return {
                "success": True,
                "matched_order": matched_order,
                "message": "匹配成功"
            }
            
        except ValueError as e:
            error_msg = f"输入验证失败: {str(e)}"
            self.log_error(error_msg)
            return {
                "success": False,
                "matched_order": None,
                "message": error_msg
            }
        except Exception as e:
            error_msg = f"匹配失败: {str(e)}"
            self.log_error(error_msg)
            return {
                "success": False,
                "matched_order": None,
                "message": error_msg
            }
