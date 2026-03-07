"""Accuracy Benchmark Script for scriptfix.

Computes Character Error Rate (CER) and Word Error Rate (WER) for each
supported script, comparing scriptfix-corrected output against ground truth.

Usage:
    python -m tests.benchmark [--ground-truth-dir tests/ground_truth]

Output: A Markdown table with CER/WER for baseline (raw Tesseract) vs
        scriptfix-corrected output.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ── Ground truth pairs ──────────────────────────────────────────────────────
# Each entry: {"language": str, "ocr": str (raw Tesseract), "truth": str}
GROUND_TRUTH: list[dict[str, Any]] = [
    # Gurmukhi (10 samples)
    {"language": "gurmukhi", "ocr": "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ", "truth": "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ"},
    {"language": "gurmukhi", "ocr": "ਵਾਹਿ ਗੁਰੂ", "truth": "ਵਾਹਿਗੁਰੂ"},
    {"language": "gurmukhi", "ocr": "ਪੰਜਾਬੀ ਬੋਲੀ", "truth": "ਪੰਜਾਬੀ ਬੋਲੀ"},
    {"language": "gurmukhi", "ocr": "ਗੁਰੂ ਗ੍ਰੰਥ ਸਾਹਿਬ", "truth": "ਗੁਰੂ ਗ੍ਰੰਥ ਸਾਹਿਬ"},
    {"language": "gurmukhi", "ocr": "ਅੰਮ੍ਰਿਤਸਰ", "truth": "ਅੰਮ੍ਰਿਤਸਰ"},
    {"language": "gurmukhi", "ocr": "ਭਾਈ ਗੁਰਦਾਸ", "truth": "ਭਾਈ ਗੁਰਦਾਸ"},
    {"language": "gurmukhi", "ocr": "ਸਿੱਖ ਧਰਮ", "truth": "ਸਿੱਖ ਧਰਮ"},
    {"language": "gurmukhi", "ocr": "ਨਾਨਕ ਨਾਮ", "truth": "ਨਾਨਕ ਨਾਮ"},
    {"language": "gurmukhi", "ocr": "ਸੰਗਤ ਪੰਗਤ", "truth": "ਸੰਗਤ ਪੰਗਤ"},
    {"language": "gurmukhi", "ocr": "ਖਾਲਸਾ ਪੰਥ", "truth": "ਖਾਲਸਾ ਪੰਥ"},
    # Punjabi (10 samples)
    {"language": "punjabi", "ocr": "ਪੰਜਾਬੀ ਭਾਸ਼ਾ", "truth": "ਪੰਜਾਬੀ ਭਾਸ਼ਾ"},
    {"language": "punjabi", "ocr": "ਲਾਹੌਰ ਸ਼ਹਿਰ", "truth": "ਲਾਹੌਰ ਸ਼ਹਿਰ"},
    {"language": "punjabi", "ocr": "ਗੱਲ ਕਰਨਾ", "truth": "ਗੱਲ ਕਰਨਾ"},
    {"language": "punjabi", "ocr": "ਜੱਟ ਜ਼ਮੀਨ", "truth": "ਜੱਟ ਜ਼ਮੀਨ"},
    {"language": "punjabi", "ocr": "ਪਿੰਡ ਵਾਲੇ", "truth": "ਪਿੰਡ ਵਾਲੇ"},
    {"language": "punjabi", "ocr": "ਮਾਂ ਬੋਲੀ", "truth": "ਮਾਂ ਬੋਲੀ"},
    {"language": "punjabi", "ocr": "ਸੱਭਿਆਚਾਰ", "truth": "ਸੱਭਿਆਚਾਰ"},
    {"language": "punjabi", "ocr": "ਭੰਗੜਾ ਨਾਚ", "truth": "ਭੰਗੜਾ ਨਾਚ"},
    {"language": "punjabi", "ocr": "ਕਿਸਾਨ ਵਰਗ", "truth": "ਕਿਸਾਨ ਵਰਗ"},
    {"language": "punjabi", "ocr": "ਵਿਰਸਾ ਪੰਜਾਬ", "truth": "ਵਿਰਸਾ ਪੰਜਾਬ"},
    # Hindi (10 samples)
    {"language": "hindi", "ocr": "नमस्ते दुनिया", "truth": "नमस्ते दुनिया"},
    {"language": "hindi", "ocr": "हिंदी भाषा", "truth": "हिंदी भाषा"},
    {"language": "hindi", "ocr": "भारत देश", "truth": "भारत देश"},
    {"language": "hindi", "ocr": "गांधी जी", "truth": "गांधी जी"},
    {"language": "hindi", "ocr": "राष्ट्रीय ध्वज", "truth": "राष्ट्रीय ध्वज"},
    {"language": "hindi", "ocr": "संविधान सभा", "truth": "संविधान सभा"},
    {"language": "hindi", "ocr": "स्वतंत्रता दिवस", "truth": "स्वतंत्रता दिवस"},
    {"language": "hindi", "ocr": "महात्मा गांधी", "truth": "महात्मा गांधी"},
    {"language": "hindi", "ocr": "प्रधानमंत्री", "truth": "प्रधानमंत्री"},
    {"language": "hindi", "ocr": "विश्वविद्यालय", "truth": "विश्वविद्यालय"},
    # Urdu (10 samples)
    {"language": "urdu", "ocr": "اردو زبان", "truth": "اردو زبان"},
    {"language": "urdu", "ocr": "پاکستان ملک", "truth": "پاکستان ملک"},
    {"language": "urdu", "ocr": "محبت کا پیغام", "truth": "محبت کا پیغام"},
    {"language": "urdu", "ocr": "تاریخ قدیم", "truth": "تاریخ قدیم"},
    {"language": "urdu", "ocr": "شاعری ادب", "truth": "شاعری ادب"},
    {"language": "urdu", "ocr": "فلسفہ حکمت", "truth": "فلسفہ حکمت"},
    {"language": "urdu", "ocr": "قلم کاغذ", "truth": "قلم کاغذ"},
    {"language": "urdu", "ocr": "آزادی حقوق", "truth": "آزادی حقوق"},
    {"language": "urdu", "ocr": "ہندوستان ملک", "truth": "ہندوستان ملک"},
    {"language": "urdu", "ocr": "سیاست حکومت", "truth": "سیاست حکومت"},
    # Farsi (10 samples)
    {"language": "farsi", "ocr": "زبان فارسی", "truth": "زبان فارسی"},
    {"language": "farsi", "ocr": "ایران کشور", "truth": "ایران کشور"},
    {"language": "farsi", "ocr": "شعر ادبیات", "truth": "شعر ادبیات"},
    {"language": "farsi", "ocr": "تاریخ باستان", "truth": "تاریخ باستان"},
    {"language": "farsi", "ocr": "فرهنگ هنر", "truth": "فرهنگ هنر"},
    {"language": "farsi", "ocr": "دانشگاه علم", "truth": "دانشگاه علم"},
    {"language": "farsi", "ocr": "کتاب مطالعه", "truth": "کتاب مطالعه"},
    {"language": "farsi", "ocr": "موسیقی هنر", "truth": "موسیقی هنر"},
    {"language": "farsi", "ocr": "پزشکی سلامت", "truth": "پزشکی سلامت"},
    {"language": "farsi", "ocr": "آموزش پرورش", "truth": "آموزش پرورش"},
]


# ── Metric functions ─────────────────────────────────────────────────────────

def _edit_distance(a: str, b: str) -> int:
    """Compute the Levenshtein edit distance between two strings."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev = list(range(lb + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * lb
        for j, cb in enumerate(b, 1):
            curr[j] = min(
                prev[j] + 1,
                curr[j - 1] + 1,
                prev[j - 1] + (0 if ca == cb else 1),
            )
        prev = curr
    return prev[lb]


def character_error_rate(hypothesis: str, reference: str) -> float:
    """CER = edit_distance(hyp, ref) / len(ref)."""
    if not reference:
        return 0.0
    return _edit_distance(hypothesis, reference) / len(reference)


def word_error_rate(hypothesis: str, reference: str) -> float:
    """WER = edit_distance(hyp_words, ref_words) / len(ref_words)."""
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    if not ref_words:
        return 0.0
    return _edit_distance(hyp_words, ref_words) / len(ref_words)  # type: ignore[arg-type]


# ── Benchmark runner ─────────────────────────────────────────────────────────

def run_benchmark(
    ground_truth: list[dict[str, Any]] | None = None,
    ground_truth_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Run the benchmark and return per-language CER/WER metrics.

    Args:
        ground_truth: List of {"language", "ocr", "truth"} dicts.
        ground_truth_dir: Directory of JSON files following the same schema.
    """
    from scriptfix.integration import process_document

    if ground_truth is None:
        ground_truth = []

    if ground_truth_dir is not None:
        for f in sorted(Path(ground_truth_dir).glob("*.json")):
            with f.open(encoding="utf-8") as fh:
                entries = json.load(fh)
                if isinstance(entries, list):
                    ground_truth.extend(entries)

    if not ground_truth:
        ground_truth = GROUND_TRUTH

    results: dict[str, dict[str, list[float]]] = {}

    for entry in ground_truth:
        lang = entry["language"]
        ocr_text: str = entry["ocr"]
        truth: str = entry["truth"]

        if lang not in results:
            results[lang] = {"baseline_cer": [], "corrected_cer": [], "baseline_wer": [], "corrected_wer": []}

        # Baseline (raw Tesseract OCR — no correction)
        baseline_cer = character_error_rate(ocr_text, truth)
        baseline_wer = word_error_rate(ocr_text, truth)

        # Corrected
        tess_data = {"words": [{"text": w, "conf": 70.0, "bbox": [], "alternatives": []} for w in ocr_text.split()]}
        result = process_document(tess_data, lang)
        corrected_text = result["corrected_text"]
        corrected_cer = character_error_rate(corrected_text, truth)
        corrected_wer = word_error_rate(corrected_text, truth)

        results[lang]["baseline_cer"].append(baseline_cer)
        results[lang]["corrected_cer"].append(corrected_cer)
        results[lang]["baseline_wer"].append(baseline_wer)
        results[lang]["corrected_wer"].append(corrected_wer)

    summary: dict[str, Any] = {}
    for lang, metrics in results.items():
        n = len(metrics["baseline_cer"])
        avg_baseline_cer = sum(metrics["baseline_cer"]) / n
        avg_corrected_cer = sum(metrics["corrected_cer"]) / n
        avg_baseline_wer = sum(metrics["baseline_wer"]) / n
        avg_corrected_wer = sum(metrics["corrected_wer"]) / n
        cer_improvement = (
            (avg_baseline_cer - avg_corrected_cer) / avg_baseline_cer * 100
            if avg_baseline_cer > 0
            else 0.0
        )
        summary[lang] = {
            "samples": n,
            "baseline_cer": round(avg_baseline_cer, 4),
            "corrected_cer": round(avg_corrected_cer, 4),
            "cer_improvement_pct": round(cer_improvement, 2),
            "baseline_wer": round(avg_baseline_wer, 4),
            "corrected_wer": round(avg_corrected_wer, 4),
        }

    return summary


def print_table(summary: dict[str, Any]) -> None:
    """Print a Markdown table of benchmark results."""
    header = "| Language | Samples | Baseline CER | Corrected CER | CER Improvement | Baseline WER | Corrected WER |"
    sep =    "|----------|---------|--------------|---------------|-----------------|--------------|---------------|"
    print(header)
    print(sep)
    for lang, m in summary.items():
        print(
            f"| {lang:<8} | {m['samples']:>7} | "
            f"{m['baseline_cer']:.4f}       | "
            f"{m['corrected_cer']:.4f}         | "
            f"{m['cer_improvement_pct']:>+.1f}%           | "
            f"{m['baseline_wer']:.4f}       | "
            f"{m['corrected_wer']:.4f}         |"
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="scriptfix accuracy benchmark")
    parser.add_argument(
        "--ground-truth-dir",
        default=str(Path(__file__).parent / "ground_truth"),
        help="Directory containing ground truth JSON files.",
    )
    args = parser.parse_args()

    print("Running benchmark …\n")
    summary = run_benchmark(ground_truth_dir=args.ground_truth_dir)
    print_table(summary)
    print()

    # Check minimum acceptable improvement
    improvements = [m["cer_improvement_pct"] for m in summary.values()]
    if improvements:
        avg_improvement = sum(improvements) / len(improvements)
        print(f"Average CER improvement: {avg_improvement:+.1f}%")
        if avg_improvement >= 15.0:
            print("✓ Meets 15% minimum CER improvement target.")
        else:
            print("✗ Does NOT meet 15% minimum CER improvement target.")
