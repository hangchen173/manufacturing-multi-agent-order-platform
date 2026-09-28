import json
import unittest
from pathlib import Path

from application.agents.source_map import count_source_rows
from infrastructure.document_processing import DocumentLoader
from tests.support import build_harness, run_ir

FIXTURES = Path(__file__).resolve().parents[1] / "datasets/self_built/pdf_regression_v1"


def _source(name="mfg_auto_approve_0011"):
    return DocumentLoader().load_document(str(FIXTURES / "orders" / (name + ".pdf")))[0]


def _ir(name="mfg_auto_approve_0011"):
    return DocumentLoader().load_ir(str(FIXTURES / "orders" / (name + ".pdf")))[0]


class PDFDocumentIrTests(unittest.TestCase):
    def test_real_two_page_pdf_preserves_all_cells_and_header(self):
        source = _source()
        document = json.loads(source)

        self.assertEqual(len(document["pages"]), 2)
        self.assertIn("要求交期：2026-09-25", source)
        self.assertEqual(count_source_rows(document), 30)

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
                self.assertIsNone(count_source_rows({"document_type": "text", "text": source}))
        self.assertEqual(
            count_source_rows({"document_type": "text", "text": "1 螺丝 M8\n2 螺母 M8"}), 2
        )

    def test_every_regression_pdf_has_extractable_text(self):
        for path in (FIXTURES / "orders").glob("*.pdf"):
            with self.subTest(file=path.name):
                source, kind = DocumentLoader().load_document(str(path))
                self.assertEqual(kind, "pdf")
                self.assertTrue(json.loads(source)["pages"])


class PDFExtractionProtocolTests(unittest.TestCase):
    def test_missing_rows_still_retry_and_block_without_rewriting_confidence(self):
        payload = {
            "items": [{"material_name": "同步带轮", "specification": "HTD-3M-36齿-15mm",
                       "quantity": 500, "unit": "个", "unit_price": 90.9,
                       "confidence_score": 0.96}],
            "parsing_confidence": 0.96,
        }
        harness = build_harness(payloads=[payload, payload])

        result = run_ir(harness, _ir())

        self.assertEqual(len(harness.prompts), 2)
        parsed_order = result["verdict"]["parsed_order"]
        self.assertIn("原文共 30 行明细，解析出 1 行",
                      parsed_order["parsing_issues"][0]["description"])
        self.assertEqual(parsed_order["items"][0]["confidence_score"], 0.96)
        self.assertEqual(parsed_order["parsing_confidence"], 0.96)

        risk_result = result["verdict"]["risk_result"]
        self.assertTrue(risk_result["needs_confirmation"])
        self.assertTrue(any(issue["issue_type"] == "unresolved_parsing_problem"
                            for issue in risk_result["issues"]))

    def test_table_cell_material_names_are_grounded(self):
        # 表内物料名必须能在原文（含表格单元格）中定位，不得被误判为幻觉
        gold = json.loads((FIXTURES / "annotations/mfg_auto_approve_0011.json").read_text())
        payload = {
            "items": [{"material_name": row["material_name_raw"],
                       "specification": row["specification_raw"],
                       "quantity": row["quantity"], "unit": row["unit"],
                       "unit_price": row["unit_price"], "confidence_score": 0.96}
                      for row in gold["items"]],
            "parsing_confidence": 0.96,
        }
        harness = build_harness(payloads=[payload])

        result = run_ir(harness, _ir())

        self.assertEqual(result["diagnostics"]["parse"]["challenges"], [])


if __name__ == "__main__":
    unittest.main()
