"""Render the three authoritative PDF pages without cropping or redrawing."""
import argparse
import hashlib
import json
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
FIGURES = ("Fig1_pipeline", "Fig2_reference_sensitivity", "Fig3_positional_target")


def render(output):
    output = Path(output).resolve()
    output.relative_to((ROOT / "work").resolve())
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for name in FIGURES:
        source = ROOT / "figures" / (name + ".pdf")
        target = output / (name + ".png")
        with fitz.open(source) as doc:
            assert len(doc) == 1
            page = doc[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72),
                                 colorspace=fitz.csRGB, alpha=False)
            pix.set_dpi(300, 300)
            pix.save(target)
            records.append({
                "source_pdf": "figures/" + source.name,
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "png_name": target.name,
                "png_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "width": pix.width, "height": pix.height, "dpi": 300,
                "pdf_width_points": page.rect.width,
                "pdf_height_points": page.rect.height,
                "method": "Full PDF page rendered with PyMuPDF, RGB, no crop or redraw",
            })
    return {"status": "PASS", "previews": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = render(args.output)
    (Path(args.output) / "preview_checks.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("PASS")
