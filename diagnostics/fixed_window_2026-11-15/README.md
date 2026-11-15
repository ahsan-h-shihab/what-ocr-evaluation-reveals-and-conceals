# Fixed-window scope diagnostic

Automated diagnostic submitted for supervisor review; not an independently approved result or a final release.

This controlled follow-up preserves the historical files under `results/` and changes only identified non-body regions of the archived Tesseract text. It uses the original reference queries, normalization, tokenizer, BM25 settings and positional target assignments. It is not a content-based retrieval evaluation.

| Condition | OCR tokens | Maximum block size | MRR |
|---|---:|---:|---:|
| Original | 18,507 | 412 | 0.4460912866 |
| Glossary removed only | 17,857 | 397 | 0.9229629630 |
| Postmatter removed only | 18,418 | 410 | 0.4566835943 |
| Glossary and postmatter removed | 17,768 | 395 | 0.9555555556 |
| Other two endnote spans removed only | 18,468 | 411 | 0.4566016187 |
| All four identified regions removed | 17,729 | 394 | 0.9777777778 |

All conditions have 45 reference and 45 OCR blocks and the same 45 queries. Reference block size is at most 383 tokens. `results.json` includes exact values, per-query target ranks and token-coordinate boundaries. Four normalized intervals come from the earlier export-page/source-scope audit; the script independently checks their closing page boundaries. The glossary spans 4,114 normalized characters and 650 tokens. The earlier 4,095 count describes its aligned insertions, not its character length.

The crop routine finds heading 45 but never uses that match. Clipping at the heading would wrongly discard section 45. Export pages 218–219 provide the previously identified trailing postmatter boundary. Embedded notes require separate exclusions.

The glossary-only intervention supports a substantial scope-related effect within the legacy positional metric. Because block size is `ceil(total_tokens/45)`, deletion changes partitioning before as well as after the removed material. These scores do not validate passage relevance, establish OCR superiority or disprove token fragmentation. No new queries, qrels, OCR outputs or human judgments were created.

The optional `--original-script` argument verifies all nine legacy rows using the actual recovered script's function bodies, with only its four obsolete filesystem-routing assignments omitted. The unmodified script cannot be imported at its present shallow path because `parents[4]` raises `IndexError`. Its SHA-256 is recorded. Private source material and machine paths are not included here.

See the repository README for the tested replay command using separately authorized hash-identified inputs.
