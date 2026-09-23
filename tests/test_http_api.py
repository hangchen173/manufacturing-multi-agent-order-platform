import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from config import Config
from interfaces.http.flask_app import create_app


class FakeOrchestrator:
    def __init__(self):
        self.text_requests = []
        self.document_requests = []

    def process_order_from_text(self, order_text):
        self.text_requests.append(order_text)
        return {"success": True, "order_id": "order-1", "message": "订单处理完成"}

    def get_order_status(self, order_id):
        if order_id != "order-1":
            return None
        return {"order_id": order_id, "status": "completed"}

    def list_orders(self):
        return [{"order_id": "order-1", "status": "completed"}]

    def get_order_detail(self, order_id):
        if order_id != "order-1":
            return None
        return {"order_id": order_id, "status": "completed", "transition_history": []}

    def process_order_from_document(self, file_path):
        self.document_requests.append(file_path)
        return {"success": True, "order_id": "order-1", "message": "订单处理完成"}

    def confirm_order(self, order_id, confirmation):
        return {
            "success": order_id == "order-1",
            "order_id": order_id,
            "message": confirmation["action"],
        }

    def generate_review_suggestion(self, order_id):
        if order_id == "order-1":
            return {
                "success": True,
                "order_id": order_id,
                "review_suggestion": {"summary": "审核参考", "references": [], "retrieval": []},
            }
        if order_id == "completed-1":
            return {"success": False, "message": "仅待人工确认状态的订单可以生成审核参考"}
        return {"success": False, "message": "订单不存在"}


class HttpApiTests(unittest.TestCase):
    def test_sdk_timeout_is_queryable_and_does_not_retry(self):
        import httpx
        from openai import OpenAI
        from application.agents import ParserAgent
        from application.orchestrators import OrderProcessingOrchestrator
        from application.services import OrderManager
        from tests.fakes import InMemoryOrderRepository
        from tests.test_order_flow import FixedMatcher, FixedRiskControl

        config = Config()
        config.model.api_key = "test-only"
        config.data.order_auto_archive_days = 0
        parser = ParserAgent(config=config)
        calls = []

        def timeout(request):
            calls.append(request)
            raise httpx.ReadTimeout("simulated upstream timeout", request=request)

        with httpx.Client(transport=httpx.MockTransport(timeout)) as transport:
            parser._get_llm().client = OpenAI(
                api_key="test-only", http_client=transport, max_retries=0
            ).chat.completions
            manager = OrderManager(config=config, repository=InMemoryOrderRepository())
            orchestrator = OrderProcessingOrchestrator(
                config=config, order_manager=manager, parser_agent_general=parser,
                matching_agent=FixedMatcher(), risk_agent=FixedRiskControl(),
            )
            app = create_app(config=config, container=SimpleNamespace(
                orchestrator=orchestrator, readiness=lambda: {"materials": 720}
            ))
            client = app.test_client()
            response = client.post("/api/upload_text", json={"order_text": "1 螺丝 M8 10 个 1元"})
            self.assertEqual(response.status_code, 400)
            self.assertFalse(response.json["success"])
            result = response.json["data"]
            detail = client.get("/api/orders/" + result["order_id"])
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json["data"]["status"], "failed")
            self.assertEqual(len(calls), 1)
            diagnostics = result["diagnostics"]["parser_general"]
            self.assertEqual(diagnostics["model_calls"][0]["error_type"], "APITimeoutError")
            self.assertEqual(diagnostics["usage"]["reported_calls"], 0)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        config = Config()
        config.data.data_dir = self.directory.name
        self.orchestrator = FakeOrchestrator()
        self.app = create_app(
            config=config,
            container=SimpleNamespace(orchestrator=self.orchestrator, readiness=lambda: {"materials": 720}),
        )
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        self.directory.cleanup()

    def test_health_endpoint(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "healthy")

    def test_unready_service_is_live_but_rejects_new_processing(self):
        container = self.app.extensions["container"]
        with patch.object(container, "readiness", side_effect=RuntimeError("index unavailable")):
            self.assertEqual(self.client.get("/api/health").status_code, 200)
            self.assertEqual(self.client.get("/api/ready").status_code, 503)
            self.assertEqual(self.client.post("/api/upload_text", json={"order_text": "订单"}).status_code, 503)
        self.assertEqual(self.orchestrator.text_requests, [])

    def test_text_upload_delegates_to_orchestrator(self):
        response = self.client.post("/api/upload_text", json={"order_text": "测试订单"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertEqual(self.orchestrator.text_requests, ["测试订单"])

    def test_invalid_text_upload_is_rejected(self):
        response = self.client.post("/api/upload_text", json={})

        self.assertEqual(response.status_code, 400)

    def test_document_upload_is_saved_outside_sample_documents(self):
        response = self.client.post(
            "/api/upload",
            data={"file": (BytesIO("订单编号: ORD-1".encode()), "order.txt")},
        )

        self.assertEqual(response.status_code, 200)
        saved_path = Path(self.orchestrator.document_requests[0])
        self.assertEqual(saved_path.parent.name, "uploads")
        self.assertEqual(saved_path.read_text(encoding="utf-8"), "订单编号: ORD-1")

    def test_upload_rejects_an_unsupported_extension(self):
        response = self.client.post(
            "/api/upload",
            data={"file": (BytesIO(b"content"), "order.exe")},
        )

        self.assertEqual(response.status_code, 400)

    def test_orders_list_is_returned(self):
        response = self.client.get("/api/orders")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["data"][0]["order_id"], "order-1")

    def test_unknown_order_is_not_found(self):
        response = self.client.get("/api/orders/missing")

        self.assertEqual(response.status_code, 404)

    def test_review_suggestion_is_generated_for_confirmation_order(self):
        response = self.client.post("/api/orders/order-1/review-suggestion")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertEqual(
            response.json["data"]["review_suggestion"]["summary"], "审核参考"
        )

    def test_review_suggestion_for_completed_order_is_conflicted(self):
        response = self.client.post("/api/orders/completed-1/review-suggestion")

        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.json["success"])

    def test_review_suggestion_for_unknown_order_is_not_found(self):
        response = self.client.post("/api/orders/missing/review-suggestion")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
