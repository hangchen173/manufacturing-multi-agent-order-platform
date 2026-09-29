import unittest

from langchain_core.messages import AIMessage

from application.agents import ReviewAssistant
from config import Config
from domain.agent_roles import AgentRole
from domain.messages import Performative
from domain.models import (
    MatchedOrder,
    MatchedOrderItem,
    RiskCheckResult,
    RiskIssue,
)
from domain.tasks import TaskStatus
from tests.support import (
    FakeFAISSManager,
    build_harness,
    item,
    order_payload,
)
from tests.test_matching_ambiguity import CBL_003, CBL_043, CATALOG


class CapturingLLM:
    def __init__(self, content: str = "审核参考：建议与供应商确认价格后再放行。"):
        self.content = content
        self.prompt_text = None
        self.call_count = 0

    def __call__(self, prompt_value):
        self.call_count += 1
        self.prompt_text = prompt_value.to_string()
        return AIMessage(content=self.content)


def _build_risky_order():
    return MatchedOrder(
        order_number="PO-RAG-1",
        customer_name="测试客户",
        items=[
            MatchedOrderItem(
                material_name="屏蔽控制电缆",
                specification="RVVP 4×0.5mm² 普通屏蔽",
                quantity=100,
                unit="米",
                unit_price=9.9,
                confidence_score=0.95,
                sku_code="CBL-003",
                matched_material_name="屏蔽控制电缆",
                matched_specification="RVVP 4×0.5mm² 普通屏蔽",
                match_score=0.95,
                candidate_skus=["CBL-003"],
            ),
            MatchedOrderItem(
                material_name="神秘特种线缆",
                specification=None,
                quantity=None,
                unit=None,
                unit_price=None,
                confidence_score=0.6,
                match_score=0.2,
                candidate_skus=[],
            ),
        ],
        total_amount=990.0,
    )


def _build_risk_result():
    return RiskCheckResult(
        needs_confirmation=True,
        overall_confidence=0.6,
        issues=[
            RiskIssue(
                item_index=0,
                issue_type="price_out_of_policy",
                description="单价 9.9 为参考价 4.16 的 2.38 倍，超过 1.5 倍上限",
                severity="high",
            ),
            RiskIssue(
                item_index=1,
                issue_type="unknown_material",
                description="物料 '神秘特种线缆' 未能可靠匹配标准物料库，匹配得分 0.20",
                severity="high",
            ),
        ],
    )


class ReviewAssistantTests(unittest.TestCase):
    def _make_agent(self, llm, search_results=None):
        manager = FakeFAISSManager(CATALOG, search_results=search_results or [
            (CBL_003, 0.1),
            (CBL_043, 0.5),
        ])
        return ReviewAssistant(llm=llm, faiss_manager=manager, config=Config())

    def test_retrieved_materials_augment_llm_prompt(self):
        llm = CapturingLLM()
        agent = self._make_agent(llm)

        result = agent.suggest(_build_risky_order(), _build_risk_result())

        self.assertTrue(result["success"])
        suggestion = result["review_suggestion"]
        self.assertEqual(
            suggestion["summary"],
            "审核参考：建议与供应商确认价格后再放行。",
        )
        # 已接受 SKU 的资料确定性纳入，向量召回的异规格候选同步进入参考资料
        reference_skus = [doc["sku_code"] for doc in suggestion["references"]]
        self.assertIn("CBL-003", reference_skus)
        self.assertIn("CBL-043", reference_skus)
        # 每个风险行都留下检索轨迹，便于审计 RAG 的召回环节
        self.assertEqual(
            [(trace["item_index"], trace["query"]) for trace in suggestion["retrieval"]],
            [(0, "屏蔽控制电缆 RVVP 4×0.5mm² 普通屏蔽"), (1, "神秘特种线缆")],
        )
        # 关键断言：检索资料与确定性风险结论同时进入了 LLM 提示词（RAG 闭环证据）
        self.assertIn("2.38 倍", llm.prompt_text)
        self.assertIn("CBL-043", llm.prompt_text)
        self.assertIn("23.36", llm.prompt_text)
        self.assertEqual(llm.call_count, 1)

    def test_search_failure_keeps_accepted_sku_context(self):
        class FailingSearchManager(FakeFAISSManager):
            def search(self, _query, k=3):
                raise RuntimeError("index unavailable")

        agent = ReviewAssistant(
            llm=CapturingLLM(),
            faiss_manager=FailingSearchManager(CATALOG),
            config=Config(),
        )

        result = agent.suggest(_build_risky_order(), _build_risk_result())

        self.assertTrue(result["success"])
        reference_skus = [
            doc["sku_code"] for doc in result["review_suggestion"]["references"]
        ]
        self.assertEqual(reference_skus, ["CBL-003"])

    def test_missing_required_keys_returns_failure(self):
        agent = self._make_agent(CapturingLLM())

        result = agent.suggest(_build_risky_order(), None)

        self.assertFalse(result["success"])
        self.assertIn("risk_result", result["message"])

    def test_without_risk_issues_no_suggestion_is_generated(self):
        agent = self._make_agent(CapturingLLM())

        result = agent.suggest(_build_risky_order(), RiskCheckResult(
            needs_confirmation=False, issues=[], overall_confidence=1.0
        ))

        self.assertFalse(result["success"])
        self.assertIsNone(result["review_suggestion"])


class StubReviewAssistant:
    """桩：记录 suggest 的入参，返回固定审核参考。"""

    def __init__(self):
        self.calls = []

    def suggest(self, matched_order, risk_result):
        self.calls.append((matched_order, risk_result))
        return {
            "success": True,
            "review_suggestion": {
                "summary": "RAG 审核建议（桩）",
                "references": [{"sku_code": "CBL-003"}],
                "retrieval": [],
            },
            "message": "审核参考生成成功（仅供人工审核参考，不构成最终决定）",
        }


# 缺区分限定词：确定性路径拒识、向量召回低分候选 → 送人工审核
SUFFIX_CATALOG = [
    {"sku_code": "ELC-025", "material_name": "交流接触器",
     "specification": "CJX2-0910 AC220V 01", "unit": "个", "reference_price": 215.60,
     "category": "电气", "aliases": ["CJX2 9A 220V"]},
]

# 名称与规格完全一致：自动通过，不需要人工确认
PLAIN_CATALOG = [
    {"sku_code": "SKU-001", "material_name": "螺丝", "specification": "M8",
     "unit": "个", "reference_price": 1.0, "category": "紧固件", "aliases": []},
]


class ReviewSuggestionOrchestratorTests(unittest.TestCase):
    def _pending_harness(self):
        store = FakeFAISSManager(SUFFIX_CATALOG, search_results=[(SUFFIX_CATALOG[0], 0.5)])
        harness = build_harness(
            payloads=[order_payload([item("交流接触器", "CJX2-0910 AC220V", 10, "个", 200.0)])],
            faiss_manager=store,
        )
        stub = StubReviewAssistant()
        # orchestrator / supervisor / executor 共享同一个 agents 字典，替换即全局生效
        harness.agents[AgentRole.REVIEW_ASSISTANT] = stub
        return harness, stub

    def test_suggestion_available_only_for_pending_confirmation_order(self):
        harness, stub = self._pending_harness()
        processed = harness.orchestrator.process_order_from_text(
            "1 交流接触器 CJX2-0910 AC220V 10 个 200.0"
        )
        self.assertTrue(processed["needs_confirmation"])

        result = harness.orchestrator.generate_review_suggestion(processed["order_id"])

        self.assertTrue(result["success"])
        self.assertEqual(result["review_suggestion"]["summary"], "RAG 审核建议（桩）")
        self.assertEqual(
            result["review_suggestion"]["references"], [{"sku_code": "CBL-003"}]
        )
        self.assertEqual(len(stub.calls), 1)

    def test_completed_order_rejects_suggestion_request(self):
        harness = build_harness(
            payloads=[order_payload([item("螺丝", "M8", 10, "个", 1.0)])],
            catalog=PLAIN_CATALOG,
        )
        processed = harness.orchestrator.process_order_from_text("1 螺丝 M8 10 个 1.0")
        self.assertFalse(processed["needs_confirmation"])

        result = harness.orchestrator.generate_review_suggestion(processed["order_id"])

        self.assertFalse(result["success"])
        self.assertIn("待人工确认", result["message"])

    def test_unknown_order_returns_failure(self):
        harness, _ = self._pending_harness()

        result = harness.orchestrator.generate_review_suggestion("nonexistent-id")

        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "订单不存在")

    def test_escalation_is_recorded_and_assist_task_is_dispatched(self):
        """裁决转人工时必须留下 ESCALATE 事件，并真正派发 review_assistant 任务。

        回归背景：ReviewAssistant 一度只挂在「人工主动请求」这条路上
        （POST /review-suggestion），裁决阶段的升级既不写消息轨迹、也不进任务 DAG，
        导致 /trace 答不出「为何升级」、/tasks 看不到旁路任务。
        本测试故意不替换 agents 字典里的 ReviewAssistant，让它走真实 handle() 链路。
        """
        store = FakeFAISSManager(SUFFIX_CATALOG, search_results=[(SUFFIX_CATALOG[0], 0.5)])
        harness = build_harness(
            payloads=[order_payload([item("交流接触器", "CJX2-0910 AC220V", 10, "个", 200.0)])],
            faiss_manager=store,
        )
        processed = harness.orchestrator.process_order_from_text(
            "1 交流接触器 CJX2-0910 AC220V 10 个 200.0"
        )
        self.assertTrue(processed["needs_confirmation"])
        order_id = processed["order_id"]

        messages = harness.orchestrator.get_trace(order_id)["messages"]
        by_performative = {}
        for message in messages:
            by_performative.setdefault(message["performative"], []).append(message)

        self.assertIn(Performative.ESCALATE.value, by_performative)
        escalate = by_performative[Performative.ESCALATE.value][0]
        self.assertEqual(escalate["sender"], AgentRole.SUPERVISOR.value)
        self.assertEqual(escalate["payload"]["action"], "manual_review")

        self.assertIn(Performative.REQUEST.value, by_performative)
        request = by_performative[Performative.REQUEST.value][0]
        self.assertEqual(request["sender"], AgentRole.SUPERVISOR.value)
        self.assertEqual(request["recipient"], AgentRole.REVIEW_ASSISTANT.value)

        tasks = harness.orchestrator.get_tasks(order_id)
        assist = [task for task in tasks if task["stage"] == "assist"]
        self.assertEqual(len(assist), 1)
        self.assertEqual(assist[0]["agent"], AgentRole.REVIEW_ASSISTANT.value)
        self.assertEqual(assist[0]["status"], TaskStatus.DONE.value)

        # 设计文档 §S8：审核建议必须以证据形式写入黑板 Layer 2，而非只回一段文本。
        inform = [
            message for message in by_performative.get(Performative.INFORM.value, [])
            if message["sender"] == AgentRole.REVIEW_ASSISTANT.value
        ]
        self.assertEqual(len(inform), 1)
        self.assertTrue(inform[0]["evidence"])

        # 旁路任务确实调用了模型：升级事件之外还留下了审核参考
        self.assertEqual(harness.review_llm.calls, 1)


if __name__ == "__main__":
    unittest.main()
