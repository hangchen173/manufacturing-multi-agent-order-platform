from typing import Any, Dict, List, Optional
from datetime import datetime
from core.agents.base_agent import BaseAgent
from core.models import MatchedOrder, RiskIssue, RiskCheckResult
from core.constants import (
    SeverityLevel, 
    IssueType, 
    PRICE_ABNORMALITY_RATIO_HIGH,
    PRICE_ABNORMALITY_RATIO_LOW
)
from core.exceptions import RiskControlException
from config import Config

class RiskControlAgent(BaseAgent):
    def __init__(self, llm=None, config: Optional[Config] = None):
        super().__init__(llm, config)
        self.confidence_threshold = self.config.risk.confidence_threshold
    
    def _check_parsing_confidence(self, item: Any, item_index: int) -> List[RiskIssue]:
        issues = []
        if item.confidence_score and item.confidence_score < self.confidence_threshold:
            issues.append(RiskIssue(
                item_index=item_index,
                issue_type=IssueType.LOW_CONFIDENCE.value,
                description=f"解析置信度 {item.confidence_score:.2f} 低于阈值 {self.confidence_threshold}",
                severity=SeverityLevel.MEDIUM.value
            ))
        return issues
    
    def _check_match_score(self, item: Any, item_index: int) -> List[RiskIssue]:
        issues = []
        if hasattr(item, 'match_score') and item.match_score < self.confidence_threshold:
            issues.append(RiskIssue(
                item_index=item_index,
                issue_type=IssueType.LOW_MATCH_SCORE.value,
                description=f"物料匹配得分 {item.match_score:.2f} 低于阈值 {self.confidence_threshold}",
                severity=SeverityLevel.MEDIUM.value
            ))
        return issues
    
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
    
    def _check_delivery_date(self, item: Any, item_index: int) -> List[RiskIssue]:
        issues = []
        
        if not item.delivery_date:
            return issues
        
        try:
            delivery_date = datetime.strptime(item.delivery_date, "%Y-%m-%d")
            if delivery_date < datetime.now():
                issues.append(RiskIssue(
                    item_index=item_index,
                    issue_type=IssueType.PAST_DELIVERY.value,
                    description=f"交期 {item.delivery_date} 已过",
                    severity=SeverityLevel.HIGH.value
                ))
        except ValueError:
            issues.append(RiskIssue(
                item_index=item_index,
                issue_type=IssueType.INVALID_DATE_FORMAT.value,
                description=f"交期格式 {item.delivery_date} 无效，应为 YYYY-MM-DD",
                severity=SeverityLevel.MEDIUM.value
            ))
        
        return issues
    
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
            return 1.0
        
        high_severity_count = sum(1 for issue in issues if issue.severity == SeverityLevel.HIGH.value)
        medium_severity_count = sum(1 for issue in issues if issue.severity == SeverityLevel.MEDIUM.value)
        
        penalty = high_severity_count * 0.2 + medium_severity_count * 0.1
        return max(0.0, min(1.0, 1.0 - penalty))
    
    def _validate_item(self, item: Any, item_index: int, reference_price: Optional[float] = None) -> List[RiskIssue]:
        all_issues = []
        all_issues.extend(self._check_parsing_confidence(item, item_index))
        all_issues.extend(self._check_match_score(item, item_index))
        all_issues.extend(self._check_price_abnormality(item, item_index, reference_price))
        all_issues.extend(self._check_delivery_date(item, item_index))
        all_issues.extend(self._check_quantity(item, item_index))
        return all_issues
    
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.log_info("开始风控检查")
        
        try:
            self.validate_input(input_data, required_keys=["matched_order"])
            
            matched_order: MatchedOrder = input_data.get("matched_order")
            reference_prices: Dict[int, float] = input_data.get("reference_prices", {})
            
            all_issues: List[RiskIssue] = []
            
            for idx, item in enumerate(matched_order.items):
                reference_price = reference_prices.get(idx)
                item_issues = self._validate_item(item, idx, reference_price)
                all_issues.extend(item_issues)
            
            overall_confidence = self._calculate_overall_confidence(
                all_issues, 
                len(matched_order.items)
            )
            
            needs_confirmation = (
                len(all_issues) > 0 or 
                overall_confidence < self.confidence_threshold
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
