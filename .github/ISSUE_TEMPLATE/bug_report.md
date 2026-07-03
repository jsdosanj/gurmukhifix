---
name: Bug report
about: Report incorrect output, a corruption, or a crash — so we can turn it into a regression test
title: "[bug] "
labels: bug
assignees: ''
---

<!--
The most valuable bug report gives us the EXACT input that misbehaves. Every bug
fix in gurmukhifix ships with a regression test built from that input, so the more
precisely you can paste it below, the faster it gets fixed and stays fixed.
-->

## What went wrong

<!-- One or two sentences. Is this wrong output, a CORRUPTION of valid/scripture
text (the most serious kind), or a crash? -->

## Exact OCR input that triggered it

<!-- REQUIRED. Paste the exact OCR text (or the minimal snippet) that produced the
bad result. Copy it verbatim, preserving the Unicode as-is — do not retype it, so
the codepoints are exactly what gurmukhifix saw. If it came from a file (TSV/hOCR/
ALTO/JSON), paste the relevant fragment. Do not include personal data. -->

```text

```

## Script / language

<!-- REQUIRED. e.g. gurmukhi, punjabi, hindi, devanagari, urdu, farsi. This picks
the config and lexicon, so the wrong answer can depend on it. -->

- Language:

## What gurmukhifix produced

```text

```

## What the correct output should be

```text

```

## Is this a corruption of valid or scripture text?

<!-- Did gurmukhifix change text that was already CORRECT (e.g. altered a valid
word, or touched verbatim Gurbani)? If so, say so clearly — this is the highest-
priority failure class and is covered by the evidence gate / scripture lock. -->

- [ ] Yes — correct/scripture text was altered
- [ ] No — the input was already wrong and the correction was just insufficient/incorrect

## Environment

- gurmukhifix version (`pip show gurmukhifix`):
- Python version:
- OCR engine that produced the input (Tesseract / Surya / Google Vision / … ):
- OS:

## Anything else

<!-- Stack trace (for a crash), the input format, or other context. -->
