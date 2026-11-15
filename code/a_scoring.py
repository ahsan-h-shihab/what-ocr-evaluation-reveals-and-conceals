"""Exact scoring function extracts; no inference or historical filesystem routing."""
from __future__ import annotations
import re, random
from pathlib import Path
from rapidfuzz.distance import Levenshtein

def normalize_text(text: str) -> str:
    text = text.replace("\ufeff", "")
    text = re.sub(r"--- PAGE \d+ ---", " ", text)
    text = re.sub(r"(?m)^\s*\d+\s*$", " ", text)
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()

def tokenize(text: str) -> list[str]:
    return re.findall(r"[\wӘәҒғҚқҢңӨөҰұҮүҺһІі]+", text.lower(), flags=re.UNICODE)

def cer(ref: str, hyp: str) -> float:
    ref = normalize_text(ref)
    hyp = normalize_text(hyp)
    return Levenshtein.distance(ref, hyp) / max(1, len(ref))

def wer(ref: str, hyp: str) -> float:
    ref_tokens = tokenize(normalize_text(ref))
    hyp_tokens = tokenize(normalize_text(hyp))
    return Levenshtein.distance(ref_tokens, hyp_tokens) / max(1, len(ref_tokens))

def load_page_marked_hypothesis(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    parts = re.split(r"(?m)^--- PAGE \d+ ---\s*$", text)
    pages = [part.strip() for part in parts if part.strip()]
    if len(pages) != 7:
        raise ValueError(f"Expected 7 pages in {path}, found {len(pages)}")
    return pages

def percentile(values: list[float], q: float) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    pos = (len(values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(values) - 1)
    frac = pos - lo
    return values[lo] * (1 - frac) + values[hi] * frac

def bootstrap_ci(ref_pages: list[str], hyp_pages: list[str], metric, n: int = 2000, seed: int = 20260602) -> tuple[float, float, float]:
    rng = random.Random(seed)
    observed = metric("\n".join(ref_pages), "\n".join(hyp_pages))
    samples: list[float] = []
    for _ in range(n):
        indices = [rng.randrange(len(ref_pages)) for _ in ref_pages]
        ref = "\n".join(ref_pages[idx] for idx in indices)
        hyp = "\n".join(hyp_pages[idx] for idx in indices)
        samples.append(metric(ref, hyp))
    return observed, percentile(samples, 0.025), percentile(samples, 0.975)
