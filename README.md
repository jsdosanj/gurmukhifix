# gurmukhifix

[![CI](https://github.com/jsdosanj/gurmukhifix/actions/workflows/ci.yml/badge.svg)](https://github.com/jsdosanj/gurmukhifix/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/gurmukhifix)](https://pypi.org/project/gurmukhifix/)
![Python](https://img.shields.io/pypi/pyversions/gurmukhifix)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> **Safe, evidence-gated OCR correction for Gurmukhi and other Indic scripts.**
> Reverses the systematic Unicode-order and diacritic errors that OCR makes on
> Gurmukhi (Punjabi), Hindi, and Devanagari — and is built so it can **never
> silently corrupt correct text**, including Gurbani.

**🌐 [Live demo & docs →](https://jsdosanj.github.io/gurmukhifix/)** — paste OCR
text and watch it become clean Unicode, entirely in your browser.

<!-- SPDX-License-Identifier: MIT -->

```
OCR engine  →  gurmukhifix  →  corrected Unicode + report + metadata
(Tesseract / Surya / Gemini / Google Vision / …)
```

---

## What it does — and what it refuses to do

OCR engines convert an image to characters but have no linguistic rules. On
Gurmukhi they make a small set of **systematic, predictable** errors:

- **Sihari misordering** — the vowel sign ਿ is drawn *before* its base consonant
  but must be encoded *after* it. `ਸਿਮਰਿ` is frequently emitted as `ਿਸਮਰਿ`.
- **I-matra misordering** (Devanagari) — the same problem for ि.
- **Nukta / dependent-vowel order** — e.g. `ਖ਼ਾਸ` emitted as `ਖਾ਼ਸ`.
- **Character confusions** where OCR picks a valid-but-wrong look-alike letter.

gurmukhifix corrects these **after** OCR. The defining principle is safety:

> **Every automatic change must clear an evidence gate.** A verbatim scripture
> (Gurbani) word is *locked* and never altered automatically. Any other edit must
> either strictly improve script-validity **or** turn a non-word into a known
> dictionary word — a blind swap between two valid characters is refused, not
> guessed at. Re-ordering the same characters into canonical order is always safe.

This matters because the target material includes sacred and heritage text, where
turning one valid word into a *different* valid word is the worst possible failure.
The guarantee is not a hope — it is [property-tested](tests/test_zero_corruption.py)
across every supported script and against the whole Gurbani corpus.

### Script support

| Script | Status | What runs |
|--------|--------|-----------|
| **Gurmukhi / Punjabi** | ✅ Primary | Sihari/nukta reordering, dictionary-gated confusion correction, Gurbani scripture lock |
| **Hindi / Devanagari** | ✅ Supported | I-matra reordering, structural validation, evidence-gated confusion correction |
| **Urdu / Farsi** | 🧪 Experimental | Structural validation only. Diacritic heuristics are evidence-gated and do **not** fire without a validity or dictionary signal, so no accuracy is claimed yet |

> "Hindi" and "Devanagari" share the Devanagari script; the two config names exist
> so Hindi-specific rules can layer on top of the shared Devanagari base.

---

## Install

```bash
pip install gurmukhifix
```

Python 3.10+. No system OCR libraries required — gurmukhifix processes OCR *output*,
so your OCR engine is a peer, not a runtime dependency.

## First correction in 30 seconds

```bash
gurmukhifix demo --lang gurmukhi
```

```
Sample [gurmukhi]: gurmukhi.json
  OCR input : ਗੁਰਮੁਖਿ ਜਾਪੈ ਸਬਦਿ ਿਲਵ ਲਾਇ
  Corrected : ਗੁਰਮੁਖਿ ਜਾਪੈ ਸਬਦਿ ਲਿਵ ਲਾਇ
  1 fix(es) : 'ਿਲ'→'ਲਿ' (sihari_order_fix)
```

## Quickstart on your own scans

Stock Tesseract emits TSV and hOCR (it has **no** JSON renderer) — feed either
straight in:

```bash
# 1. OCR your page with any engine. With Tesseract:
tesseract my_gurmukhi_page.png out --oem 1 --psm 6 tsv

# 2. Correct it (format auto-detected):
gurmukhifix correct --input out.tsv --lang gurmukhi --output ./results

# 3. Read the results
cat ./results/corrected_text.txt
```

### Python API

```python
from gurmukhifix import process_document

# Feed OCR output from any supported engine: a dict, a file path, a plain string,
# or a list of word dicts.
result = process_document({"words": [{"text": "ਿਸਮਰ", "conf": 72}]}, "gurmukhi")

print(result["corrected_text"])   # ਸਿਮਰ
print(result["correction_report"])
```

---

## Supported OCR formats

gurmukhifix is **OCR-engine-agnostic**. `process_document` (and `gurmukhifix
correct`) auto-detect the format; run `gurmukhifix formats` to list them:

| Format | Source |
|--------|--------|
| `tesseract_json` | Tesseract `--output-type json` |
| `tesseract_tsv`  | Tesseract `tsv` / `image_to_data` |
| `hocr`           | hOCR (Tesseract, OCRopus, Kraken) |
| `alto`           | ALTO XML (library / heritage pipelines) |
| `surya`          | [Surya](https://github.com/VikParuchuri/surya) OCR JSON |
| `google_vision`  | Google Cloud Vision / Gemini document JSON |
| `text`           | plain UTF-8 text |
| generic          | a Python `list` of `{text, conf, bbox}` dicts |

Because transformer OCR (Surya, Gemini, TrOCR) now beats Tesseract on Indic and
Nastaliq scripts, this layer keeps gurmukhifix useful no matter which engine wins.

Each word record is `{"text": str, "conf": 0–100, "bbox": [x, y, w, h],
"alternatives": [...]}`. Confidence bands: ≥ 85 passes through unchanged, 60–85 is
fully corrected, < 60 is flagged for human review.

---

## Accuracy

The benchmark runs on **real verbatim Gurbani** — 300 lines of Sri Guru Granth
Sahib Ji ([`tests/ground_truth/gurbani_sggs.txt`](tests/ground_truth/)) — into
which the most common Tesseract Gurmukhi error (word-initial sihari misordering) is
injected. It reports Character Error Rate of the corrupted text vs gurmukhifix's
output, both against the truth:

| Language | Lines w/ injected error | Baseline CER | Corrected CER | Clean text corrupted? |
|----------|------------------------:|-------------:|--------------:|----------------------:|
| gurmukhi | 148 / 300 | 0.0776 | **0.0000** | none |

```bash
python -m tests.benchmark   # reproduce
```

**Honest scope:** this measures the engine's ability to reverse a *documented,
targeted* error class on real Gurbani — not end-to-end accuracy on a scanned
manuscript, which needs a human-labelled scan corpus. Drop paired
`{"language","ocr","truth"}` JSON into `tests/ground_truth/` and it is folded in
automatically. The clean lines double as a corruption check: their corrected CER
must stay `0.0000`.

---

## How it works

| Module | Role |
|--------|------|
| `evidence.py` | The evidence gate — the single rule every automatic change must clear |
| `lexicon.py` | Gurbani + Punjabi word lists (scripture lock + dictionary evidence) |
| `validator.py` | Script-grammar validity ("badness") scoring |
| `corrector.py` | Evidence-gated confusion/diacritic correction |
| `diacritic.py` | Sihari / i-matra / nukta reordering |
| `ligature.py` | Ligature / conjunct handling |
| `ocr.py` | OCR-engine-agnostic input adapters |
| `integration.py` | Pipeline orchestration + output artifacts |
| `learner.py` | SQLite store; promotes a correction after 10 confirmations (a frequency threshold, not a Bayesian model) |

The lexicon is derived from the [Shabad OS database](https://github.com/shabados/database);
see [`gurmukhifix/data/LEXICON.md`](gurmukhifix/data/LEXICON.md) for provenance.

---

## Output artifacts

Each `gurmukhifix correct` / `batch` run writes:

| File | Contents |
|------|----------|
| `corrected_text.txt` | Final corrected Unicode text |
| `correction_report.json` | Every correction: original, corrected, rule, position, bbox |
| `metadata.json` | Per-region confidence, flags, Tesseract alternatives preserved |
| `flagged.json` | Regions below the review threshold or still structurally invalid |

## Per-corpus learning

Confirmed corrections are stored in SQLite; once a pattern is confirmed 10+ times it
is promoted. Promoted corrections are still run through the evidence gate — they
apply in the context they were confirmed and **never** override the scripture lock.

```bash
gurmukhifix review --flagged ./results/flagged.json --corrections ./my.db
gurmukhifix report --corrections ./my.db --lang gurmukhi
```

---

## Development

```bash
pip install -e ".[dev]"
pytest                      # full suite incl. property-based no-corruption tests
python -m tests.benchmark   # accuracy benchmark
ruff check . && mypy gurmukhifix   # lint + types
```

Every bug fix must ship with a regression test using the exact input that exposed
it. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Releasing

Publishes to PyPI from a GitHub Release via Trusted Publishing — see
[PUBLISHING.md](PUBLISHING.md).

## License

**MIT** — free and open source for any use, including commercial. See [LICENSE](LICENSE).

## Acknowledgements

- **[Shabad OS](https://github.com/shabados/database)** and **[BaniDB](https://banidb.com)** —
  the Gurbani corpus behind the lexicon and benchmark.
- **Tesseract**, **Surya**, and the transformer-OCR community — the engines whose
  output this tool corrects.
- The Unicode Consortium — Gurmukhi, Devanagari, and Arabic block documentation.
