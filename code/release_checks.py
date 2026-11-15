"""Public-only integrity, representation, preview and README-link checks."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import fitz


ROOT = Path(__file__).resolve().parents[1]


def check():
    record = json.loads((ROOT / "analysis/results.json").read_text("utf-8"))
    assert len(record["rows"]) == 8
    for row in record["rows"]:
        assert sum(row[k] for k in "SDI") == row["edits"]
        assert row["H"] - row["N"] == row["I"] - row["D"]
        assert math.isclose(row["edits"] / row["N"], row["rate"], abs_tol=1e-14)
    for mode, gap in record["gap_pp_DP_minus_DeepSeek"].items():
        rates = {r["system"]: r["rate"] for r in record["rows"]
                 if r["representation"] == mode}
        assert math.isclose(100 * (rates["DP2"] - rates["DeepSeek"]), gap,
                            abs_tol=1e-12)
    assert sum(r["insertion_ops"] for r in record["longest_runs"]["DP2"].values()) == 3991
    assert record["inserted_character_diagnostics"]["DP2"]["insertions"] == 5431
    manifest = json.loads((ROOT / "MANIFEST.json").read_text("utf-8"))
    ignored = {"work", ".git", ".venv", "venv", "__pycache__"}
    actual = {
        f.relative_to(ROOT).as_posix() for f in ROOT.rglob("*")
        if f.is_file() and not ignored.intersection(f.relative_to(ROOT).parts)
    }
    assert actual == {r["path"] for r in manifest["files"]} | {"MANIFEST.json"}
    for item in manifest["files"]:
        file = ROOT / item["path"]
        assert hashlib.sha256(file.read_bytes()).hexdigest() == item["sha256"], item["path"]
    previews = []
    for item in manifest["readme_previews"]:
        png = ROOT / item["path"]
        with fitz.open(ROOT / item["source_pdf"]) as doc:
            pix = doc[0].get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72),
                                   colorspace=fitz.csRGB, alpha=False)
            decoded = fitz.Pixmap(str(png))
            assert (pix.width, pix.height, pix.samples) == (
                decoded.width, decoded.height, decoded.samples)
        previews.append(item["path"])
    links = []
    for href in re.findall(r"\]\(([^)]+)\)", (ROOT / "README.md").read_text("utf-8")):
        if urlsplit(href).scheme or href.startswith("#"):
            continue
        file = (ROOT / unquote(href.split("#", 1)[0])).resolve()
        file.relative_to(ROOT)
        assert file.is_file(), href
        links.append(href)
    return {"status": "PASS", "representation_rows": 8, "gaps": 4,
            "selected_insertion_ops": 3991, "all_insertion_ops": 5431,
            "manifest_members": len(manifest["files"]),
            "preview_pixel_matches": previews, "readme_links_checked": links,
            "scope": "Saved public records and approved artwork only. No fresh book-text alignment or human judgments."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    target = Path(args.output).resolve()
    target.relative_to((ROOT / "work").resolve())
    target.parent.mkdir(parents=True, exist_ok=True)
    result = check()
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("PASS")
