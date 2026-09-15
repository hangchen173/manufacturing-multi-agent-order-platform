"""Run four real file uploads and preserve HTTP, storage and review evidence."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from time import perf_counter

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from application.agents.parser_agent import prompt_fingerprint


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:5001")
    parser.add_argument("--output", type=Path, default=ROOT / "output/interview_validation/http.json")
    args = parser.parse_args()
    dataset = ROOT / "datasets/self_built/interview_v1/smoke"
    cases = ["smoke_01_standard.txt", "smoke_02_equivalent_spec.xlsx", "smoke_04_ambiguous_spec.png", "smoke_09_missing_price.txt"]
    records = []
    with httpx.Client(base_url=args.url, timeout=175) as client:
        assert client.get("/api/ready").status_code == 200
        for name in cases:
            path = dataset / "orders" / name
            annotation = json.loads((dataset / "annotations" / (path.stem + ".json")).read_text())
            start = perf_counter()
            response = client.post("/api/upload", files={"file": (name, path.read_bytes())})
            try:
                payload = response.json()
            except ValueError:
                payload = {"success": False, "message": "Non-JSON HTTP response", "body": response.text[:1000]}
            result = payload.get("data") or {}
            record = {"sample": name, "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                      "http_status": response.status_code, "latency_ms": (perf_counter() - start) * 1000,
                      "response": payload, "expected_action": annotation["business_decision"]["action"]}
            if result.get("order_id"):
                detail = client.get("/api/orders/" + result["order_id"]).json()["data"]
                record["stored_before_review"] = detail
                record["action_matches"] = (result.get("business_decision") or {}).get("action") == record["expected_action"]
                if detail["status"] == "needs_confirmation":
                    action = "reject" if "ambiguous" in name else "confirm"
                    record["review_response"] = client.post("/api/confirm/" + result["order_id"], json={"action": action, "comment": "HTTP acceptance fixture"}).json()
                    record["duplicate_review_status"] = client.post("/api/confirm/" + result["order_id"], json={"action": action}).status_code
                    record["stored_after_review"] = client.get("/api/orders/" + result["order_id"]).json()["data"]
            records.append(record)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps({"prompt_fingerprint": prompt_fingerprint(), "records": records}, ensure_ascii=False, indent=2) + "\n")
            print(name, response.status_code, record.get("action_matches"), flush=True)
    assert all(record["http_status"] == 200 and record.get("action_matches") for record in records)
    for record in records:
        if "review_response" in record:
            assert record["review_response"]["success"]
            assert record["duplicate_review_status"] == 400
            assert len(record["stored_after_review"]["review_actions"]) == 1
    print(f"Saved HTTP evidence: {args.output}")


if __name__ == "__main__":
    main()
