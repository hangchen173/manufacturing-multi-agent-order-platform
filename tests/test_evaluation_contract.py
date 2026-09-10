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


if __name__ == "__main__":
    unittest.main()
