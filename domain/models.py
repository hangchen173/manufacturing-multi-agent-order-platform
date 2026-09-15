from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from enum import Enum
import math


def _require_finite(value: Optional[float], label: str) -> Optional[float]:
    if value is not None and not math.isfinite(value):
        raise ValueError(f"{label}必须是有限数值")
    return value


def _require_unit_interval(value: Optional[float], label: str) -> Optional[float]:
    if value is None:
        return None
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{label}必须在 0 到 1 之间")
    return value


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
    specification: Optional[str] = Field(None, description="规格型号")
    quantity: Optional[float] = Field(None, description="数量，缺失表示未知，禁止猜测")
    unit: Optional[str] = Field(None, description="单位")
    unit_price: Optional[float] = Field(None, description="单价，缺失表示未知，禁止按零计算")
    delivery_date: Optional[str] = Field(None, description="交期")
    confidence_score: Optional[float] = Field(None, description="解析置信度")

    @field_validator("quantity", "unit_price")
    @classmethod
    def _validate_finite_number(cls, value: Optional[float]) -> Optional[float]:
        return _require_finite(value, "数值")

    @field_validator("confidence_score")
    @classmethod
    def _validate_confidence(cls, value: Optional[float]) -> Optional[float]:
        return _require_unit_interval(value, "解析置信度")

class ParsingIssue(BaseModel):
    item_index: Optional[int] = Field(None, description="相关明细行索引，null 表示订单级问题")
    description: str = Field(description="解析自检未解决的问题描述")

class ParsedOrder(BaseModel):
    order_number: Optional[str] = Field(None, description="订单编号")
    customer_name: Optional[str] = Field(None, description="客户名称")
    items: List[OrderItem] = Field(description="订单明细")
    total_amount: Optional[float] = Field(None, description="总金额，缺失表示未知，禁止补造")
    parsing_confidence: float = Field(description="整体解析置信度")
    parsing_issues: List[ParsingIssue] = Field(default_factory=list, description="自检未解决的确定性校验问题")

    @field_validator("total_amount")
    @classmethod
    def _validate_total_amount(cls, value: Optional[float]) -> Optional[float]:
        return _require_finite(value, "总金额")

    @field_validator("parsing_confidence")
    @classmethod
    def _validate_parsing_confidence(cls, value: float) -> float:
        return _require_unit_interval(value, "整体解析置信度")

class MatchedOrderItem(OrderItem):
    sku_code: Optional[str] = Field(None, description="标准SKU编号")
    matched_material_name: Optional[str] = Field(None, description="匹配的标准物料名")
    matched_specification: Optional[str] = Field(None, description="匹配到的标准规格型号")
    match_score: float = Field(description="匹配得分")
    candidate_skus: List[str] = Field(default_factory=list, description="召回但未接受的候选SKU")
    match_basis: Optional[str] = Field(None, description="接受该SKU的匹配依据")
    rejection_reason: Optional[str] = Field(None, description="未接受任何SKU的拒识原因")

class MatchedOrder(BaseModel):
    order_number: Optional[str] = Field(None, description="订单编号")
    customer_name: Optional[str] = Field(None, description="客户名称")
    items: List[MatchedOrderItem] = Field(description="匹配后的订单明细")
    total_amount: Optional[float] = Field(None, description="总金额")
    parsing_issues: List[ParsingIssue] = Field(default_factory=list, description="沿用自解析结果的自检未解决问题")

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

class NormalizationChange(BaseModel):
    item_index: int = Field(description="被归一化的明细行索引，从 0 开始")
    field: str = Field(description="被归一化的字段")
    original_value: str = Field(description="采购方原始书写")
    standard_value: str = Field(description="标准物料库取值")
    basis: str = Field(description="归一化依据")

class BusinessDecision(BaseModel):
    action: BusinessAction = Field(description="最终动作")
    reason: str = Field(description="决策依据")
    normalizations: List[NormalizationChange] = Field(
        default_factory=list, description="auto_correct 实际执行的确定性归一化记录"
    )

class FinalOrderResult(BaseModel):
    status: OrderStatus = Field(description="订单处理状态")
    parsed_order: Optional[ParsedOrder] = Field(None, description="解析结果")
    matched_order: Optional[MatchedOrder] = Field(None, description="匹配结果")
    risk_result: Optional[RiskCheckResult] = Field(None, description="风控结果")
    business_decision: Optional[BusinessDecision] = Field(None, description="最终动作")
    message: Optional[str] = Field(None, description="处理信息")
