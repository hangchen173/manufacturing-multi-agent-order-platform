"""Verify the reported Excel column shift and a real risk case via HTTP."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from time import perf_counter

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from application.agents import ParserAgent
from domain.models import ParsedOrder
from evaluation.run_evaluation import fingerprint_files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = []
    evidence = {
        "code_version": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_fingerprint": fingerprint_files([ROOT / "config.py", ROOT / "requirements.txt"] + [
            path for directory in ("application", "domain", "infrastructure", "interfaces", "evaluation")
            for path in (ROOT / directory).rglob("*.py")]),
        "scope": "Two original Excel files, real HTTP and PostgreSQL; not an independent benchmark",
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(base_url="http://127.0.0.1:5001", timeout=175, trust_env=False) as client:
        client.get("/api/ready").raise_for_status()
        for name, expected_action, count, date in (
            ("mfg_auto_approve_0005", "auto_approve", 23, "2026-09-19"),
            ("mfg_manual_review_0394", "manual_review", 25, "2026-10-08"),
        ):
            path = ROOT / "datasets/self_built/excel_regression_v1/orders" / (name + ".xlsx")
            gold_path = ROOT / "datasets/self_built/excel_regression_v1/annotations" / (name + ".json")
            start = perf_counter()
            response = client.post("/api/upload", files={"file": (path.name, path.read_bytes())})
            record = {"sample": name, "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                      "annotation_sha256": hashlib.sha256(gold_path.read_bytes()).hexdigest(),
                      "http_status": response.status_code, "response": response.json(),
                      "latency_ms": (perf_counter() - start) * 1000}
            records.append(record)
            args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
            response.raise_for_status()
            result = response.json()["data"]
            detail = client.get("/api/orders/" + result["order_id"]).json()["data"]
            record["order"] = detail
            args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
            parsed = ParsedOrder(**detail["parsed_order"])
            assert detail["document_type"] == "excel"
            assert len(parsed.items) == count
            assert not ParserAgent()._detect_excel_cell_problems(parsed, detail["order_text"])
            assert not parsed.parsing_issues
            assert all(row.delivery_date == date for row in parsed.items)
            assert result["business_decision"]["action"] == expected_action
            if expected_action == "auto_approve":
                gold = json.loads(gold_path.read_text())
                for row, expected in zip(detail["matched_order"]["items"], gold["items"]):
                    assert row["sku_code"] == expected["golden_sku_code"]
                assert parsed.items[0].specification == "CJX2-1810 AC380V 31"
                assert parsed.items[0].quantity == 20
                assert parsed.total_amount == 177607.8
                assert detail["risk_result"]["issues"] == []
            else:
                assert any(issue["issue_type"] == "line_total_mismatch" for issue in detail["risk_result"]["issues"])
            record["checks_passed"] = True
            args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
            print(name, result["order_id"], expected_action, "passed", flush=True)


if __name__ == "__main__":
    main()
