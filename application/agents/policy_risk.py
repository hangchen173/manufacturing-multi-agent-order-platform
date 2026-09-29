"""价格与金额政策风控 Agent。

独立工具集：参考价按 SKU 精确查询（字典索引，不再线性扫描）、价格政策、
金额一致性、数量政策。

它**不读**抽取自报置信度，改读 GroundingVerifier 的证据通过率（`_grounding.rate`），
对应设计文档 B7：“移除对模型自报置信度的依赖”。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from application.agents.base_agent import CollaborativeAgent
from application.agents.match_keys import CatalogIndex
from domain.agent_roles import AgentRole
from domain.constants import (
    IssueType,
    LINE_TOTAL_TOLERANCE,
    PACK_QUANTITY_MULTIPLE,
    PACK_QUANTITY_UNITS,
    PRICE_ABNORMALITY_RATIO_HIGH,
    PRICE_ABNORMALITY_RATIO_LOW,
    PRICE_POLICY_RATIO_MAX,
    SeverityLevel,
)
from domain.messages import AgentMessage, Evidence, Performative
from domain.tasks import Task

ORDER_LEVEL_ITEM_INDEX = -1


class PolicyRisk(CollaborativeAgent):
    role = AgentRole.POLICY_RISK

    def __init__(self, blackboard: Any = None, budget: Any = None, config: Any = None):
        super().__init__(blackboard, budget, config)
        self.confidence_threshold = getattr(getattr(config, "risk", None), "confidence_threshold", 0.8)
        self.match_threshold = getattr(getattr(config, "risk", None), "match_threshold", 0.8)

    # ------------------------------------------------------------------ entry
    def handle(self, task: Task) -> List[AgentMessage]:
        view = self.read_slice(task)
        index = view.get("item_index")

        if index is None:
            issues = self.check_line_total(view.get("items") or [],
                                           (view.get("order_facts") or {}).get("total_amount"))
            return [self._inform(task, issues, item_index=ORDER_LEVEL_ITEM_INDEX)]

        item = view.get("item") or {}
        catalog = view.get("catalog") or []
        reference_price = self._reference_price(catalog, item.get("sku_code"))
        issues = self.validate_item(item, index, reference_price)
        return [self._inform(task, issues, item_index=index, reference_price=reference_price)]

    def _inform(self, task: Task, issues: List[Dict[str, Any]], *, item_index: int,
                reference_price: Optional[float] = None) -> AgentMessage:
        return self.emit(
            task,
            Performative.INFORM,
            subject={"item_index": item_index, "claim_subject": f"item[{item_index}].risk.policy"},
            payload={"issues": issues, "item_index": item_index, "reference_price": reference_price},
            evidence=[Evidence(
                kind="rule_id",
                locator={"rule": issue["issue_type"], "item_index": item_index},
                value=issue["description"],
                reproducible=True,
            ) for issue in issues],
        )

    @staticmethod
    def _reference_price(catalog: List[Dict[str, Any]], sku_code: Optional[str]) -> Optional[float]:
        if not catalog or not sku_code:
            return None
        return CatalogIndex(catalog).reference_price(sku_code)

    # ------------------------------------------------------------------ checks
    def validate_item(self, item: Dict[str, Any], item_index: int,
                      reference_price: Optional[float] = None) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        issues.extend(self.check_grounding_evidence(item, item_index))
        issues.extend(self.check_unknown_material(item, item_index))
        issues.extend(self.check_ambiguous_match(item, item_index))
        issues.extend(self.check_ambiguous_specification(item, item_index))
        issues.extend(self.check_missing_quantity(item, item_index))
        issues.extend(self.check_missing_unit_price(item, item_index))
        issues.extend(self.check_non_pack_quantity(item, item_index))
        issues.extend(self.check_price_abnormality(item, item_index, reference_price))
        issues.extend(self.check_price_policy(item, item_index, reference_price))
        issues.extend(self.check_quantity(item, item_index))
        return issues

    def check_unknown_material(self, item: Dict[str, Any], item_index: int) -> List[Dict[str, Any]]:
        if item.get("sku_code") and item.get("match_score", 0.0) >= self.match_threshold:
            return []
        if item.get("candidate_skus"):
            # 已召回候选但无法唯一确认，交由 check_ambiguous_match 处理
            return []
        return [self._issue(
            item_index, IssueType.UNKNOWN_MATERIAL,
            f"物料 '{item.get('material_name')}' 未能可靠匹配标准物料库，"
            f"匹配得分 {item.get('match_score', 0.0):.2f}",
            SeverityLevel.HIGH,
        )]

    def check_ambiguous_match(self, item: Dict[str, Any], item_index: int) -> List[Dict[str, Any]]:
        if item.get("sku_code"):
            return []
        if not item.get("candidate_skus"):
            return []
        if not (item.get("specification") or "").strip():
            # 缺规格已由 check_ambiguous_specification 覆盖
            return []
        reason = item.get("rejection_reason") or "存在多个候选，无法唯一确认标准物料"
        return [self._issue(
            item_index, IssueType.AMBIGUOUS_MATCH,
            f"物料 '{item.get('material_name')}' 无法唯一确认标准物料：{reason}",
            SeverityLevel.HIGH,
        )]

    def check_ambiguous_specification(self, item: Dict[str, Any], item_index: int) -> List[Dict[str, Any]]:
        if (item.get("specification") or "").strip():
            return []
        if self._spec_known_from_catalog(item):
            # 规格并非「缺失」：标准库该 SKU 自身登记了规格，物料已被唯一确定。
            # 能走到这里的唯一路径是「物料名称整串命中已登记别名、规格内嵌在别名里」，
            # 因为向量路径在规格为空时一律 REFUSE（见 Disambiguator.decide）。
            # 此时判「无法唯一定位标准物料」是误报，且会阻断本可自动修正的订单。
            return []
        return [self._issue(
            item_index, IssueType.AMBIGUOUS_MISSING_SPECIFICATION,
            f"物料 '{item.get('material_name')}' 缺少规格型号，无法唯一定位标准物料",
            SeverityLevel.HIGH,
        )]

    @staticmethod
    def _spec_known_from_catalog(item: Dict[str, Any]) -> bool:
        """标准库已为该 SKU 登记规格：规格的权威来源是标准库行，而非抽取文本。"""
        return bool(item.get("sku_code")) and bool(
            (item.get("matched_specification") or "").strip()
        )

    def check_grounding_evidence(self, item: Dict[str, Any], item_index: int) -> List[Dict[str, Any]]:
        """证据通过率替代模型自报置信度：溯源不过关的行必须送审。"""
        grounding = item.get("_grounding") or {}
        if not grounding:
            return []
        rate = float(grounding.get("rate", 1.0))
        if rate >= self.confidence_threshold:
            return []
        return [self._issue(
            item_index, IssueType.LOW_CONFIDENCE,
            f"溯源证据通过率 {rate:.2f} 低于阈值 {self.confidence_threshold}"
            f"（已核对 {grounding.get('verified', 0)}/{grounding.get('total', 0)} 个字段）",
            SeverityLevel.MEDIUM,
        )]

    def check_missing_quantity(self, item: Dict[str, Any], item_index: int) -> List[Dict[str, Any]]:
        if item.get("quantity") is not None:
            return []
        return [self._issue(
            item_index, IssueType.MISSING_QUANTITY,
            f"物料 '{item.get('material_name')}' 缺少数量，禁止猜测，需人工确认",
            SeverityLevel.HIGH,
        )]

    def check_missing_unit_price(self, item: Dict[str, Any], item_index: int) -> List[Dict[str, Any]]:
        if item.get("unit_price") is not None:
            return []
        return [self._issue(
            item_index, IssueType.MISSING_UNIT_PRICE,
            f"物料 '{item.get('material_name')}' 缺少单价，禁止按零计算，需人工确认",
            SeverityLevel.HIGH,
        )]

    def check_non_pack_quantity(self, item: Dict[str, Any], item_index: int) -> List[Dict[str, Any]]:
        quantity = item.get("quantity")
        if quantity is None or quantity <= 0:
            return []
        if (item.get("unit") or "").strip() not in PACK_QUANTITY_UNITS:
            return []
        if quantity % PACK_QUANTITY_MULTIPLE == 0:
            return []
        return [self._issue(
            item_index, IssueType.NON_PACK_QUANTITY,
            f"数量 {quantity} {item.get('unit')} 不是包装数量 {PACK_QUANTITY_MULTIPLE} 的整数倍",
            SeverityLevel.HIGH,
        )]

    def check_quantity(self, item: Dict[str, Any], item_index: int) -> List[Dict[str, Any]]:
        quantity = item.get("quantity")
        if quantity is not None and quantity <= 0:
            return [self._issue(item_index, IssueType.INVALID_QUANTITY,
                                f"数量 {quantity} 无效，必须大于 0", SeverityLevel.HIGH)]
        return []

    def check_price_abnormality(self, item: Dict[str, Any], item_index: int,
                                reference_price: Optional[float] = None) -> List[Dict[str, Any]]:
        unit_price = item.get("unit_price")
        if unit_price is None:
            return []
        if unit_price <= 0:
            return [self._issue(item_index, IssueType.INVALID_PRICE,
                                f"单价 {unit_price} 无效，必须大于 0", SeverityLevel.HIGH)]
        if reference_price and reference_price > 0:
            ratio = unit_price / reference_price
            if ratio > PRICE_ABNORMALITY_RATIO_HIGH or ratio < PRICE_ABNORMALITY_RATIO_LOW:
                return [self._issue(
                    item_index, IssueType.PRICE_ABNORMAL,
                    f"单价 {unit_price} 相对于参考价格 {reference_price} 异常",
                    SeverityLevel.MEDIUM,
                )]
        return []

    def check_price_policy(self, item: Dict[str, Any], item_index: int,
                           reference_price: Optional[float] = None) -> List[Dict[str, Any]]:
        unit_price = item.get("unit_price")
        if unit_price is None or not reference_price or reference_price <= 0:
            return []
        if item.get("match_score", 0.0) < self.match_threshold:
            return []
        ratio = unit_price / reference_price
        if ratio <= PRICE_POLICY_RATIO_MAX:
            return []
        return [self._issue(
            item_index, IssueType.PRICE_OUT_OF_POLICY,
            f"单价 {unit_price} 为参考价 {reference_price} 的 {ratio:.2f} 倍，"
            f"超过 {PRICE_POLICY_RATIO_MAX} 倍上限",
            SeverityLevel.HIGH,
        )]

    def check_line_total(self, items: List[Dict[str, Any]],
                         total_amount: Optional[float]) -> List[Dict[str, Any]]:
        if total_amount is None:
            return []
        incomplete = [
            index for index, item in enumerate(items)
            if item.get("quantity") is None or item.get("unit_price") is None
        ]
        if incomplete:
            return [self._issue(
                ORDER_LEVEL_ITEM_INDEX, IssueType.INSUFFICIENT_AMOUNT_INFO,
                f"第 {[index + 1 for index in incomplete]} 行缺少数量或单价，"
                "无法核验订单总额，未按零参与计算",
                SeverityLevel.MEDIUM,
            )]
        computed_total = sum(item["quantity"] * item["unit_price"] for item in items)
        if abs(computed_total - total_amount) <= LINE_TOTAL_TOLERANCE:
            return []
        return [self._issue(
            ORDER_LEVEL_ITEM_INDEX, IssueType.LINE_TOTAL_MISMATCH,
            f"明细金额合计 {computed_total:.2f} 与订单总额 {total_amount:.2f} 不一致",
            SeverityLevel.HIGH,
        )]

    @staticmethod
    def _issue(item_index: int, issue_type: Any, description: str, severity: Any) -> Dict[str, Any]:
        issue_type_value = issue_type.value if hasattr(issue_type, "value") else str(issue_type)
        severity_value = severity.value if hasattr(severity, "value") else str(severity)
        return {
            "item_index": item_index,
            "issue_type": issue_type_value,
            "description": description,
            "severity": severity_value,
        }
