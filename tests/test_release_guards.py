import json
import unittest
from types import SimpleNamespace

import httpx

from application.agents import MatchingAgent, ParserAgent
from config import Config
from domain.models import OrderItem
from tests.test_core_behaviors import _build_parser_agent, _order_payload, _ungrounded_name_payload, ORDER_TEXT


class ReleaseGuardTests(unittest.TestCase):
    def test_missing_specification_is_not_retried_or_invented(self):
        parser, prompts = _build_parser_agent(_order_payload(None))
        result = parser.run({"order_text": "1 螺丝 规格未提供 数量10个 单价1元"})
        self.assertTrue(result["success"])
        self.assertEqual(len(prompts), 1)
        self.assertIsNone(result["parsed_order"].items[0].specification)

    def test_arithmetic_conflict_is_preserved_without_reextraction(self):
        payload = _order_payload("M8")
        payload["total_amount"] = 100
        parser, prompts = _build_parser_agent(payload)
        result = parser.run({"order_text": ORDER_TEXT + "\n订单总额100元"})
        self.assertTrue(result["success"])
        self.assertEqual(len(prompts), 1)
        self.assertEqual(result["parsed_order"].total_amount, 100)

    def test_correction_contains_previous_output_and_records_changed_field(self):
        parser, prompts = _build_parser_agent(_ungrounded_name_payload(), _order_payload("M8"))
        result = parser.run({"order_text": ORDER_TEXT})
        self.assertIn("不存在的物料", prompts[1].to_string())
        self.assertEqual(result["usage"]["attempted_calls"], 2)
        self.assertEqual(len(result["diagnostics"]["model_calls"]), 2)
        changes = result["diagnostics"]["self_correction"]["changes"]
        self.assertEqual(changes, [{"item_index": 0, "field": "material_name", "before": "不存在的物料", "after": "螺丝"}])

    def test_network_timeout_is_not_retried_as_structure_correction(self):
        calls = []
        def timeout(_):
            calls.append(1)
            raise TimeoutError("model timed out")
        parser = ParserAgent(llm=timeout, config=Config())
        result = parser.run({"order_text": ORDER_TEXT})
        self.assertFalse(result["success"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["usage"]["reported_calls"], 0)
        self.assertIsNone(result["diagnostics"]["model_calls"][0]["total_tokens"])
        self.assertEqual(result["diagnostics"]["model_calls"][0]["error_type"], "TimeoutError")

    def test_catalog_ambiguity_does_not_depend_on_retrieved_candidates(self):
        rows = [dict(sku_code=sku, material_name="螺丝", specification="M8") for sku in ("A", "B")]
        store = SimpleNamespace(metadata=rows, search=lambda query, k: [(rows[0], .01)])
        matched = MatchingAgent(faiss_manager=store)._match_item(
            OrderItem(material_name="螺丝", specification="M8", quantity=10)
        )
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
        parser = ParserAgent(config=config)
        llm = parser._get_llm()
        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            from openai import OpenAI
            llm.client = OpenAI(api_key="test-only", http_client=client).chat.completions
            llm.invoke("test")
        self.assertIs(requests[0]["enable_thinking"], False)
        self.assertNotIn("extra_body", requests[0])
        self.assertEqual(parser.last_usage["total_tokens"], 120)
        self.assertEqual(parser.last_usage["reported_calls"], 1)


if __name__ == "__main__":
    unittest.main()
