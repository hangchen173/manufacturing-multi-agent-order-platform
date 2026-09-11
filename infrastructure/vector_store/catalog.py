import csv
from pathlib import Path

from domain.constants import FAISS_INDEX_DIMENSION


def load_material_catalog(path):
    with Path(path).open(encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    documents = []
    for row in rows:
        alias = (row.get("aliases") or "").strip()
        documents.append({
            "sku_code": row["sku_code"], "material_name": row["material_name"],
            "specification": row["specification"], "unit": row["unit"],
            "reference_price": float(row["reference_price"]), "category": row["category"],
            "aliases": [alias] if alias else [],
            "text": f"{row['material_name']} {row['specification']} {row['category']}",
        })
    if not documents or any(not row["sku_code"] for row in documents):
        raise ValueError("Material catalog must contain nonempty SKU codes")
    if len({row["sku_code"] for row in documents}) != len(documents):
        raise ValueError("Duplicate SKU in material catalog")
    return documents


def validate_catalog_index(documents, metadata, index):
    if not isinstance(metadata, list) or index is None or index.d != FAISS_INDEX_DIMENSION:
        raise ValueError("Invalid FAISS metadata or vector dimension")
    if index is None or index.ntotal != len(documents) or len(metadata) != len(documents):
        raise ValueError("Material catalog, FAISS vectors and metadata counts differ")
    expected = {row["sku_code"]: row for row in documents}
    actual = {row["sku_code"]: row for row in metadata}
    if len(actual) != len(metadata) or expected.keys() != actual.keys():
        raise ValueError("Material catalog and FAISS metadata SKU sets differ")
    for sku, row in expected.items():
        for key, value in row.items():
            if actual[sku].get(key) != value:
                raise ValueError(f"Material/index mismatch: {sku} {key}")
