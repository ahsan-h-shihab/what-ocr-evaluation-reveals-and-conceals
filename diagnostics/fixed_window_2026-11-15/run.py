"""Controlled archived-window sensitivity; no OCR inference or content judgments."""
import argparse
import ast
import hashlib
import importlib.util
import json
import math
import re
import types
from collections import Counter
from pathlib import Path


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(release, inputs, output, original=None):
    b = load(release / 'code/b_scoring.py', 'frozen_scoring')
    metadata = json.loads((release / 'metadata/restricted_inputs.json').read_text('utf-8'))
    records = [x for x in metadata['inputs'] if x['input_path'].startswith('benchmark_b/')]
    texts = {}
    for record in records:
        path = inputs / record['input_path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
            raise ValueError('Input digest mismatch: ' + record['input_path'])
        texts[record['input_path']] = path.read_text('utf-8-sig')
    ref_raw = texts['benchmark_b/reference_pravda.txt']
    tess_raw = texts['benchmark_b/Tesseract_Abai_Karasoz_201096.txt']
    ref = b.normalize_text(b.crop_to_qara_sozder(ref_raw))
    raw = b.crop_to_qara_sozder(tess_raw)
    tess = b.normalize_text(raw)
    assert len(ref) == 119453 and len(tess) == 125461
    ranges = {
        'glossary': [102964, 107078],
        'postmatter': [124851, 125461],
        'notes43': [121969, 122081],
        'notes27': [53683, 53817],
    }
    # Corroborate stored normalized ranges from explicit export page boundaries.
    boundary_checks = []
    for label, page in [('glossary', 199), ('postmatter', 218), ('notes43', 215), ('notes27', 145)]:
        match = re.search(r'(?m)^=== PAGE ' + str(page) + r' ===\s*', raw)
        assert match, page
        following = b.normalize_text(raw[match.end():])[:70]
        assert tess.count(following) == 1
        found = tess.index(following)
        target = ranges[label][0 if label == 'postmatter' else 1]
        assert found == target, (label, found, target)
        boundary_checks.append({'region': label, 'next_export_page': page, 'normalized_offset': found})
    conditions = {
        'original': [],
        'glossary_only_removed': ['glossary'],
        'postmatter_only_removed': ['postmatter'],
        'glossary_and_postmatter_removed': ['glossary', 'postmatter'],
        'other_endnotes_only_removed': ['notes27', 'notes43'],
        'body_scope_all_identified_notes_removed': list(ranges),
    }
    ref_windows = b.split_equal_token_blocks(ref, 45)
    counts = Counter(t for window in ref_windows for t in set(b.tokens(window)))
    queries = [b.distinctive_query(window, counts) for window in ref_windows]
    results = []
    details = {}
    for name, removed in conditions.items():
        text = tess
        for a, z in sorted((ranges[k] for k in removed), reverse=True):
            text = text[:a] + text[z:]
        blocks = b.split_equal_token_blocks(text, 45)
        docs = [b.tokens(w) for w in blocks]
        metrics = b.retrieval_metrics_for_queries(queries, docs, list(range(45)))
        ranks = [b.bm25_rank(q, docs).index(i) + 1 for i, q in enumerate(queries)]
        nt = len(b.tokens(text))
        results.append({'condition': name, 'removed_regions': removed,
                        'normalized_characters': len(text), 'tokens': nt,
                        'reference_windows': len(ref_windows), 'OCR_windows': len(blocks),
                        'reference_window_size': math.ceil(len(b.tokens(ref)) / 45),
                        'OCR_window_size': math.ceil(nt / 45),
                        'last_OCR_window_tokens': len(docs[-1]), **metrics})
        details[name] = {'target_ranks': ranks,
                         'reference_token_boundaries': [[i*math.ceil(len(b.tokens(ref))/45), i*math.ceil(len(b.tokens(ref))/45)+len(b.tokens(w))] for i,w in enumerate(ref_windows)],
                         'OCR_token_boundaries': [[i*math.ceil(nt/45), i*math.ceil(nt/45)+len(d)] for i,d in enumerate(docs)],
                         'query_rank_changes_from_original': None if name == 'original' else sum(x != y for x,y in zip(ranks, details['original']['target_ranks'])),
                         'all_zero_overlap_queries': sum(not any(set(q)&set(d) for d in docs) for q in queries)}
    assert abs(results[0]['mrr'] - 0.44609128659802866) < 1e-14
    independent = None
    if original:
        # The recovered script's old directory routing raises IndexError here.
        # Compile its actual imports, constants and functions, omitting only
        # four machine-specific path assignments. Do not alter function bodies.
        tree = ast.parse(original.read_text('utf-8-sig'))
        tree.body = [node for node in tree.body if not (
            isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and
            t.id in {'ROOT', 'ARTICLE_DIR', 'REPORT_DIR', 'OUT_DIR'} for t in node.targets))]
        o = types.ModuleType('original_archived_script')
        o.__file__ = str(original)
        exec(compile(tree, str(original), 'exec'), o.__dict__)
        verification = []
        for alias, text in texts.items():
            if alias.endswith('reference_pravda.txt'):
                continue
            original_rows = o.retrieval_sensitivity(o.crop_to_qara_sozder(ref_raw), o.crop_to_qara_sozder(text))
            frozen_rows = b.retrieval_sensitivity(b.crop_to_qara_sozder(ref_raw), b.crop_to_qara_sozder(text))
            assert original_rows == frozen_rows
            verification.extend({'input': alias, 'mode': row['mode'], 'queries': row['queries'], 'mrr': row['mrr']} for row in original_rows)
        independent = {'source_sha256': hashlib.sha256(original.read_bytes()).hexdigest(), 'nine_original_rows_equal_frozen_adapter': True, 'rows': verification}
    result = {'scope': 'Controlled positional-target sensitivity only; no valid content qrels or retrieval-effectiveness claim.',
              'configuration': {'windows': 45, 'BM25_k1': 1.5, 'BM25_b': 0.75, 'queries': 'Same 45 original reference-window queries in every condition', 'ties': 'Original descending candidate index', 'normalization_and_tokenization': 'Unchanged code/b_scoring.py', 'ref_and_OCR_windows': 'Independent ceil(token_count/45) partitions; not shared  fixed-length boundaries'},
              'input_hashes': {x['input_path']: x['sha256'] for x in records},
              'ranges': ranges, 'boundary_checks': boundary_checks,
              'original_script_verification': independent, 'results': results, 'window_diagnostics': details}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', 'utf-8')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--release', type=Path, required=True)
    p.add_argument('--input-root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--original-script', type=Path)
    a = p.parse_args()
    run(a.release, a.input_root, a.output, a.original_script)
