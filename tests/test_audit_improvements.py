"""Tests for the audit-driven accuracy/robustness/efficiency/security fixes."""

from __future__ import annotations

import json
from pathlib import Path

from gurmukhifix.config import load_config
from gurmukhifix.corrector import CharacterCorrector
from gurmukhifix.diacritic import DiacriticRecovery
from gurmukhifix.integration import process_document
from gurmukhifix.learner import CorrectionStore
from gurmukhifix.validator import ScriptValidator


class TestPromotedFeedback:
    """Promoted, corpus-learned corrections must reach the corrector."""

    def test_promoted_pair_refused_on_scripture(self) -> None:
        # ਕਾਲ is verbatim Gurbani — a promoted swap must never silently rewrite it.
        c = CharacterCorrector("gurmukhi", promoted=[("ਕ", "ਖ")])
        out, corrections = c.correct("ਕਾਲ")
        assert out == "ਕਾਲ"
        assert corrections == []

    def test_promoted_pair_applies_with_confirmed_context(self) -> None:
        # A promotion confirmed in a specific context applies there, on a
        # non-scripture token, even at unchanged validity — the human confirmation
        # is the evidence that authorises a same-class swap.
        rules = [
            {
                "original_sequence": "ਬ",
                "corrected_sequence": "ਭ",
                "context_before": "ਕੁ",
                "context_after": "",
            }
        ]
        c = CharacterCorrector("gurmukhi", promoted=rules)
        out, corrections = c.correct("ਕੁਬ")  # confirmed context ਕੁ_ present
        # The confirmed-context promotion fires (ਬ -> ਭ). Downstream lexicon-gated
        # passes may legitimately refine the token further, so assert on the
        # recorded promoted correction rather than the exact final string.
        assert any(
            x["rule"] == "promoted_correction"
            and x["original"] == "ਬ"
            and x["corrected"] == "ਭ"
            for x in corrections
        )
        assert "ਭ" in out

    def test_promoted_swap_refused_without_evidence(self) -> None:
        # No confirmed context, no dictionary/validity gain: a blind same-validity
        # swap on clean text is refused rather than guessed at.
        c = CharacterCorrector("gurmukhi", promoted=[("ਬ", "ਭ")])
        out, corrections = c.correct("ਕੁਬ")
        assert out == "ਕੁਬ"
        assert corrections == []

    def test_without_promotion_unchanged(self) -> None:
        out, _ = CharacterCorrector("gurmukhi").correct("ਕਾਲ")
        assert out == "ਕਾਲ"  # gating leaves valid text alone

    def test_promotion_never_increases_badness(self) -> None:
        # A promoted swap that would create an invalid sequence must be refused.
        v = ScriptValidator("gurmukhi")
        c = CharacterCorrector("gurmukhi", promoted=[("ਕ", "ਾ")])  # consonant -> matra
        out, _ = c.correct("ਕ")
        assert v.badness(out) <= v.badness("ਕ")

    def test_learner_promotes_and_feeds_back(self) -> None:
        store = CorrectionStore(":memory:")
        for _ in range(10):
            store.record_correction(
                script="gurmukhi", original_sequence="ੴ", corrected_sequence="ਓ"
            )
        assert ("ੴ", "ਓ") in store.get_promoted_pairs("gurmukhi")
        # Fewer than threshold should not promote.
        for _ in range(3):
            store.record_correction(
                script="gurmukhi", original_sequence="ਃ", corrected_sequence="ਂ"
            )
        assert ("ਃ", "ਂ") not in store.get_promoted_pairs("gurmukhi")
        store.close()

    def test_store_promoted_refused_on_scripture_through_pipeline(self) -> None:
        # Even a promoted, corpus-confirmed pair must not corrupt scripture as it
        # flows through the full pipeline: ਕਾਲ is Gurbani and stays ਕਾਲ.
        store = CorrectionStore(":memory:")
        for _ in range(10):
            store.record_correction(
                script="gurmukhi", original_sequence="ਕ", corrected_sequence="ਖ"
            )
        data = {"words": [{"text": "ਕਾਲ", "conf": 70.0, "bbox": [], "alternatives": []}]}
        result = process_document(data, "gurmukhi", store=store)
        assert result["corrected_text"] == "ਕਾਲ"
        store.close()


class TestDevanagariIMatra:
    def test_imatra_reordered(self) -> None:
        out, corrections = DiacriticRecovery("hindi").recover("िकताब")
        assert out == "किताब"
        assert any(x["rule"] == "imatra_order_fix" for x in corrections)

    def test_correct_imatra_unchanged(self) -> None:
        out, corrections = DiacriticRecovery("devanagari").recover("किताब")
        assert out == "किताब"
        assert corrections == []


class TestZwnjValidity:
    def test_zwj_not_flagged_indic(self) -> None:
        assert ScriptValidator("gurmukhi").badness("ਕ‍ਰ") == 0
        assert ScriptValidator("hindi").badness("क‌ष") == 0

    def test_zwnj_not_flagged_arabic(self) -> None:
        assert ScriptValidator("urdu").badness("کتاب‌ها") == 0


class TestRobustness:
    def test_non_numeric_conf_does_not_crash(self) -> None:
        data = {"words": [{"text": "ਸਤਿ", "conf": "high", "bbox": [], "alternatives": []}]}
        result = process_document(data, "gurmukhi")
        assert isinstance(result["corrected_text"], str)

    def test_learner_uses_wal(self, tmp_path: Path) -> None:
        store = CorrectionStore(tmp_path / "c.db")
        mode = store._conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"
        store.close()


class TestConfigCache:
    def test_returns_distinct_copies(self) -> None:
        a = load_config("gurmukhi")
        b = load_config("gurmukhi")
        assert a == b
        assert a is not b  # deep-copied, safe to mutate
        a["confusion_pairs"].clear()
        assert load_config("gurmukhi")["confusion_pairs"], "cache must not be mutated"


class TestBatchPaths:
    def test_batch_mirrors_relative_paths(self, tmp_path: Path) -> None:
        from click.testing import CliRunner
        from gurmukhifix.cli import cli

        word = {"words": [{"text": "ਸਤਿ", "conf": 70.0, "bbox": [], "alternatives": []}]}
        # Two inputs that share a stem in different subdirs.
        for sub in ("a", "b"):
            d = tmp_path / "in" / sub
            d.mkdir(parents=True)
            (d / "page.json").write_text(json.dumps(word), encoding="utf-8")

        out = tmp_path / "out"
        res = CliRunner().invoke(
            cli,
            ["batch", "--input-dir", str(tmp_path / "in"), "--lang", "gurmukhi",
             "--output-dir", str(out), "--workers", "1", "--pattern", "**/*.json"],
        )
        assert res.exit_code == 0, res.output
        # Both pages produced their own output dir — no clobbering.
        assert (out / "a" / "page" / "corrected_text.txt").exists()
        assert (out / "b" / "page" / "corrected_text.txt").exists()
