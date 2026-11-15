# Exclusion verification

Project: **What OCR Evaluation Reveals and Conceals: Reference Integrity, Text Representation, and Retrieval Diagnostics for Printed Kazakh Book OCR**

**PASS for the reviewed local staging inventory.** The package contains 68 files: 48 unchanged A-class allowlist copies and 20 documented additions. No B-class or optional C-class source file was copied. STAGING_PROVENANCE.json provides the exact source/destination map and addition rationales.

## Scope and methods

Every staged file was enumerated. Text and source files were scanned for credential patterns, private-key headers, email addresses and machine-specific absolute paths. No findings were detected. The software citation and README list only Ahsan Habib Shihab and Iskander Akhmetov as repository contributors. The preferred manuscript citation retains its six approved author names, ORCIDs and title exactly. No AI tool is listed as an author or contributor. No contact addresses are included.

The scanner compared hashes against 29 known restricted source/photograph/scan files, including the 15 hash-identified replay inputs. It also compared normalized 120-character windows from those 15 restricted texts against all staged text. No matching literary passages or restricted input copies were found. Short ordinal labels needed for the heading diagnostic remain part of the approved assets.

Every file was checked for ZIP structure; no archives or archive members are included. Archive extensions, notebooks, manuscript source dependencies, photographs and unrelated binary formats are absent.

The binary allowlist contains exactly three one-page vector PDFs, their three PNG previews and two Noto font files. The PDFs have embedded fonts and no embedded raster photographs. The preview pixels match a full-page 300-dpi rendering of their respective PDFs. Original Noto files and license notices retain their source hashes.

## Explicit exclusions confirmed

- No book scans or stored source-page images.
- No full reference/transcription, OCR or correction output.
- No author photograph, manuscript PDF or source ZIP.
- No unapproved contact details, credential literals or private review evidence.
- No historical conference package or manuscript-only dependency.
- No installed environment, cache, generated work directory or archive.
- No Git repository, remote configuration, commit, push or publication.

README image/PDF links resolve. All three captions match the final manuscript; the Table 1 cross-reference is resolved for Markdown. The superseded MRR chart is absent.

## Reproduction boundary

Public aggregate checks, 11 synthetic tests and all three figure regenerations passed. The figures regenerate byte for byte in the pinned tested environment. Missing private inputs correctly block fresh archived-text scoring. The empty prospective template correctly emits no empirical performance metrics.

The updated README was checked with an offline HTML layout renderer at desktop and mobile widths. All three previews were embedded and visually inspected. The narrow proof does not emulate GitHub horizontal table scrolling. No live GitHub rendering or upload is claimed.

## Rights and remaining decisions

Study-use permissions and manuscript author approval remain confirmed. Public release and project-artifact licensing still require the authorized rights holder's decision. No new project license, DOI, publication date or external access arrangement has been invented. The existing repository URL and slug supplied by the user are recorded consistently; no remote settings were changed.

Pattern and hash scans are evidence-based screening, not proof against every possible secret. Their practical scope is strengthened by the exact 48-source boundary, inspected additions and absence of opaque archives. See release_validation.json for the test receipt and MANIFEST.json for hashes.
