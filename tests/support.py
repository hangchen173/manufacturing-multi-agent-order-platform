"""多 Agent 测试公共设施。

把「装配 Supervisor + 全部 Agent + 假模型 + 假向量库」的样板收敛到一处，
使各测试文件只关心行为断言，而不是装配细节。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage

from application.agents import (
    Adjudicator,
    CatalogMatcher,
    Disambiguator,
    Extractor,
    GroundingVerifier,
    PolicyRisk,
    ReviewAssistant,
    ScheduleRisk,
    SemanticMatcher,
    StructureScout,
    Supervisor,
)
from application.orchestrators import OrderProcessingOrchestrator
from application.services import OrderManager
from config import Config
from domain.agent_roles import AgentRole
from infrastructure.repositories.memory import InMemoryOrderRepository

DEFAULT_REFERENCE_DATE = "2026-05-10"


class FakeFAISSManager:
    """确定性向量库替身：给出目录元数据与可定制的召回结果。"""

    def __init__(self, metadata: List[Dict[str, Any]], search_results: Optional[List] = None):
        self.metadata = metadata
        self._search_results = search_results or []

    def search(self, _query, k: int = 3):
        return self._search_results[:k]


class OfflineFAISSManager(FakeFAISSManager):
    """空召回：使匹配只走确定性目录路径。"""

    def __init__(self):
        super().__init__([], [])


def make_config(evaluation_as_of: str = DEFAULT_REFERENCE_DATE) -> Config:
    config = Config()
    config.data.order_auto_archive_days = 0
    if evaluation_as_of:
        config.risk.evaluation_as_of = evaluation_as_of
    return config


def build_agents(*, config: Config, llm=None, faiss_manager=None) -> Dict[AgentRole, Any]:
    return {
        AgentRole.STRUCTURE_SCOUT: StructureScout(config=config),
        AgentRole.EXTRACTOR: Extractor(llm=llm, config=config),
        AgentRole.GROUNDING_VERIFIER: GroundingVerifier(config=config),
        AgentRole.CATALOG_MATCHER: CatalogMatcher(config=config),
        AgentRole.SEMANTIC_MATCHER: SemanticMatcher(faiss_manager=faiss_manager, config=config),
        AgentRole.DISAMBIGUATOR: Disambiguator(
            match_threshold=config.risk.match_threshold, config=config
        ),
        AgentRole.POLICY_RISK: PolicyRisk(config=config),
        AgentRole.SCHEDULE_RISK: ScheduleRisk(config=config),
        AgentRole.ADJUDICATOR: Adjudicator(config=config),
        AgentRole.REVIEW_ASSISTANT: ReviewAssistant(faiss_manager=faiss_manager, config=config),
    }


class SupervisorHarness:
    """一组已装配好的协作组件，便于单测直接驱动。"""

    def __init__(self, *, config, agents, manager, supervisor, orchestrator, prompts):
        self.config = config
        self.agents = agents
        self.manager = manager
        self.supervisor = supervisor
        self.orchestrator = orchestrator
        self.prompts = prompts


def build_harness(
    *,
    payloads=(),
    catalog: Optional[List[Dict[str, Any]]] = None,
    faiss_manager=None,
    config: Optional[Config] = None,
    reference_date: str = DEFAULT_REFERENCE_DATE,
    llm=None,
    repository=None,
    rng_seed: Optional[int] = None,
) -> SupervisorHarness:
    config = config or make_config()
    # 默认使用离线向量库替身，避免单测触发真实嵌入模型加载（慢且耗内存）。
    faiss_manager = faiss_manager or OfflineFAISSManager()
    prompts: List[Any] = []
    if llm is None and payloads:
        responses = iter(payloads)

        def llm(prompt_value):  # noqa: F811 - 假模型：按调用顺序返回预置载荷
            prompts.append(prompt_value)
            return AIMessage(content=json.dumps(next(responses)))

    agents = build_agents(config=config, llm=llm, faiss_manager=faiss_manager)
    if catalog is None:
        catalog = list(getattr(faiss_manager, "metadata", []) or [])
    manager = OrderManager(repository=repository or InMemoryOrderRepository(), config=config)
    supervisor = Supervisor(
        agents=agents, order_manager=manager, catalog=catalog or [],
        reference_date=reference_date, rng_seed=rng_seed,
    )
    orchestrator = OrderProcessingOrchestrator(
        order_manager=manager, config=config, faiss_manager=faiss_manager,
        supervisor=supervisor, agents=agents,
    )
    return SupervisorHarness(
        config=config, agents=agents, manager=manager, supervisor=supervisor,
        orchestrator=orchestrator, prompts=prompts,
    )


# ---------------------------------------------------------------- document IR
EXCEL_HEADER = ["序号", "物料名称", "规格型号", "数量", "单位", "含税单价", "交期"]


def excel_ir(rows: List[List[Any]], sheet_name: str = "采购订单") -> Dict[str, Any]:
    """构造最小可用的 Excel Document IR（含唯一序号列）。"""
    return {
        "document_type": "excel",
        "sheets": [{
            "name": sheet_name, "index": 0, "hidden": False,
            "rows": [EXCEL_HEADER] + rows, "merged_regions": [],
        }],
    }


def excel_row(index: int, name: str, spec: str, quantity: float, unit: str = "个",
              price: Optional[float] = 1.0, delivery_date: Optional[str] = None) -> List[Any]:
    return [index, name, spec, quantity, unit, price, delivery_date]


def order_payload(items: List[Dict[str, Any]], *, order_number: str = "PO-1",
                  customer_name: str = "客户01", total_amount: Optional[float] = None,
                  parsing_confidence: float = 0.95) -> Dict[str, Any]:
    return {
        "order_number": order_number,
        "customer_name": customer_name,
        "items": items,
        "total_amount": total_amount,
        "parsing_confidence": parsing_confidence,
    }


def item(name: str, spec: Optional[str], quantity: Optional[float] = 10,
         unit: Optional[str] = "个", price: Optional[float] = 1.0,
         delivery_date: Optional[str] = None, confidence: float = 0.95) -> Dict[str, Any]:
    return {
        "material_name": name, "specification": spec, "quantity": quantity,
        "unit": unit, "unit_price": price, "delivery_date": delivery_date,
        "confidence_score": confidence,
    }


def run_ir(harness: SupervisorHarness, document_ir: Dict[str, Any],
           order_text: str = "") -> Dict[str, Any]:
    """直接以 Document IR 驱动 Supervisor（绕过文件加载）。"""
    order_id = harness.manager.create_order(order_text=order_text)
    return harness.supervisor.run(order_id, document_ir)
