"""审核协助 Agent。

从“装饰性旁路”升级为**参与者**：它响应 ESCALATE / 人工请求，把检索到的标准物料
资料与确定性风险事实组织成审核参考，并把结果作为证据写入黑板 Layer 2。

它仍然只读、不参与自动决策，也不回写任何事实。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from application.agents.base_agent import CollaborativeAgent
from application.protocol.model_output import assert_not_truncated
from domain.agent_roles import AgentRole
from domain.messages import AgentMessage, Evidence, Performative
from domain.models import MatchedOrder, RiskCheckResult
from domain.tasks import Task

ORDER_LEVEL_ITEM_INDEX = -1
RETRIEVE_TOP_K = 3

#: 推理与正文共享 max_tokens；审核参考虽是短文，但推理阶段实测可消耗上千 token，
#: 上限过低会让正文返回空串。此处留出足够空间。
REVIEW_MAX_TOKENS = 4096

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


class ReviewAssistant(CollaborativeAgent):
    role = AgentRole.REVIEW_ASSISTANT

    def __init__(self, llm: Any = None, faiss_manager: Any = None, blackboard: Any = None,
                 budget: Any = None, config: Any = None):
        super().__init__(blackboard, budget, config)
        self.llm = llm
        self._faiss_manager = faiss_manager

    @property
    def faiss_manager(self):
        if self._faiss_manager is None and self.config is not None:
            from infrastructure.vector_store.faiss_manager import FAISSManager

            self._faiss_manager = FAISSManager(index_path=self.config.data.faiss_index_path)
        return self._faiss_manager

    def _get_llm(self):
        if self.llm is None:
            from langchain_openai import ChatOpenAI

            # 角色级模型路由：审核助手可独立选型（见 Config.model_for）。
            model_config = self.config.model_for(self.role.value)
            self.llm = ChatOpenAI(
                model=model_config.model,
                api_key=model_config.api_key or self.config.require_model_api_key(),
                base_url=model_config.base_url,
                temperature=0,
                max_tokens=REVIEW_MAX_TOKENS,
                model_kwargs={"extra_body": model_config.request_body()},
                timeout=60,
                max_retries=0,
            )
        return self.llm

    # ------------------------------------------------------------------ task entry
    def handle(self, task: Task) -> List[AgentMessage]:
        """响应 ESCALATE：输出写入黑板 Layer 2 作为证据。"""
        view = self.read_slice(task)
        matched_order = task.slice_key.get("matched_order")
        risk_result = task.slice_key.get("risk_result")
        if matched_order is None or risk_result is None:
            return [self.emit(task, Performative.REFUSE,
                              payload={"reason": "缺少 matched_order 或 risk_result"})]
        result = self.suggest(matched_order, risk_result)
        if not result.get("success"):
            return [self.emit(task, Performative.REFUSE,
                              payload={"reason": result.get("message", "审核参考生成失败")})]
        suggestion = result["review_suggestion"]
        return [self.emit(
            task,
            Performative.INFORM,
            subject={"claim_subject": "order.review_assistance"},
            payload={"review_suggestion": suggestion},
            evidence=[Evidence(
                kind="catalog_row",
                locator={"kind": "catalog", "sku_code": reference.get("sku_code")},
                value=reference.get("reference_price"),
                reproducible=True,
            ) for reference in suggestion.get("references", []) if reference.get("sku_code")],
        )]

    # ------------------------------------------------------------------ RAG
    def suggest(self, matched_order: MatchedOrder, risk_result: RiskCheckResult) -> Dict[str, Any]:
        self.log_info("开始生成人工审核辅助建议")
        try:
            if matched_order is None or risk_result is None:
                return {"success": False, "review_suggestion": None,
                        "message": "缺少 matched_order 或 risk_result"}
            if not risk_result.issues:
                return {"success": False, "review_suggestion": None,
                        "message": "订单无风险问题，无需生成审核参考"}

            risk_facts, risky_indexes = self._build_risk_facts(matched_order, risk_result)
            references, traces = self._retrieve_materials(matched_order, risky_indexes)

            prompt = self._create_prompt()
            message = (prompt | self._get_llm()).invoke({
                "order_context": self._build_order_context(matched_order),
                "risk_facts": risk_facts,
                "materials": json.dumps(references, ensure_ascii=False),
            })
            # 截断（finish_reason='length' / 空正文）要给出可诊断的原因，而不是
            # 笼统的「模型未返回审核建议内容」。
            assert_not_truncated(message, agent_name="ReviewAssistant",
                                 max_tokens=REVIEW_MAX_TOKENS)
            summary = (message.content or "").strip()
            if not summary:
                return {"success": False, "review_suggestion": None,
                        "message": "模型未返回审核建议内容"}

            self.log_info(f"审核辅助建议生成完成，引用 {len(references)} 条标准物料资料")
            return {
                "success": True,
                "review_suggestion": {
                    "summary": summary,
                    "references": references,
                    "retrieval": traces,
                },
                "message": "审核参考生成成功（仅供人工审核参考，不构成最终决定）",
            }
        except Exception as exc:  # noqa: BLE001 - 审核辅助失败不得影响订单终态
            self.log_error(f"审核参考生成失败: {exc}")
            return {"success": False, "review_suggestion": None,
                    "message": f"审核参考生成失败: {exc}"}

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

    def _build_risk_facts(self, matched_order: MatchedOrder,
                          risk_result: RiskCheckResult) -> Tuple[str, List[int]]:
        issues_by_item: Dict[int, List[str]] = {}
        order_level_issues: List[str] = []
        for issue in risk_result.issues:
            if issue.item_index == ORDER_LEVEL_ITEM_INDEX:
                order_level_issues.append(issue.description)
            else:
                issues_by_item.setdefault(issue.item_index, []).append(issue.description)

        facts: List[Dict[str, Any]] = []
        for index in sorted(issues_by_item):
            if index >= len(matched_order.items):
                facts.append({"item_index": index, "risk_issues": issues_by_item[index]})
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
            facts.append({"item_index": ORDER_LEVEL_ITEM_INDEX, "risk_issues": order_level_issues})

        return json.dumps(facts, ensure_ascii=False), sorted(issues_by_item)

    @staticmethod
    def _material_reference(doc: Dict[str, Any]) -> Dict[str, Any]:
        return {key: doc.get(key) for key in _REFERENCE_FIELDS}

    def _find_doc_by_sku(self, sku_code: str) -> Optional[Dict[str, Any]]:
        if self.faiss_manager is None:
            return None
        return next(
            (row for row in self.faiss_manager.metadata if row.get("sku_code") == sku_code),
            None,
        )

    def _retrieve_materials(self, matched_order: MatchedOrder,
                            risky_indexes: List[int]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
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
            if query and self.faiss_manager is not None:
                try:
                    results = self.faiss_manager.search(query, k=RETRIEVE_TOP_K)
                except Exception as exc:  # noqa: BLE001 - 检索失败只降级，不失败整单
                    self.log_warning(f"审核辅助检索失败 item_index={index} query='{query}': {exc}")
                    results = []
                for doc, _distance in results:
                    sku_code = doc.get("sku_code")
                    if sku_code:
                        recalled_skus.append(sku_code)
                    if sku_code and sku_code not in references:
                        references[sku_code] = self._material_reference(doc)

            traces.append({"item_index": index, "query": query, "recalled_skus": recalled_skus})

        return list(references.values()), traces

    def _create_prompt(self):
        from langchain_core.prompts import ChatPromptTemplate

        return ChatPromptTemplate.from_messages([
            ("system", _SYSTEM_PROMPT),
            ("user", _USER_TEMPLATE),
        ])
