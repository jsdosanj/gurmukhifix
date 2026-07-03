# Changelog

All notable changes to **gurmukhifix** are documented here. The format loosely
follows [Keep a Changelog](https://keepachangelog.com/); versions follow
[Semantic Versioning](https://semver.org/).

## [0.2.0] — 2026-07-03

A safety- and credibility-focused release: gurmukhifix is repositioned around what
it does excellently — **safe, evidence-gated Gurmukhi/Indic OCR correction** — and
is now provably unable to silently corrupt correct text, including Gurbani.

### Added
- **Evidence gate** (`gurmukhifix/evidence.py`): every automatic codepoint change
  is judged at the word level. Scripture words are locked; substitutions need a
  strict validity gain or a dictionary hit; re-orderings are always safe.
- **Gurbani + Punjabi lexicons** (`gurmukhifix/data/`, 67,515 + 70,986 words),
  derived from the Shabad OS database, plus a reproducible `tools/build_lexicon.py`.
  These power the scripture lock and dictionary-gated confusion correction — making
  the previously-inert confusion pairs fire *safely*.
- **OCR-engine-agnostic input layer** (`gurmukhifix/ocr.py`): adapters for Tesseract
  JSON/TSV/hOCR, ALTO, Surya, Google Vision/Gemini, plain text, and generic word
  lists, with auto-detection. `process_document` accepts all of them and a `fmt` hint.
- `gurmukhifix demo` (first correction in seconds on bundled samples) and
  `gurmukhifix formats`; a `--format` option on `correct` and `batch`.
- Bundled per-language sample OCR files (`gurmukhifix/samples/`).
- Property-based **zero-corruption** test battery (`tests/test_zero_corruption.py`):
  fuzzes every script and locks the whole Gurbani corpus, incl. adversarial promotions.
- Real-Gurbani **benchmark** (300 SGGS lines, documented error injection) replacing
  the previous synthetic one; `tests/ground_truth/` now exists as the README claimed.
- `from gurmukhifix import process_document` and the rest of the public API are
  re-exported from the package root.

### Fixed
- **Silent corruption:** the hamza-carrier heuristic rewrote valid Arabic-script
  text (`یء` → `ئ`) with no evidence — now evidence-gated.
- **Silent corruption:** a learner-promoted pair globally rewrote clean scripture
  (`ਕਾਲ ਕਰ` → `ਖਾਲ ਖਰ`) — now context-aware, gated, and blocked on scripture.
- `gurmukhifix correct` no longer prints a traceback on bad input; it reports a
  one-line error and exits 1. A malformed `.json` file is reported clearly.
- `extends` no longer produces duplicate correction candidates (28 duplicate
  Punjabi confusion pairs removed).
- README H1 rename artifact; the "Bayesian" overstatement (it is a frequency
  threshold); the uncited error-rate claim.
- Per-pass gating replaces the all-or-nothing revert, so a good early fix survives
  a regressing later pass.

### Changed
- Repositioned Gurmukhi/Indic-first. **Urdu/Farsi are now experimental
  (structural-only)** with no accuracy claim.
- Batch reports per-file failure reasons instead of swallowing them.

## [0.1.0]

- Initial release: evidence-gated confusion/diacritic correction, SQLite learner,
  Click CLI, interactive docs site, PyPI Trusted Publishing.
