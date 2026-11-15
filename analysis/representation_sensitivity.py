"""Offline paired representation check for the two same-scan B releases."""
import argparse
import csv
import hashlib
import importlib.util
import json
import platform
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import rapidfuzz
from rapidfuzz.distance import Levenshtein


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_scorer(release):
    source = release / "code/b_scoring.py"
    spec = importlib.util.spec_from_file_location("archived_b", source)
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)
    return scorer


RUN_PATTERNS = {"empty_brackets": r"\[ \](?: \[ \])*", "digit_five": r"5+",
                "closing_guillemet": r"\u00bb+"}


def longest_runs(text):
    runs = {}
    for label, pattern in RUN_PATTERNS.items():
        match = max(re.finditer(pattern, text), key=lambda m: len(m[0]), default=None)
        start, end = match.span() if match else (0, 0)
        repeats = (end-start+1)//4 if label == "empty_brackets" else end-start
        runs[label] = dict(start=start, end=end, repeats=repeats)
    return runs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--repository-root", type=Path)
    inputs.add_argument("--input-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dp-json", type=Path, help="Optional archived page-grounded extraction for tracing observed runs")
    args = parser.parse_args()
    if rapidfuzz.__version__ != "3.14.6":
        raise ValueError("Expected RapidFuzz 3.14.6 for the archived alignment tie handling")
    scorer = load_scorer(args.release)
    manifest = json.loads((args.release / "metadata/restricted_inputs.json").read_text("utf-8"))
    records = {r["input_path"]: r for r in manifest["inputs"]}
    reference_name = "benchmark_b/reference_pravda.txt"
    names = {
        "DeepSeek": "benchmark_b/DeepSeek_OCR_prediction.txt",
        "DP2": "benchmark_b/DP2_mini_LandingAI_prediction.txt",
    }
    checked = {}

    def representations(name):
        entry = records[name]
        path = (args.repository_root / entry["repository_path"] if args.repository_root
                else args.input_root / name)
        checked[name] = digest(path)
        if checked[name] != entry["sha256"]:
            raise ValueError(f"Archived input differs: {name}")
        raw = path.read_text(encoding="utf-8-sig")
        body = scorer.crop_to_qara_sozder(raw)
        normalized = scorer.normalize_text(body)
        words = scorer.tokens(body)
        return {"original_char": normalized, "lowercase_char": normalized.lower(),
                "token_string_char": " ".join(words), "token_word": words}

    ref = representations(reference_name)
    rows = []
    inserted = {}
    runs = {"reference": longest_runs(ref["original_char"])}
    rates = {mode: {} for mode in ref}
    for system, name in names.items():
        hyp = representations(name)
        runs[system] = longest_runs(hyp["original_char"])
        for mode, target in ref.items():
            candidate = hyp[mode]
            ops = Levenshtein.editops(target, candidate)
            counts = Counter(op.tag for op in ops)
            edits = len(ops)
            assert edits == Levenshtein.distance(target, candidate)
            assert len(candidate) - len(target) == counts["insert"] - counts["delete"]
            rates[mode][system] = edits / len(target)
            rows.append(dict(system=system, representation=mode, N=len(target),
                             H=len(candidate), S=counts["replace"], D=counts["delete"],
                             I=counts["insert"], edits=edits, rate=edits / len(target)))
            if mode == "original_char":
                for run in runs[system].values():
                    run["insertion_ops"] = sum(op.tag == "insert" and run["start"] <= op.dest_pos < run["end"] for op in ops)
                symbols = Counter(candidate[op.dest_pos] for op in ops if op.tag == "insert")
                inserted[system] = {"insertions": counts["insert"],
                    "by_unicode_category": dict(sorted(Counter(
                        unicodedata.category(c) for c in symbols.elements()).items())),
                    "most_frequent_codepoints": {f"U+{ord(c):04X}": n for c, n in symbols.most_common(5)}}

    def archived(name):
        with (args.release / "results/benchmark_b" / name).open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))

    primary = archived("unchanged_original_score_verification.csv")
    historic = archived("benchmark_b_alignment_counts.csv")
    for row in rows:
        mode, system = row["representation"], row["system"]
        if mode == "token_string_char":
            continue
        if mode == "lowercase_char":
            name = {"DeepSeek": "DeepSeek-OCR", "DP2": "DP-2-mini / LandingAI"}[system]
            old = next(r for r in historic if r["system"] == name and r["alignment"] == "lowercase_diagnostic")
            denominator = "reference_characters"
        else:
            unit = "word" if mode == "token_word" else "character"
            old = next(r for r in primary if r["system"] == system and r["unit"] == unit)
            denominator = "N"
        assert all(row[k] == int(old[k]) for k in ("S", "D", "I", "edits"))
        assert row["N"] == int(old[denominator])

    result = {"question": "How does the common-source difference in reference distance depend on text representation and edit unit?",
              "python": platform.python_version(), "rapidfuzz": rapidfuzz.__version__,
              "unicode_version": unicodedata.unidata_version, "input_sha256": checked,
              "scorer_sha256": digest(args.release / "code/b_scoring.py"), "rows": rows,
              "gap_pp_DP_minus_DeepSeek": {k: 100*(r["DP2"]-r["DeepSeek"]) for k, r in rates.items()},
              "inserted_character_diagnostics": inserted, "longest_runs": runs}
    if args.dp_json:
        source_hash = digest(args.dp_json)
        if source_hash != "291adde99385d05f4aa4179ade1054b034ed51269060a937506971d9b7a7057d":
            raise ValueError("Unrecognized DP page-grounded extraction")
        chunks = json.loads(args.dp_json.read_text("utf-8"))["chunks"]
        locations = {}
        for label in RUN_PATTERNS:
            count = runs["DP2"][label]["repeats"]
            matches = [(i, c["grounding"]["page"]) for i, c in enumerate(chunks)
                       if c["type"] == "text" and longest_runs(c["markdown"])[label]["repeats"] == count]
            assert len(matches) == 1 and count > 1
            i, page = matches[0]
            locations[label] = {"chunk_zero_based": i, "pdf_page_one_based": page+1}
        result["raw_chunk_corroboration"] = {"sha256": source_hash, "locations": locations}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    main()
