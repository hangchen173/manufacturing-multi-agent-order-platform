import copy
import json
import unittest
from pathlib import Path

from application.agents.source_map import count_source_rows
from infrastructure.document_processing import DocumentLoader
from tests.support import build_harness, run_ir

FIXTURES = Path(__file__).resolve().parents[1] / "datasets/self_built/excel_regression_v1"
SOURCE = FIXTURES / "orders/mfg_auto_approve_0005.xlsx"
GOLD = json.loads((FIXTURES / "annotations/mfg_auto_approve_0005.json").read_text())


def _ir():
    document, _ = DocumentLoader().load_ir(str(SOURCE))
    return document


def _payload(delivery_date="2026-09-19", confidence=0.98):
    return {
        "parsing_confidence": confidence,
        "items": [
            {"material_name": row["material_name_raw"], "specification": row["specification_raw"],
             "quantity": row["quantity"], "unit": row["unit"], "unit_price": row["unit_price"],
             "delivery_date": delivery_date, "confidence_score": confidence}
            for row in GOLD["items"]
        ],
    }


class ExcelDocumentIrTests(unittest.TestCase):
    def test_multi_sheet_ir_preserves_cells_and_flags_hidden_sheet(self):
        document = _ir()

        self.assertEqual([sheet["name"] for sheet in document["sheets"]], ["采购订单", "说明-勿导入"])
        self.assertFalse(document["sheets"][0]["hidden"])
        self.assertTrue(document["sheets"][1]["hidden"])
        rows = document["sheets"][0]["rows"]
        self.assertEqual(rows[9][2:4], ["规格型号", "数量"])
        self.assertEqual(rows[10][2:4], ["CJX2-1810 AC380V 31", 20])
        self.assertEqual(rows[5][:2], ["要求交期", "2026-09-19"])
        self.assertNotIn("Unnamed:", json.dumps(document, ensure_ascii=False))
        self.assertEqual(len(rows), 35)

    def test_row_count_uses_the_unique_sequence_column(self):
        self.assertEqual(count_source_rows(_ir()), 23)

    def test_unknown_headers_do_not_claim_a_definite_row_count(self):
        document = _ir()
        document["sheets"][0]["rows"][9][0] = "备注"

        self.assertIsNone(count_source_rows(document))


class ExcelExtractionProtocolTests(unittest.TestCase):
    def test_correct_order_does_not_trigger_another_model_call(self):
        harness = build_harness(payloads=[_payload()])

        result = run_ir(harness, _ir())

        self.assertTrue(result["success"])
        self.assertEqual(len(harness.prompts), 1)
        self.assertEqual(result["diagnostics"]["parse"]["challenges"], [])
        self.assertEqual(result["verdict"]["parsed_order"]["parsing_issues"], [])

    def test_shifted_spec_and_quantity_are_challenged_and_corrected(self):
        broken = copy.deepcopy(_payload())
        broken["items"][0].update(specification="CJX2-1810 AC380V", quantity=31)
        harness = build_harness(payloads=[broken, _payload()])

        result = run_ir(harness, _ir())

        self.assertEqual(len(harness.prompts), 2)
        feedback = harness.prompts[1].to_string()
        for field in ("specification", "quantity"):
            self.assertIn(field, feedback)
        self.assertIn("第 11 行", feedback)
        self.assertEqual(result["verdict"]["parsed_order"]["items"][0]["quantity"], 20)
        self.assertTrue(result["diagnostics"]["parse"]["self_correction"]["resolved"])

    def test_repeated_wrong_quantity_is_blocked_even_at_high_confidence(self):
        broken = copy.deepcopy(_payload())
        broken["items"][0]["quantity"] = 30
        harness = build_harness(payloads=[broken, broken])

        result = run_ir(harness, _ir())

        self.assertEqual(len(harness.prompts), 2)
        parsed_order = result["verdict"]["parsed_order"]
        self.assertEqual(parsed_order["items"][0]["confidence_score"], 0.98)
        self.assertTrue(any("quantity" in issue["description"]
                            for issue in parsed_order["parsing_issues"]))

        issue_types = [issue["issue_type"] for issue in result["verdict"]["risk_result"]["issues"]]
        self.assertTrue(result["verdict"]["risk_result"]["needs_confirmation"])
        self.assertIn("unresolved_parsing_problem", issue_types)

    def test_missing_source_values_are_not_invented(self):
        document = _ir()
        document["sheets"][0]["rows"][10][2] = ""
        document["sheets"][0]["rows"][10][3] = ""
        harness = build_harness(payloads=[_payload(), _payload()])

        result = run_ir(harness, document)

        challenges = result["diagnostics"]["parse"]["challenges"]
        self.assertTrue(any(challenge["field"] == "quantity" for challenge in challenges))
        self.assertTrue(any(challenge["field"] == "specification" for challenge in challenges))

    def test_source_numbers_are_not_dropped_by_the_claim(self):
        payload = copy.deepcopy(_payload())
        payload["items"][0]["quantity"] = None
        harness = build_harness(payloads=[payload, payload])

        result = run_ir(harness, _ir())

        challenges = result["diagnostics"]["parse"]["challenges"]
        self.assertTrue(any(challenge["field"] == "quantity" for challenge in challenges))


if __name__ == "__main__":
    unittest.main()
