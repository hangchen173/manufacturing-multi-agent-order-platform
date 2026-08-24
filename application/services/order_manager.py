import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Type, TypeVar

from config import Config
from domain.exceptions import InvalidOrderStatusException, OrderNotFoundException
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
        self.orders: Dict[str, OrderProcessingContext] = self._load_orders()
        if self.config.data.order_auto_archive_days > 0:
            self.archive_terminal_orders(self.config.data.order_auto_archive_days)

    def _load_orders(self) -> Dict[str, OrderProcessingContext]:
        snapshots = self.repository.load_all(archived=False)
        orders: Dict[str, OrderProcessingContext] = {}

        for order_id, snapshot in snapshots.items():
            orders[order_id] = OrderProcessingContext.from_snapshot(snapshot)

        return orders

    def _persist(self) -> None:
        snapshots = {
            order_id: context.to_snapshot()
            for order_id, context in self.orders.items()
        }
        self.repository.save_all(snapshots, archived=False)

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

        self.orders[order_id] = context
        self._persist()
        self.logger.info(f"创建订单: {order_id}")
        return order_id

    def _generate_order_id(self) -> str:
        return str(uuid.uuid4())

    def _validate_order_exists(self, order_id: str) -> OrderProcessingContext:
        if order_id not in self.orders:
            raise OrderNotFoundException(
                f"订单不存在: {order_id}",
                details={"order_id": order_id},
            )
        return self.orders[order_id]

    def get_order(self, order_id: str) -> Optional[OrderProcessingContext]:
        return self.orders.get(order_id)

    def update_order_status(
        self,
        order_id: str,
        status: OrderStatus,
        reason: Optional[str] = None,
    ) -> bool:
        try:
            context = self._validate_order_exists(order_id)
            try:
                validate_transition(context.status, status)
            except InvalidOrderStatusException as exc:
                raise InvalidOrderStatusException(
                    order_id=order_id,
                    current_status=context.status.value,
                    expected_status=exc.expected_status,
                ) from exc

            previous_status = context.status
            context.status = status
            context.updated_at = datetime.now()
            context.transition_history.append(
                OrderStatusTransition(
                    from_status=previous_status,
                    to_status=status,
                    timestamp=context.updated_at,
                    reason=reason,
                )
            )

            if context.final_result is not None:
                context.final_result.status = status

            self._persist()
            self.logger.info(f"订单 {order_id} 状态更新为: {status.value}")
            return True

        except (OrderNotFoundException, InvalidOrderStatusException) as exc:
            self.logger.warning("更新订单状态失败: %s", exc)
            return False

    def update_parsed_order(self, order_id: str, parsed_order: ParsedOrder) -> bool:
        try:
            context = self._validate_order_exists(order_id)
            context.parsed_order = parsed_order
            context.updated_at = datetime.now()
            self._persist()

            self.logger.info(f"订单 {order_id} 解析结果已更新")
            return True

        except OrderNotFoundException:
            self.logger.warning(f"更新解析结果失败，订单不存在: {order_id}")
            return False

    def update_matched_order(self, order_id: str, matched_order: MatchedOrder) -> bool:
        try:
            context = self._validate_order_exists(order_id)
            context.matched_order = matched_order
            context.updated_at = datetime.now()
            self._persist()

            self.logger.info(f"订单 {order_id} 匹配结果已更新")
            return True

        except OrderNotFoundException:
            self.logger.warning(f"更新匹配结果失败，订单不存在: {order_id}")
            return False

    def update_risk_result(self, order_id: str, risk_result: RiskCheckResult) -> bool:
        try:
            context = self._validate_order_exists(order_id)
            context.risk_result = risk_result
            context.updated_at = datetime.now()
            self._persist()

            self.logger.info(f"订单 {order_id} 风控结果已更新")
            return True

        except OrderNotFoundException:
            self.logger.warning(f"更新风控结果失败，订单不存在: {order_id}")
            return False

    def update_final_result(self, order_id: str, final_result: FinalOrderResult) -> bool:
        try:
            context = self._validate_order_exists(order_id)
            context.final_result = final_result
            context.updated_at = datetime.now()
            self._persist()

            self.logger.info(f"订单 {order_id} 最终结果已更新")
            return True

        except OrderNotFoundException:
            self.logger.warning(f"更新最终结果失败，订单不存在: {order_id}")
            return False

    def set_error(self, order_id: str, error_message: str) -> bool:
        try:
            context = self._validate_order_exists(order_id)
            context.error_message = error_message
            updated = self.update_order_status(
                order_id,
                OrderStatus.FAILED,
                reason=f"error:{error_message}",
            )
            if not updated:
                return False
            context.updated_at = datetime.now()
            self._persist()

            self.logger.error(f"订单 {order_id} 发生错误: {error_message}")
            return True

        except OrderNotFoundException:
            self.logger.warning(f"设置错误状态失败，订单不存在: {order_id}")
            return False

    def add_confirmation_request(self, order_id: str, request: Dict[str, Any]) -> bool:
        try:
            context = self._validate_order_exists(order_id)
            context.confirmation_requests.append(request)
            context.updated_at = datetime.now()
            self._persist()

            self.logger.info(f"订单 {order_id} 添加确认请求")
            return True

        except OrderNotFoundException:
            self.logger.warning(f"添加确认请求失败，订单不存在: {order_id}")
            return False

    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        order = self.get_order(order_id)
        if not order:
            return None

        return {
            "order_id": order.order_id,
            "status": order.status.value,
            "created_at": order.created_at.isoformat(),
            "updated_at": order.updated_at.isoformat(),
            "needs_confirmation": len(order.confirmation_requests) > 0,
            "confirmation_requests": order.confirmation_requests,
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
                self.orders.values(), key=lambda context: context.created_at, reverse=True
            )
        ]

    def get_all_orders(self) -> Dict[str, OrderProcessingContext]:
        return self.orders.copy()

    def get_orders_by_status(self, status: OrderStatus) -> List[OrderProcessingContext]:
        return [
            context for context in self.orders.values()
            if context.status == status
        ]

    def get_pending_orders(self) -> List[OrderProcessingContext]:
        return self.get_orders_by_status(OrderStatus.PENDING)

    def get_failed_orders(self) -> List[OrderProcessingContext]:
        return self.get_orders_by_status(OrderStatus.FAILED)

    def get_orders_needing_confirmation(self) -> List[OrderProcessingContext]:
        return self.get_orders_by_status(OrderStatus.NEEDS_CONFIRMATION)

    def delete_order(self, order_id: str) -> bool:
        if order_id in self.orders:
            del self.orders[order_id]
            self._persist()
            self.logger.info(f"删除订单: {order_id}")
            return True
        return False

    def get_order_count(self) -> int:
        return len(self.orders)

    def clear_completed_orders(self) -> int:
        completed_orders = self.get_orders_by_status(OrderStatus.COMPLETED)
        count = 0

        for context in completed_orders:
            if self.delete_order(context.order_id):
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
        order_ids_to_archive = [
            order_id
            for order_id, context in self.orders.items()
            if context.status in statuses and context.updated_at <= cutoff
        ]
        if not order_ids_to_archive:
            return 0

        archived_snapshots = {
            order_id: self.orders[order_id].to_snapshot()
            for order_id in order_ids_to_archive
        }
        active_snapshots = {
            order_id: context.to_snapshot()
            for order_id, context in self.orders.items()
            if order_id not in archived_snapshots
        }

        self.repository.archive_orders(archived_snapshots, active_snapshots)

        for order_id in order_ids_to_archive:
            del self.orders[order_id]

        self.logger.info("归档了 %s 个历史订单", len(order_ids_to_archive))
        return len(order_ids_to_archive)

    def get_storage_summary(self) -> Dict[str, Any]:
        active_index = self.repository.load_index(archived=False)
        archived_index = self.repository.load_index(archived=True)
        return {
            "active": active_index,
            "archived": archived_index,
        }
