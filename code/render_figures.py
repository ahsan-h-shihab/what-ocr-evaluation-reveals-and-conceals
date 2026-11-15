"""Bridge the preserved adapter to the final three approved figure assets."""
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def render(root, target):
    root, target = Path(root), Path(target)
    target.resolve().relative_to((root / "work").resolve())
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ocr_figures_") as folder:
        stage = Path(folder)
        shutil.copytree(root / "figures", stage / "figures")
        subprocess.run([sys.executable, "-B", "figures/draw_figures.py"],
                       cwd=stage, check=True)
        records = []
        for name in ("Fig1_pipeline.pdf", "Fig2_reference_sensitivity.pdf",
                     "Fig3_positional_target.pdf"):
            generated = stage / "figures" / name
            source = root / "figures" / name
            shutil.copyfile(generated, target / name)
            records.append({
                "figure": name,
                "sha256": hashlib.sha256(generated.read_bytes()).hexdigest(),
                "byte_identical_to_authoritative": generated.read_bytes() == source.read_bytes(),
            })
    return {"status": "PASS", "figures": records,
            "scope": "Current three-figure generation. Figure 2 asserts both bar series against its saved CSV. No scoring or inference.",
            "rendering_note": "Byte identity is recorded for the pinned tested environment. The authoritative PDFs remain unchanged."}
