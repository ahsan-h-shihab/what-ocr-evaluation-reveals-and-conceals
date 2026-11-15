# Paired representation sensitivity

Project: **What OCR Scores Conceal: Reference Integrity, Text Representation, and Retrieval Diagnostics for Printed Kazakh Books**

analysis/results.json preserves eight rows for the two common-scan outputs. The four representations use original normalized characters, lowercase normalized characters, characters in lowercase WER tokens joined by one space, and the same token lists aligned as words.

code/release_checks.py verifies the saved counts, denominator identities, rates, gaps and 3,991 selected insertions without restricted text. It does not recompute the underlying alignments.

For optional fresh alignment of the exact separately authorized texts, run from the package root with RapidFuzz 3.14.6.

    python -B analysis/representation_sensitivity.py --release . --input-root ../authorized_inputs --output work/representation_replay.json

Use the three benchmark_b input aliases and exact hashes in metadata/restricted_inputs.json. No machine-specific path or local dependency directory is required.

The optional --dp-json argument accepts the raw page-grounded extraction matching the digest recorded in results.json. It corroborates the three source pages. Omitting it preserves distance and span calculations while omitting page-grounding corroboration.

The comparison jointly changes punctuation, separators, reference length and optimal alignment. Gaps use the unrounded DP-2-mini rate minus DeepSeek rate. The spans were selected for exploratory inspection after examining the original character alignment. All remained in the scored output. The count is alignment-dependent and the extraction cause is unknown.
