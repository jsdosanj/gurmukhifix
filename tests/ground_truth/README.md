# Benchmark ground truth

`gurbani_sggs.txt` — 300 verbatim lines of **Sri Guru Granth Sahib Ji**, sampled
deterministically across the text, drawn from the Shabad OS corpus (see
[`gurmukhifix/data/LEXICON.md`](../../gurmukhifix/data/LEXICON.md) for provenance).
The Gurbani text is in the public domain.

[`tests/benchmark.py`](../benchmark.py) treats these as **truth**, injects a
documented systematic OCR error (word-initial sihari emitted before its base
consonant — the most common Tesseract Gurmukhi failure), and measures how well the
engine reverses it, while proving the clean lines are never altered.

## Adding real, human-labelled scans

Drop a JSON file here shaped as a list of paired samples:

```json
[
  { "language": "gurmukhi", "ocr": "ਿਸਮਰ ਮਨ", "truth": "ਸਿਮਰ ਮਨ" }
]
```

Every `*.json` file in this directory is folded into the benchmark automatically.
Real scanned-manuscript pairs are the most valuable contribution here: they move
the benchmark from "reverses a known injected error class" toward true end-to-end
scan accuracy.
