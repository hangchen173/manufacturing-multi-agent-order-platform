"""Check frozen hashes and render a contact sheet for visual fixture inspection."""
import csv
import hashlib
from pathlib import Path

import fitz
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
dataset = ROOT / "datasets/self_built/interview_v1"
tiles = []
with (dataset / "manifest.csv").open() as stream:
    for row in csv.DictReader(stream):
        for field, digest in (("document_file", "input_sha256"), ("annotation_file", "annotation_sha256")):
            assert hashlib.sha256((dataset / row[field]).read_bytes()).hexdigest() == row[digest]
        path = dataset / row["document_file"]
        if path.suffix == ".pdf":
            with fitz.open(path) as document:
                page = document[0]
                assert page.get_text().strip()
                pixmap = page.get_pixmap(matrix=fitz.Matrix(1, 1))
                tile = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
        elif path.suffix == ".png":
            tile = Image.open(path).convert("RGB")
        else:
            continue
        tile.thumbnail((650, 410))
        panel = Image.new("RGB", (670, 450), "#e5e7eb")
        panel.paste(tile, (10, 30))
        ImageDraw.Draw(panel).text((10, 8), path.stem, fill="black")
        tiles.append(panel)
sheet = Image.new("RGB", (1340, ((len(tiles) + 1) // 2) * 450), "white")
for index, tile in enumerate(tiles):
    sheet.paste(tile, ((index % 2) * 670, (index // 2) * 450))
output = ROOT / "output/interview_validation/fixture-contact.png"
output.parent.mkdir(parents=True, exist_ok=True)
sheet.save(output)
print(f"Verified all hashes; rendered {len(tiles)} PDF/image fixtures: {output}")
