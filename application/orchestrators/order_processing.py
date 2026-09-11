from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

from application.agents import MatchingAgent, ParserAgent, ParserScenario, RiskControlAgent
from application.pipeline import AgentPipelineStage
from application.services import OrderManager
from config import Config
from domain.constants import SUPPORTED_IMAGE_EXTENSIONS
from domain.models import (
    BusinessAction,
    BusinessDecision,
    FinalOrderResult,
    MatchedOrderItem,
    NormalizationChange,
    OrderStatus,
)
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
        self._last_usage: Dict[str, int] = self._empty_usage()
        
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

    @staticmethod
    def _empty_usage() -> Dict[str, int]:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def _build_error_response(self, message: str, order_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            order = self.order_manager.get_order(order_id) if order_id else None
        except Exception:
            order = None
        return {
            "success": False,
            "order_id": order_id,
            "message": message,
            "usage": dict(self._last_usage),
            "diagnostics": order.processing_diagnostics if order else {},
        }
    
    def process_order_from_document(self, file_path: str) -> Dict[str, Any]:
        self._last_usage = self._empty_usage()
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
        self._last_usage = self._empty_usage()
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
        self, order_id: str, parser_stage: AgentPipelineStage, parser_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            return self._run_order_pipeline(order_id, parser_stage, parser_input)
        except Exception as exc:
            message = f"订单处理失败: {exc}"
            try:
                persisted = self.order_manager.set_error(order_id, message)
            except Exception:
                persisted = False
            response = self._build_error_response(message, order_id)
            response["failure_status_persisted"] = persisted
            return response

    def _run_order_pipeline(
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
        self._last_usage = dict(parser_result.usage)
        if not parser_result.success:
            return self._build_error_response(parser_result.message, order_id)

        parsed_order = parser_result.payload

        if not parsed_order.items:
            message = "未从订单中解析出任何物料明细，已拒绝处理"
            self.order_manager.set_error(order_id, message)
            return self._build_error_response(message, order_id)

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
        if not matched_order.items:
            message = "订单无有效物料明细，已拒绝处理"
            self.order_manager.set_error(order_id, message)
            return self._build_error_response(message, order_id)

        needs_confirmation = risk_check_result.needs_confirmation
        business_decision = self._decide_business_action(matched_order, needs_confirmation)
        
        final_status = OrderStatus.COMPLETED
        confirmation_request = None
        if needs_confirmation:
            final_status = OrderStatus.NEEDS_CONFIRMATION
            confirmation_request = self._create_confirmation_request(
                order_id, 
                risk_check_result
            )
        
        order = self.order_manager.get_order(order_id)
        final_result = FinalOrderResult(
            status=final_status,
            parsed_order=order.parsed_order,
            matched_order=matched_order,
            risk_result=risk_check_result,
            business_decision=business_decision,
            message="订单处理完成"
        )
        if not self.order_manager.finalize_order(order_id, final_result, confirmation_request):
            return self._build_error_response("订单状态已变化，无法保存最终结果", order_id)
        
        return {
            "success": True,
            "order_id": order_id,
            "final_result": final_result,
            "business_decision": business_decision,
            "needs_confirmation": needs_confirmation,
            "message": "订单处理完成",
            "usage": dict(self._last_usage),
            "diagnostics": order.processing_diagnostics,
        }
    
    def _decide_business_action(
        self, matched_order: Any, needs_confirmation: bool
    ) -> BusinessDecision:
        if needs_confirmation:
            return BusinessDecision(
                action=BusinessAction.MANUAL_REVIEW,
                reason="风控发现高风险明细项，需人工确认",
            )

        normalizations: List[NormalizationChange] = []
        for index, item in enumerate(matched_order.items):
            normalizations.extend(self._collect_normalizations(item, index))

        if normalizations:
            fields = sorted({change.field for change in normalizations})
            return BusinessDecision(
                action=BusinessAction.AUTO_CORRECT,
                reason=(
                    f"{len(normalizations)} 处明细字段按标准物料库完成确定性归一化"
                    f"（{'、'.join(fields)}），未改变采购意图，未发现风险"
                ),
                normalizations=normalizations,
            )

        return BusinessDecision(
            action=BusinessAction.AUTO_APPROVE,
            reason="全部明细与标准物料库一致，未发现风险",
        )

    _NAME_BASIS = {
        "catalog_alias_spec_exact": "物料名称命中标准库已登记别名",
        "catalog_name_spec_exact": "物料名称为标准名的等价书写",
        "vector_spec_exact": "物料名称与标准库名称兼容且规格一致",
    }

    def _collect_normalizations(
        self, item: MatchedOrderItem, item_index: int
    ) -> List[NormalizationChange]:
        # 仅在接受标准 SKU 后才做归一化；未接受任何 SKU 时不得改写任何字段
        if not item.sku_code:
            return []

        changes: List[NormalizationChange] = []

        # 名称：登记别名或标准名的等价书写，属于不改变采购意图的确定性归一化
        if self._differs(item.material_name, item.matched_material_name):
            changes.append(NormalizationChange(
                item_index=item_index,
                field="material_name",
                original_value=item.material_name,
                standard_value=item.matched_material_name,
                basis=self._NAME_BASIS.get(
                    item.match_basis or "", "名称归一化为标准物料名"
                ),
            ))

        # 规格：匹配已确认标准规格与原规格为等价书写时才归一化，绝不猜测规格
        if self._differs(item.specification, item.matched_specification):
            changes.append(NormalizationChange(
                item_index=item_index,
                field="specification",
                original_value=item.specification,
                standard_value=item.matched_specification,
                basis="标准规格与原规格为等价书写",
            ))

        # 数量、单价、交期不参与自动纠正；单位换算无明确依据一律不自动执行
        return changes

    @staticmethod
    def _differs(original: Optional[str], standard: Optional[str]) -> bool:
        if not original or not standard:
            return False
        return original.strip() != standard.strip()
    
    def _create_confirmation_request(
        self, 
        order_id: str, 
        risk_result: Any
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
        if risk_result.issues:
            reasons.append(f"发现 {len(risk_result.issues)} 个风险问题")
        
        return {
            "type": "risk_confirmation",
            "order_id": order_id,
            "overall_confidence": risk_result.overall_confidence,
            "issues": issues_summary,
            "needs_confirmation_reasons": reasons,
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
        if action not in {"confirm", "reject"}:
            return {
                "success": False,
                "message": "无效的确认操作"
            }
        if not self.order_manager.review_order(order_id, action, confirmation.get("comment")):
            return {"success": False, "order_id": order_id, "message": "订单已被处理，请刷新后查看"}
        return {
            "success": True, "order_id": order_id,
            "message": "订单已确认" if action == "confirm" else "订单已拒绝",
        }
    
    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        return self.order_manager.get_order_status(order_id)

    def get_order_detail(self, order_id: str) -> Optional[Dict[str, Any]]:
        return self.order_manager.get_order_detail(order_id)

    def list_orders(self) -> list[Dict[str, Any]]:
        return self.order_manager.list_order_summaries()
