"""Verify a local demo worker restart preserves completed order snapshots."""
import argparse
import json
import os
import signal
import time
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--http-evidence", type=Path, required=True)
    parser.add_argument("--pid-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--url", default="http://127.0.0.1:5001")
    args = parser.parse_args()
    records = json.loads(args.http_evidence.read_text())["records"]
    ids = [r["response"]["data"]["order_id"] for r in records]
    with httpx.Client(base_url=args.url, timeout=15) as client:
        before = {oid: client.get("/api/orders/" + oid).json()["data"] for oid in ids}
        os.kill(int(args.pid_file.read_text().strip()), signal.SIGHUP)
        time.sleep(3)
        ready = client.get("/api/ready")
        ready.raise_for_status()
        after = {oid: client.get("/api/orders/" + oid).json()["data"] for oid in ids}
        interrupted = client.get("/api/orders/a4de1b65-2fec-4d69-a506-9d67116bd947").json()["data"]
    evidence = {"operation": "Gunicorn SIGHUP worker replacement, same PostgreSQL database",
                "snapshots_equal": before == after, "before": before, "after": after,
                "previous_worker_crash_order": interrupted}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    assert before == after
    assert interrupted["status"] == "failed"
    print("Four snapshots unchanged after worker replacement; interrupted order is failed.")


if __name__ == "__main__":
    main()
