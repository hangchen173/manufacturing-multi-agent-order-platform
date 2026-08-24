import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

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


class HttpApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        config = Config()
        config.data.data_dir = self.directory.name
        self.orchestrator = FakeOrchestrator()
        self.app = create_app(
            config=config,
            container=SimpleNamespace(orchestrator=self.orchestrator),
        )
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        self.directory.cleanup()

    def test_health_endpoint(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "healthy")

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


if __name__ == "__main__":
    unittest.main()
