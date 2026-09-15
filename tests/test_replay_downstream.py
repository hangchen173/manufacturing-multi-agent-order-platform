import unittest

from domain.models import ParsedOrder
from evaluation.replay_downstream import (
    analyze_high_score_wrong_skus,
    classify_items,
    coverage_summary,
    reconstruct_parsed_order,
)


def _predicted(sku_code=None, match_score=0.0, **extra):
    item = {"sku_code": sku_code, "match_score": match_score}
    item.update(extra)
    return item


class ClassifyItemsTests(unittest.TestCase):
    def test_golden_splits_into_correct_match_wrong_accept_and_reject(self):
        expected = [
            {"golden_sku_code": "ELC-001"},
            {"golden_sku_code": "ELC-001"},
            {"golden_sku_code": "CBL-003"},
        ]
        predicted = [
            _predicted("ELC-001", 0.95),  # correct_match
            _predicted("ELC-025", 0.9),   # wrong_accept
            _predicted(None, 0.3, rejection_reason="规格冲突"),  # rejected
        ]

        counts, records = classify_items(expected, predicted)

        self.assertEqual(counts["golden_items"], 3)
        self.assertEqual(counts["correct_match"], 1)
        self.assertEqual(counts["wrong_accept"], 1)
        self.assertEqual(counts["rejected"], 1)
        self.assertEqual(records[2]["category"], "rejected")
        self.assertEqual(records[2]["rejection_reason"], "规格冲突")

    def test_missing_golden_splits_into_correct_reject_and_wrong_accept(self):
        expected = [{"golden_sku_code": None}, {"golden_sku_code": ""}]
        predicted = [_predicted(None), _predicted("CBL-043", 0.7)]

        counts, records = classify_items(expected, predicted)

        self.assertEqual(counts["no_golden_items"], 2)
        self.assertEqual(counts["correct_reject"], 1)
        self.assertEqual(counts["wrong_accept_no_golden"], 1)
        self.assertEqual(records[1]["category"], "wrong_accept_no_golden")

    def test_predicted_longer_than_expected_is_kept(self):
        expected = [{"golden_sku_code": "ELC-001"}]
        predicted = [_predicted("ELC-001", 0.9), _predicted(None)]

        counts, records = classify_items(expected, predicted)

        self.assertEqual(len(records), 2)
        # 多出的行没有金标，且未接受 SKU，归为正确拒识
        self.assertEqual(counts["correct_reject"], 1)
        self.assertEqual(records[1]["line_index"], 2)


class CoverageSummaryTests(unittest.TestCase):
    def test_coverage_precision_and_accuracy(self):
        counts = {
            "golden_items": 10,
            "no_golden_items": 2,
            "correct_match": 8,
            "wrong_accept": 1,
            "rejected": 1,
            "correct_reject": 2,
            "wrong_accept_no_golden": 0,
        }

        summary = coverage_summary(counts)

        self.assertAlmostEqual(summary["accepted_sku_coverage"], 0.9)
        self.assertAlmostEqual(summary["accepted_sku_precision"], 8 / 9)
        self.assertAlmostEqual(summary["sku_accuracy"], 0.8)

    def test_empty_golden_is_safe(self):
        counts = {
            "golden_items": 0,
            "no_golden_items": 0,
            "correct_match": 0,
            "wrong_accept": 0,
            "rejected": 0,
            "correct_reject": 0,
            "wrong_accept_no_golden": 0,
        }

        summary = coverage_summary(counts)

        self.assertEqual(summary["accepted_sku_coverage"], 0.0)
        self.assertEqual(summary["accepted_sku_precision"], 0.0)
        self.assertEqual(summary["sku_accuracy"], 0.0)


class HighScoreWrongSkuTests(unittest.TestCase):
    def _archived(self, sku_code, score):
        return {"matched_order": {"items": [{"sku_code": sku_code, "match_score": score}]}}

    def _replayed(self, sku_code):
        return {"matched_order": {"items": [{"sku_code": sku_code, "match_score": 0.9}]}}

    def test_high_score_wrong_sku_fixed(self):
        findings = analyze_high_score_wrong_skus(
            self._archived("ELC-025", 0.92),
            self._replayed("ELC-001"),
            {"items": [{"golden_sku_code": "ELC-001"}]},
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["outcome"], "fixed")
        self.assertEqual(findings[0]["old_sku"], "ELC-025")

    def test_high_score_wrong_sku_now_rejected(self):
        findings = analyze_high_score_wrong_skus(
            self._archived("ELC-025", 0.92),
            self._replayed(None),
            {"items": [{"golden_sku_code": "ELC-001"}]},
        )

        self.assertEqual(findings[0]["outcome"], "rejected")

    def test_high_score_wrong_sku_still_wrong(self):
        findings = analyze_high_score_wrong_skus(
            self._archived("ELC-025", 0.92),
            self._replayed("CBL-043"),
            {"items": [{"golden_sku_code": "ELC-001"}]},
        )

        self.assertEqual(findings[0]["outcome"], "still_wrong")

    def test_low_score_or_already_correct_is_skipped(self):
        annotation = {"items": [{"golden_sku_code": "ELC-001"}]}
        low_score = analyze_high_score_wrong_skus(
            self._archived("ELC-025", 0.5), self._replayed(None), annotation
        )
        already_correct = analyze_high_score_wrong_skus(
            self._archived("ELC-001", 0.99), self._replayed("ELC-001"), annotation
        )

        self.assertEqual(low_score, [])
        self.assertEqual(already_correct, [])


class ReconstructParsedOrderTests(unittest.TestCase):
    def test_rebuilds_from_archived_prediction(self):
        row = {
            "prediction": {
                "final_result": {
                    "parsed_order": {
                        "items": [{"material_name": "交流接触器"}],
                        "parsing_confidence": 0.9,
                    }
                }
            }
        }

        parsed = reconstruct_parsed_order(row)

        self.assertIsInstance(parsed, ParsedOrder)
        self.assertEqual(parsed.items[0].material_name, "交流接触器")

    def test_returns_none_without_parsed_order(self):
        self.assertIsNone(reconstruct_parsed_order({"prediction": {}}))
        self.assertIsNone(reconstruct_parsed_order({}))


if __name__ == "__main__":
    unittest.main()
