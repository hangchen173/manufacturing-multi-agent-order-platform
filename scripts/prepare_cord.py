"""Export the official CORD v2 Parquet split into project evaluation inputs."""

from __future__ import annotations

import argparse
import csv
import json
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable

import pyarrow.parquet as pq
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "datasets/public/cord/raw/test-00000-of-00001-9c204eb3f4e11791.parquet"
DEFAULT_OUTPUT = PROJECT_ROOT / "datasets/public/cord/processed"
DEFAULT_MANIFEST = PROJECT_ROOT / "evaluation/manifests/cord_v2_test_manifest.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export CORD v2 data for project evaluation.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--limit", type=int, help="Optional number of leading test samples to export.")
    return parser.parse_args()


def parse_number(value: Any) -> float | None:
    if value is None:
        return None
    normalized = str(value).strip().replace(",", "").replace("x", "").replace("X", "")
    if not normalized:
        return None
    try:
        return float(Decimal(normalized))
    except InvalidOperation:
        return None


def flatten_menu(menu: Any) -> Iterable[dict[str, Any]]:
    if isinstance(menu, dict):
        yield menu
        sub_item = menu.get("sub")
        if isinstance(sub_item, dict):
            yield sub_item
    elif isinstance(menu, list):
        for item in menu:
            if isinstance(item, dict):
                yield item


def build_annotation(document_id: str, ground_truth: str, image_name: str) -> dict[str, Any]:
    parsed = json.loads(ground_truth)["gt_parse"]
    total = (parsed.get("total") or {}).get("total_price")
    order_level: dict[str, Any] = {}
    total_amount = parse_number(total)
    if total_amount is not None:
        order_level["total_amount"] = total_amount

    items = []
    for index, menu_item in enumerate(flatten_menu(parsed.get("menu")), start=1):
        item: dict[str, Any] = {"line_index": index}
        field_mapping = {
            "nm": "material_name_raw",
            "cnt": "quantity",
            "unitprice": "unit_price",
        }
        for cord_field, output_field in field_mapping.items():
            value = menu_item.get(cord_field)
            if value not in (None, ""):
                item[output_field] = parse_number(value) if output_field in {"quantity", "unit_price"} else value

        # CORD's `price` is frequently a line total, not a unit price. Preserve it
        # as metadata rather than comparing it to the project's unit-price field.
        if menu_item.get("price") not in (None, ""):
            item["source_line_price"] = parse_number(menu_item["price"])
        if "material_name_raw" in item:
            items.append(item)

    return {
        "document_id": document_id,
        "source_type": "public_benchmark",
        "source_dataset": "CORD v2",
        "source_split": "test",
        "document_type": "receipt",
        "file_path": image_name,
        "quality_tag": ["real_scanned_receipt"],
        "order_level": order_level,
        "items": items,
        "source_field_mapping": {
            "total.total_price": "order_level.total_amount",
            "menu.nm": "items[].material_name_raw",
            "menu.cnt": "items[].quantity",
            "menu.unitprice": "items[].unit_price",
        },
    }


def export_dataset(input_path: Path, output_dir: Path, manifest_path: Path, limit: int | None) -> int:
    if not input_path.is_file():
        raise FileNotFoundError(f"CORD Parquet input does not exist: {input_path}")

    images_dir = output_dir / "images"
    annotations_dir = output_dir / "annotations"
    images_dir.mkdir(parents=True, exist_ok=True)
    annotations_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    rows = pq.read_table(input_path).to_pylist()
    if limit is not None:
        rows = rows[:limit]

    manifest_rows = []
    for index, row in enumerate(rows):
        document_id = f"cord_v2_test_{index:03d}"
        image_name = f"{document_id}.jpg"
        annotation_name = f"{document_id}.json"
        image_path = images_dir / image_name
        annotation_path = annotations_dir / annotation_name

        with Image.open(BytesIO(row["image"]["bytes"])) as image:
            image.convert("RGB").save(image_path, format="JPEG", quality=95)
        annotation = build_annotation(document_id, row["ground_truth"], image_name)
        annotation_path.write_text(json.dumps(annotation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest_rows.append({
            "document_id": document_id,
            "source_type": "public_benchmark",
            "document_type": "receipt",
            "quality_tag": "real_scanned_receipt",
            "file_name": image_name,
            "annotation_file": annotation_name,
            "source_dataset": "CORD v2",
            "source_split": "test",
            "source_url": "https://huggingface.co/datasets/naver-clova-ix/cord-v2",
            "notes": "Official test split; only fields with an explicit CORD mapping are evaluated.",
        })

    with manifest_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=manifest_rows[0].keys())
        writer.writeheader()
        writer.writerows(manifest_rows)
    return len(rows)


def main() -> int:
    args = parse_args()
    exported = export_dataset(args.input.resolve(), args.output_dir.resolve(), args.manifest.resolve(), args.limit)
    print(f"Exported {exported} CORD v2 samples to {args.output_dir.resolve()}")
    print(f"Manifest: {args.manifest.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
