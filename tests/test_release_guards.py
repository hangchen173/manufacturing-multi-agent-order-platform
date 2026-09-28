import json
import unittest

import httpx

from application.agents import Extractor
from application.orchestrators import OrderProcessingOrchestrator
from application.services import OrderManager
from config import Config
from tests.fakes import InMemoryOrderRepository
from tests.support import build_harness, item, order_payload

ORDER_TEXT = "1 螺丝 M8 10 个 1.0"
TWO_ROW_TEXT = "1 螺丝 M8 10 个 1.0\n2 螺母 M8 5 个 2.0"


def _payload(spec="M8", name="螺丝", total_amount=None):
    payload = order_payload([item(name, spec, 10, "个", 1.0)])
    payload["total_amount"] = total_amount
    return payload


class ReleaseGuardTests(unittest.TestCase):
    def test_missing_specification_is_not_retried_or_invented(self):
        harness = build_harness(payloads=[_payload(spec=None)])

        result = harness.orchestrator.process_order_from_text("1 螺丝 规格未提供 数量10个 单价1元")

        self.assertTrue(result["success"])
        self.assertEqual(len(harness.prompts), 1)
        self.assertIsNone(result["final_result"].parsed_order.items[0].specification)

    def test_arithmetic_conflict_is_preserved_without_reextraction(self):
        harness = build_harness(payloads=[_payload(total_amount=100)])

        result = harness.orchestrator.process_order_from_text(ORDER_TEXT + "\n订单总额100元")

        self.assertTrue(result["success"])
        self.assertEqual(len(harness.prompts), 1)
        self.assertEqual(result["final_result"].parsed_order.total_amount, 100)

    def test_correction_contains_previous_output_and_records_the_retry(self):
        harness = build_harness(payloads=[_payload(name="不存在的物料"), _payload()])

        result = harness.orchestrator.process_order_from_text(ORDER_TEXT)

        self.assertIn("不存在的物料", harness.prompts[1].to_string())
        self.assertEqual(result["usage"]["attempted_calls"], 2)
        self.assertEqual(len(result["diagnostics"]["parse"]["model_calls"]), 2)
        self.assertEqual(result["diagnostics"]["parse"]["attempts"], 2)

    def test_model_timeout_is_retried_as_transient_not_as_structure_feedback(self):
        calls = []

        def timeout(_prompt):
            calls.append(1)
            raise TimeoutError("model timed out")

        harness = build_harness(llm=timeout)

        result = harness.orchestrator.process_order_from_text(ORDER_TEXT)

        self.assertFalse(result["success"])
        # 模型超时属可重试错误：有限重试，但不得注入结构修正反馈
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["usage"]["reported_calls"], 0)
        node = result["diagnostics"]["node:extractor"]
        self.assertFalse(node["success"])
        self.assertIn("TimeoutError", node["error"])

    def test_catalog_ambiguity_does_not_depend_on_retrieved_candidates(self):
        rows = [{"sku_code": sku, "material_name": "螺丝", "specification": "M8",
                 "unit": "个", "reference_price": 1.0, "aliases": []} for sku in ("A", "B")]
        from tests.support import FakeFAISSManager

        store = FakeFAISSManager(rows, search_results=[(rows[0], 0.01)])
        harness = build_harness(payloads=[_payload()], faiss_manager=store)

        result = harness.orchestrator.process_order_from_text(ORDER_TEXT)
        matched = result["final_result"].matched_order.items[0]

        self.assertIsNone(matched.sku_code)
        self.assertEqual(matched.candidate_skus, ["A", "B"])

    def test_actual_sdk_request_disables_thinking_and_captures_usage(self):
        requests = []

        def respond(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json={
                "id": "test", "object": "chat.completion", "created": 0, "model": "test",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {
                    "role": "assistant", "content": '{"items": [], "parsing_confidence": 0.5}'
                }}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            })

        config = Config()
        config.model.api_key = "test-only"
        extractor = Extractor(config=config)
        llm = extractor._get_llm()
        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            from openai import OpenAI
            llm.client = OpenAI(api_key="test-only", http_client=client).chat.completions
            llm.invoke("test")

        self.assertIs(requests[0]["enable_thinking"], False)
        self.assertNotIn("extra_body", requests[0])
        self.assertEqual(extractor.last_usage["total_tokens"], 120)
        self.assertEqual(extractor.last_usage["reported_calls"], 1)


if __name__ == "__main__":
    unittest.main()
