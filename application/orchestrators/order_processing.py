from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path

from application.agents import MatchingAgent, ParserAgent, ParserScenario, RiskControlAgent
from application.pipeline import AgentPipelineStage
from application.services import OrderManager
from config import Config
from domain.constants import SUPPORTED_IMAGE_EXTENSIONS
from domain.models import FinalOrderResult, OrderStatus
from infrastructure.document_processing import DocumentLoader

class OrderProcessingOrchestrator:
    def __init__(
        self,
        order_manager: Optional[OrderManager] = None,
        config: Optional[Config] = None,
        document_loader: Optional[DocumentLoader] = None,
        parser_agent_general: Optional[ParserAgent] = None,
        parser_agent_vl: Optional[ParserAgent] = None,
        matching_agent: Optional[MatchingAgent] = None,
        risk_agent: Optional[RiskControlAgent] = None,
    ):
        self.config = config or Config()
        self.order_manager = order_manager or OrderManager(config=self.config)
        self.document_loader = document_loader or DocumentLoader()
        
        self.parser_agent_general = parser_agent_general or ParserAgent(
            scenario=ParserScenario.GENERAL_PARSING,
            config=self.config,
        )
        self.parser_agent_vl = parser_agent_vl or ParserAgent(
            scenario=ParserScenario.IMAGE_OCR,
            config=self.config,
        )
        self.matching_agent = matching_agent or MatchingAgent(config=self.config)
        self.risk_agent = risk_agent or RiskControlAgent(config=self.config)

        self.parser_stage_general = AgentPipelineStage(
            name="parser_general",
            target_status=OrderStatus.PARSING,
            status_reason="parser_started",
            runner=self.parser_agent_general.run,
            payload_key="parsed_order",
            persist_callback=self.order_manager.update_parsed_order,
        )
        self.parser_stage_vl = AgentPipelineStage(
            name="parser_image",
            target_status=OrderStatus.PARSING,
            status_reason="image_parser_started",
            runner=self.parser_agent_vl.run,
            payload_key="parsed_order",
            persist_callback=self.order_manager.update_parsed_order,
        )
        self.matching_stage = AgentPipelineStage(
            name="matching",
            target_status=OrderStatus.MATCHING,
            status_reason="matching_started",
            runner=self.matching_agent.run,
            payload_key="matched_order",
            persist_callback=self.order_manager.update_matched_order,
        )
        self.risk_stage = AgentPipelineStage(
            name="risk_control",
            target_status=OrderStatus.RISK_CHECKING,
            status_reason="risk_check_started",
            runner=self.risk_agent.run,
            payload_key="risk_result",
            persist_callback=self.order_manager.update_risk_result,
        )

    def _build_error_response(self, message: str, order_id: Optional[str] = None) -> Dict[str, Any]:
        return {
            "success": False,
            "order_id": order_id,
            "message": message,
        }
    
    def process_order_from_document(self, file_path: str) -> Dict[str, Any]:
        try:
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext in SUPPORTED_IMAGE_EXTENSIONS:
                return self._process_image_order(file_path)
            else:
                return self._process_text_based_order(file_path)
        except Exception as e:
            return self._build_error_response(f"文档处理失败: {str(e)}")
    
    def _process_text_based_order(self, file_path: str) -> Dict[str, Any]:
        order_text, doc_type = self.document_loader.load_document(file_path)
        order_id = self.order_manager.create_order(
            document_path=file_path,
            document_type=doc_type,
            order_text=order_text
        )
        return self._process_order_with_parser(
            order_id,
            self.parser_stage_general,
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
            self.parser_stage_vl,
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
                self.parser_stage_general,
                {"order_text": order_text}
            )
        except Exception as e:
            return self._build_error_response(f"订单处理失败: {str(e)}")
    
    def _process_order_with_parser(
        self, 
        order_id: str, 
        parser_stage: AgentPipelineStage,
        parser_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        parser_result = parser_stage.execute(
            order_manager=self.order_manager,
            order_id=order_id,
            input_data=parser_input,
        )
        if not parser_result.success:
            return self._build_error_response(parser_result.message, order_id)

        parsed_order = parser_result.payload
        
        return self._process_matching_phase(order_id, parsed_order)
    
    def _process_matching_phase(self, order_id: str, parsed_order: Any) -> Dict[str, Any]:
        matching_result = self.matching_stage.execute(
            order_manager=self.order_manager,
            order_id=order_id,
            input_data={"parsed_order": parsed_order},
        )
        if not matching_result.success:
            return self._build_error_response(matching_result.message, order_id)

        matched_order = matching_result.payload
        
        return self._process_risk_phase(order_id, matched_order)
    
    def _process_risk_phase(self, order_id: str, matched_order: Any) -> Dict[str, Any]:
        reference_prices = self.matching_agent.get_reference_prices(matched_order)
        risk_result = self.risk_stage.execute(
            order_manager=self.order_manager,
            order_id=order_id,
            input_data={
                "matched_order": matched_order,
                "reference_prices": reference_prices,
            },
        )
        if not risk_result.success:
            return self._build_error_response(risk_result.message, order_id)

        risk_check_result = risk_result.payload
        
        return self._finalize_order(order_id, matched_order, risk_check_result)
    
    def _finalize_order(
        self, 
        order_id: str, 
        matched_order: Any, 
        risk_check_result: Any
    ) -> Dict[str, Any]:
        low_match_score = any(
            item.match_score < self.config.risk.match_threshold
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
        
        self.order_manager.update_order_status(
            order_id,
            final_status,
            reason="requires_manual_confirmation" if needs_confirmation else "processing_completed",
        )
        
        order = self.order_manager.get_order(order_id)
        final_result = FinalOrderResult(
            status=final_status,
            parsed_order=order.parsed_order,
            matched_order=matched_order,
            risk_result=risk_check_result,
            message="订单处理完成"
        )
        self.order_manager.update_final_result(order_id, final_result)
        
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
            reasons.append(f"部分物料匹配得分低于 {self.config.risk.match_threshold:.1f}")
        if risk_result.issues:
            reasons.append(f"发现 {len(risk_result.issues)} 个风险问题")
        
        return {
            "type": "risk_confirmation",
            "order_id": order_id,
            "overall_confidence": risk_result.overall_confidence,
            "issues": issues_summary,
            "needs_confirmation_reasons": reasons,
            "low_match_score": low_match_score,
            "timestamp": datetime.now().isoformat(),
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
            self.order_manager.update_order_status(
                order_id,
                OrderStatus.COMPLETED,
                reason="manually_confirmed",
            )
            return {
                "success": True,
                "order_id": order_id,
                "message": "订单已确认"
            }
        elif action == "reject":
            self.order_manager.update_order_status(
                order_id,
                OrderStatus.FAILED,
                reason="manually_rejected",
            )
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

    def get_order_detail(self, order_id: str) -> Optional[Dict[str, Any]]:
        return self.order_manager.get_order_detail(order_id)

    def list_orders(self) -> list[Dict[str, Any]]:
        return self.order_manager.list_order_summaries()
