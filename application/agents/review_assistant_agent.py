import json
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from application.agents.base_agent import BaseAgent
from config import Config
from domain.models import MatchedOrder, RiskCheckResult

if TYPE_CHECKING:
    from infrastructure.vector_store.faiss_manager import FAISSManager

ORDER_LEVEL_ITEM_INDEX = -1
RETRIEVE_TOP_K = 3

_REFERENCE_FIELDS = (
    "sku_code", "material_name", "specification", "unit",
    "reference_price", "category", "aliases",
)

_SYSTEM_PROMPT = """你是制造业采购订单的人工审核辅助助手。系统会提供两类材料：
1. 确定性风控规则已检出的风险问题：规则结论可信，不要质疑，不要重新计算金额或比例；
2. 通过向量检索从标准物料库召回的相关物料资料。

请基于这些材料生成一份简明的中文审核参考，内容包括：
1. 总体概述：本单为什么被拦截人工审核；
2. 逐项风险说明：风险问题是什么，检索到的物料资料（标准名称、规格、参考价等）如何佐证或辅助判断；
3. 建议的人工处置方向（例如补充规格型号、与供应商确认价格、确认采购数量、拒收无法识别的物料等）。

要求：
- 只能引用材料中出现的 SKU、物料名称、规格、价格与风险结论，禁止编造任何材料外的信息；
- 检索资料为空时，必须明确说明“未检索到相关标准物料”，不得凭空猜测物料或价格；
- 输出仅供审核人员参考，不得替审核人员做出“同意/驳回”等最终决定。"""

_USER_TEMPLATE = """订单信息：
{order_context}

确定性风控规则检出的风险问题：
{risk_facts}

向量检索召回的标准物料资料（JSON）：
{materials}

请生成审核参考。"""


class ReviewAssistantAgent(BaseAgent):
    """只读 RAG 节点：检索标准物料资料增强 LLM，生成人工审核参考，不参与自动决策。"""

    def __init__(
        self,
        llm=None,
        faiss_manager: "FAISSManager" = None,
        config: Config = None,
    ):
        super().__init__(llm, config)
        self._faiss_manager = faiss_manager

    @property
    def faiss_manager(self):
        if self._faiss_manager is None:
            from infrastructure.vector_store.faiss_manager import FAISSManager

            self._faiss_manager = FAISSManager(
                index_path=self.config.data.faiss_index_path
            )
        return self._faiss_manager

    def _get_llm(self):
        if self.llm is None:
            from langchain_openai import ChatOpenAI

            self.llm = ChatOpenAI(
                model=self.config.model.model,
                api_key=self.config.require_model_api_key(),
                base_url=self.config.model.base_url,
                temperature=0,
                max_tokens=1024,
                model_kwargs={"extra_body": {"enable_thinking": False}},
                timeout=60,
                max_retries=0,
            )
        return self.llm

    @staticmethod
    def _build_query_text(item: Any) -> str:
        return " ".join(
            part for part in (item.material_name, item.specification) if part
        ).strip()

    def _build_order_context(self, matched_order: MatchedOrder) -> str:
        return json.dumps(
            {
                "order_number": matched_order.order_number,
                "customer_name": matched_order.customer_name,
                "total_amount": matched_order.total_amount,
            },
            ensure_ascii=False,
        )

    def _build_risk_facts(
        self, matched_order: MatchedOrder, risk_result: RiskCheckResult
    ) -> Tuple[str, List[int]]:
        issues_by_item: Dict[int, List[str]] = {}
        order_level_issues: List[str] = []
        for issue in risk_result.issues:
            if issue.item_index == ORDER_LEVEL_ITEM_INDEX:
                order_level_issues.append(issue.description)
            else:
                issues_by_item.setdefault(issue.item_index, []).append(
                    issue.description
                )

        facts: List[Dict[str, Any]] = []
        for index in sorted(issues_by_item):
            if index >= len(matched_order.items):
                facts.append({
                    "item_index": index,
                    "risk_issues": issues_by_item[index],
                })
                continue
            item = matched_order.items[index]
            facts.append({
                "item_index": index,
                "material_name": item.material_name,
                "specification": item.specification,
                "quantity": item.quantity,
                "unit": item.unit,
                "unit_price": item.unit_price,
                "sku_code": item.sku_code,
                "candidate_skus": item.candidate_skus,
                "risk_issues": issues_by_item[index],
            })
        if order_level_issues:
            facts.append({
                "item_index": ORDER_LEVEL_ITEM_INDEX,
                "risk_issues": order_level_issues,
            })

        return json.dumps(facts, ensure_ascii=False), sorted(issues_by_item)

    @staticmethod
    def _material_reference(doc: Dict[str, Any]) -> Dict[str, Any]:
        return {key: doc.get(key) for key in _REFERENCE_FIELDS}

    def _find_doc_by_sku(self, sku_code: str) -> Dict[str, Any]:
        return next(
            (row for row in self.faiss_manager.metadata if row.get("sku_code") == sku_code),
            None,
        )

    def _retrieve_materials(
        self, matched_order: MatchedOrder, risky_indexes: List[int]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        references: Dict[str, Dict[str, Any]] = {}
        traces: List[Dict[str, Any]] = []

        for index in risky_indexes:
            item = matched_order.items[index]

            # 已接受的 SKU 确定性纳入，保证参考价等关键资料不被向量排序遗漏
            if item.sku_code and item.sku_code not in references:
                doc = self._find_doc_by_sku(item.sku_code)
                if doc is not None:
                    references[item.sku_code] = self._material_reference(doc)

            query = self._build_query_text(item)
            recalled_skus: List[str] = []
            if query:
                try:
                    results = self.faiss_manager.search(query, k=RETRIEVE_TOP_K)
                except Exception as exc:
                    self.log_warning(
                        f"审核辅助检索失败 item_index={index} query='{query}': {exc}"
                    )
                    results = []
                for doc, _distance in results:
                    sku_code = doc.get("sku_code")
                    if sku_code:
                        recalled_skus.append(sku_code)
                    if sku_code and sku_code not in references:
                        references[sku_code] = self._material_reference(doc)

            traces.append({
                "item_index": index,
                "query": query,
                "recalled_skus": recalled_skus,
            })

        return list(references.values()), traces

    def _create_prompt(self):
        from langchain_core.prompts import ChatPromptTemplate

        return ChatPromptTemplate.from_messages([
            ("system", _SYSTEM_PROMPT),
            ("user", _USER_TEMPLATE),
        ])

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.log_info("开始生成人工审核辅助建议")
        try:
            self.validate_input(
                input_data, required_keys=["matched_order", "risk_result"]
            )
            matched_order: MatchedOrder = input_data["matched_order"]
            risk_result: RiskCheckResult = input_data["risk_result"]

            if not risk_result.issues:
                return {
                    "success": False,
                    "review_suggestion": None,
                    "message": "订单无风险问题，无需生成审核参考",
                }

            risk_facts, risky_indexes = self._build_risk_facts(
                matched_order, risk_result
            )
            references, traces = self._retrieve_materials(
                matched_order, risky_indexes
            )

            prompt = self._create_prompt()
            message = (prompt | self._get_llm()).invoke({
                "order_context": self._build_order_context(matched_order),
                "risk_facts": risk_facts,
                "materials": json.dumps(references, ensure_ascii=False),
            })
            summary = (message.content or "").strip()
            if not summary:
                return {
                    "success": False,
                    "review_suggestion": None,
                    "message": "模型未返回审核建议内容",
                }

            self.log_info(
                f"审核辅助建议生成完成，引用 {len(references)} 条标准物料资料"
            )
            return {
                "success": True,
                "review_suggestion": {
                    "summary": summary,
                    "references": references,
                    "retrieval": traces,
                },
                "message": "审核参考生成成功（仅供人工审核参考，不构成最终决定）",
            }
        except ValueError as e:
            error_msg = f"输入验证失败: {str(e)}"
            self.log_error(error_msg)
            return {"success": False, "review_suggestion": None, "message": error_msg}
        except Exception as e:
            error_msg = f"审核参考生成失败: {str(e)}"
            self.log_error(error_msg)
            return {"success": False, "review_suggestion": None, "message": error_msg}
