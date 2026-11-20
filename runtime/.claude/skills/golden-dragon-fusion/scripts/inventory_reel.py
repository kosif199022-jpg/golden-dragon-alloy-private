"""Reconcile exported stock counts and render the verified totals as a portrait video."""
import argparse
import csv
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import tempfile
from PIL import Image, ImageDraw, ImageFont
from render_vertical import render

ALIASES = {"item": ("item", "الصنف"), "expected": ("expected", "الرصيد الدفتري"), "counted": ("counted", "الكمية الفعلية")}


def reconcile(source):
    totals = {"matched": 0, "short": 0, "over": 0}
    items = set()
    with source.open(encoding="utf-8-sig", newline="") as stream:
        table = csv.DictReader(stream)
        header = table.fieldnames or []
        columns = {}
        for key, aliases in ALIASES.items():
            choices = [name for name in header if name.strip().lower() in aliases]
            if len(choices) != 1:
                raise ValueError("Expected exactly one column for " + key)
            columns[key] = choices[0]
        for line, row in enumerate(table, 2):
            item = (row[columns["item"]] or "").strip()
            if not item or item in items:
                raise ValueError(f"Missing or duplicate item on line {line}")
            expected = Decimal(row[columns["expected"]])
            counted = Decimal(row[columns["counted"]])
            if not expected.is_finite() or not counted.is_finite():
                raise ValueError(f"Invalid quantity on line {line}")
            items.add(item)
            key = "matched" if counted == expected else "short" if counted < expected else "over"
            totals[key] += 1
    if not items or sum(totals.values()) != len(items):
        raise ValueError("Stock count reconciliation failed")
    return totals


def report(source, output):
    totals = reconcile(source)
    with tempfile.TemporaryDirectory() as directory:
        card = Image.new("RGB", (1080, 1920), "#182928")
        draw = ImageDraw.Draw(card)
        draw.text((82, 280), "Inventory count", font=ImageFont.load_default(size=84), fill="white")
        draw.text((84, 428), f"{sum(totals.values())} items counted", font=ImageFont.load_default(size=52), fill="#C7D7C4")
        for i, (key, value) in enumerate(totals.items()):
            draw.text((84, 730+i*190), f"{key.title()}     {value}", font=ImageFont.load_default(size=70), fill="white")
        image = Path(directory)/"summary.png"
        card.save(image)
        intermediate = Path(directory)/"summary.mp4"
        subprocess.run(["ffmpeg","-nostdin","-v","error","-loop","1","-i",str(image),"-t","3","-r","30","-pix_fmt","yuv420p",str(intermediate)],check=True)
        return {"counts": totals, "media": render(intermediate, output)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args=parser.parse_args()
    print(json.dumps(report(args.source,args.output)))
