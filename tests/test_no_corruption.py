"""Full-pipeline accuracy regression tests.

These are the tests that the original confusion-pair engine could never pass:
they assert that scriptfix, run end-to-end via ``process_document``, never makes
text *worse* than the raw Tesseract output, and that it leaves already-correct
text byte-for-byte unchanged. Type/plumbing assertions elsewhere in the suite do
not catch a corrupting corrector — these do.
"""

from __future__ import annotations

import pytest

from scriptfix.integration import process_document
from tests.benchmark import GROUND_TRUTH, character_error_rate, run_benchmark


def _correct(language: str, text: str) -> str:
    """Run a single word/phrase through the full pipeline at the correction band."""
    words = [
        {"text": w, "conf": 70.0, "bbox": [], "alternatives": []}
        for w in text.split()
    ]
    result = process_document({"words": words}, language)
    return result["corrected_text"]


# Entries whose OCR text already equals the truth: the pipeline must be a no-op.
CLEAN_ENTRIES = [e for e in GROUND_TRUTH if e["ocr"] == e["truth"]]
# Misordered-sihari samples: a dependent sihari (ਿ) emitted before its base
# consonant. These are the systematic errors the engine is designed to repair —
# unlike e.g. word-segmentation errors, which it must not guess at.
SIHARI_ERROR_ENTRIES = [
    e
    for e in GROUND_TRUTH
    if e["ocr"] != e["truth"] and any(w.startswith("ਿ") for w in e["ocr"].split())
]


class TestNoCorruption:
    @pytest.mark.parametrize(
        "entry", CLEAN_ENTRIES, ids=[e["truth"] for e in CLEAN_ENTRIES]
    )
    def test_clean_text_is_unchanged(self, entry: dict) -> None:
        """Already-correct text must round-trip through the pipeline untouched."""
        out = _correct(entry["language"], entry["ocr"])
        assert out == entry["truth"], (
            f"{entry['language']}: clean input {entry['ocr']!r} was corrupted "
            f"to {out!r}"
        )

    @pytest.mark.parametrize(
        "entry", GROUND_TRUTH, ids=[e["truth"] for e in GROUND_TRUTH]
    )
    def test_never_worse_than_baseline(self, entry: dict) -> None:
        """Corrected CER must never exceed the raw-Tesseract baseline CER."""
        baseline = character_error_rate(entry["ocr"], entry["truth"])
        corrected = character_error_rate(
            _correct(entry["language"], entry["ocr"]), entry["truth"]
        )
        assert corrected <= baseline + 1e-9, (
            f"{entry['language']}: scriptfix raised CER from {baseline:.4f} to "
            f"{corrected:.4f} on {entry['ocr']!r}"
        )


class TestRepairsRealErrors:
    @pytest.mark.parametrize(
        "entry", SIHARI_ERROR_ENTRIES, ids=[e["ocr"] for e in SIHARI_ERROR_ENTRIES]
    )
    def test_known_errors_are_fixed(self, entry: dict) -> None:
        """The misordered-sihari samples must be corrected to the truth."""
        out = _correct(entry["language"], entry["ocr"])
        assert out == entry["truth"], (
            f"{entry['language']}: failed to repair {entry['ocr']!r} "
            f"(got {out!r}, want {entry['truth']!r})"
        )

    def test_orphaned_sihari_is_reordered(self) -> None:
        # Sihari emitted before its base consonant must move after it.
        assert _correct("gurmukhi", "ਿਸੱਖ") == "ਸਿੱਖ"


class TestBenchmarkGate:
    def test_no_language_regresses(self) -> None:
        """The aggregate benchmark must show no per-language CER regression."""
        summary = run_benchmark()
        regressed = {
            lang: m
            for lang, m in summary.items()
            if m["corrected_cer"] > m["baseline_cer"] + 1e-9
        }
        assert not regressed, f"scriptfix regressed CER for: {sorted(regressed)}"
