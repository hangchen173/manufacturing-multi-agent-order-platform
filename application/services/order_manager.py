import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Type, TypeVar

from config import Config
from domain.exceptions import InvalidOrderStatusException
from domain.models import FinalOrderResult, MatchedOrder, OrderStatus, ParsedOrder, RiskCheckResult
from domain.order_state_machine import validate_transition
from infrastructure.repositories import OrderRepository, PostgresOrderRepository

ModelT = TypeVar("ModelT")


def _serialize_model(model: Any) -> Optional[Dict[str, Any]]:
    if model is None:
        return None
    return model.model_dump(mode="json")


def _deserialize_model(model_class: Type[ModelT], payload: Optional[Dict[str, Any]]) -> Optional[ModelT]:
    if payload is None:
        return None
    return model_class.model_validate(payload)


@dataclass
class OrderStatusTransition:
    from_status: Optional[OrderStatus]
    to_status: OrderStatus
    timestamp: datetime = field(default_factory=datetime.now)
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_status": self.from_status.value if self.from_status else None,
            "to_status": self.to_status.value,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "OrderStatusTransition":
        from_status = payload.get("from_status")
        return cls(
            from_status=OrderStatus(from_status) if from_status else None,
            to_status=OrderStatus(payload["to_status"]),
            timestamp=datetime.fromisoformat(payload["timestamp"]),
            reason=payload.get("reason"),
        )


@dataclass
class OrderProcessingContext:
    order_id: str
    created_at: datetime
    status: OrderStatus
    updated_at: datetime = field(default_factory=datetime.now)
    document_path: Optional[str] = None
    document_type: Optional[str] = None
    order_text: Optional[str] = None
    parsed_order: Optional[ParsedOrder] = None
    matched_order: Optional[MatchedOrder] = None
    risk_result: Optional[RiskCheckResult] = None
    final_result: Optional[FinalOrderResult] = None
    confirmation_requests: List[Dict[str, Any]] = field(default_factory=list)
    review_actions: List[Dict[str, Any]] = field(default_factory=list)
    processing_diagnostics: Dict[str, Any] = field(default_factory=dict)
    transition_history: List[OrderStatusTransition] = field(default_factory=list)
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status.value,
            "document_path": self.document_path,
            "document_type": self.document_type,
            "order_text": self.order_text,
            "has_parsed_order": self.parsed_order is not None,
            "has_matched_order": self.matched_order is not None,
            "has_risk_result": self.risk_result is not None,
            "has_final_result": self.final_result is not None,
            "confirmation_count": len(self.confirmation_requests),
            "error_message": self.error_message,
            "last_transition_at": self.transition_history[-1].timestamp.isoformat()
            if self.transition_history
            else None,
        }

    def to_snapshot(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status.value,
            "document_path": self.document_path,
            "document_type": self.document_type,
            "order_text": self.order_text,
            "parsed_order": _serialize_model(self.parsed_order),
            "matched_order": _serialize_model(self.matched_order),
            "risk_result": _serialize_model(self.risk_result),
            "final_result": _serialize_model(self.final_result),
            "confirmation_requests": self.confirmation_requests,
            "review_actions": self.review_actions,
            "processing_diagnostics": self.processing_diagnostics,
            "transition_history": [item.to_dict() for item in self.transition_history],
            "error_message": self.error_message,
        }

    @classmethod
    def from_snapshot(cls, payload: Dict[str, Any]) -> "OrderProcessingContext":
        transition_payload = payload.get("transition_history", [])
        transition_history = [
            OrderStatusTransition.from_dict(item) for item in transition_payload
        ]

        context = cls(
            order_id=payload["order_id"],
            created_at=datetime.fromisoformat(payload["created_at"]),
            updated_at=datetime.fromisoformat(payload["updated_at"]),
            status=OrderStatus(payload["status"]),
            document_path=payload.get("document_path"),
            document_type=payload.get("document_type"),
            order_text=payload.get("order_text"),
            parsed_order=_deserialize_model(ParsedOrder, payload.get("parsed_order")),
            matched_order=_deserialize_model(MatchedOrder, payload.get("matched_order")),
            risk_result=_deserialize_model(RiskCheckResult, payload.get("risk_result")),
            final_result=_deserialize_model(FinalOrderResult, payload.get("final_result")),
            confirmation_requests=payload.get("confirmation_requests", []),
            review_actions=payload.get("review_actions", []),
            processing_diagnostics=payload.get("processing_diagnostics", {}),
            transition_history=transition_history,
            error_message=payload.get("error_message"),
        )

        if not context.transition_history:
            raise ValueError(f"订单 {context.order_id} 缺少状态流转记录")

        return context


class OrderManager:
    def __init__(
        self,
        repository: Optional[OrderRepository] = None,
        config: Optional[Config] = None,
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config or Config()
        self.repository = repository or PostgresOrderRepository(self.config.database.url)
        if self.config.data.order_auto_archive_days > 0:
            self.archive_terminal_orders(self.config.data.order_auto_archive_days)

    def _load_orders(self) -> Dict[str, OrderProcessingContext]:
        snapshots = self.repository.load_all(archived=False)
        orders: Dict[str, OrderProcessingContext] = {}

        for order_id, snapshot in snapshots.items():
            orders[order_id] = OrderProcessingContext.from_snapshot(snapshot)

        return orders

    def _update(
        self,
        order_id: str,
        mutate: Callable[[OrderProcessingContext], None],
        expected_status: Optional[OrderStatus] = None,
    ) -> bool:
        context = self.get_order(order_id)
        if context is None:
            return False
        if expected_status is not None and context.status != expected_status:
            return False
        expected_updated_at = context.updated_at.isoformat()
        context.updated_at = max(datetime.now(), context.updated_at + timedelta(microseconds=1))
        try:
            mutate(context)
        except InvalidOrderStatusException as exc:
            self.logger.warning("更新订单失败: %s", exc)
            return False
        return self.repository.update(context.to_snapshot(), expected_updated_at)

    @staticmethod
    def _transition(context: OrderProcessingContext, status: OrderStatus, reason: Optional[str]) -> None:
        validate_transition(context.status, status)
        if context.status == status:
            return
        context.transition_history.append(OrderStatusTransition(
            from_status=context.status, to_status=status,
            timestamp=context.updated_at, reason=reason,
        ))
        context.status = status
        if context.final_result is not None:
            context.final_result.status = status

    def create_order(
        self,
        document_path: Optional[str] = None,
        document_type: Optional[str] = None,
        order_text: Optional[str] = None,
    ) -> str:
        order_id = self._generate_order_id()
        now = datetime.now()

        context = OrderProcessingContext(
            order_id=order_id,
            created_at=now,
            status=OrderStatus.PENDING,
            updated_at=now,
            document_path=document_path,
            document_type=document_type,
            order_text=order_text,
            transition_history=[
                OrderStatusTransition(
                    from_status=None,
                    to_status=OrderStatus.PENDING,
                    timestamp=now,
                    reason="order_created",
                )
            ],
        )

        self.repository.create(context.to_snapshot())
        self.logger.info(f"创建订单: {order_id}")
        return order_id

    def _generate_order_id(self) -> str:
        return str(uuid.uuid4())

    def get_order(self, order_id: str) -> Optional[OrderProcessingContext]:
        snapshot = self.repository.get(order_id)
        return OrderProcessingContext.from_snapshot(snapshot) if snapshot else None

    def update_order_status(
        self,
        order_id: str,
        status: OrderStatus,
        reason: Optional[str] = None,
        expected_status: Optional[OrderStatus] = None,
    ) -> bool:
        return self._update(
            order_id, lambda context: self._transition(context, status, reason), expected_status,
        )

    def update_parsed_order(self, order_id: str, parsed_order: ParsedOrder) -> bool:
        return self._update(order_id, lambda context: setattr(context, "parsed_order", parsed_order), OrderStatus.PARSING)

    def update_matched_order(self, order_id: str, matched_order: MatchedOrder) -> bool:
        return self._update(order_id, lambda context: setattr(context, "matched_order", matched_order), OrderStatus.MATCHING)

    def update_risk_result(self, order_id: str, risk_result: RiskCheckResult) -> bool:
        return self._update(order_id, lambda context: setattr(context, "risk_result", risk_result), OrderStatus.RISK_CHECKING)

    def record_stage(self, order_id: str, stage: str, diagnostics: Dict[str, Any]) -> bool:
        return self._update(order_id, lambda context: context.processing_diagnostics.update({stage: diagnostics}))

    def finalize_order(
        self, order_id: str, final_result: FinalOrderResult,
        confirmation_request: Optional[Dict[str, Any]] = None,
    ) -> bool:
        def mutate(context):
            context.final_result = final_result
            if confirmation_request is not None:
                context.confirmation_requests.append(confirmation_request)
            reason = "requires_manual_confirmation" if final_result.status == OrderStatus.NEEDS_CONFIRMATION else "processing_completed"
            self._transition(context, final_result.status, reason)
        return self._update(order_id, mutate, OrderStatus.RISK_CHECKING)

    def review_order(self, order_id: str, action: str, comment: Optional[str] = None) -> bool:
        if action not in {"confirm", "reject"}:
            return False
        def mutate(context):
            target = OrderStatus.COMPLETED if action == "confirm" else OrderStatus.FAILED
            reason = "manually_confirmed" if action == "confirm" else "manually_rejected"
            self._transition(context, target, reason)
            context.review_actions.append({
                "action": action, "comment": comment,
                "timestamp": context.updated_at.isoformat(),
            })
        return self._update(order_id, mutate, OrderStatus.NEEDS_CONFIRMATION)

    def set_error(self, order_id: str, error_message: str) -> bool:
        current = self.get_order(order_id)
        if current is None or current.status not in {
            OrderStatus.PENDING, OrderStatus.PARSING, OrderStatus.MATCHING, OrderStatus.RISK_CHECKING,
        }:
            return False
        def mutate(context):
            context.error_message = error_message
            self._transition(context, OrderStatus.FAILED, f"error:{error_message}")
        return self._update(order_id, mutate, current.status)

    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        order = self.get_order(order_id)
        if not order:
            return None

        return {
            "order_id": order.order_id,
            "status": order.status.value,
            "created_at": order.created_at.isoformat(),
            "updated_at": order.updated_at.isoformat(),
            "needs_confirmation": order.status == OrderStatus.NEEDS_CONFIRMATION,
            "confirmation_requests": order.confirmation_requests,
            "review_actions": order.review_actions,
            "error_message": order.error_message,
            "has_final_result": order.final_result is not None,
            "transition_history": [item.to_dict() for item in order.transition_history],
        }

    def get_order_detail(self, order_id: str) -> Optional[Dict[str, Any]]:
        order = self.get_order(order_id)
        if not order:
            return None
        return order.to_snapshot()

    def list_order_summaries(self) -> List[Dict[str, Any]]:
        return [
            context.to_dict()
            for context in sorted(
                self._load_orders().values(), key=lambda context: context.created_at, reverse=True
            )
        ]

    def get_all_orders(self) -> Dict[str, OrderProcessingContext]:
        return self._load_orders()

    def get_orders_by_status(self, status: OrderStatus) -> List[OrderProcessingContext]:
        return [
            context for context in self._load_orders().values()
            if context.status == status
        ]

    def get_pending_orders(self) -> List[OrderProcessingContext]:
        return self.get_orders_by_status(OrderStatus.PENDING)

    def get_failed_orders(self) -> List[OrderProcessingContext]:
        return self.get_orders_by_status(OrderStatus.FAILED)

    def get_orders_needing_confirmation(self) -> List[OrderProcessingContext]:
        return self.get_orders_by_status(OrderStatus.NEEDS_CONFIRMATION)

    def delete_order(self, order_id: str) -> bool:
        context = self.get_order(order_id)
        return bool(context and self.repository.delete(order_id, context.updated_at.isoformat()))

    def get_order_count(self) -> int:
        return self.repository.load_index()["total_count"]

    def clear_completed_orders(self) -> int:
        completed_orders = self.get_orders_by_status(OrderStatus.COMPLETED)
        count = 0

        for context in completed_orders:
            if self.repository.delete(context.order_id, context.updated_at.isoformat()):
                count += 1

        self.logger.info(f"清理了 {count} 个已完成订单")
        return count

    def archive_terminal_orders(
        self,
        older_than_days: int,
        statuses: Optional[Set[OrderStatus]] = None,
    ) -> int:
        if older_than_days <= 0:
            return 0

        statuses = statuses or {OrderStatus.COMPLETED, OrderStatus.FAILED}
        cutoff = datetime.now() - timedelta(days=older_than_days)
        return sum(
            self.repository.archive(order_id, context.updated_at.isoformat())
            for order_id, context in self._load_orders().items()
            if context.status in statuses and context.updated_at <= cutoff
        )

    def get_storage_summary(self) -> Dict[str, Any]:
        active_index = self.repository.load_index(archived=False)
        archived_index = self.repository.load_index(archived=True)
        return {
            "active": active_index,
            "archived": archived_index,
        }

    def fail_stale_processing_orders(self, older_than_seconds: int = 180) -> int:
        cutoff = datetime.now() - timedelta(seconds=older_than_seconds)
        count = 0
        for context in self._load_orders().values():
            if context.status not in {
                OrderStatus.PENDING, OrderStatus.PARSING, OrderStatus.MATCHING, OrderStatus.RISK_CHECKING,
            } or context.updated_at > cutoff:
                continue
            expected = context.updated_at.isoformat()
            context.updated_at = datetime.now()
            context.error_message = "处理超时或服务中断，请重新提交订单"
            self._transition(context, OrderStatus.FAILED, "processing_interrupted_or_expired")
            count += self.repository.update(context.to_snapshot(), expected)
        return count
