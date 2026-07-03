"""Full-pipeline accuracy regression tests on real Gurbani.

These are the tests the original confusion-pair engine could never pass: run
end-to-end via ``process_document`` on real SGGS text (with a documented OCR error
class injected), gurmukhifix must never make text *worse* than the raw OCR and must
leave already-correct scripture byte-for-byte unchanged.
"""

from __future__ import annotations

import pytest

from gurmukhifix.integration import process_document
from tests.benchmark import _load_pairs, character_error_rate, run_benchmark

_SAMPLES = _load_pairs()
_CLEAN = [e for e in _SAMPLES if not e.get("injected")][:60]
_ERRORS = [e for e in _SAMPLES if e.get("injected")][:60]


def _correct(language: str, text: str) -> str:
    return process_document(text, language)["corrected_text"]


class TestNoCorruption:
    @pytest.mark.parametrize("entry", _CLEAN, ids=[e["truth"] for e in _CLEAN])
    def test_clean_scripture_is_unchanged(self, entry: dict) -> None:
        """Already-correct scripture must round-trip through the pipeline untouched."""
        out = _correct(entry["language"], entry["truth"])
        assert out == entry["truth"], (
            f"{entry['language']}: clean scripture {entry['truth']!r} was corrupted to {out!r}"
        )

    @pytest.mark.parametrize("entry", _ERRORS, ids=[e["ocr"] for e in _ERRORS])
    def test_never_worse_than_baseline(self, entry: dict) -> None:
        """Corrected CER must never exceed the raw-OCR baseline CER."""
        baseline = character_error_rate(entry["ocr"], entry["truth"])
        corrected = character_error_rate(_correct(entry["language"], entry["ocr"]), entry["truth"])
        assert corrected <= baseline + 1e-9, (
            f"{entry['language']}: CER rose {baseline:.4f} -> {corrected:.4f} on {entry['ocr']!r}"
        )


class TestRepairsRealErrors:
    @pytest.mark.parametrize("entry", _ERRORS, ids=[e["ocr"] for e in _ERRORS])
    def test_injected_sihari_errors_are_fixed(self, entry: dict) -> None:
        """Word-initial-sihari OCR errors on real Gurbani must be repaired to truth."""
        assert _correct(entry["language"], entry["ocr"]) == entry["truth"]

    def test_orphaned_sihari_is_reordered(self) -> None:
        assert _correct("gurmukhi", "ਿਸੱਖ") == "ਸਿੱਖ"


class TestBenchmarkGate:
    def test_no_regression_and_no_clean_corruption(self) -> None:
        summary = run_benchmark()
        assert summary, "benchmark produced no results"
        for lang, m in summary.items():
            assert m["corrected_cer"] <= m["baseline_cer"] + 1e-9, f"{lang} regressed CER"
            assert m["clean_subset_corrupted"] <= 1e-9, f"{lang} corrupted clean text"
