import uuid
import time
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from core.models import OrderStatus, ParsedOrder, MatchedOrder, RiskCheckResult, FinalOrderResult

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
    confirmation_requests: list = field(default_factory=list)
    error_message: Optional[str] = None

class OrderManager:
    def __init__(self):
        self.orders: Dict[str, OrderProcessingContext] = {}
    
    def create_order(self, document_path: Optional[str] = None, document_type: Optional[str] = None, order_text: Optional[str] = None) -> str:
        order_id = str(uuid.uuid4())
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
        return order_id
    
    def get_order(self, order_id: str) -> Optional[OrderProcessingContext]:
        return self.orders.get(order_id)
    
    def update_order_status(self, order_id: str, status: OrderStatus) -> bool:
        if order_id not in self.orders:
            return False
        self.orders[order_id].status = status
        self.orders[order_id].updated_at = datetime.now()
        return True
    
    def update_parsed_order(self, order_id: str, parsed_order: ParsedOrder) -> bool:
        if order_id not in self.orders:
            return False
        self.orders[order_id].parsed_order = parsed_order
        self.orders[order_id].updated_at = datetime.now()
        return True
    
    def update_matched_order(self, order_id: str, matched_order: MatchedOrder) -> bool:
        if order_id not in self.orders:
            return False
        self.orders[order_id].matched_order = matched_order
        self.orders[order_id].updated_at = datetime.now()
        return True
    
    def update_risk_result(self, order_id: str, risk_result: RiskCheckResult) -> bool:
        if order_id not in self.orders:
            return False
        self.orders[order_id].risk_result = risk_result
        self.orders[order_id].updated_at = datetime.now()
        return True
    
    def set_error(self, order_id: str, error_message: str) -> bool:
        if order_id not in self.orders:
            return False
        self.orders[order_id].status = OrderStatus.FAILED
        self.orders[order_id].error_message = error_message
        self.orders[order_id].updated_at = datetime.now()
        return True
    
    def add_confirmation_request(self, order_id: str, request: Dict[str, Any]) -> bool:
        if order_id not in self.orders:
            return False
        self.orders[order_id].confirmation_requests.append(request)
        self.orders[order_id].updated_at = datetime.now()
        return True
    
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
