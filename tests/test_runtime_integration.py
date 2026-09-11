import os
import tempfile
import unittest
from unittest.mock import patch

from application.container import ApplicationContainer
from config import Config
from interfaces.http.flask_app import create_app


@unittest.skipUnless(os.getenv("RUN_EMBEDDING_INTEGRATION") == "1" and os.getenv("TEST_DATABASE_URL"),
                     "Requires cached embedding model and an isolated test database")
class RuntimeIntegrationTests(unittest.TestCase):
    def test_clean_directory_builds_index_and_readiness_checks_real_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Config()
            config.database.url = os.environ["TEST_DATABASE_URL"]
            config.data.data_dir = directory
            config.data.faiss_index_path = directory + "/index"
            config.data.order_auto_archive_days = 0
            config.model.api_key = "test-only-no-model-call"
            container = ApplicationContainer(config=config)
            container.initialize()
            app = create_app(config=config, container=container)
            client = app.test_client()
            response = client.get("/api/ready")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["data"]["materials"], 720)
            store = container.orchestrator.matching_agent.faiss_manager
            self.assertEqual(store.index.ntotal, len(store.metadata))
            self.assertTrue(os.path.isfile(directory + "/index/index.faiss"))
            repository = container.orchestrator.order_manager.repository
            with patch.object(repository, "_connect", side_effect=ConnectionError("database unavailable")):
                self.assertEqual(client.get("/api/ready").status_code, 503)
            self.assertEqual(client.get("/api/ready").status_code, 200)
            store.index.reset()
            self.assertEqual(client.get("/api/ready").status_code, 503)
            self.assertEqual(client.get("/api/health").status_code, 200)


if __name__ == "__main__":
    unittest.main()
