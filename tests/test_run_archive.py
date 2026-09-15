import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from evaluation import run_evaluation as runner

from evaluation.run_evaluation import (
    AttemptWriter,
    describe_identity_mismatch,
    load_attempts,
    next_attempt_index,
    select_final_rows,
    summarize_attempts,
)


def _row(document_id, attempt, success, *, latency_ms=1.0, tokens=10):
    return {
        "document_id": document_id,
        "attempt": attempt,
        "success": success,
        "latency_ms": latency_ms,
        "usage": {
            "prompt_tokens": tokens,
            "completion_tokens": tokens,
            "total_tokens": tokens * 2,
        },
    }


class AttemptPersistenceTests(unittest.TestCase):
    def test_appended_attempts_survive_interruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "attempts.jsonl"
            writer = AttemptWriter(path)
            writer.append(_row("doc-1", 1, False))
            writer.append(_row("doc-2", 1, True))

            # 模拟中断：不调用任何收尾逻辑，已落盘记录仍可恢复。
            recovered = load_attempts(Path(tmp))
            self.assertEqual([row["document_id"] for row in recovered], ["doc-1", "doc-2"])
            self.assertFalse(recovered[0]["success"])
            self.assertTrue(recovered[1]["success"])

    def test_next_attempt_index_resumes_per_document(self):
        attempts = [_row("doc-1", 1, False), _row("doc-1", 2, True), _row("doc-2", 3, False)]
        self.assertEqual(next_attempt_index(attempts), {"doc-1": 2, "doc-2": 3})


class FinalSelectionTests(unittest.TestCase):
    def test_first_successful_attempt_wins_and_keeps_failure(self):
        documents = [Path("doc-1.txt")]
        attempts = [
            _row("doc-1", 1, False),
            _row("doc-1", 2, True),
            _row("doc-1", 3, True),
        ]
        final_rows = select_final_rows(documents, attempts)
        self.assertEqual(len(final_rows), 1)
        self.assertEqual(final_rows[0]["attempt"], 2)
        self.assertEqual(final_rows[0]["attempt_count"], 3)
        self.assertTrue(final_rows[0]["success"])

    def test_all_failed_uses_last_attempt(self):
        documents = [Path("doc-1.txt")]
        attempts = [_row("doc-1", 1, False), _row("doc-1", 2, False)]
        final_rows = select_final_rows(documents, attempts)
        self.assertEqual(final_rows[0]["attempt"], 2)
        self.assertFalse(final_rows[0]["success"])


class AttemptSummaryTests(unittest.TestCase):
    def test_partial_reported_usage_still_marks_unknown_call(self):
        attempt = _row("doc-1", 1, False)
        attempt["usage"].update(attempted_calls=2, reported_calls=1)
        summary = summarize_attempts([attempt])
        self.assertEqual(summary["usage_missing_attempts"], 1)
        self.assertEqual(summary["usage_missing_calls"], 1)
        self.assertEqual(summary["total_usage"]["total_tokens"], 20)

    def test_reports_first_retry_and_cumulative_cost_separately(self):
        attempts = [
            _row("doc-1", 1, True, latency_ms=2.0, tokens=5),
            _row("doc-2", 1, False, latency_ms=3.0, tokens=7),
            _row("doc-2", 2, True, latency_ms=4.0, tokens=11),
        ]
        summary = summarize_attempts(attempts)
        self.assertEqual(summary["total_documents"], 2)
        self.assertEqual(summary["total_attempts"], 3)
        self.assertEqual(summary["first_attempt_success_count"], 1)
        self.assertEqual(summary["final_success_count"], 2)
        self.assertEqual(summary["retried_documents"], 1)
        self.assertEqual(summary["retry_success_count"], 1)
        self.assertEqual(summary["retry_success_rate"], 1.0)
        self.assertEqual(summary["total_latency_ms"], 9.0)
        self.assertEqual(summary["total_usage"]["total_tokens"], (5 + 7 + 11) * 2)


class IdentityMismatchTests(unittest.TestCase):
    def test_identical_identity_is_resumable(self):
        identity = {"prompt_fingerprint": "a", "model_config": {"model": "qwen"}}
        self.assertIsNone(describe_identity_mismatch(identity, dict(identity)))

    def test_model_or_prompt_change_blocks_resume(self):
        prior = {"prompt_fingerprint": "a", "model_config": {"model": "qwen"}}
        current = {"prompt_fingerprint": "b", "model_config": {"model": "qwen"}}
        self.assertIn("prompt_fingerprint", describe_identity_mismatch(prior, current))

        prior_model = {"prompt_fingerprint": "a", "model_config": {"model": "qwen"}}
        current_model = {"prompt_fingerprint": "a", "model_config": {"model": "gpt"}}
        self.assertIn("model_config", describe_identity_mismatch(prior_model, current_model))

    def test_missing_prior_identity_blocks_resume(self):
        self.assertIsNotNone(describe_identity_mismatch(None, {"prompt_fingerprint": "a"}))


class RunRecoveryTests(unittest.TestCase):
    def test_interrupted_first_run_resumes_without_repeating_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = root / "inputs"
            inputs.mkdir()
            for name in ("a.pdf", "b.pdf"):
                (inputs / name).touch()
            args = SimpleNamespace(
                input_dir=str(inputs), annotation_dir=None, manifest_csv=None,
                dataset_name="recovery", output_dir=str(root / "out"),
                no_recursive=False, limit=None, concurrency=1, resume_run=None,
            )
            seen = []

            def evaluate(**kwargs):
                document = kwargs["document_path"]
                seen.append(document.stem)
                if len(seen) == 2:
                    raise KeyboardInterrupt()
                return dict(document_id=document.stem, success=True, latency_ms=1,
                            prediction={"success": True}, needs_confirmation=False)

            with patch.object(runner, "parse_args", return_value=args), \
                 patch.object(runner, "validate_material_index"), \
                 patch.object(runner, "build_run_identity", return_value={"code": "fixed"}), \
                 patch.object(runner, "create_evaluation_orchestrator"), \
                 patch.object(runner, "evaluate_document", side_effect=evaluate):
                with self.assertRaises(KeyboardInterrupt):
                    runner.run()
                run_dir = next((root / "out").iterdir())
                self.assertTrue((run_dir / runner.MANIFEST_FILE).is_file())
                args.resume_run = str(run_dir)
                self.assertEqual(runner.run(), 0)
            self.assertEqual(seen, ["a", "b", "b"])
            self.assertEqual(len(runner.load_attempts(run_dir)), 2)

    def test_content_hash_changes_without_file_status_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.py"
            path.write_text("value = 1\n")
            before = runner.fingerprint_files([path])
            path.write_text("value = 2\n")
            self.assertNotEqual(before, runner.fingerprint_files([path]))


if __name__ == "__main__":
    unittest.main()
