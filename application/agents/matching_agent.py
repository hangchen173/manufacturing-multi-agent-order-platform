from typing import TYPE_CHECKING, Any, Dict, List, Optional

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
    
    def _create_unmatched_item(self, item: Any) -> MatchedOrderItem:
        return MatchedOrderItem(
            material_name=item.material_name,
            specification=item.specification,
            quantity=item.quantity,
            unit=item.unit,
            unit_price=item.unit_price,
            delivery_date=item.delivery_date,
            confidence_score=item.confidence_score,
            sku_code=None,
            matched_material_name=None,
            match_score=0.0
        )
    
    def _match_item(self, item: Any) -> MatchedOrderItem:
        query_text = self._build_query_text(item)
        
        if not query_text:
            self.log_warning(f"Empty query for item: {item.material_name}")
            return self._create_unmatched_item(item)
        
        try:
            search_results = self.faiss_manager.search(query_text, k=3)
        except Exception as e:
            self.log_error(f"FAISS search failed for '{query_text}': {str(e)}")
            return self._create_unmatched_item(item)
        
        if not search_results:
            self.log_warning(f"No matches found for '{query_text}'")
            return self._create_unmatched_item(item)
        
        best_match = None
        best_score = 0.0
        
        for doc, distance in search_results:
            score = self._calculate_match_score(distance)
            if score > best_score:
                best_score = score
                best_match = doc

        if best_score < self.match_threshold:
            self.log_warning(
                f"物料 '{item.material_name}' 的最佳匹配低于阈值 {self.match_threshold:.2f}"
            )
        
        return MatchedOrderItem(
            material_name=item.material_name,
            specification=item.specification,
            quantity=item.quantity,
            unit=item.unit,
            unit_price=item.unit_price,
            delivery_date=item.delivery_date,
            confidence_score=item.confidence_score,
            sku_code=best_match.get('sku_code') if best_match else None,
            matched_material_name=best_match.get('material_name') if best_match else None,
            match_score=best_score
        )

    def get_reference_prices(self, matched_order: MatchedOrder) -> Dict[int, float]:
        reference_prices: Dict[int, float] = {}

        for idx, item in enumerate(matched_order.items):
            if not getattr(item, "sku_code", None):
                continue

            try:
                search_text = f"{item.sku_code} {item.matched_material_name or ''}".strip()
                results = self.faiss_manager.search(search_text, k=1)
                if not results:
                    continue

                doc, _ = results[0]
                reference_price = doc.get("reference_price")
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
                total_amount=parsed_order.total_amount
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
