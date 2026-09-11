import json
import unittest
from pathlib import Path

from application.agents import ParserAgent, RiskControlAgent
from domain.models import MatchedOrder, MatchedOrderItem
from infrastructure.document_processing import DocumentLoader
from tests.test_core_behaviors import _build_parser_agent


FIXTURES = Path(__file__).resolve().parents[1] / "datasets/self_built/pdf_regression_v1"


class PDFParsingTests(unittest.TestCase):
    def source(self, name="mfg_auto_approve_0011"):
        return DocumentLoader().load_document(str(FIXTURES / "orders" / (name + ".pdf")))[0]

    def test_real_two_page_pdf_preserves_all_cells_and_header(self):
        source = self.source()
        document = json.loads(source)
        self.assertEqual(len(document["pages"]), 2)
        self.assertIn("要求交期：2026-09-25", source)
        self.assertEqual(ParserAgent._count_source_rows(source), 30)
        rows = [row for page in document["pages"] for table in page["tables"]
                if table[0][0] == "序号" for row in table[1:]]
        gold = json.loads((FIXTURES / "annotations/mfg_auto_approve_0011.json").read_text())
        self.assertEqual(len(rows), len(gold["items"]))
        for row, expected in zip(rows, gold["items"]):
            self.assertEqual(row[1:3], [expected["material_name_raw"], expected["specification_raw"]])
            self.assertEqual(float(row[3]), expected["quantity"])
            self.assertEqual(float(row[5]), expected["unit_price"])

    def test_material_grades_and_unreliable_sequences_are_not_row_counts(self):
        for source in ("316 M6×40\n316 M8×16\n316 M6×16", "1 螺丝\n3 螺母", "1\n螺丝\n20\n个"):
            with self.subTest(source=source):
                self.assertIsNone(ParserAgent._count_source_rows(source))
        self.assertEqual(ParserAgent._count_source_rows("1 螺丝 M8\n2 螺母 M8"), 2)

    def test_real_missing_rows_still_retry_and_block_without_rewriting_confidence(self):
        source = self.source()
        payload = {"items": [{"material_name": "同步带轮", "specification": "HTD-3M-36齿-15mm",
                              "quantity": 500, "unit": "个", "unit_price": 90.9,
                              "confidence_score": 0.96}], "parsing_confidence": 0.96}
        parser, prompts = _build_parser_agent(payload, payload)
        result = parser.run({"order_text": source})
        parsed = result["parsed_order"]
        self.assertEqual(len(prompts), 2)
        self.assertIn("原文共 30 行明细，解析出 1 行", parsed.parsing_issues[0].description)
        self.assertEqual(parsed.items[0].confidence_score, 0.96)
        self.assertEqual(parsed.parsing_confidence, 0.96)
        matched = MatchedOrder(items=[MatchedOrderItem(**parsed.items[0].model_dump(),
                               sku_code="TRN-001", match_score=1)], parsing_issues=parsed.parsing_issues)
        risk = RiskControlAgent().run({"matched_order": matched})["risk_result"]
        self.assertTrue(risk.needs_confirmation)
        self.assertTrue(any(issue.issue_type == "unresolved_parsing_problem" for issue in risk.issues))

    def test_every_regression_pdf_has_extractable_text(self):
        for path in (FIXTURES / "orders").glob("*.pdf"):
            with self.subTest(file=path.name):
                source, kind = DocumentLoader().load_document(str(path))
                self.assertEqual(kind, "pdf")
                self.assertTrue(json.loads(source)["pages"])


if __name__ == "__main__":
    unittest.main()
