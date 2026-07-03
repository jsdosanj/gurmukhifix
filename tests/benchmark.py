"""Accuracy benchmark for gurmukhifix — honest, reproducible, on real Gurbani.

What this measures
------------------
Ground truth is **real verbatim scripture** (``tests/ground_truth/gurbani_sggs.txt``:
300 lines of Sri Guru Granth Sahib Ji from the Shabad OS corpus). Into that clean
text we inject a *documented, systematic* OCR error — the single most common
Tesseract failure on Gurmukhi: a **word-initial sihari** (ਿ) emitted before its
base consonant (its visual position) instead of after it (its Unicode order), e.g.
``ਸਿਮਰਿ`` OCR'd as ``ਿਸਮਰਿ``. We then measure Character/Word Error Rate of the
corrupted text (baseline) versus gurmukhifix's output, both against the truth.

Honest scope
------------
* This is **synthetic error injection on real Gurbani text** — it measures how well
  the engine reverses a known, targeted error class, not end-to-end accuracy on a
  scanned manuscript. The latter needs a human-labelled scan corpus; drop paired
  ``{"language","ocr","truth"}`` JSON files into ``tests/ground_truth/`` and they
  are folded into the report automatically.
* Lines with no injectable error are still run through the engine: their corrected
  CER must stay **0.0** — proof the engine does not corrupt clean scripture.
* Urdu/Farsi are experimental (structural-only) and carry **no accuracy claim**.

Usage::

    python -m tests.benchmark
"""

from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path
from typing import Any

import regex

from gurmukhifix.integration import process_document

_GT_DIR = Path(__file__).parent / "ground_truth"
_SIHARI = "ਿ"
_GURMUKHI_CONSONANT = regex.compile(r"[ਕ-ਹਖ਼-ਫ਼]")

# Real truth-only corpora: filename -> language.
_CORPORA = {"gurbani_sggs.txt": "gurmukhi"}


# ── Metrics ─────────────────────────────────────────────────────────────────


def _edit_distance(a: list[Any] | str, b: list[Any] | str) -> int:
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return la or lb
    prev = list(range(lb + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * lb
        for j, cb in enumerate(b, 1):
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (0 if ca == cb else 1))
        prev = curr
    return prev[lb]


def character_error_rate(hyp: str, ref: str) -> float:
    return 0.0 if not ref else _edit_distance(hyp, ref) / len(ref)


def word_error_rate(hyp: str, ref: str) -> float:
    ref_w, hyp_w = ref.split(), hyp.split()
    return 0.0 if not ref_w else _edit_distance(hyp_w, ref_w) / len(ref_w)


# ── Documented OCR-error injection ──────────────────────────────────────────


def inject_word_initial_sihari(text: str) -> tuple[str, int]:
    """Simulate the word-initial-sihari Tesseract error; return (ocr_text, n_errors).

    For each word beginning consonant + sihari (the correct Unicode order), emit
    the sihari first (its visual position) — the exact systematic misrecognition
    the engine is built to reverse.
    """
    out_words: list[str] = []
    n = 0
    for word in text.split(" "):
        if (
            len(word) >= 2
            and _GURMUKHI_CONSONANT.match(word[0])
            and word[1] == _SIHARI
        ):
            out_words.append(_SIHARI + word[0] + word[2:])
            n += 1
        else:
            out_words.append(word)
    return " ".join(out_words), n


# ── Runner ──────────────────────────────────────────────────────────────────


def _load_pairs() -> list[dict[str, Any]]:
    """Build (language, ocr, truth) samples from real corpora + any paired JSON."""
    pairs: list[dict[str, Any]] = []

    for filename, language in _CORPORA.items():
        path = _GT_DIR / filename
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            truth = unicodedata.normalize("NFC", line.strip())
            if not truth:
                continue
            ocr, n = inject_word_initial_sihari(truth)
            pairs.append({"language": language, "ocr": ocr, "truth": truth, "injected": n})

    # Real human-labelled scan samples, if any were dropped in.
    for path in sorted(_GT_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for entry in data if isinstance(data, list) else []:
            entry.setdefault("injected", 1)
            pairs.append(entry)

    return pairs


def run_benchmark() -> dict[str, Any]:
    per_lang: dict[str, dict[str, list[float]]] = {}
    for entry in _load_pairs():
        lang, ocr, truth = entry["language"], entry["ocr"], entry["truth"]
        injected = entry.get("injected", 0)
        bucket = per_lang.setdefault(
            lang,
            {"base_cer": [], "corr_cer": [], "base_wer": [], "corr_wer": [],
             "err_base_cer": [], "err_corr_cer": [], "clean_corr_cer": []},
        )
        corrected = process_document(ocr, lang)["corrected_text"]
        b_cer, c_cer = character_error_rate(ocr, truth), character_error_rate(corrected, truth)
        bucket["base_cer"].append(b_cer)
        bucket["corr_cer"].append(c_cer)
        bucket["base_wer"].append(word_error_rate(ocr, truth))
        bucket["corr_wer"].append(word_error_rate(corrected, truth))
        (bucket["err_base_cer"] if injected else bucket["clean_corr_cer"]).append(b_cer if injected else c_cer)
        if injected:
            bucket["err_corr_cer"].append(c_cer)

    def avg(xs: list[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    summary: dict[str, Any] = {}
    for lang, m in per_lang.items():
        n = len(m["base_cer"])
        base_cer, corr_cer = avg(m["base_cer"]), avg(m["corr_cer"])
        summary[lang] = {
            "samples": n,
            "with_errors": len(m["err_corr_cer"]),
            "baseline_cer": round(base_cer, 4),
            "corrected_cer": round(corr_cer, 4),
            "cer_improvement_pct": round((base_cer - corr_cer) / base_cer * 100, 2) if base_cer else 0.0,
            "baseline_wer": round(avg(m["base_wer"]), 4),
            "corrected_wer": round(avg(m["corr_wer"]), 4),
            "error_subset_baseline_cer": round(avg(m["err_base_cer"]), 4),
            "error_subset_corrected_cer": round(avg(m["err_corr_cer"]), 4),
            "clean_subset_corrupted": round(avg(m["clean_corr_cer"]), 6),  # must be 0.0
        }
    return summary


def print_table(summary: dict[str, Any]) -> None:
    print("| Language | Samples | w/ errors | Baseline CER | Corrected CER | CER Δ | Clean-text corrupted? |")
    print("|----------|--------:|----------:|-------------:|--------------:|------:|----------------------:|")
    for lang, m in summary.items():
        corrupted = "none ✓" if m["clean_subset_corrupted"] == 0 else f"{m['clean_subset_corrupted']:.4f} ✗"
        print(
            f"| {lang} | {m['samples']} | {m['with_errors']} | {m['baseline_cer']:.4f} | "
            f"{m['corrected_cer']:.4f} | {m['cer_improvement_pct']:+.1f}% | {corrupted} |"
        )


def main() -> int:
    """Run the benchmark. Hard gates: no CER regression, and zero clean-text corruption."""
    argparse.ArgumentParser(description="gurmukhifix accuracy benchmark").parse_args()
    print("Running benchmark on real Gurbani with injected word-initial-sihari OCR errors …\n")
    summary = run_benchmark()
    print_table(summary)
    print("\nReproduce: python -m tests.benchmark")
    print("Scope: synthetic injection of a documented Tesseract error class on real")
    print("SGGS text — not end-to-end scan accuracy. See tests/benchmark.py docstring.\n")

    regressions = [lang for lang, m in summary.items() if m["corrected_cer"] > m["baseline_cer"] + 1e-9]
    corruptions = [lang for lang, m in summary.items() if m["clean_subset_corrupted"] > 1e-9]
    if regressions:
        print("✗ REGRESSION (corrected worse than raw OCR): " + ", ".join(sorted(regressions)))
        return 1
    if corruptions:
        print("✗ CORRUPTION (clean scripture altered): " + ", ".join(sorted(corruptions)))
        return 1
    print("✓ No regression and no clean-text corruption on any script.")
    for lang, m in summary.items():
        if m["with_errors"]:
            print(
                f"  {lang}: on {m['with_errors']} lines with injected errors, "
                f"CER {m['error_subset_baseline_cer']:.4f} → {m['error_subset_corrected_cer']:.4f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
