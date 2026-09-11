import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier
from unittest.mock import patch

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from application.orchestrators import OrderProcessingOrchestrator
from application.services import OrderManager
from config import Config
from domain.models import FinalOrderResult, OrderStatus, ParsedOrder
from infrastructure.repositories import PostgresOrderRepository
from tests.fakes import InMemoryOrderRepository
from tests.test_order_flow import FixedMatcher, FixedParser, FixedRiskControl


class StorageContract:
    def manager(self, repository=None):
        config = Config()
        config.data.order_auto_archive_days = 0
        return OrderManager(repository=repository or self.repository, config=config)

    def prepare_review(self, manager):
        order_id = manager.create_order(order_text="review fixture")
        for status in (OrderStatus.PARSING, OrderStatus.MATCHING, OrderStatus.RISK_CHECKING):
            self.assertTrue(manager.update_order_status(order_id, status))
        result = FinalOrderResult(status=OrderStatus.NEEDS_CONFIRMATION)
        self.assertTrue(manager.finalize_order(order_id, result, {"issues": ["test risk"]}))
        return order_id

    def orchestrator(self, manager):
        return OrderProcessingOrchestrator(
            config=manager.config, order_manager=manager,
            parser_agent_general=FixedParser(), matching_agent=FixedMatcher(),
            risk_agent=FixedRiskControl(),
        )

    def test_independent_managers_do_not_lose_orders_or_updates(self):
        first, second = self.manager(), self.manager(self.second_repository)
        a = first.create_order(order_text="a")
        b = second.create_order(order_text="b")
        self.assertTrue(first.update_order_status(a, OrderStatus.PARSING))
        self.assertTrue(second.update_order_status(b, OrderStatus.PARSING))
        self.assertTrue(second.update_parsed_order(a, ParsedOrder(items=[], parsing_confidence=0.9)))
        restored = self.manager(self.second_repository)
        self.assertEqual(set(restored.get_all_orders()), {a, b})
        self.assertEqual(first.get_order(b).status, OrderStatus.PARSING)
        self.assertIsNotNone(restored.get_order(a).parsed_order)
        detached = first.get_order(a)
        detached.error_message = "must not leak into storage"
        self.assertIsNone(second.get_order(a).error_message)

    def test_stale_update_delete_and_archive_are_rejected(self):
        first, second = self.manager(), self.manager(self.second_repository)
        order_id = first.create_order(order_text="cas")
        old = self.repository.get(order_id)
        self.assertTrue(second.update_order_status(order_id, OrderStatus.PARSING))
        self.assertFalse(self.repository.update(old, old["updated_at"]))
        self.assertFalse(self.repository.delete(order_id, old["updated_at"]))
        self.assertFalse(self.repository.archive(order_id, old["updated_at"]))
        self.assertEqual(first.get_order(order_id).status, OrderStatus.PARSING)

    def test_restart_expires_only_stale_inflight_orders(self):
        manager = self.manager()
        stale = manager.create_order()
        manager.update_order_status(stale, OrderStatus.PARSING)
        snapshot = self.repository.get(stale)
        expected = snapshot["updated_at"]
        snapshot["updated_at"] = (datetime.now() - timedelta(minutes=5)).isoformat()
        self.assertTrue(self.repository.update(snapshot, expected))
        fresh = manager.create_order()
        review = self.prepare_review(manager)
        restarted = self.manager(self.second_repository)
        self.assertEqual(restarted.fail_stale_processing_orders(), 1)
        self.assertEqual(restarted.get_order(stale).status, OrderStatus.FAILED)
        self.assertIn("重新提交", restarted.get_order(stale).error_message)
        self.assertEqual(restarted.get_order(fresh).status, OrderStatus.PENDING)
        self.assertEqual(restarted.get_order(review).status, OrderStatus.NEEDS_CONFIRMATION)

    def test_concurrent_confirm_reject_has_one_winner_and_one_audit_action(self):
        first, second = self.manager(), self.manager(self.second_repository)
        order_id = self.prepare_review(first)
        barrier = Barrier(2)
        first_update, second_update = self.repository.update, self.second_repository.update

        def synchronized(update):
            def write(*args):
                barrier.wait(timeout=10)
                return update(*args)
            return write

        # Both managers read the same revision before either can persist.
        with patch.object(self.repository, "update", side_effect=synchronized(first_update)), \
             patch.object(self.second_repository, "update", side_effect=synchronized(second_update)), \
             ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(self.orchestrator(first).confirm_order, order_id, {"action": "confirm"})
            b = pool.submit(self.orchestrator(second).confirm_order, order_id, {"action": "reject"})
            outcomes = [a.result(timeout=15), b.result(timeout=15)]
        self.assertEqual(sum(outcome["success"] for outcome in outcomes), 1)
        stored = first.get_order(order_id)
        self.assertEqual(len(stored.review_actions), 1)
        self.assertEqual(len(stored.transition_history), 6)
        self.assertEqual(stored.final_result.status, stored.status)
        expected = OrderStatus.COMPLETED if stored.review_actions[0]["action"] == "confirm" else OrderStatus.FAILED
        self.assertEqual(stored.status, expected)
        self.assertFalse(first.get_order_status(order_id)["needs_confirmation"])
        self.assertFalse(first.review_order(order_id, "confirm"))
        self.assertFalse(second.review_order(order_id, "reject"))
        self.assertFalse(first.update_parsed_order(order_id, ParsedOrder(items=[], parsing_confidence=0.9)))

    def test_finalize_failure_does_not_publish_status_without_result(self):
        manager = self.manager()
        order_id = manager.create_order()
        for status in (OrderStatus.PARSING, OrderStatus.MATCHING, OrderStatus.RISK_CHECKING):
            manager.update_order_status(order_id, status)
        with patch.object(self.repository, "update", side_effect=RuntimeError("write failed")):
            with self.assertRaises(RuntimeError):
                manager.finalize_order(order_id, FinalOrderResult(status=OrderStatus.NEEDS_CONFIRMATION), {"issues": []})
        stored = manager.get_order(order_id)
        self.assertEqual(stored.status, OrderStatus.RISK_CHECKING)
        self.assertIsNone(stored.final_result)
        self.assertEqual(stored.confirmation_requests, [])

    def test_archive_moves_only_selected_order_and_preserves_latest_history(self):
        manager = self.manager()
        a = self.prepare_review(manager)
        self.assertTrue(manager.review_order(a, "reject", "review comment"))
        old = self.repository.get(a)
        b = self.manager(self.second_repository).create_order(order_text="keep")
        self.assertTrue(self.repository.archive(a, old["updated_at"]))
        self.assertEqual(set(manager.get_all_orders()), {b})
        archived = self.repository.load_all(archived=True)[a]
        self.assertEqual(archived["review_actions"][0]["comment"], "review comment")
        self.assertEqual(archived["final_result"]["status"], "failed")


class MemoryStorageTests(StorageContract, unittest.TestCase):
    def setUp(self):
        self.repository = InMemoryOrderRepository()
        # Separate adapters share one store and lock, like separate database clients.
        self.second_repository = InMemoryOrderRepository()
        self.second_repository.active = self.repository.active
        self.second_repository.archived = self.repository.archived
        self.second_repository._lock = self.repository._lock


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "TEST_DATABASE_URL is required for PostgreSQL integration")
class PostgresStorageTests(StorageContract, unittest.TestCase):
    def setUp(self):
        self.url = os.environ["TEST_DATABASE_URL"]
        self.schema = "test_orders_" + uuid.uuid4().hex
        with psycopg.connect(self.url) as connection:
            connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.schema)))
        isolated_url = make_conninfo(self.url, options=f"-c search_path={self.schema}")
        self.repository = PostgresOrderRepository(isolated_url)
        self.second_repository = PostgresOrderRepository(isolated_url)

    def tearDown(self):
        with psycopg.connect(self.url) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.schema)))


if __name__ == "__main__":
    unittest.main()
