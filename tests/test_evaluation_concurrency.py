import threading
import unittest
from pathlib import Path

from evaluation.run_evaluation import (
    create_evaluation_orchestrator,
    run_concurrent_evaluation,
)


class ConcurrentEvaluationIsolationTests(unittest.TestCase):
    WORKER_COUNT = 4

    def _documents(self):
        return [Path(f"doc-{index}.txt") for index in range(self.WORKER_COUNT)]

    def _run(self, process):
        return run_concurrent_evaluation(
            documents=self._documents(),
            worker_count=self.WORKER_COUNT,
            process=process,
            orchestrator_factory=create_evaluation_orchestrator,
        )

    def test_each_worker_thread_gets_its_own_orchestrator(self):
        barrier = threading.Barrier(self.WORKER_COUNT)
        observed_threads = []
        lock = threading.Lock()

        def process(document_path, orchestrator):
            with lock:
                observed_threads.append(threading.get_ident())
            barrier.wait(timeout=10)
            return {"document_id": document_path.stem, "orchestrator": orchestrator}

        outcomes = self._run(process)

        self.assertEqual(len({id(o["orchestrator"]) for o in outcomes}), self.WORKER_COUNT)
        self.assertEqual(len(set(observed_threads)), self.WORKER_COUNT)

    def test_order_context_stays_with_owning_thread(self):
        barrier = threading.Barrier(self.WORKER_COUNT)

        def process(document_path, orchestrator):
            order_id = orchestrator.order_manager.create_order(order_text=document_path.stem)
            barrier.wait(timeout=10)
            owned = list(orchestrator.order_manager.get_all_orders().keys())
            return {"document_id": document_path.stem, "order_id": order_id, "owned": owned}

        outcomes = self._run(process)

        for outcome in outcomes:
            self.assertEqual(outcome["owned"], [outcome["order_id"]])

    def test_parser_diagnostics_do_not_leak_across_threads(self):
        barrier = threading.Barrier(self.WORKER_COUNT)

        def process(document_path, orchestrator):
            agent = orchestrator.parser_agent_general
            agent.last_self_correction = {"attempts": 2, "marker": document_path.stem}
            barrier.wait(timeout=10)
            return {
                "document_id": document_path.stem,
                "marker": agent.last_self_correction["marker"],
                "parser_id": id(agent),
            }

        outcomes = self._run(process)

        for outcome in outcomes:
            self.assertEqual(outcome["marker"], outcome["document_id"])
        self.assertEqual(len({o["parser_id"] for o in outcomes}), self.WORKER_COUNT)

    def test_serial_and_concurrent_results_match(self):
        def process(document_path, orchestrator):
            return {
                "document_id": document_path.stem,
                "order_count": orchestrator.order_manager.get_order_count(),
            }

        serial = run_concurrent_evaluation(
            documents=self._documents(),
            worker_count=1,
            process=process,
            orchestrator_factory=create_evaluation_orchestrator,
        )
        concurrent = self._run(process)
        self.assertEqual(serial, concurrent)


if __name__ == "__main__":
    unittest.main()
