from typing import Any, Dict, List
from datetime import datetime
from core.agents.base_agent import BaseAgent
from core.models import MatchedOrder, RiskIssue, RiskCheckResult
from config import Config

class RiskControlAgent(BaseAgent):
    def __init__(self, llm=None):
        super().__init__(llm)
        self.config = Config()
        self.confidence_threshold = self.config.RISK_CONFIDENCE_THRESHOLD
    
    def _check_parsing_confidence(self, item: Any, item_index: int) -> List[RiskIssue]:
        issues = []
        if item.confidence_score and item.confidence_score < self.confidence_threshold:
            issues.append(RiskIssue(
                item_index=item_index,
                issue_type="low_confidence",
                description=f"解析置信度 {item.confidence_score:.2f} 低于阈值 {self.confidence_threshold}",
                severity="medium"
            ))
        return issues
    
    def _check_match_score(self, item: Any, item_index: int) -> List[RiskIssue]:
        issues = []
        if hasattr(item, 'match_score') and item.match_score < self.confidence_threshold:
            issues.append(RiskIssue(
                item_index=item_index,
                issue_type="low_match_score",
                description=f"物料匹配得分 {item.match_score:.2f} 低于阈值 {self.confidence_threshold}",
                severity="medium"
            ))
        return issues
    
    def _check_price_abnormality(self, item: Any, item_index: int, reference_price: float = None) -> List[RiskIssue]:
        issues = []
        if item.unit_price is not None:
            if item.unit_price <= 0:
                issues.append(RiskIssue(
                    item_index=item_index,
                    issue_type="invalid_price",
                    description=f"单价 {item.unit_price} 无效，必须大于 0",
                    severity="high"
                ))
            elif reference_price and reference_price > 0:
                price_ratio = item.unit_price / reference_price
                if price_ratio > 2.0 or price_ratio < 0.5:
                    issues.append(RiskIssue(
                        item_index=item_index,
                        issue_type="price_abnormal",
                        description=f"单价 {item.unit_price} 相对于参考价格 {reference_price} 异常",
                        severity="medium"
                    ))
        return issues
    
    def _check_delivery_date(self, item: Any, item_index: int) -> List[RiskIssue]:
        issues = []
        if item.delivery_date:
            try:
                delivery_date = datetime.strptime(item.delivery_date, "%Y-%m-%d")
                today = datetime.now()
                if delivery_date < today:
                    issues.append(RiskIssue(
                        item_index=item_index,
                        issue_type="past_delivery",
                        description=f"交期 {item.delivery_date} 已过",
                        severity="high"
                    ))
            except ValueError:
                issues.append(RiskIssue(
                    item_index=item_index,
                    issue_type="invalid_date_format",
                    description=f"交期格式 {item.delivery_date} 无效，应为 YYYY-MM-DD",
                    severity="medium"
                ))
        return issues
    
    def _check_quantity(self, item: Any, item_index: int) -> List[RiskIssue]:
        issues = []
        if item.quantity is not None and item.quantity <= 0:
            issues.append(RiskIssue(
                item_index=item_index,
                issue_type="invalid_quantity",
                description=f"数量 {item.quantity} 无效，必须大于 0",
                severity="high"
            ))
        return issues
    
    def _calculate_overall_confidence(self, issues: List[RiskIssue], item_count: int) -> float:
        if item_count == 0:
            return 1.0
        
        high_severity_count = sum(1 for issue in issues if issue.severity == "high")
        medium_severity_count = sum(1 for issue in issues if issue.severity == "medium")
        
        penalty = high_severity_count * 0.2 + medium_severity_count * 0.1
        return max(0.0, min(1.0, 1.0 - penalty))
    
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.log_info("开始风控检查")
        
        try:
            matched_order: MatchedOrder = input_data.get("matched_order")
            if not matched_order:
                raise ValueError("匹配订单不能为空")
            
            reference_prices = input_data.get("reference_prices", {})
            
            all_issues: List[RiskIssue] = []
            
            for idx, item in enumerate(matched_order.items):
                reference_price = reference_prices.get(idx)
                all_issues.extend(self._check_parsing_confidence(item, idx))
                all_issues.extend(self._check_match_score(item, idx))
                all_issues.extend(self._check_price_abnormality(item, idx, reference_price))
                all_issues.extend(self._check_delivery_date(item, idx))
                all_issues.extend(self._check_quantity(item, idx))
            
            overall_confidence = self._calculate_overall_confidence(all_issues, len(matched_order.items))
            needs_confirmation = len(all_issues) > 0 or overall_confidence < self.confidence_threshold
            
            risk_result = RiskCheckResult(
                needs_confirmation=needs_confirmation,
                issues=all_issues,
                overall_confidence=overall_confidence
            )
            
            self.log_info(f"风控检查完成，发现 {len(all_issues)} 个问题，整体置信度: {overall_confidence:.2f}")
            if needs_confirmation:
                self.log_info("需要人工确认")
            
            return {
                "success": True,
                "risk_result": risk_result,
                "message": "风控检查完成"
            }
        except Exception as e:
            self.log_error(f"风控检查失败: {str(e)}")
            return {
                "success": False,
                "risk_result": None,
                "message": f"风控检查失败: {str(e)}"
            }
