import copy
import json
import unittest
from pathlib import Path

from application.agents import ParserAgent, RiskControlAgent
from domain.models import MatchedOrder, MatchedOrderItem
from infrastructure.document_processing import DocumentLoader
from tests.test_core_behaviors import _build_parser_agent


FIXTURES = Path(__file__).resolve().parents[1] / "datasets/self_built/excel_regression_v1"


class ExcelParsingTests(unittest.TestCase):
    def setUp(self):
        self.source, _ = DocumentLoader().load_document(str(FIXTURES / "orders/mfg_auto_approve_0005.xlsx"))
        gold = json.loads((FIXTURES / "annotations/mfg_auto_approve_0005.json").read_text())
        self.payload = {"parsing_confidence": 0.98, "items": [
            {"material_name": row["material_name_raw"], "specification": row["specification_raw"],
             "quantity": row["quantity"], "unit": row["unit"], "unit_price": row["unit_price"],
             "delivery_date": "2026-09-19", "confidence_score": 0.98} for row in gold["items"]]}

    def test_original_cells_are_preserved_and_instruction_sheet_is_not_loaded(self):
        document = json.loads(self.source)
        self.assertEqual(document["sheet_name"], "采购订单")
        self.assertEqual(document["rows"][9][2:4], ["规格型号", "数量"])
        self.assertEqual(document["rows"][10][2:4], ["CJX2-1810 AC380V 31", 20])
        self.assertEqual(document["rows"][5][:2], ["要求交期", "2026-09-19"])
        self.assertNotIn("Unnamed:", self.source)
        self.assertEqual(ParserAgent._count_source_rows(self.source), 23)
        self.assertEqual(len(document["rows"]), 35)

    def test_correct_order_does_not_trigger_another_model_call(self):
        parser, calls = _build_parser_agent(self.payload)
        result = parser.run({"order_text": self.source})
        self.assertTrue(result["success"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["parsed_order"].parsing_issues, [])

    def test_shifted_spec_quantity_and_missing_delivery_are_corrected(self):
        broken = copy.deepcopy(self.payload)
        broken["items"][0].update(specification="CJX2-1810 AC380V", quantity=31, delivery_date=None)
        parser, calls = _build_parser_agent(broken, self.payload)
        result = parser.run({"order_text": self.source})
        self.assertEqual(len(calls), 2)
        feedback = calls[1].to_string()
        for field in ("specification", "quantity", "delivery_date"):
            self.assertIn(field, feedback)
        self.assertIn("Excel 第 11 行", feedback)
        self.assertEqual(result["parsed_order"].items[0].quantity, 20)
        self.assertTrue(parser.last_self_correction["resolved"])

    def test_repeated_wrong_quantity_is_blocked_even_at_high_confidence(self):
        broken = copy.deepcopy(self.payload)
        broken["items"][0]["quantity"] = 30
        parser, calls = _build_parser_agent(broken, broken)
        parsed = parser.run({"order_text": self.source})["parsed_order"]
        self.assertEqual(len(calls), 2)
        self.assertEqual(parsed.items[0].confidence_score, 0.98)
        self.assertTrue(any("quantity" in issue.description for issue in parsed.parsing_issues))
        matched = MatchedOrder(items=[MatchedOrderItem(**row.model_dump(), match_score=1, sku_code="test")
                                      for row in parsed.items], parsing_issues=parsed.parsing_issues)
        risk = RiskControlAgent().run({"matched_order": matched})["risk_result"]
        self.assertTrue(risk.needs_confirmation)
        self.assertTrue(any(issue.issue_type == "unresolved_parsing_problem" for issue in risk.issues))

    def test_missing_source_values_are_not_invented_and_source_numbers_are_not_dropped(self):
        source = json.loads(self.source)
        source["rows"][10][2] = ""
        source["rows"][10][3] = ""
        parser, _ = _build_parser_agent(self.payload)
        from domain.models import ParsedOrder
        problems = parser._detect_excel_cell_problems(ParsedOrder(**self.payload), json.dumps(source, ensure_ascii=False))
        self.assertTrue(any("quantity" in problem.description for problem in problems))
        self.assertTrue(any("specification" in problem.description for problem in problems))
        dropped = copy.deepcopy(self.payload)
        dropped["items"][0]["quantity"] = None
        problems = parser._detect_excel_cell_problems(ParsedOrder(**dropped), self.source)
        self.assertTrue(any("quantity" in problem.description for problem in problems))

    def test_unknown_headers_do_not_claim_a_definite_row_count(self):
        document = json.loads(self.source)
        document["rows"][9][0] = "备注"
        self.assertIsNone(ParserAgent._count_source_rows(json.dumps(document, ensure_ascii=False)))


if __name__ == "__main__":
    unittest.main()
