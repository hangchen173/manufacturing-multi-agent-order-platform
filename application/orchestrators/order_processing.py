"""订单处理编排器（薄适配层）。

设计文档 §3.2 要求本模块**降级为薄适配层**：只负责

```
HTTP 请求 → 组装 Agent 群 + Supervisor → 提交订单 → 映射裁决结果
```

全部业务判定逻辑（解析、匹配、风控、终裁）都已下沉到 Agent 与 Supervisor。
这里不再有任何 `if/else` 决策分支，也不再持有"某个 Agent 的阶段执行器"。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from application.agents import (
    Adjudicator,
    CatalogMatcher,
    Disambiguator,
    Extractor,
    GroundingVerifier,
    PolicyRisk,
    ReviewAssistant,
    ScheduleRisk,
    SemanticMatcher,
    StructureScout,
    Supervisor,
)
from application.services import OrderManager
from config import Config
from domain.agent_roles import AgentRole
from domain.constants import SUPPORTED_IMAGE_EXTENSIONS
from domain.models import (
    BusinessDecision,
    FinalOrderResult,
    MatchedOrder,
    OrderStatus,
    ParsedOrder,
    RiskCheckResult,
)
from infrastructure.document_processing import DocumentLoader


class OrderProcessingOrchestrator:
    def __init__(
        self,
        order_manager: OrderManager,
        config: Optional[Config] = None,
        document_loader: Optional[DocumentLoader] = None,
        supervisor: Optional[Supervisor] = None,
        faiss_manager: Optional[Any] = None,
        agents: Optional[Dict[AgentRole, Any]] = None,
        reference_date: Optional[str] = None,
    ):
        self.config = config or Config()
        self.order_manager = order_manager
        self.document_loader = document_loader or DocumentLoader()
        self.faiss_manager = faiss_manager
        self._last_usage: Dict[str, int] = self._empty_usage()
        self._last_diagnostics: Dict[str, Any] = {}

        self.agents = agents or self._build_agents(faiss_manager)
        self.supervisor = supervisor or Supervisor(
            agents=self.agents,
            order_manager=self.order_manager,
            catalog=self._catalog(),
            reference_date=reference_date or self.config.risk.evaluation_as_of,
        )

    # ------------------------------------------------------------------ wiring
    def _build_agents(self, faiss_manager: Optional[Any]) -> Dict[AgentRole, Any]:
        return {
            AgentRole.STRUCTURE_SCOUT: StructureScout(config=self.config),
            AgentRole.EXTRACTOR: Extractor(config=self.config),
            AgentRole.GROUNDING_VERIFIER: GroundingVerifier(config=self.config),
            AgentRole.CATALOG_MATCHER: CatalogMatcher(config=self.config),
            AgentRole.SEMANTIC_MATCHER: SemanticMatcher(
                faiss_manager=faiss_manager, config=self.config
            ),
            AgentRole.DISAMBIGUATOR: Disambiguator(
                match_threshold=self.config.risk.match_threshold, config=self.config
            ),
            AgentRole.POLICY_RISK: PolicyRisk(config=self.config),
            AgentRole.SCHEDULE_RISK: ScheduleRisk(config=self.config),
            AgentRole.ADJUDICATOR: Adjudicator(config=self.config),
            AgentRole.REVIEW_ASSISTANT: ReviewAssistant(
                faiss_manager=faiss_manager, config=self.config
            ),
        }

    def _catalog(self) -> List[Dict[str, Any]]:
        return list(getattr(self.faiss_manager, "metadata", []) or [])

    @staticmethod
    def _empty_usage() -> Dict[str, int]:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    # ------------------------------------------------------------------ entries
    def process_order_from_document(self, file_path: str) -> Dict[str, Any]:
        self._last_usage = self._empty_usage()
        try:
            file_ext = Path(file_path).suffix.lower()
            if file_ext in SUPPORTED_IMAGE_EXTENSIONS:
                return self._process_image_order(file_path)
            return self._process_text_based_order(file_path)
        except Exception as exc:  # noqa: BLE001 - 适配层兜底，不得泄漏异常
            return self._build_error_response(f"文档处理失败: {exc}")

    def process_order_from_text(self, order_text: str) -> Dict[str, Any]:
        self._last_usage = self._empty_usage()
        try:
            order_id = self.order_manager.create_order(order_text=order_text)
            return self._run(order_id, {"document_type": "text", "text": order_text})
        except Exception as exc:  # noqa: BLE001
            return self._build_error_response(f"订单处理失败: {exc}")

    def _process_text_based_order(self, file_path: str) -> Dict[str, Any]:
        order_text, doc_type = self.document_loader.load_document(file_path)
        order_id = self.order_manager.create_order(
            document_path=file_path, document_type=doc_type, order_text=order_text,
        )
        return self._run(order_id, self._to_document_ir(order_text, doc_type))

    def _process_image_order(self, file_path: str) -> Dict[str, Any]:
        file_ext = Path(file_path).suffix.lower()
        image_type = "jpeg" if file_ext in (".jpg", ".jpeg") else "png"
        order_id = self.order_manager.create_order(
            document_path=file_path, document_type="image", order_text="",
        )
        return self._run(
            order_id, {"document_type": "image"}, image_path=file_path, image_type=image_type,
        )

    @staticmethod
    def _to_document_ir(order_text: str, doc_type: Optional[str]) -> Dict[str, Any]:
        if doc_type in {"pdf", "excel"}:
            return json.loads(order_text)
        return {"document_type": "text", "text": order_text}

    # ------------------------------------------------------------------ run
    def _run(
        self,
        order_id: str,
        document_ir: Dict[str, Any],
        image_path: Optional[str] = None,
        image_type: str = "jpeg",
    ) -> Dict[str, Any]:
        result = self.supervisor.run(
            order_id, document_ir, image_path=image_path, image_type=image_type,
        )
        self._last_usage = dict(result.get("usage") or self._empty_usage())
        self._last_diagnostics = dict(result.get("diagnostics") or {})
        if self._last_diagnostics:
            self.order_manager.record_stage(order_id, "pipeline", self._last_diagnostics)
        if not result.get("success"):
            message = result.get("message") or "订单处理失败"
            response = self._build_error_response(message, order_id)
            response["failure_status_persisted"] = self._safe_set_error(order_id, message)
            return response
        return self._finalize(order_id, result)

    def _finalize(self, order_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        verdict = result.get("verdict") or {}
        try:
            parsed_order = ParsedOrder.model_validate(verdict["parsed_order"])
            matched_order = MatchedOrder.model_validate(verdict["matched_order"])
            risk_result = RiskCheckResult.model_validate(verdict["risk_result"])
            business_decision = BusinessDecision.model_validate(verdict["business_decision"])
        except (KeyError, ValueError) as exc:
            message = f"裁决结果不完整，无法落库: {exc}"
            self.order_manager.set_error(order_id, message)
            return self._build_error_response(message, order_id)

        if not matched_order.items:
            message = "订单无有效物料明细，已拒绝处理"
            self.order_manager.set_error(order_id, message)
            return self._build_error_response(message, order_id)

        # Layer 1 落库：只有终裁者晋升的事实会被写入订单上下文。
        self.order_manager.record_verdict(order_id, parsed_order, matched_order, risk_result)

        needs_confirmation = bool(verdict.get("needs_confirmation"))
        final_status = (
            OrderStatus.NEEDS_CONFIRMATION if needs_confirmation else OrderStatus.COMPLETED
        )
        confirmation_request = (
            self._create_confirmation_request(order_id, risk_result) if needs_confirmation else None
        )
        final_result = FinalOrderResult(
            status=final_status,
            parsed_order=parsed_order,
            matched_order=matched_order,
            risk_result=risk_result,
            business_decision=business_decision,
            message="订单处理完成",
        )
        if not self.order_manager.finalize_order(order_id, final_result, confirmation_request):
            return self._build_error_response("订单状态已变化，无法保存最终结果", order_id)

        order = self.order_manager.get_order(order_id)
        return {
            "success": True,
            "order_id": order_id,
            "final_result": final_result,
            "business_decision": business_decision,
            "needs_confirmation": needs_confirmation,
            "message": "订单处理完成",
            "usage": dict(self._last_usage),
            "diagnostics": self._diagnostics(order),
            "reason_chain": verdict.get("reason_chain") or [],
        }

    # ------------------------------------------------------------------ helpers
    def _diagnostics(self, order: Optional[Any]) -> Dict[str, Any]:
        merged = dict(self._last_diagnostics)
        if order is not None:
            merged.update(order.processing_diagnostics)
        return merged

    def _safe_set_error(self, order_id: str, message: str) -> bool:
        try:
            return self.order_manager.set_error(order_id, message)
        except Exception:  # noqa: BLE001 - 落库失败不得掩盖原始错误
            return False

    def _build_error_response(self, message: str, order_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            order = self.order_manager.get_order(order_id) if order_id else None
        except Exception:  # noqa: BLE001
            order = None
        return {
            "success": False,
            "order_id": order_id,
            "message": message,
            "usage": dict(self._last_usage),
            "diagnostics": self._diagnostics(order),
        }

    def _create_confirmation_request(
        self, order_id: str, risk_result: RiskCheckResult,
    ) -> Dict[str, Any]:
        issues_summary = [
            {
                "item_index": issue.item_index,
                "issue_type": issue.issue_type,
                "description": issue.description,
                "severity": issue.severity,
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
            "required_actions": ["review_issues", "confirm_or_reject"],
        }

    # ------------------------------------------------------------------ review / query
    def confirm_order(self, order_id: str, confirmation: Dict[str, Any]) -> Dict[str, Any]:
        order = self.order_manager.get_order(order_id)
        if not order:
            return {"success": False, "message": "订单不存在"}
        if order.status != OrderStatus.NEEDS_CONFIRMATION:
            return {"success": False, "message": "订单不需要确认"}

        action = confirmation.get("action")
        if action not in {"confirm", "reject"}:
            return {"success": False, "message": "无效的确认操作"}
        if not self.order_manager.review_order(order_id, action, confirmation.get("comment")):
            return {"success": False, "order_id": order_id, "message": "订单已被处理，请刷新后查看"}
        return {
            "success": True, "order_id": order_id,
            "message": "订单已确认" if action == "confirm" else "订单已拒绝",
        }

    def generate_review_suggestion(self, order_id: str) -> Dict[str, Any]:
        order = self.order_manager.get_order(order_id)
        if not order:
            return {"success": False, "message": "订单不存在"}
        if order.status != OrderStatus.NEEDS_CONFIRMATION:
            return {"success": False, "message": "仅待人工确认状态的订单可以生成审核参考"}
        if not order.final_result or order.final_result.matched_order is None:
            return {"success": False, "message": "订单缺少匹配或风控结果，无法生成审核参考"}

        assistant: ReviewAssistant = self.agents[AgentRole.REVIEW_ASSISTANT]
        result = assistant.suggest(
            order.final_result.matched_order, order.final_result.risk_result,
        )
        if not result.get("success"):
            return {"success": False, "message": result.get("message", "审核参考生成失败")}
        return {
            "success": True,
            "order_id": order_id,
            "review_suggestion": result["review_suggestion"],
            "message": result["message"],
        }

    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        return self.order_manager.get_order_status(order_id)

    def get_order_detail(self, order_id: str) -> Optional[Dict[str, Any]]:
        return self.order_manager.get_order_detail(order_id)

    def list_orders(self) -> List[Dict[str, Any]]:
        return self.order_manager.list_order_summaries()

    def get_trace(self, order_id: str) -> Dict[str, Any]:
        return self.order_manager.get_trace(order_id)

    def get_tasks(self, order_id: str) -> List[Dict[str, Any]]:
        return self.order_manager.get_tasks(order_id)
