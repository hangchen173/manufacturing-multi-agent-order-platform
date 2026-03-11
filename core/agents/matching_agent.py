from typing import Any, Dict, List
from core.agents.base_agent import BaseAgent
from core.models import ParsedOrder, MatchedOrder, MatchedOrderItem
from utils.vector_store.faiss_manager import FAISSManager
from config import Config

class MatchingAgent(BaseAgent):
    def __init__(self, llm=None, faiss_manager=None):
        super().__init__(llm)
        self.config = Config()
        if faiss_manager:
            self.faiss_manager = faiss_manager
        else:
            self.faiss_manager = FAISSManager(
                index_path=self.config.FAISS_INDEX_PATH
            )
    
    def _calculate_match_score(self, distance: float) -> float:
        return max(0.0, min(1.0, 1.0 - distance / 2.0))
    
    def _match_item(self, item: Any) -> MatchedOrderItem:
        query_text = f"{item.material_name} {item.specification}"
        
        search_results = self.faiss_manager.search(query_text, k=3)
        
        best_match = None
        best_score = 0.0
        
        if search_results:
            for doc, distance in search_results:
                score = self._calculate_match_score(distance)
                if score > best_score:
                    best_score = score
                    best_match = doc
        
        matched_item = MatchedOrderItem(
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
        
        return matched_item
    
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.log_info("开始物料匹配")
        
        try:
            parsed_order: ParsedOrder = input_data.get("parsed_order")
            if not parsed_order:
                raise ValueError("解析订单不能为空")
            
            matched_items: List[MatchedOrderItem] = []
            for item in parsed_order.items:
                matched_item = self._match_item(item)
                matched_items.append(matched_item)
                self.log_info(f"物料 '{item.material_name}' 匹配完成，得分: {matched_item.match_score:.2f}")
            
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
        except Exception as e:
            self.log_error(f"匹配失败: {str(e)}")
            return {
                "success": False,
                "matched_order": None,
                "message": f"匹配失败: {str(e)}"
            }
