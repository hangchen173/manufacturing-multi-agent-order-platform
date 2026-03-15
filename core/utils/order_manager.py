import uuid
import logging
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from datetime import datetime

from core.models import OrderStatus, ParsedOrder, MatchedOrder, RiskCheckResult, FinalOrderResult
from core.exceptions import OrderNotFoundException, OrderManagerException

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
            "confirmation_count": len(self.confirmation_requests),
            "error_message": self.error_message
        }

class OrderManager:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.orders: Dict[str, OrderProcessingContext] = {}
    
    def create_order(
        self, 
        document_path: Optional[str] = None, 
        document_type: Optional[str] = None, 
        order_text: Optional[str] = None
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
            order_text=order_text
        )
        
        self.orders[order_id] = context
        self.logger.info(f"创建订单: {order_id}")
        
        return order_id
    
    def _generate_order_id(self) -> str:
        return str(uuid.uuid4())
    
    def _validate_order_exists(self, order_id: str) -> OrderProcessingContext:
        if order_id not in self.orders:
            raise OrderNotFoundException(
                f"订单不存在: {order_id}",
                details={"order_id": order_id}
            )
        return self.orders[order_id]
    
    def get_order(self, order_id: str) -> Optional[OrderProcessingContext]:
        return self.orders.get(order_id)
    
    def update_order_status(self, order_id: str, status: OrderStatus) -> bool:
        try:
            context = self._validate_order_exists(order_id)
            context.status = status
            context.updated_at = datetime.now()
            
            self.logger.info(f"订单 {order_id} 状态更新为: {status.value}")
            return True
            
        except OrderNotFoundException:
            self.logger.warning(f"更新订单状态失败，订单不存在: {order_id}")
            return False
    
    def update_parsed_order(self, order_id: str, parsed_order: ParsedOrder) -> bool:
        try:
            context = self._validate_order_exists(order_id)
            context.parsed_order = parsed_order
            context.updated_at = datetime.now()
            
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
            
            self.logger.info(f"订单 {order_id} 风控结果已更新")
            return True
            
        except OrderNotFoundException:
            self.logger.warning(f"更新风控结果失败，订单不存在: {order_id}")
            return False
    
    def set_error(self, order_id: str, error_message: str) -> bool:
        try:
            context = self._validate_order_exists(order_id)
            context.status = OrderStatus.FAILED
            context.error_message = error_message
            context.updated_at = datetime.now()
            
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
            "error_message": order.error_message
        }
    
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
