"""Exact archived B computation extracts; legacy retrieval defects intentionally preserved."""
from __future__ import annotations
import math, random, re
from collections import Counter, defaultdict
from rapidfuzz.distance import Levenshtein

ORDINALS = [
    "Бірінші", "Екінші", "Үшінші", "Төртінші", "Бесінші", "Алтыншы", "Жетінші",
    "Сегізінші", "Тоғызыншы", "Оныншы", "Он бірінші", "Он екінші", "Он үшінші",
    "Он төртінші", "Он бесінші", "Он алтыншы", "Он жетінші", "Он сегізінші",
    "Он тоғызыншы", "Жиырмасыншы", "Жиырма бірінші", "Жиырма екінші",
    "Жиырма үшінші", "Жиырма төртінші", "Жиырма бесінші", "Жиырма алтыншы",
    "Жиырма жетінші", "Жиырма сегізінші", "Жиырма тоғызыншы", "Отызыншы",
    "Отыз бірінші", "Отыз екінші", "Отыз үшінші", "Отыз төртінші",
    "Отыз бесінші", "Отыз алтыншы", "Отыз жетінші", "Отыз сегізінші",
    "Отыз тоғызыншы", "Қырқыншы", "Қырық бірінші", "Қырық екінші",
    "Қырық үшінші", "Қырық төртінші", "Қырық бесінші",
]

KAZAKH_SPECIFIC_PAIRS = {
    frozenset(("қ", "к")): "қ/к",
    frozenset(("ғ", "г")): "ғ/г",
    frozenset(("ң", "н")): "ң/н",
    frozenset(("і", "и")): "і/и",
    frozenset(("ұ", "у")): "ұ/у",
    frozenset(("ү", "у")): "ү/у",
    frozenset(("ө", "о")): "ө/о",
    frozenset(("ә", "а")): "ә/а",
    frozenset(("һ", "х")): "һ/х",
}

def normalize_text(text: str) -> str:
    text = text.replace("\ufeff", "")
    text = re.sub(r"<a[^>]+></a>", " ", text)
    text = re.sub(r"(?m)^# File:.*$", " ", text)
    text = re.sub(r"(?m)^=== PAGE \d+ ===$", " ", text)
    text = re.sub(r"(?m)^\s*\d+\s*$", " ", text)
    text = text.replace("—", "-").replace("–", "-")
    text = re.sub(r"#+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def crop_to_qara_sozder(text: str) -> str:
    start = re.search(r"[БBВ]?[іiІI]р[іiІI]нш[іiІI]\s+с[өоo]з", text, flags=re.IGNORECASE)
    end = re.search(r"Қырық\s+бес[іiІI]нш[іiІI]\s+с[өоo]з", text, flags=re.IGNORECASE)
    if start and end:
        return text[start.start():]
    if start:
        return text[start.start():]
    return text

def tokens(text: str) -> list[str]:
    return re.findall(r"[\wӘәҒғҚқҢңӨөҰұҮүҺһІі]+", normalize_text(text).lower(), flags=re.UNICODE)

def cer(ref: str, hyp: str) -> float:
    ref_n = normalize_text(ref)
    hyp_n = normalize_text(hyp)
    return Levenshtein.distance(ref_n, hyp_n) / max(1, len(ref_n))

def wer(ref: str, hyp: str) -> float:
    ref_t = tokens(ref)
    hyp_t = tokens(hyp)
    return Levenshtein.distance(ref_t, hyp_t) / max(1, len(ref_t))

def detect_section_positions(text: str) -> tuple[list[tuple[int, str]], list[str]]:
    text = normalize_text(crop_to_qara_sozder(text))
    positions: list[int] = []
    found: list[str] = []
    lower = text.lower()
    cursor = 0
    for ordinal in ORDINALS:
        pattern = ordinal.lower().replace(" ", r"\s+") + r"\s+с[өоo]з"
        match = re.search(pattern, lower[cursor:], flags=re.IGNORECASE)
        if match:
            pos = cursor + match.start()
            positions.append(pos)
            found.append(ordinal)
            cursor = pos + 1
    paired = sorted(set(zip(positions, found)))
    missing = [ordinal for ordinal in ORDINALS if ordinal not in found]
    return paired, missing

def split_sections_with_diagnostics(text: str) -> tuple[list[str], dict]:
    text = normalize_text(crop_to_qara_sozder(text))
    paired, missing = detect_section_positions(text)
    positions = [pos for pos, _ in paired]
    if len(positions) >= 30:
        sections = []
        for idx, start in enumerate(positions):
            end = positions[idx + 1] if idx + 1 < len(positions) else len(text)
            sections.append(text[start:end])
        returned = sections[:45]
        return returned, {
            "detected_headings": len(positions),
            "returned_units": len(returned),
            "expected_headings": len(ORDINALS),
            "fallback_used": "false",
            "token_count": len(tokens(text)),
            "missing_headings": "; ".join(missing),
        }

    toks = tokens(text)
    size = max(1, math.ceil(len(toks) / 45))
    returned = [" ".join(toks[i:i + size]) for i in range(0, len(toks), size)][:45]
    return returned, {
        "detected_headings": len(positions),
        "returned_units": len(returned),
        "expected_headings": len(ORDINALS),
        "fallback_used": "true",
        "token_count": len(toks),
        "missing_headings": "; ".join(missing),
    }

def split_sections(text: str) -> list[str]:
    sections, _ = split_sections_with_diagnostics(text)
    return sections

def split_equal_token_blocks(text: str, n: int = 45) -> list[str]:
    toks = tokens(text)
    size = max(1, math.ceil(len(toks) / n))
    return [" ".join(toks[i:i + size]) for i in range(0, len(toks), size)][:n]

def percentile(values: list[float], q: float) -> float:
    values = sorted(values)
    pos = (len(values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(values) - 1)
    frac = pos - lo
    return values[lo] * (1 - frac) + values[hi] * frac

def bootstrap_sections(ref_sections: list[str], hyp_sections: list[str], metric, n: int = 100) -> tuple[float, float, float]:
    rng = random.Random(20260602)
    m = min(len(ref_sections), len(hyp_sections))
    ref_sections = ref_sections[:m]
    hyp_sections = hyp_sections[:m]
    section_values = [metric(ref_sections[i], hyp_sections[i]) for i in range(m)]
    observed = sum(section_values) / max(1, len(section_values))
    values = []
    for _ in range(n):
        idxs = [rng.randrange(m) for _ in range(m)]
        values.append(sum(section_values[i] for i in idxs) / max(1, len(idxs)))
    return observed, percentile(values, 0.025), percentile(values, 0.975)

def bootstrap_edit_bins(ref: str, hyp: str, level: str = "char", bins: int = 45, n: int = 500) -> tuple[float, float, float]:
    if level == "word":
        ref_seq = tokens(ref)
        hyp_seq = tokens(hyp)
    else:
        ref_seq = list(normalize_text(ref))
        hyp_seq = list(normalize_text(hyp))

    ops = Levenshtein.editops(ref_seq, hyp_seq)
    denom = [0] * bins
    errors = [0] * bins
    for idx in range(len(ref_seq)):
        denom[min(bins - 1, idx * bins // max(1, len(ref_seq)))] += 1
    for op in ops:
        pos = min(max(0, op.src_pos), max(0, len(ref_seq) - 1))
        bin_idx = min(bins - 1, pos * bins // max(1, len(ref_seq)))
        errors[bin_idx] += 1

    observed = sum(errors) / max(1, sum(denom))
    rng = random.Random(20260602)
    samples = []
    for _ in range(n):
        idxs = [rng.randrange(bins) for _ in range(bins)]
        samples.append(sum(errors[i] for i in idxs) / max(1, sum(denom[i] for i in idxs)))
    return observed, percentile(samples, 0.025), percentile(samples, 0.975)

def error_summary(ref: str, hyp: str) -> tuple[Counter, Counter]:
    ref_n = normalize_text(ref).lower()
    hyp_n = normalize_text(hyp).lower()
    ops = Levenshtein.editops(ref_n, hyp_n)
    summary = Counter()
    substitutions = Counter()
    for op in ops:
        if op.tag == "replace":
            a = ref_n[op.src_pos]
            b = hyp_n[op.dest_pos]
            summary["substitution"] += 1
            substitutions[f"{a}->{b}"] += 1
            pair = KAZAKH_SPECIFIC_PAIRS.get(frozenset((a, b)))
            if pair:
                summary[f"kazakh_specific:{pair}"] += 1
        elif op.tag == "insert":
            summary["insertion"] += 1
        elif op.tag == "delete":
            summary["deletion"] += 1
    return summary, substitutions

def bm25_rank(query: list[str], docs: list[list[str]], k1: float = 1.5, b: float = 0.75) -> list[int]:
    n_docs = len(docs)
    avg_len = sum(len(d) for d in docs) / max(1, n_docs)
    dfs = Counter()
    doc_counts = []
    for doc in docs:
        counts = Counter(doc)
        doc_counts.append(counts)
        for term in counts:
            dfs[term] += 1
    scores = []
    for idx, counts in enumerate(doc_counts):
        score = 0.0
        doc_len = len(docs[idx])
        for term in query:
            if term not in counts:
                continue
            idf = math.log(1 + (n_docs - dfs[term] + 0.5) / (dfs[term] + 0.5))
            tf = counts[term]
            score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / max(1, avg_len)))
        scores.append((score, idx))
    return [idx for _, idx in sorted(scores, reverse=True)]

def distinctive_query(section: str, global_counts: Counter, n: int = 10) -> list[str]:
    stop = {"мен", "деп", "бір", "бар", "жоқ", "да", "де", "ол", "бұл", "сол", "үшін", "еді", "екен", "менен"}
    counts = Counter(t for t in tokens(section) if len(t) >= 4 and t not in stop)
    ranked = sorted(counts, key=lambda t: (global_counts[t], -counts[t], t))
    return ranked[:n] or tokens(section)[:n]

def retrieval_metrics_for_queries(
    queries: list[list[str]],
    docs: list[list[str]],
    target_indexes: list[int],
) -> dict[str, float]:
    m = min(len(queries), len(target_indexes))
    docs = docs[:]
    ranks = []
    for idx in range(m):
        target = target_indexes[idx]
        if target >= len(docs):
            ranks.append(999)
            continue
        ranked = bm25_rank(queries[idx], docs)
        rank = ranked.index(target) + 1 if target in ranked else 999
        ranks.append(rank)
    return {
        "queries": float(m),
        "recall_at_1": sum(r <= 1 for r in ranks) / max(1, m),
        "recall_at_3": sum(r <= 3 for r in ranks) / max(1, m),
        "recall_at_5": sum(r <= 5 for r in ranks) / max(1, m),
        "mrr": sum(1 / r for r in ranks) / max(1, m),
    }

def retrieval_metrics(ref_sections: list[str], hyp_sections: list[str]) -> dict[str, float]:
    m = min(len(ref_sections), len(hyp_sections))
    ref_sections = ref_sections[:m]
    hyp_sections = hyp_sections[:m]
    docs = [tokens(s) for s in hyp_sections]
    global_counts = Counter(t for s in ref_sections for t in set(tokens(s)))
    queries = [distinctive_query(section, global_counts) for section in ref_sections]
    return retrieval_metrics_for_queries(queries, docs, list(range(m)))

def retrieval_sensitivity(ref: str, hyp: str) -> list[dict[str, float | str]]:
    ref_sections, _ = split_sections_with_diagnostics(ref)
    hyp_sections, hyp_diag = split_sections_with_diagnostics(hyp)
    ref_windows = split_equal_token_blocks(ref, 45)
    hyp_windows = split_equal_token_blocks(hyp, 45)

    rows: list[dict[str, float | str]] = []

    m_sections = min(len(ref_sections), len(hyp_sections))
    section_ref = ref_sections[:m_sections]
    global_counts = Counter(t for s in section_ref for t in set(tokens(s)))
    rows.append({
        "mode": "distinctive_reference_tokens",
        "ref_units": len(ref_sections),
        "hyp_units": len(hyp_sections),
        "note": "queries are rare content tokens from reference sections; diagnostic proxy with circular-bias risk",
        **retrieval_metrics_for_queries(
            [distinctive_query(section, global_counts) for section in section_ref],
            [tokens(s) for s in hyp_sections[:m_sections]],
            list(range(m_sections)),
        ),
    })

    title_queries = [tokens(f"{ordinal} сөз") for ordinal in ORDINALS[:m_sections]]
    rows.append({
        "mode": "section_title_queries",
        "ref_units": len(ref_sections),
        "hyp_units": len(hyp_sections),
        "note": "queries use Kazakh ordinal section titles; sensitive to heading OCR and section segmentation",
        **retrieval_metrics_for_queries(
            title_queries,
            [tokens(s) for s in hyp_sections[:m_sections]],
            list(range(m_sections)),
        ),
    })

    m_windows = min(len(ref_windows), len(hyp_windows))
    window_ref = ref_windows[:m_windows]
    window_counts = Counter(t for s in window_ref for t in set(tokens(s)))
    rows.append({
        "mode": "fixed_window_chunks",
        "ref_units": len(ref_windows),
        "hyp_units": len(hyp_windows),
        "note": "queries and documents use equal token windows, avoiding heading-detection failures",
        **retrieval_metrics_for_queries(
            [distinctive_query(section, window_counts) for section in window_ref],
            [tokens(s) for s in hyp_windows[:m_windows]],
            list(range(m_windows)),
        ),
    })

    if hyp_diag["fallback_used"] == "false" and int(hyp_diag["returned_units"]) < len(ORDINALS):
        for row in rows:
            row["layout_warning"] = "section headings detected but fewer than 45 units; retrieval may reflect merged/missing sections"
    elif hyp_diag["fallback_used"] == "true":
        for row in rows:
            row["layout_warning"] = "heading detection fallback used; section-level retrieval is approximate"
    return rows
