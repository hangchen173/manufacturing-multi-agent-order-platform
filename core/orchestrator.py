from typing import Any, Dict, Optional
from pathlib import Path
from core.agents import ParserAgent, MatchingAgent, RiskControlAgent
from core.agents.parser_agent import ParserScenario
from core.models import OrderStatus, FinalOrderResult
from core.utils.order_manager import OrderManager
from core.constants import SUPPORTED_IMAGE_EXTENSIONS
from core.exceptions import OrchestratorException, OrderNotFoundException
from utils.data_processing.document_loader import DocumentLoader
from config import Config

class OrderProcessingOrchestrator:
    def __init__(self, order_manager: Optional[OrderManager] = None, config: Optional[Config] = None):
        self.config = config or Config()
        self.order_manager = order_manager or OrderManager()
        self.document_loader = DocumentLoader()
        
        self.parser_agent_general = ParserAgent(scenario=ParserScenario.GENERAL_PARSING, config=self.config)
        self.parser_agent_logic = ParserAgent(scenario=ParserScenario.LOGIC_DECISION, config=self.config)
        self.parser_agent_vl = ParserAgent(scenario=ParserScenario.IMAGE_OCR, config=self.config)
        self.matching_agent = MatchingAgent(config=self.config)
        self.risk_agent = RiskControlAgent(config=self.config)
    
    def process_order_from_document(self, file_path: str) -> Dict[str, Any]:
        try:
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext in SUPPORTED_IMAGE_EXTENSIONS:
                return self._process_image_order(file_path)
            else:
                return self._process_text_based_order(file_path)
        except Exception as e:
            return {
                "success": False,
                "order_id": None,
                "message": f"文档处理失败: {str(e)}"
            }
    
    def _process_text_based_order(self, file_path: str) -> Dict[str, Any]:
        order_text, doc_type = self.document_loader.load_document(file_path)
        order_id = self.order_manager.create_order(
            document_path=file_path,
            document_type=doc_type,
            order_text=order_text
        )
        return self._process_order_with_parser(
            order_id,
            self.parser_agent_general,
            {"order_text": order_text}
        )
    
    def _process_image_order(self, file_path: str) -> Dict[str, Any]:
        file_ext = Path(file_path).suffix.lower()
        image_type = 'jpeg' if file_ext in ['.jpg', '.jpeg'] else 'png'
        
        order_id = self.order_manager.create_order(
            document_path=file_path,
            document_type='image',
            order_text=""
        )
        
        return self._process_order_with_parser(
            order_id,
            self.parser_agent_vl,
            {
                "image_path": file_path,
                "image_type": image_type
            }
        )
    
    def process_order_from_text(self, order_text: str) -> Dict[str, Any]:
        try:
            order_id = self.order_manager.create_order(order_text=order_text)
            return self._process_order_with_parser(
                order_id,
                self.parser_agent_general,
                {"order_text": order_text}
            )
        except Exception as e:
            return {
                "success": False,
                "order_id": None,
                "message": f"订单处理失败: {str(e)}"
            }
    
    def _process_order_with_parser(
        self, 
        order_id: str, 
        parser_agent: ParserAgent, 
        parser_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        self.order_manager.update_order_status(order_id, OrderStatus.PARSING)
        
        parser_result = parser_agent.run(parser_input)
        
        if not parser_result["success"]:
            self.order_manager.set_error(order_id, parser_result["message"])
            return {
                "success": False,
                "order_id": order_id,
                "message": parser_result["message"]
            }
        
        parsed_order = parser_result["parsed_order"]
        self.order_manager.update_parsed_order(order_id, parsed_order)
        
        return self._process_matching_phase(order_id, parsed_order)
    
    def _process_matching_phase(self, order_id: str, parsed_order: Any) -> Dict[str, Any]:
        self.order_manager.update_order_status(order_id, OrderStatus.MATCHING)
        matching_result = self.matching_agent.run({"parsed_order": parsed_order})
        
        if not matching_result["success"]:
            self.order_manager.set_error(order_id, matching_result["message"])
            return {
                "success": False,
                "order_id": order_id,
                "message": matching_result["message"]
            }
        
        matched_order = matching_result["matched_order"]
        self.order_manager.update_matched_order(order_id, matched_order)
        
        return self._process_risk_phase(order_id, matched_order)
    
    def _process_risk_phase(self, order_id: str, matched_order: Any) -> Dict[str, Any]:
        self.order_manager.update_order_status(order_id, OrderStatus.RISK_CHECKING)
        
        reference_prices = self._get_reference_prices(matched_order)
        
        risk_input = {
            "matched_order": matched_order,
            "reference_prices": reference_prices
        }
        risk_result = self.risk_agent.run(risk_input)
        
        if not risk_result["success"]:
            self.order_manager.set_error(order_id, risk_result["message"])
            return {
                "success": False,
                "order_id": order_id,
                "message": risk_result["message"]
            }
        
        risk_check_result = risk_result["risk_result"]
        self.order_manager.update_risk_result(order_id, risk_check_result)
        
        return self._finalize_order(order_id, matched_order, risk_check_result)
    
    def _get_reference_prices(self, matched_order: Any) -> Dict[int, float]:
        reference_prices = {}
        for idx, item in enumerate(matched_order.items):
            if hasattr(item, 'sku_code') and item.sku_code:
                try:
                    if hasattr(self.matching_agent, 'faiss_manager'):
                        search_text = f"{item.sku_code} {item.matched_material_name or ''}"
                        results = self.matching_agent.faiss_manager.search(search_text, k=1)
                        if results:
                            doc, _ = results[0]
                            reference_prices[idx] = doc.get('reference_price')
                except Exception:
                    pass
        return reference_prices
    
    def _finalize_order(
        self, 
        order_id: str, 
        matched_order: Any, 
        risk_check_result: Any
    ) -> Dict[str, Any]:
        low_match_score = any(
            item.match_score < 0.8 
            for item in matched_order.items 
            if hasattr(item, 'match_score')
        )
        needs_confirmation = low_match_score or risk_check_result.needs_confirmation
        
        final_status = OrderStatus.COMPLETED
        if needs_confirmation:
            final_status = OrderStatus.NEEDS_CONFIRMATION
            confirmation_request = self._create_confirmation_request(
                order_id, 
                risk_check_result, 
                matched_order, 
                low_match_score
            )
            self.order_manager.add_confirmation_request(order_id, confirmation_request)
        
        self.order_manager.update_order_status(order_id, final_status)
        
        order = self.order_manager.get_order(order_id)
        final_result = FinalOrderResult(
            status=final_status,
            parsed_order=order.parsed_order,
            matched_order=matched_order,
            risk_result=risk_check_result,
            message="订单处理完成"
        )
        
        return {
            "success": True,
            "order_id": order_id,
            "final_result": final_result,
            "needs_confirmation": needs_confirmation,
            "message": "订单处理完成"
        }
    
    def _create_confirmation_request(
        self, 
        order_id: str, 
        risk_result: Any, 
        matched_order: Any = None, 
        low_match_score: bool = False
    ) -> Dict[str, Any]:
        issues_summary = [
            {
                "item_index": issue.item_index,
                "issue_type": issue.issue_type,
                "description": issue.description,
                "severity": issue.severity
            }
            for issue in risk_result.issues
        ]
        
        reasons = []
        if low_match_score:
            reasons.append("部分物料匹配得分低于 0.8")
        if risk_result.issues:
            reasons.append(f"发现 {len(risk_result.issues)} 个风险问题")
        
        return {
            "type": "risk_confirmation",
            "order_id": order_id,
            "overall_confidence": risk_result.overall_confidence,
            "issues": issues_summary,
            "needs_confirmation_reasons": reasons,
            "low_match_score": low_match_score,
            "timestamp": None,
            "required_actions": ["review_issues", "confirm_or_reject"]
        }
    
    def confirm_order(self, order_id: str, confirmation: Dict[str, Any]) -> Dict[str, Any]:
        order = self.order_manager.get_order(order_id)
        if not order:
            return {
                "success": False,
                "message": "订单不存在"
            }
        
        if order.status != OrderStatus.NEEDS_CONFIRMATION:
            return {
                "success": False,
                "message": "订单不需要确认"
            }
        
        action = confirmation.get("action")
        if action == "confirm":
            self.order_manager.update_order_status(order_id, OrderStatus.COMPLETED)
            return {
                "success": True,
                "order_id": order_id,
                "message": "订单已确认"
            }
        elif action == "reject":
            self.order_manager.update_order_status(order_id, OrderStatus.FAILED)
            return {
                "success": True,
                "order_id": order_id,
                "message": "订单已拒绝"
            }
        else:
            return {
                "success": False,
                "message": "无效的确认操作"
            }
    
    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        return self.order_manager.get_order_status(order_id)
