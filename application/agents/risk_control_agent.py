from typing import Any, Dict, List, Optional
from datetime import date, datetime
from application.agents.base_agent import BaseAgent
from config import Config
from domain.constants import (
    SeverityLevel, 
    IssueType, 
    LINE_TOTAL_TOLERANCE,
    PACK_QUANTITY_MULTIPLE,
    PACK_QUANTITY_UNITS,
    PRICE_ABNORMALITY_RATIO_HIGH,
    PRICE_ABNORMALITY_RATIO_LOW,
    PRICE_POLICY_RATIO_MAX
)
from domain.models import MatchedOrder, RiskCheckResult, RiskIssue

ORDER_LEVEL_ITEM_INDEX = -1

class RiskControlAgent(BaseAgent):
    def __init__(self, llm=None, config: Optional[Config] = None):
        super().__init__(llm, config)
        self.confidence_threshold = self.config.risk.confidence_threshold
        self.match_threshold = self.config.risk.match_threshold
        self.evaluation_as_of = self.config.risk.evaluation_as_of
    
    def _check_parsing_confidence(self, item: Any, item_index: int) -> List[RiskIssue]:
        issues = []
        if item.confidence_score is not None and item.confidence_score < self.confidence_threshold:
            issues.append(RiskIssue(
                item_index=item_index,
                issue_type=IssueType.LOW_CONFIDENCE.value,
                description=f"解析置信度 {item.confidence_score:.2f} 低于阈值 {self.confidence_threshold}",
                severity=SeverityLevel.MEDIUM.value
            ))
        return issues
    
    def _check_unknown_material(self, item: Any, item_index: int) -> List[RiskIssue]:
        if getattr(item, 'sku_code', None) and item.match_score >= self.match_threshold:
            return []
        if getattr(item, "candidate_skus", None):
            # 已召回候选但无法唯一确认，交由 _check_ambiguous_match 处理
            return []
        return [RiskIssue(
            item_index=item_index,
            issue_type=IssueType.UNKNOWN_MATERIAL.value,
            description=(
                f"物料 '{item.material_name}' 未能可靠匹配标准物料库，"
                f"匹配得分 {item.match_score:.2f}"
            ),
            severity=SeverityLevel.HIGH.value
        )]

    def _check_ambiguous_match(self, item: Any, item_index: int) -> List[RiskIssue]:
        if getattr(item, "sku_code", None):
            return []
        if not getattr(item, "candidate_skus", None):
            return []
        if not (item.specification or "").strip():
            # 缺规格已由 _check_ambiguous_specification 覆盖
            return []
        reason = (
            getattr(item, "rejection_reason", None)
            or "存在多个候选，无法唯一确认标准物料"
        )
        return [RiskIssue(
            item_index=item_index,
            issue_type=IssueType.AMBIGUOUS_MATCH.value,
            description=f"物料 '{item.material_name}' 无法唯一确认标准物料：{reason}",
            severity=SeverityLevel.HIGH.value
        )]

    def _check_parsing_issues(self, matched_order: MatchedOrder) -> List[RiskIssue]:
        issues = []
        for problem in getattr(matched_order, "parsing_issues", None) or []:
            item_index = (
                problem.item_index
                if problem.item_index is not None
                else ORDER_LEVEL_ITEM_INDEX
            )
            issues.append(RiskIssue(
                item_index=item_index,
                issue_type=IssueType.UNRESOLVED_PARSING_PROBLEM.value,
                description=f"解析自检未解决：{problem.description}",
                severity=SeverityLevel.HIGH.value
            ))
        return issues

    def _check_ambiguous_specification(self, item: Any, item_index: int) -> List[RiskIssue]:
        if (item.specification or "").strip():
            return []
        return [RiskIssue(
            item_index=item_index,
            issue_type=IssueType.AMBIGUOUS_MISSING_SPECIFICATION.value,
            description=f"物料 '{item.material_name}' 缺少规格型号，无法唯一定位标准物料",
            severity=SeverityLevel.HIGH.value
        )]

    def _check_missing_quantity(self, item: Any, item_index: int) -> List[RiskIssue]:
        if item.quantity is not None:
            return []
        return [RiskIssue(
            item_index=item_index,
            issue_type=IssueType.MISSING_QUANTITY.value,
            description=f"物料 '{item.material_name}' 缺少数量，禁止猜测，需人工确认",
            severity=SeverityLevel.HIGH.value
        )]

    def _check_missing_unit_price(self, item: Any, item_index: int) -> List[RiskIssue]:
        if item.unit_price is not None:
            return []
        return [RiskIssue(
            item_index=item_index,
            issue_type=IssueType.MISSING_UNIT_PRICE.value,
            description=f"物料 '{item.material_name}' 缺少单价，禁止按零计算，需人工确认",
            severity=SeverityLevel.HIGH.value
        )]

    def _check_non_pack_quantity(self, item: Any, item_index: int) -> List[RiskIssue]:
        if item.quantity is None or item.quantity <= 0:
            return []
        if (item.unit or "").strip() not in PACK_QUANTITY_UNITS:
            # 包装数量约束仅覆盖模拟业务范围内的计件单位，其他计量单位不套用
            return []
        if item.quantity % PACK_QUANTITY_MULTIPLE == 0:
            return []
        return [RiskIssue(
            item_index=item_index,
            issue_type=IssueType.NON_PACK_QUANTITY.value,
            description=(
                f"数量 {item.quantity} {item.unit} 不是包装数量 "
                f"{PACK_QUANTITY_MULTIPLE} 的整数倍"
            ),
            severity=SeverityLevel.HIGH.value
        )]

    def _check_price_policy(
        self,
        item: Any,
        item_index: int,
        reference_price: Optional[float] = None
    ) -> List[RiskIssue]:
        if item.unit_price is None or not reference_price or reference_price <= 0:
            return []
        if getattr(item, 'match_score', 0.0) < self.match_threshold:
            return []

        price_ratio = item.unit_price / reference_price
        if price_ratio <= PRICE_POLICY_RATIO_MAX:
            return []
        return [RiskIssue(
            item_index=item_index,
            issue_type=IssueType.PRICE_OUT_OF_POLICY.value,
            description=(
                f"单价 {item.unit_price} 为参考价 {reference_price} 的 {price_ratio:.2f} 倍，"
                f"超过 {PRICE_POLICY_RATIO_MAX} 倍上限"
            ),
            severity=SeverityLevel.HIGH.value
        )]

    def _check_line_total(self, matched_order: MatchedOrder) -> List[RiskIssue]:
        total_amount = getattr(matched_order, "total_amount", None)
        if total_amount is None:
            # 总额允许缺失：缺失即跳过金额核验，不补造默认值
            return []

        incomplete = [
            index for index, item in enumerate(matched_order.items)
            if item.quantity is None or item.unit_price is None
        ]
        if incomplete:
            # 条件不足时明确标识，缺失值绝不按零参与换算以制造不一致
            return [RiskIssue(
                item_index=ORDER_LEVEL_ITEM_INDEX,
                issue_type=IssueType.INSUFFICIENT_AMOUNT_INFO.value,
                description=(
                    f"第 {[index + 1 for index in incomplete]} 行缺少数量或单价，"
                    "无法核验订单总额，未按零参与计算"
                ),
                severity=SeverityLevel.MEDIUM.value
            )]

        computed_total = sum(
            item.quantity * item.unit_price for item in matched_order.items
        )
        if abs(computed_total - total_amount) <= LINE_TOTAL_TOLERANCE:
            return []
        return [RiskIssue(
            item_index=ORDER_LEVEL_ITEM_INDEX,
            issue_type=IssueType.LINE_TOTAL_MISMATCH.value,
            description=(
                f"明细金额合计 {computed_total:.2f} 与订单总额 "
                f"{total_amount:.2f} 不一致"
            ),
            severity=SeverityLevel.HIGH.value
        )]
    
    def _check_price_abnormality(
        self, 
        item: Any, 
        item_index: int, 
        reference_price: Optional[float] = None
    ) -> List[RiskIssue]:
        issues = []
        
        if item.unit_price is None:
            return issues
        
        if item.unit_price <= 0:
            issues.append(RiskIssue(
                item_index=item_index,
                issue_type=IssueType.INVALID_PRICE.value,
                description=f"单价 {item.unit_price} 无效，必须大于 0",
                severity=SeverityLevel.HIGH.value
            ))
            return issues
        
        if reference_price and reference_price > 0:
            price_ratio = item.unit_price / reference_price
            if price_ratio > PRICE_ABNORMALITY_RATIO_HIGH or price_ratio < PRICE_ABNORMALITY_RATIO_LOW:
                issues.append(RiskIssue(
                    item_index=item_index,
                    issue_type=IssueType.PRICE_ABNORMAL.value,
                    description=f"单价 {item.unit_price} 相对于参考价格 {reference_price} 异常",
                    severity=SeverityLevel.MEDIUM.value
                ))
        
        return issues
    
    def _reference_date(self) -> date:
        if self.evaluation_as_of:
            return datetime.strptime(self.evaluation_as_of, "%Y-%m-%d").date()
        return datetime.now().date()

    def _check_delivery_date(self, item: Any, item_index: int) -> List[RiskIssue]:
        if not item.delivery_date:
            return []
        
        try:
            delivery_date = datetime.strptime(item.delivery_date, "%Y-%m-%d").date()
        except ValueError:
            return [RiskIssue(
                item_index=item_index,
                issue_type=IssueType.INVALID_DATE_FORMAT.value,
                description=f"交期格式 {item.delivery_date} 无效，应为 YYYY-MM-DD",
                severity=SeverityLevel.MEDIUM.value
            )]
        
        # 按日期语义比较：当日交期不算过去
        if delivery_date < self._reference_date():
            return [RiskIssue(
                item_index=item_index,
                issue_type=IssueType.PAST_DELIVERY.value,
                description=f"交期 {item.delivery_date} 早于评估日期 {self._reference_date():%Y-%m-%d}",
                severity=SeverityLevel.HIGH.value
            )]
        
        return []
    
    def _check_quantity(self, item: Any, item_index: int) -> List[RiskIssue]:
        issues = []
        if item.quantity is not None and item.quantity <= 0:
            issues.append(RiskIssue(
                item_index=item_index,
                issue_type=IssueType.INVALID_QUANTITY.value,
                description=f"数量 {item.quantity} 无效，必须大于 0",
                severity=SeverityLevel.HIGH.value
            ))
        return issues
    
    def _calculate_overall_confidence(self, issues: List[RiskIssue], item_count: int) -> float:
        if item_count == 0:
            return 0.0
        
        high_severity_count = sum(1 for issue in issues if issue.severity == SeverityLevel.HIGH.value)
        medium_severity_count = sum(1 for issue in issues if issue.severity == SeverityLevel.MEDIUM.value)
        
        penalty = high_severity_count * 0.2 + medium_severity_count * 0.1
        return max(0.0, min(1.0, 1.0 - penalty))
    
    def _validate_item(self, item: Any, item_index: int, reference_price: Optional[float] = None) -> List[RiskIssue]:
        all_issues = []
        all_issues.extend(self._check_parsing_confidence(item, item_index))
        all_issues.extend(self._check_unknown_material(item, item_index))
        all_issues.extend(self._check_ambiguous_match(item, item_index))
        all_issues.extend(self._check_ambiguous_specification(item, item_index))
        all_issues.extend(self._check_missing_quantity(item, item_index))
        all_issues.extend(self._check_missing_unit_price(item, item_index))
        all_issues.extend(self._check_non_pack_quantity(item, item_index))
        all_issues.extend(self._check_price_abnormality(item, item_index, reference_price))
        all_issues.extend(self._check_price_policy(item, item_index, reference_price))
        all_issues.extend(self._check_delivery_date(item, item_index))
        all_issues.extend(self._check_quantity(item, item_index))
        return all_issues
    
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.log_info("开始风控检查")
        
        try:
            self.validate_input(input_data, required_keys=["matched_order"])
            
            matched_order: MatchedOrder = input_data.get("matched_order")
            reference_prices: Dict[int, float] = input_data.get("reference_prices", {})
            
            if not matched_order.items:
                self.log_info("订单无有效明细，直接标记为需要人工确认")
                return {
                    "success": True,
                    "risk_result": RiskCheckResult(
                        needs_confirmation=True,
                        issues=self._check_parsing_issues(matched_order),
                        overall_confidence=0.0
                    ),
                    "message": "订单无有效物料明细，需人工确认"
                }
            
            all_issues: List[RiskIssue] = []
            
            for idx, item in enumerate(matched_order.items):
                reference_price = reference_prices.get(idx)
                item_issues = self._validate_item(item, idx, reference_price)
                all_issues.extend(item_issues)
            
            all_issues.extend(self._check_line_total(matched_order))
            all_issues.extend(self._check_parsing_issues(matched_order))
            
            overall_confidence = self._calculate_overall_confidence(
                all_issues, 
                len(matched_order.items)
            )
            
            needs_confirmation = any(
                issue.severity == SeverityLevel.HIGH.value for issue in all_issues
            )
            
            risk_result = RiskCheckResult(
                needs_confirmation=needs_confirmation,
                issues=all_issues,
                overall_confidence=overall_confidence
            )
            
            self.log_info(
                f"风控检查完成，发现 {len(all_issues)} 个问题，"
                f"整体置信度: {overall_confidence:.2f}"
            )
            
            if needs_confirmation:
                self.log_info("需要人工确认")
            
            return {
                "success": True,
                "risk_result": risk_result,
                "message": "风控检查完成"
            }
            
        except ValueError as e:
            error_msg = f"输入验证失败: {str(e)}"
            self.log_error(error_msg)
            return {
                "success": False,
                "risk_result": None,
                "message": error_msg
            }
        except Exception as e:
            error_msg = f"风控检查失败: {str(e)}"
            self.log_error(error_msg)
            return {
                "success": False,
                "risk_result": None,
                "message": error_msg
            }
