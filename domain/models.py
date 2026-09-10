from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class OrderStatus(str, Enum):
    PENDING = "pending"
    PARSING = "parsing"
    MATCHING = "matching"
    RISK_CHECKING = "risk_checking"
    NEEDS_CONFIRMATION = "needs_confirmation"
    COMPLETED = "completed"
    FAILED = "failed"

class OrderItem(BaseModel):
    material_name: str = Field(description="物料名称")
    specification: str = Field(description="规格型号")
    quantity: float = Field(description="数量")
    unit: str = Field(description="单位")
    unit_price: Optional[float] = Field(None, description="单价")
    delivery_date: Optional[str] = Field(None, description="交期")
    confidence_score: Optional[float] = Field(None, description="解析置信度")

class ParsedOrder(BaseModel):
    order_number: Optional[str] = Field(None, description="订单编号")
    customer_name: Optional[str] = Field(None, description="客户名称")
    items: List[OrderItem] = Field(description="订单明细")
    total_amount: Optional[float] = Field(None, description="总金额")
    parsing_confidence: float = Field(description="整体解析置信度")

class MatchedOrderItem(OrderItem):
    sku_code: Optional[str] = Field(None, description="标准SKU编号")
    matched_material_name: Optional[str] = Field(None, description="匹配的标准物料名")
    match_score: float = Field(description="匹配得分")

class MatchedOrder(BaseModel):
    order_number: Optional[str] = Field(None, description="订单编号")
    customer_name: Optional[str] = Field(None, description="客户名称")
    items: List[MatchedOrderItem] = Field(description="匹配后的订单明细")
    total_amount: Optional[float] = Field(None, description="总金额")

class RiskIssue(BaseModel):
    item_index: int = Field(description="问题项索引")
    issue_type: str = Field(description="问题类型")
    description: str = Field(description="问题描述")
    severity: str = Field(description="严重程度")

class RiskCheckResult(BaseModel):
    needs_confirmation: bool = Field(description="是否需要人工确认")
    issues: List[RiskIssue] = Field(default_factory=list, description="风险问题列表")
    overall_confidence: float = Field(description="整体风控置信度")

class BusinessAction(str, Enum):
    AUTO_APPROVE = "auto_approve"
    AUTO_CORRECT = "auto_correct"
    MANUAL_REVIEW = "manual_review"

class BusinessDecision(BaseModel):
    action: BusinessAction = Field(description="最终动作")
    reason: str = Field(description="决策依据")

class FinalOrderResult(BaseModel):
    status: OrderStatus = Field(description="订单处理状态")
    parsed_order: Optional[ParsedOrder] = Field(None, description="解析结果")
    matched_order: Optional[MatchedOrder] = Field(None, description="匹配结果")
    risk_result: Optional[RiskCheckResult] = Field(None, description="风控结果")
    business_decision: Optional[BusinessDecision] = Field(None, description="最终动作")
    message: Optional[str] = Field(None, description="处理信息")
