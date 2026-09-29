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

    def get_trace(self, order_id):
        return {
            "order_id": order_id,
            "messages": [
                {
                    "message_id": "m-1",
                    "sender": "supervisor",
                    "recipient": None,
                    "performative": "escalate",
                    "subject": {"claim_subject": "order.action"},
                    "payload": {"action": "manual_review"},
                }
            ],
            "claims": [],
            "disputes": [],
            "verdicts": [{"verdict": "manual_review"}],
        }

    def get_tasks(self, order_id):
        return [
            {"task_id": "t-1", "agent": "extractor", "stage": "extract", "status": "done"},
            {"task_id": "t-2", "agent": "review_assistant", "stage": "assist", "status": "done"},
        ]

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
    def test_sdk_timeout_is_retried_then_queryable_without_usage(self):
        import httpx
        from openai import OpenAI

        from application.agents import Extractor
        from tests.support import build_harness

        config = Config()
        config.model.api_key = "test-only"
        config.data.order_auto_archive_days = 0
        config.data.data_dir = self.directory.name

        calls = []

        def timeout(request):
            calls.append(request)
            raise httpx.ReadTimeout("simulated upstream timeout", request=request)

        extractor = Extractor(config=config)
        llm = extractor._get_llm()
        with httpx.Client(transport=httpx.MockTransport(timeout)) as transport:
            llm.client = OpenAI(
                api_key="test-only", http_client=transport, max_retries=0
            ).chat.completions
            harness = build_harness(llm=llm, config=config)
            app = create_app(config=config, container=SimpleNamespace(
                orchestrator=harness.orchestrator, readiness=lambda: {"materials": 720}
            ))
            client = app.test_client()
            response = client.post("/api/upload_text", json={"order_text": "1 螺丝 M8 10 个 1元"})

            self.assertEqual(response.status_code, 400)
            self.assertFalse(response.json["success"])
            result = response.json["data"]

            detail = client.get("/api/orders/" + result["order_id"])
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json["data"]["status"], "failed")

        # SDK 超时属可重试的瞬态错误：有限重试，且不注入结构修正反馈
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["usage"]["reported_calls"], 0)
        node = result["diagnostics"]["node:extractor"]
        self.assertFalse(node["success"])
        self.assertIn("APITimeoutError", node["error"])

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

    # ------------------------------------------------------ /trace 与 /tasks
    def test_order_trace_exposes_collaboration_messages(self):
        response = self.client.get("/api/orders/order-1/trace")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        data = response.json["data"]
        self.assertEqual(data["order_id"], "order-1")
        self.assertEqual(data["messages"][0]["performative"], "escalate")
        self.assertEqual(data["verdicts"], [{"verdict": "manual_review"}])

    def test_unknown_order_trace_is_not_found(self):
        response = self.client.get("/api/orders/missing/trace")

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json["success"])

    def test_order_tasks_expose_dag_state(self):
        response = self.client.get("/api/orders/order-1/tasks")

        self.assertEqual(response.status_code, 200)
        stages = [(task["agent"], task["stage"], task["status"]) for task in response.json["data"]]
        self.assertEqual(
            stages,
            [("extractor", "extract", "done"), ("review_assistant", "assist", "done")],
        )

    def test_unknown_order_tasks_are_not_found(self):
        response = self.client.get("/api/orders/missing/tasks")

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json["success"])

    # ------------------------------------------------------------- /confirm
    def test_confirm_delegates_action_to_orchestrator(self):
        response = self.client.post("/api/confirm/order-1", json={"action": "confirm"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertEqual(response.json["data"]["order_id"], "order-1")
        self.assertEqual(response.json["data"]["message"], "confirm")

    def test_confirm_rejects_an_unknown_action(self):
        response = self.client.post("/api/confirm/order-1", json={"action": "maybe"})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json["success"])
        self.assertIn("confirm or reject", response.json["message"])

    def test_confirm_rejects_a_missing_action(self):
        response = self.client.post("/api/confirm/order-1", json={})

        self.assertEqual(response.status_code, 400)

    def test_confirm_rejects_a_non_string_comment(self):
        response = self.client.post(
            "/api/confirm/order-1", json={"action": "confirm", "comment": 5}
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("comment must be a string", response.json["message"])

    def test_confirm_failure_from_orchestrator_is_bad_request(self):
        response = self.client.post("/api/confirm/other-order", json={"action": "reject"})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json["success"])


if __name__ == "__main__":
    unittest.main()
