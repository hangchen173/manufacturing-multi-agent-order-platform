"""Re-submit the two reported PDFs through the real service, preserving evidence."""
import argparse
import json
from pathlib import Path
from time import perf_counter

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    records = []
    with httpx.Client(base_url="http://127.0.0.1:5001", timeout=175, trust_env=False) as client:
        client.get("/api/ready").raise_for_status()
        for name, action, count, date in (
            ("mfg_auto_approve_0011", "auto_approve", 30, "2026-09-25"),
            ("mfg_manual_review_0301", "manual_review", 20, "2026-10-05"),
        ):
            path = root / "datasets/self_built/pdf_regression_v1/orders" / (name + ".pdf")
            start = perf_counter()
            response = client.post("/api/upload", files={"file": (path.name, path.read_bytes())})
            response.raise_for_status()
            data = response.json()["data"]
            detail = client.get("/api/orders/" + data["order_id"]).json()["data"]
            records.append({"sample": name, "http_status": response.status_code,
                            "latency_ms": (perf_counter() - start) * 1000, "order": detail})
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n")
            result = detail["final_result"]
            assert result["business_decision"]["action"] == action
            assert len(result["parsed_order"]["items"]) == count
            assert all(item["delivery_date"] == date for item in result["parsed_order"]["items"])
            diagnostics = detail["processing_diagnostics"]["parser_general"]
            assert diagnostics["usage"]["attempted_calls"] == 1
            assert diagnostics["self_correction"] is None
            assert not any("明细数量不一致" in issue["description"] for issue in result["risk_result"]["issues"])
            if action == "auto_approve":
                gold = json.loads((root / "datasets/self_built/pdf_regression_v1/annotations" / (name + ".json")).read_text())
                for actual, expected in zip(result["matched_order"]["items"], gold["items"]):
                    for source, target in (("material_name_raw", "material_name"), ("specification_raw", "specification"),
                                           ("quantity", "quantity"), ("unit_price", "unit_price"), ("golden_sku_code", "sku_code")):
                        assert actual[target] == expected[source], (name, source, actual[target], expected[source])
            print(name, data["order_id"], action, "passed", flush=True)


if __name__ == "__main__":
    main()
