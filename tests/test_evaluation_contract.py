import unittest

from evaluation.contracts import normalize_annotation
from evaluation.metrics import EvaluationAccumulator


class EvaluationContractTests(unittest.TestCase):
    def test_business_decision_action_is_required(self):
        annotation = normalize_annotation({
            "document_id": "order-1",
            "order_level": {},
            "items": [],
            "business_decision": {"action": "manual_review"},
        })
        self.assertEqual(annotation["business_decision"]["action"], "manual_review")

    def test_obsolete_confirmation_contract_fails(self):
        with self.assertRaises(ValueError):
            normalize_annotation({
                "document_id": "order-1",
                "order_level": {},
                "items": [],
                "confirmation": {"needs_manual_confirmation": True},
            })

    def test_missing_required_annotation_fails_loudly(self):
        with self.assertRaises(ValueError):
            normalize_annotation({"document_id": "order-1", "items": []})

    def test_missing_prediction_line_counts_as_sku_error(self):
        accumulator = EvaluationAccumulator()
        accumulator.record_sample(
            success=True, latency_ms=1, needs_confirmation=False,
            parsed_item_count=0, matched_item_count=0, risk_issue_count=0,
            annotation={"document_id": "x", "order_level": {}, "items": [{"golden_sku_code": "SKU-1"}]},
            prediction={"final_result": {"parsed_order": {"items": []}, "matched_order": {"items": []}}},
        )
        self.assertEqual(accumulator.to_dict()["sku_top1_accuracy"]["total"], 1)

    def test_public_benchmark_annotation_without_decision_is_accepted(self):
        annotation = normalize_annotation({
            "document_id": "cord-1",
            "order_level": {"total_amount": 60.0},
            "items": [{"material_name_raw": "TICKET", "quantity": 2}],
        })
        accumulator = EvaluationAccumulator()
        accumulator.record_sample(
            success=True, latency_ms=1, needs_confirmation=True,
            parsed_item_count=1, matched_item_count=1, risk_issue_count=0,
            annotation=annotation,
            prediction={"final_result": {"parsed_order": {"items": []}, "matched_order": {"items": []}}},
        )
        summary = accumulator.to_dict()
        self.assertEqual(summary["business_decision_accuracy"]["total"], 0)
        self.assertEqual(summary["sku_top1_accuracy"]["total"], 0)


def _annotation(items, *, action=None):
    payload = {"document_id": "doc", "order_level": {}, "items": items}
    if action is not None:
        payload["business_decision"] = {"action": action}
    return payload


def _prediction(items, *, action=None, needs_confirmation=False):
    payload = {
        "final_result": {
            "parsed_order": {"items": items},
            "matched_order": {"items": items},
        },
        "needs_confirmation": needs_confirmation,
    }
    if action is not None:
        payload["business_decision"] = {"action": action}
    return payload


class ContentErrorMetricTests(unittest.TestCase):
    def _record(self, annotation, prediction, success=True):
        accumulator = EvaluationAccumulator()
        accumulator.record_sample(
            success=success,
            latency_ms=1,
            needs_confirmation=bool(prediction.get("needs_confirmation")) if prediction else False,
            parsed_item_count=0,
            matched_item_count=0,
            risk_issue_count=0,
            annotation=annotation,
            prediction=prediction,
        )
        return accumulator.to_dict()

    def test_technical_failure_counts_against_all_sample_content_metric(self):
        summary = self._record(
            _annotation([{"material_name_raw": "螺丝", "quantity": 1}], action="auto_approve"),
            None,
            success=False,
        )
        self.assertEqual(summary["content_exact_match"]["total"], 1)
        self.assertEqual(summary["content_exact_match"]["matched"], 0)
        # 技术失败不算自动放行。
        self.assertEqual(summary["auto_release_content_error"]["auto_release_total"], 0)

    def test_extra_row_counts_as_content_error(self):
        summary = self._record(
            _annotation([{"material_name_raw": "螺丝", "quantity": 1}], action="auto_approve"),
            _prediction(
                [
                    {"material_name": "螺丝", "quantity": 1, "sku_code": "SKU-1"},
                    {"material_name": "螺母", "quantity": 5, "sku_code": "SKU-2"},
                ],
                action="auto_approve",
            ),
        )
        self.assertEqual(summary["item_count_exact_match"]["matched"], 0)
        self.assertEqual(summary["content_exact_match"]["matched"], 0)
        self.assertEqual(summary["auto_release_content_error"]["error_count"], 1)

    def test_missing_row_counts_as_content_error(self):
        summary = self._record(
            _annotation(
                [
                    {"material_name_raw": "螺丝", "quantity": 1},
                    {"material_name_raw": "螺母", "quantity": 2},
                ],
                action="auto_correct",
            ),
            _prediction([{"material_name": "螺丝", "quantity": 1, "sku_code": "SKU-1"}], action="auto_correct"),
        )
        self.assertEqual(summary["item_count_exact_match"]["matched"], 0)
        self.assertEqual(summary["content_exact_match"]["matched"], 0)

    def test_correct_action_wrong_sku_is_released_content_error(self):
        summary = self._record(
            _annotation(
                [{"material_name_raw": "螺丝", "quantity": 1, "golden_sku_code": "SKU-1"}],
                action="auto_approve",
            ),
            _prediction(
                [{"material_name": "螺丝", "quantity": 1, "sku_code": "SKU-2"}],
                action="auto_approve",
            ),
        )
        # 动作正确但 SKU 选错，仍须计入已放行内容错误。
        self.assertEqual(summary["business_decision_accuracy"]["matched"], 1)
        self.assertEqual(summary["sku_top1_accuracy"]["matched"], 0)
        self.assertEqual(summary["auto_release_content_error"]["error_count"], 1)

    def test_contactor_error_auto_release_is_detected(self):
        summary = self._record(
            _annotation(
                [{"material_name_raw": "接触器", "quantity": 1, "golden_sku_code": "SKU-9"}],
                action="manual_review",
            ),
            _prediction(
                [{"material_name": "接触器", "quantity": 1, "sku_code": "SKU-1"}],
                action="auto_approve",
            ),
        )
        self.assertEqual(summary["error_auto_release"]["error_count"], 1)
        self.assertEqual(summary["auto_release_content_error"]["error_count"], 1)
        self.assertEqual(summary["manual_review_recall"]["matched"], 0)

    def test_manual_review_recall_counts_correct_escalation(self):
        summary = self._record(
            _annotation([{"material_name_raw": "接触器", "quantity": 1}], action="manual_review"),
            _prediction([{"material_name": "接触器", "quantity": 1}], needs_confirmation=True),
        )
        self.assertEqual(summary["manual_review_recall"]["matched"], 1)
        self.assertEqual(summary["auto_handle_coverage"]["matched"], 0)


if __name__ == "__main__":
    unittest.main()
