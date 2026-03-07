# gurmukhifix / scriptfix

> Tesseract OCR post-processing engine for handwritten South Asian and Persian scripts.
> Corrects character misrecognition, ligature errors, and diacritic placement for
> **Gurmukhi, Punjabi, Hindi, Urdu, and Farsi**.

<!-- SPDX-License-Identifier: MIT -->

```
Image  →  Tesseract (JSON)  →  scriptfix  →  Corrected Text
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
             corrected_text  correction_report  metadata
                .txt            .json            .json
```

---

## Why this exists

Tesseract performs poorly on handwritten South Asian and Persian scripts.
Character misrecognition rates for handwritten Gurmukhi and Urdu frequently
exceed 30–40%. The failure modes are systematic and predictable:

- **Gurmukhi / Punjabi** — sihari placement errors (the vowel sign ਿ appears
  visually before its base consonant but must follow it in Unicode); tippi/bindi
  nasalization confusion; aspirated consonant pair misreads.
- **Hindi (Devanagari)** — matra attachment errors; anusvara vs chandrabindu
  confusion; sibilant ambiguity (श, ष, स).
- **Urdu (Nastaliq)** — nukta placement errors (ب vs پ, د vs ذ) that change
  word meaning; hamza carrier ambiguity; connected-letter breaks.
- **Farsi (Persian)** — yeh variant encoding (ي vs ی vs ى); kaf/gaf confusion;
  Farsi-specific letters (پ چ ژ گ) misread as Arabic equivalents.

These are connected scripts with extensive diacritic systems and ligature rules.
Historical orthography variation in manuscript material makes the problem harder
than printed-text OCR. No open post-processing layer existed for all five scripts
combined. **scriptfix** addresses that gap.

---

## Why Python

Python is the implementation language because:

- **indic-nlp-library** provides Devanagari and Gurmukhi tokenization.
- **hazm** provides Farsi/Urdu NLP utilities.
- Python's Unicode support (`unicodedata`, `regex`) is mature enough for
  codepoint-level manipulation across all five Unicode blocks.
- **pytesseract** and other Tesseract Python wrappers already use Python;
  scriptfix integrates naturally into existing pipelines.
- The target users — researchers, archivists, digitization staff — are far more
  likely to run a `pip install` than to compile a Go or Rust binary.

The performance tradeoff (slower than a native binary) is acceptable because
the target use case is archival digitization, not real-time OCR.

---

## How it complements Tesseract

Tesseract does the heavy lifting of converting a document image into character
sequences. It has no access to linguistic rules: it does not know that a
dependent vowel cannot appear at the start of a word, or that a Gurmukhi
sihari must follow its base consonant in Unicode order even though it appears
before it visually.

**scriptfix** applies those rules after the fact. Neither tool replaces the
other:

```
┌───────────┐     ┌─────────────────────┐     ┌──────────────────┐
│  Document │     │  Tesseract OCR       │     │  scriptfix       │
│  Image    │────▶│  (image → chars,    │────▶│  (chars →        │
│           │     │   JSON output)       │     │   corrected text)│
└───────────┘     └─────────────────────┘     └──────────────────┘
```

Tesseract is run with `--oem 1 --psm 6` (or appropriate PSM for your document
layout) and `--output-type json`. scriptfix reads that JSON directly.

---

## Installation

```bash
pip install scriptfix
```

### System dependencies

- Python 3.10 or later
- No system OCR libraries required (Tesseract is a peer dependency, not a
  runtime dependency of scriptfix)

### Optional NLP extras

```bash
pip install "scriptfix[nlp]"
```

This adds `scikit-learn` for contextual classifiers.

---

## Quickstart

```bash
# 1. Run Tesseract on your document image
tesseract my_gurmukhi_page.tif output_tess --oem 1 --psm 6 json

# 2. Correct the Tesseract output
scriptfix correct --input output_tess.json --lang gurmukhi --output ./results

# 3. Inspect the outputs
cat ./results/corrected_text.txt
cat ./results/correction_report.json
cat ./results/metadata.json
```

All five languages:

```bash
scriptfix correct --input page.json --lang gurmukhi   --output ./out/gurmukhi
scriptfix correct --input page.json --lang punjabi    --output ./out/punjabi
scriptfix correct --input page.json --lang hindi      --output ./out/hindi
scriptfix correct --input page.json --lang urdu       --output ./out/urdu
scriptfix correct --input page.json --lang farsi      --output ./out/farsi
```

---

## Batch processing

```bash
scriptfix batch \
  --input-dir ./pages \
  --lang urdu \
  --output-dir ./results \
  --workers 4
```

Workers default to `CPU count − 1`. Each page is processed independently via
`ProcessPoolExecutor`. Pages with per-word confidence ≥ 85 % pass through
unchanged. Pages with confidence < 60 % are flagged for manual review without
attempting automatic correction.

---

## How to use with your own corpus

### Per-corpus tuning

scriptfix stores confirmed corrections in a SQLite database (`corrections.db`).
When a correction pattern is confirmed 10 or more times, it is automatically
promoted to the primary confusion dictionary for that script.

```bash
# Review flagged regions and add corrections to the database
# (flagged.json is written alongside the other artifacts by 'correct' and 'batch')
scriptfix review \
  --flagged ./results/flagged.json \
  --corrections ./my_corpus/corrections.db

# Generate a report of accumulated corrections
scriptfix report \
  --corrections ./my_corpus/corrections.db \
  --lang gurmukhi
```

### Custom correction profiles

To build a correction profile specific to, say, 19th-century Punjabi manuscripts:

1. Point `--corrections` at a corpus-specific database path.
2. Process all pages in your archive.
3. Review flagged regions using `scriptfix review`.
4. After 10+ confirmations per pattern, promoted pairs appear in the report.
5. Export the report and add promoted pairs to a custom YAML config by copying
   `scriptfix/configs/punjabi.yaml` and appending the promoted pairs to `confusion_pairs`.

---

## How to contribute

### Adding new language rules

Most high-level correction rules live in `scriptfix/configs/{language}.yaml`. Some
low-level script-specific handling (for example, ligature, diacritic, and
validator behaviour) is implemented in Python modules. To add or update rules:

1. Fork the repository.
2. Edit the relevant `scriptfix/configs/{language}.yaml`.
3. Add a test case in `tests/test_corrector.py` that exercises the new rule.
4. Run `pytest tests/` — all tests must pass.
5. Submit a pull request.

### Adding test cases

Every bug fix must include a regression test using the exact input that exposed
the bug. Place these in the appropriate `tests/test_*.py` file.

### Submitting corrections to the community database

If you have manually verified correction pairs for a specific corpus, you can
submit them as a pull request to `scriptfix/configs/{language}.yaml`. Each pair must
include a `note` field explaining the confusion and, where possible, a reference
to the source corpus or academic work.

### Promoting community corrections to default configs

When a correction pair accumulates 10 confirmed instances across independent
contributors, it is eligible for promotion. Open an issue with the correction
data and a maintainer will add it to the default config after review.

---

## Output artifacts

Each `scriptfix correct` or `scriptfix batch` run produces three files:

| File | Contents |
|------|----------|
| `corrected_text.txt` | Final corrected Unicode text |
| `correction_report.json` | Every correction: original, corrected, rule applied, confidence delta, bounding box |
| `metadata.json` | Per-region confidence scores, flagged uncertain regions, Tesseract alternatives preserved |

Spatial data (bounding boxes) is preserved throughout so downstream tools can
reconstruct document layout from the output.

---

## Confidence bands

| Confidence | Action |
|------------|--------|
| ≥ 85 % | Pass through unchanged (high-confidence Tesseract output) |
| 60–85 % | Full correction pipeline applied |
| < 60 % | Flagged for manual review; Tesseract alternatives preserved |

---

## Repository structure

```
scriptfix/
  configs/
    gurmukhi.yaml     ← Gurmukhi confusion pairs and rules
    punjabi.yaml      ← Punjabi-specific rules
    urdu.yaml         ← Urdu nukta and hamza rules
    hindi.yaml        ← Hindi matra and anusvara rules
    farsi.yaml        ← Farsi yeh, kaf/gaf, and joining rules
  corrector.py        ← Character Correction Engine
  validator.py        ← Script Integrity Validator
  ligature.py         ← Ligature and Conjunct Handler
  diacritic.py        ← Diacritic and Nukta Recovery
  integration.py      ← Tesseract JSON parsing and pipeline orchestration
  learner.py          ← SQLite learning and Bayesian promotion
  cli.py              ← Click CLI
tests/
  ground_truth/       ← JSON ground-truth samples (one file per language)
  test_corrector.py
  test_validator.py
  test_integration.py
  test_learner.py
  test_ligature_diacritic.py
  test_cli.py
  benchmark.py        ← CER/WER benchmark script
corrections.db        ← gitignored; created at runtime
schema.sql            ← corrections.db schema
pyproject.toml
LICENSE
README.md
```

---

## Running tests

```bash
pip install -e ".[dev]"
pytest tests/
```

Running the accuracy benchmark:

```bash
python -m tests.benchmark
```

---

## License

SPDX-License-Identifier: MIT

This project is released under the [MIT License](LICENSE).

MIT was chosen to maximise adoption: researchers, archivists, commercial
digitization firms, and government heritage projects all face different legal
constraints. MIT imposes none. It allows use in proprietary pipelines, forks
without contribution requirements, and redistribution in any form.

---

## Acknowledgements

- **Tesseract OCR** — the upstream engine whose output this tool corrects.
- **HANDS dataset** — handwritten historical document corpora used to inform
  frequency tables.
- **IIIT-HW** — handwritten word recognition datasets from IIIT Hyderabad.
- **OpenITI** — open Islamicate text corpus providing Urdu and Farsi training
  material references.
- **indic-nlp-library** — Devanagari and Gurmukhi tokenization.
- **hazm** — Farsi/Urdu NLP toolkit.
- The Gurmukhi Unicode specification and the Unicode Consortium for the
  Gurmukhi, Devanagari, and Arabic block documentation.

