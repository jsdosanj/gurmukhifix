"""Tests for the Learning and Adaptation Layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from scriptfix.learner import CorrectionStore


class TestCorrectionStore:
    def setup_method(self) -> None:
        # Each test gets a fresh in-memory database
        self.store = CorrectionStore(":memory:")

    def teardown_method(self) -> None:
        self.store.close()

    def test_record_correction(self) -> None:
        row_id = self.store.record_correction(
            script="gurmukhi",
            original_sequence="ਨ",
            corrected_sequence="ਣ",
            context_before="ਕ",
            context_after="ਾ",
            source_document="test_doc.pdf",
            reviewer_id="test_user",
        )
        assert row_id is not None
        assert row_id > 0

    def test_stats_accumulate(self) -> None:
        for _ in range(3):
            self.store.record_correction(
                script="hindi",
                original_sequence="न",
                corrected_sequence="ण",
            )
        stats = self.store.get_stats("hindi")
        assert len(stats) == 1
        assert stats[0]["count"] == 3

    def test_promotion_at_threshold(self) -> None:
        for _ in range(10):
            self.store.record_correction(
                script="urdu",
                original_sequence="ب",
                corrected_sequence="پ",
            )
        promoted = self.store.get_promoted_corrections("urdu")
        assert len(promoted) == 1
        assert promoted[0]["original_sequence"] == "ب"

    def test_no_premature_promotion(self) -> None:
        for _ in range(9):
            self.store.record_correction(
                script="farsi",
                original_sequence="ک",
                corrected_sequence="گ",
            )
        promoted = self.store.get_promoted_corrections("farsi")
        assert len(promoted) == 0

    def test_get_recent_corrections(self) -> None:
        self.store.record_correction(
            script="gurmukhi",
            original_sequence="ਰ",
            corrected_sequence="ਲ",
        )
        recent = self.store.get_recent_corrections(limit=10)
        assert len(recent) == 1
        assert recent[0]["original_sequence"] == "ਰ"

    def test_generate_report(self) -> None:
        self.store.record_correction(
            script="punjabi",
            original_sequence="ਸ",
            corrected_sequence="ਸ਼",
        )
        report = self.store.generate_report("punjabi")
        assert report["script"] == "punjabi"
        assert report["total_corrections"] == 1
        assert report["unique_patterns"] == 1

    def test_extract_context(self) -> None:
        text = "hello world foo"
        before, after = CorrectionStore.extract_context(text, 6, window=3)
        assert before == "lo "
        assert after == "wor"

    def test_context_clipped_to_10(self) -> None:
        self.store.record_correction(
            script="hindi",
            original_sequence="क",
            corrected_sequence="ख",
            context_before="a" * 20,  # should be clipped to 10
            context_after="b" * 20,
        )
        recent = self.store.get_recent_corrections(1)
        assert len(recent[0]["context_before"]) <= 10
        assert len(recent[0]["context_after"]) <= 10

    def test_file_based_db(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        store = CorrectionStore(db_path)
        store.record_correction(
            script="hindi",
            original_sequence="क",
            corrected_sequence="ख",
        )
        store.close()
        assert db_path.exists()

    def test_context_manager(self, tmp_path: Path) -> None:
        db_path = tmp_path / "ctx.db"
        with CorrectionStore(db_path) as store:
            store.record_correction(
                script="urdu",
                original_sequence="د",
                corrected_sequence="ذ",
            )
        # Connection should be closed without error
        assert db_path.exists()

    def test_get_stats_all_scripts(self) -> None:
        self.store.record_correction(script="gurmukhi", original_sequence="ਕ", corrected_sequence="ਖ")
        self.store.record_correction(script="hindi", original_sequence="क", corrected_sequence="ख")
        all_stats = self.store.get_stats()
        assert len(all_stats) == 2
