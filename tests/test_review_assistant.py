import unittest

from langchain_core.messages import AIMessage

from application.agents import ReviewAssistantAgent
from application.orchestrators import OrderProcessingOrchestrator
from application.services import OrderManager
from config import Config
from domain.models import (
    MatchedOrder,
    MatchedOrderItem,
    RiskCheckResult,
    RiskIssue,
)
from tests.fakes import InMemoryOrderRepository
from tests.test_matching_ambiguity import CBL_003, CBL_043, CATALOG, FakeFAISSManager
from tests.test_order_flow import FixedMatcher, FixedParser, FixedRiskControl


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


class ReviewAssistantAgentTests(unittest.TestCase):
    def _make_agent(self, llm, search_results=None):
        manager = FakeFAISSManager(CATALOG, search_results=search_results or [
            (CBL_003, 0.1),
            (CBL_043, 0.5),
        ])
        return ReviewAssistantAgent(llm=llm, faiss_manager=manager, config=Config())

    def test_retrieved_materials_augment_llm_prompt(self):
        llm = CapturingLLM()
        agent = self._make_agent(llm)

        result = agent.run({
            "matched_order": _build_risky_order(),
            "risk_result": _build_risk_result(),
        })

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

        agent = ReviewAssistantAgent(
            llm=CapturingLLM(),
            faiss_manager=FailingSearchManager(CATALOG),
            config=Config(),
        )

        result = agent.run({
            "matched_order": _build_risky_order(),
            "risk_result": _build_risk_result(),
        })

        self.assertTrue(result["success"])
        reference_skus = [
            doc["sku_code"] for doc in result["review_suggestion"]["references"]
        ]
        self.assertEqual(reference_skus, ["CBL-003"])

    def test_missing_required_keys_returns_failure(self):
        agent = self._make_agent(CapturingLLM())

        result = agent.run({"matched_order": _build_risky_order()})

        self.assertFalse(result["success"])
        self.assertIn("risk_result", result["message"])

    def test_without_risk_issues_no_suggestion_is_generated(self):
        agent = self._make_agent(CapturingLLM())

        result = agent.run({
            "matched_order": _build_risky_order(),
            "risk_result": RiskCheckResult(
                needs_confirmation=False, issues=[], overall_confidence=1.0
            ),
        })

        self.assertFalse(result["success"])
        self.assertIsNone(result["review_suggestion"])


class ManualReviewRiskControl:
    def run(self, _input_data):
        return {"success": True, "risk_result": _build_risk_result()}


class StubReviewAssistant:
    def run(self, input_data):
        assert "matched_order" in input_data and "risk_result" in input_data
        return {
            "success": True,
            "review_suggestion": {
                "summary": "RAG 审核建议（桩）",
                "references": [{"sku_code": "CBL-003"}],
                "retrieval": [],
            },
            "message": "审核参考生成成功（仅供人工审核参考，不构成最终决定）",
        }


def _build_orchestrator(risk_agent):
    config = Config()
    manager = OrderManager(repository=InMemoryOrderRepository(), config=config)
    return OrderProcessingOrchestrator(
        config=config,
        order_manager=manager,
        parser_agent_general=FixedParser(),
        matching_agent=FixedMatcher(),
        risk_agent=risk_agent,
        review_assistant=StubReviewAssistant(),
    )


class ReviewSuggestionOrchestratorTests(unittest.TestCase):
    def test_suggestion_available_only_for_pending_confirmation_order(self):
        orchestrator = _build_orchestrator(ManualReviewRiskControl())
        processed = orchestrator.process_order_from_text("订单文本")
        self.assertTrue(processed["needs_confirmation"])

        result = orchestrator.generate_review_suggestion(processed["order_id"])

        self.assertTrue(result["success"])
        self.assertEqual(result["review_suggestion"]["summary"], "RAG 审核建议（桩）")
        self.assertEqual(
            result["review_suggestion"]["references"], [{"sku_code": "CBL-003"}]
        )

    def test_completed_order_rejects_suggestion_request(self):
        orchestrator = _build_orchestrator(FixedRiskControl())
        processed = orchestrator.process_order_from_text("订单文本")
        self.assertFalse(processed["needs_confirmation"])

        result = orchestrator.generate_review_suggestion(processed["order_id"])

        self.assertFalse(result["success"])
        self.assertIn("待人工确认", result["message"])

    def test_unknown_order_returns_failure(self):
        orchestrator = _build_orchestrator(ManualReviewRiskControl())

        result = orchestrator.generate_review_suggestion("nonexistent-id")

        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "订单不存在")


if __name__ == "__main__":
    unittest.main()
