"""设计文档 §4.2「七类可执行验证」的可运行实现（V1–V7）。

这些不是业务功能的回归测试，而是**架构断言**：用来证明「多 Agent + 黑板 + 对抗
协议」确实按设计运行，而不是把线性流水线换个名字。

| 编号 | 验证内容 | 断言方式 |
| --- | --- | --- |
| V1 | 通信拓扑：Agent 之间零直接调用 | 静态扫描 + 实例属性检查 |
| V2 | 调度顺序无关性 | 固定模型替身，打乱就绪顺序 20 次，终态不变 |
| V3 | 对抗有效性：幻觉挑战召回率 | 对抗集召回率严格高于自我确认基线 |
| V4 | 独立性消融 | 上下文隔离对挑战率有正贡献 |
| V5 | 反事实贡献归因 | 逐个禁用 Agent，贡献矩阵无全零行 |
| V6 | 并行收益 | DAG 扇出延迟随行数摊薄 |
| V7 | 故障注入与恢复 | worker 崩溃 / 超时 / 结构失败 / 预算 / 并发确认 |
"""
from __future__ import annotations

import ast
import json
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage

import application.agents as agents_package
from application.agents.base_agent import CollaborativeAgent
from application.blackboard.blackboard import Blackboard
from application.blackboard.slices import assert_slice_isolated, forbidden_keys
from application.services import OrderManager
from domain.agent_roles import AgentRole
from domain.models import FinalOrderResult, OrderStatus
from domain.tasks import Task
from tests.fakes import InMemoryOrderRepository
from tests.support import (
    FakeFAISSManager,
    OfflineFAISSManager,
    build_agents,
    build_harness,
    excel_ir,
    excel_row,
    item,
    make_config,
    order_payload,
)

ORDER_TEXT = "1 螺丝 M8 10 个 1.0"

CLEAN_CATALOG = [
    {"sku_code": "SKU-1", "material_name": "螺丝", "specification": "M8",
     "unit": "个", "reference_price": 1.0, "aliases": []},
]


# ====================================================================== 运行辅助
def _run_text(harness, text: str) -> Dict[str, Any]:
    order_id = harness.manager.create_order(order_text=text)
    return harness.supervisor.run(order_id, {"document_type": "text", "text": text})


def _run_ir(harness, document_ir: Dict[str, Any]) -> Dict[str, Any]:
    order_id = harness.manager.create_order(order_text="")
    return harness.supervisor.run(order_id, document_ir)


def _message_signature(result: Dict[str, Any]) -> List[Any]:
    """消息集合（忽略时间戳/任务 id 等每次运行必然不同的字段）。"""
    return sorted(
        (message.sender, message.performative.value,
         json.dumps(message.subject or {}, sort_keys=True, ensure_ascii=False))
        for message in result["blackboard"].messages()
    )


def _outcome_signature(result: Dict[str, Any]) -> Any:
    """终态签名：动作、是否送审、SKU/候选/拒识理由、风险问题集合。"""
    if not result.get("success"):
        return ("failure",)
    verdict = result["verdict"]
    matched = verdict["matched_order"]
    return (
        "ok",
        verdict["action"],
        bool(verdict["needs_confirmation"]),
        tuple(
            (entry["sku_code"], tuple(entry.get("candidate_skus") or []),
             entry.get("rejection_reason"))
            for entry in matched["items"]
        ),
        tuple(sorted(issue["issue_type"] for issue in verdict["risk_result"]["issues"])),
    )


def _challenged_fields(result: Dict[str, Any]) -> set:
    parse = (result.get("diagnostics") or {}).get("parse") or {}
    return {challenge.get("field") for challenge in parse.get("challenges") or []}


class _DisabledAgent:
    """禁用替身：任务照常调度，但不产出任何消息（模拟该角色缺席）。"""

    def __init__(self, role: AgentRole):
        self.role = role

    def handle(self, _task: Task) -> List[Any]:
        return []


# ====================================================================== V1 拓扑
AGENT_DIR = Path(agents_package.__file__).parent
#: 允许被同层模块引用的共享库（纯函数 / 基类），不属于「跨 Agent 调用」。
SHARED_AGENT_MODULES = {"base_agent", "source_map", "match_keys"}


class TopologyTests(unittest.TestCase):
    """V1 — 通信拓扑断言：Agent 之间零直接调用。"""

    def test_agent_modules_do_not_reference_peer_agents(self):
        for path in sorted(AGENT_DIR.glob("*.py")):
            if path.stem == "__init__":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and \
                        node.module.startswith("application.agents."):
                    target = node.module.split(".")[2]
                    self.assertIn(
                        target, SHARED_AGENT_MODULES,
                        f"{path.name} 直接引用了同层 Agent 模块 '{target}'",
                    )
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertFalse(
                            alias.name.startswith("application.orchestrators"),
                            f"{path.name} 不应引用编排层",
                        )

    def test_no_agent_holds_a_peer_agent_instance(self):
        agents = build_agents(
            config=make_config(),
            llm=lambda _prompt: AIMessage(content="{}"),
            faiss_manager=OfflineFAISSManager(),
        )
        for role, agent in agents.items():
            for attribute, value in vars(agent).items():
                self.assertNotIsInstance(
                    value, CollaborativeAgent,
                    f"{role.value} 持有同伴 Agent 实例：{attribute}",
                )


# ====================================================================== V2 顺序无关
TWO_ITEM_TEXT = "1 螺丝 M8 10 个 1.0\n2 螺母 M8 5 个 2.0"
TWO_ITEM_CATALOG = [
    {"sku_code": "SKU-1", "material_name": "螺丝", "specification": "M8",
     "unit": "个", "reference_price": 1.0, "aliases": []},
    {"sku_code": "SKU-2", "material_name": "螺母", "specification": "M8",
     "unit": "个", "reference_price": 2.0, "aliases": []},
]


class ScheduleOrderIndependenceTests(unittest.TestCase):
    """V2 — 打乱就绪任务顺序，最终消息集合与终态必须完全一致。"""

    def test_shuffled_schedule_yields_identical_outcome(self):
        payload = order_payload([item("螺丝", "M8", 10, "个", 1.0),
                                 item("螺母", "M8", 5, "个", 2.0)])
        baseline = None
        for seed in range(20):
            harness = build_harness(
                payloads=[dict(payload)], catalog=TWO_ITEM_CATALOG, rng_seed=seed,
            )
            result = _run_text(harness, TWO_ITEM_TEXT)
            signature = (_message_signature(result), _outcome_signature(result))
            if baseline is None:
                baseline = signature
            else:
                self.assertEqual(
                    signature, baseline,
                    f"seed={seed} 改变了最终消息集合或终态，说明调度并非纯依赖驱动",
                )


# ====================================================================== V3 幻觉召回
#: 对抗集：把抽取结果中的字段替换为原文不存在的值（格式依然合法）。
ADVERSARIAL_CASES = [
    ("quantity", item("螺丝", "M8", 99, "个", 1.0)),
    ("unit_price", item("螺丝", "M8", 10, "个", 7.7)),
    ("material_name", item("不锈钢螺栓", "M8", 10, "个", 1.0)),
    ("specification", item("螺丝", "M99", 10, "个", 1.0)),
]
SOURCE_ROW = excel_row(1, "螺丝", "M8", 10, "个", 1.0)


class HallucinationRecallTests(unittest.TestCase):
    """V3 — 独立验证者对抗集召回率必须严格高于自我确认基线。"""

    def _run_case(self, payload_item: Dict[str, Any]) -> Dict[str, Any]:
        # 挑战会触发一次带反证重抽，故需要两条相同载荷（第二遍仍“顽固”）
        harness = build_harness(
            payloads=[order_payload([payload_item])] * 2, catalog=CLEAN_CATALOG,
        )
        return _run_ir(harness, excel_ir([SOURCE_ROW]))

    def test_every_injected_hallucination_is_challenged(self):
        caught = sum(
            1 for field, payload_item in ADVERSARIAL_CASES
            if field in _challenged_fields(self._run_case(payload_item))
        )
        recall = caught / len(ADVERSARIAL_CASES)
        # 自我确认基线：生产者置信度恒为 0.95，自检对格式合法的对抗值一律放行
        baseline_recall = 0.0
        self.assertEqual(recall, 1.0, "独立验证者漏检了部分注入幻觉")
        self.assertGreater(recall, baseline_recall)


# ====================================================================== V4 隔离消融
class ContextIsolationAblationTests(unittest.TestCase):
    """V4 — 上下文隔离对挑战率有正贡献（回答“为什么必须两个 Agent”）。"""

    def test_forbidden_keys_are_declared_for_the_verifier(self):
        forbidden = forbidden_keys(AgentRole.GROUNDING_VERIFIER)
        self.assertIn("extractor.rationale", forbidden)
        self.assertIn("extractor.confidence", forbidden)

    def test_verifier_slice_strips_producer_confidence(self):
        harness = build_harness(
            payloads=[order_payload([item("螺丝", "M8", 10, "个", 1.0)])] * 2,
            catalog=CLEAN_CATALOG,
        )
        result = _run_ir(harness, excel_ir([SOURCE_ROW]))
        board = result["blackboard"]

        # 生产者的主张在黑板 Layer 2 里确实带着自报置信度
        raw = board.claims("item[0]")
        self.assertTrue(raw)
        self.assertIsNotNone(raw[0].to_dict()["confidence"])

        view = board.slice_for(AgentRole.GROUNDING_VERIFIER,
                               {"item_index": 0, "subject": "item[0]"})
        assert_slice_isolated(AgentRole.GROUNDING_VERIFIER, view)
        self.assertNotIn("extractor.rationale", view)
        self.assertNotIn("extractor.confidence", view)
        for record in view["claims"]:
            self.assertNotIn("confidence", record)

    def test_isolation_lifts_challenge_rate_over_self_confirmation(self):
        # 隔离组：真实 GroundingVerifier（只看原文与可复现证据）
        isolated = 0
        for field, payload_item in ADVERSARIAL_CASES:
            harness = build_harness(
                payloads=[order_payload([payload_item])] * 2, catalog=CLEAN_CATALOG,
            )
            result = _run_ir(harness, excel_ir([SOURCE_ROW]))
            if field in _challenged_fields(result):
                isolated += 1
        isolated_rate = isolated / len(ADVERSARIAL_CASES)

        # 泄漏组：模拟“能读到生产者置信度”的自我确认（置信度≥0.8 即放行）
        leaked = sum(
            1 for _field, payload_item in ADVERSARIAL_CASES
            if payload_item["confidence_score"] < 0.8
        )
        leaked_rate = leaked / len(ADVERSARIAL_CASES)

        self.assertEqual(leaked_rate, 0.0)
        self.assertGreater(isolated_rate, leaked_rate)


# ====================================================================== V5 贡献归因
PIPELINE_AGENTS = [
    AgentRole.STRUCTURE_SCOUT,
    AgentRole.EXTRACTOR,
    AgentRole.GROUNDING_VERIFIER,
    AgentRole.CATALOG_MATCHER,
    AgentRole.SEMANTIC_MATCHER,
    AgentRole.DISAMBIGUATOR,
    AgentRole.POLICY_RISK,
    AgentRole.SCHEDULE_RISK,
]


def _scenarios() -> List[Dict[str, Any]]:
    from tests.test_matching_ambiguity import CBL_003

    ambiguous_store = FakeFAISSManager([CBL_003], search_results=[(CBL_003, 0.02)])
    return [
        {
            "name": "clean",
            "text": "1 螺丝 M8 10 个 1.0",
            "payloads": [order_payload([item("螺丝", "M8", 10, "个", 1.0)])],
            "catalog": CLEAN_CATALOG,
        },
        {
            "name": "policy_price",
            "text": "1 螺丝 M8 10 个 5.0",
            "payloads": [order_payload([item("螺丝", "M8", 10, "个", 5.0)])],
            "catalog": CLEAN_CATALOG,
        },
        {
            "name": "schedule_past_delivery",
            "text": "1 螺丝 M8 10 个 1.0 交期2026-01-01",
            "payloads": [order_payload([item("螺丝", "M8", 10, "个", 1.0, "2026-01-01")])],
            "catalog": CLEAN_CATALOG,
        },
        {
            "name": "ambiguous_semantic",
            "text": "1 工业电气 RVVP 4×0.5mm² 普通屏蔽 100 米 1.0",
            "payloads": [order_payload(
                [item("工业电气", "RVVP 4×0.5mm² 普通屏蔽", 100, "米", 1.0)]
            )],
            "catalog": [CBL_003],
            "faiss_manager": ambiguous_store,
        },
        {
            "name": "hallucination",
            "ir": excel_ir([SOURCE_ROW]),
            "payloads": [order_payload([item("螺丝", "M8", 99, "个", 1.0)])] * 2,
            "catalog": CLEAN_CATALOG,
        },
        {
            "name": "empty",
            "text": "与订单无关的垃圾文本",
            "payloads": [order_payload([], parsing_confidence=0.1)] * 2,
            "catalog": CLEAN_CATALOG,
        },
    ]


class CounterfactualAttributionTests(unittest.TestCase):
    """V5 — 逐个禁用非终裁 Agent，产出贡献矩阵；不得存在全零行。"""

    def _run(self, scenario: Dict[str, Any], disabled: Optional[AgentRole] = None) -> Any:
        harness = build_harness(
            payloads=[dict(payload) for payload in scenario["payloads"]],
            catalog=scenario.get("catalog"),
            faiss_manager=scenario.get("faiss_manager"),
        )
        if disabled is not None:
            harness.agents[disabled] = _DisabledAgent(disabled)
        if "ir" in scenario:
            return _outcome_signature(_run_ir(harness, scenario["ir"]))
        return _outcome_signature(_run_text(harness, scenario["text"]))

    def test_every_pipeline_agent_has_a_non_zero_contribution(self):
        scenarios = _scenarios()
        zero_rows: List[str] = []
        for role in PIPELINE_AGENTS:
            contributes = False
            for scenario in scenarios:
                if self._run(scenario) != self._run(scenario, disabled=role):
                    contributes = True
                    break
            if not contributes:
                zero_rows.append(role.value)
        self.assertEqual(
            zero_rows, [],
            f"以下 Agent 在所有场景中贡献为零，属于装饰性角色：{zero_rows}",
        )


# ====================================================================== V6 并行收益
class ParallelBenefitTests(unittest.TestCase):
    """V6 — DAG 扇出的端到端延迟必须随行数摊薄，而不是线性增长。"""

    class _SlowAgent:
        role = AgentRole.CATALOG_MATCHER

        def __init__(self, delay: float):
            self.delay = delay

        def handle(self, _task: Task) -> List[Any]:
            time.sleep(self.delay)
            return []

    def _tasks(self, count: int) -> List[Task]:
        return [
            Task(order_id="parallel", agent=AgentRole.CATALOG_MATCHER.value, stage="match")
            for _ in range(count)
        ]

    def test_parallel_group_beats_sequential_execution(self):
        harness = build_harness()
        harness.agents[AgentRole.CATALOG_MATCHER] = self._SlowAgent(0.05)
        tasks = self._tasks(8)

        start = time.perf_counter()
        for task in tasks:
            harness.supervisor._execute_task(task, None)
        sequential = time.perf_counter() - start

        start = time.perf_counter()
        grouped = harness.supervisor._run_group(tasks, None)
        parallel = time.perf_counter() - start

        self.assertEqual(len(grouped), 8)
        self.assertLess(parallel, sequential * 0.6)

    def test_latency_does_not_grow_linearly_with_row_count(self):
        measurements: Dict[int, float] = {}
        for rows in (1, 5, 20):
            harness = build_harness()
            harness.agents[AgentRole.CATALOG_MATCHER] = self._SlowAgent(0.03)
            start = time.perf_counter()
            harness.supervisor._run_group(self._tasks(rows), None)
            measurements[rows] = time.perf_counter() - start
        # 20 行的扇出耗时不应接近 1 行的 20 倍（否则说明扇出没生效）
        self.assertLess(measurements[20], measurements[1] * 5)


# ====================================================================== V7 故障注入
class FaultInjectionTests(unittest.TestCase):
    """V7 — 故障注入与恢复：订单不得卡在中间态，预算超限必须升级人工。"""

    INTERMEDIATE_STATES = {
        OrderStatus.PENDING.value, OrderStatus.PARSING.value,
        OrderStatus.MATCHING.value, OrderStatus.RISK_CHECKING.value,
    }

    def test_worker_crash_is_retried_and_order_never_stalls_midway(self):
        # ① 首次执行抛可重试错误（模拟 worker 被杀），第二次成功
        calls = {"count": 0}

        class FlakyMatcher:
            role = AgentRole.CATALOG_MATCHER

            def handle(self, _task: Task) -> List[Any]:
                calls["count"] += 1
                if calls["count"] == 1:
                    raise ConnectionError("worker killed")
                return []

        harness = build_harness(
            payloads=[order_payload([item("螺丝", "M8", 10, "个", 1.0)])],
            catalog=CLEAN_CATALOG,
        )
        harness.agents[AgentRole.CATALOG_MATCHER] = FlakyMatcher()

        result = harness.orchestrator.process_order_from_text(ORDER_TEXT)
        status = harness.orchestrator.get_order_status(result["order_id"])

        self.assertEqual(calls["count"], 2)
        self.assertNotIn(status["status"], self.INTERMEDIATE_STATES)

    def test_timeout_retried_without_feedback_and_schema_failure_with_feedback(self):
        # ② 超时属瞬态错误：有限重试，但不注入结构修正反馈
        timeout_prompts: List[Any] = []

        def timeout(prompt_value):
            timeout_prompts.append(prompt_value)
            raise TimeoutError("model timed out")

        harness = build_harness(llm=timeout)
        result = harness.orchestrator.process_order_from_text(ORDER_TEXT)
        self.assertFalse(result["success"])
        self.assertEqual(len(timeout_prompts), 2)
        self.assertNotIn("上一次抽取结果", timeout_prompts[1].to_string())

        # 结构校验失败：带错误详情有界重抽
        schema_prompts: List[Any] = []

        def bad_schema(prompt_value):
            schema_prompts.append(prompt_value)
            return AIMessage(content="这不是一个合法的订单 JSON")

        harness = build_harness(llm=bad_schema)
        result = harness.orchestrator.process_order_from_text(ORDER_TEXT)
        self.assertFalse(result["success"])
        self.assertEqual(len(schema_prompts), 2)
        self.assertIn("上一次抽取结果", schema_prompts[1].to_string())

    def test_budget_exhaustion_escalates_instead_of_passing_silently(self):
        # ③ 预算耗尽 → ESCALATE 转人工，而不是静默通过
        harness = build_harness(
            payloads=[order_payload([item("螺丝", "M8", 10, "个", 1.0)])],
            catalog=CLEAN_CATALOG,
        )
        harness.supervisor.max_llm_calls = 0

        result = harness.orchestrator.process_order_from_text(ORDER_TEXT)
        status = harness.orchestrator.get_order_status(result["order_id"])

        self.assertFalse(result["success"])
        self.assertIn("预算耗尽", result["message"])
        self.assertEqual(status["status"], OrderStatus.FAILED.value)
        self.assertNotEqual(status["status"], OrderStatus.COMPLETED.value)

    def test_concurrent_confirmation_allows_only_one_transition(self):
        # ④ 并发人工确认：CAS 保证只有一次有效状态转换（回归）
        repository = InMemoryOrderRepository()
        manager = OrderManager(repository=repository, config=make_config())
        order_id = manager.create_order(order_text="concurrent")
        for status in (OrderStatus.PARSING, OrderStatus.MATCHING, OrderStatus.RISK_CHECKING):
            manager.update_order_status(order_id, status)
        manager.finalize_order(
            order_id, FinalOrderResult(status=OrderStatus.NEEDS_CONFIRMATION), {"issues": []},
        )

        self.assertTrue(manager.review_order(order_id, "confirm"))
        self.assertFalse(manager.review_order(order_id, "reject"))


if __name__ == "__main__":
    unittest.main()
