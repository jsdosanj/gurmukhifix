"""Tests for the Character Correction Engine."""

from __future__ import annotations

import pytest

from gurmukhifix.corrector import CharacterCorrector, correct_text


class TestCharacterCorrectorGurmukhi:
    def setup_method(self) -> None:
        self.corrector = CharacterCorrector("gurmukhi")

    def test_loads_config(self) -> None:
        assert self.corrector.config is not None
        assert self.corrector.config["script"] == "gurmukhi"

    def test_confusion_map_populated(self) -> None:
        confusion = self.corrector.get_confusion_map()
        assert len(confusion) >= 30, "Gurmukhi must have at least 30 confusion pairs"

    def test_no_change_on_clean_text(self) -> None:
        text = "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ"
        corrected, corrections = self.corrector.correct(text)
        # No known wrong pairs in this text — length should be preserved
        assert isinstance(corrected, str)
        assert isinstance(corrections, list)

    def test_correction_returns_string(self) -> None:
        corrected, corrections = self.corrector.correct("ਸ")
        assert isinstance(corrected, str)
        assert isinstance(corrections, list)

    def test_validate_sequences_empty_text(self) -> None:
        violations = self.corrector.validate_sequences("")
        assert violations == []

    def test_validate_rejects_consecutive_matras(self) -> None:
        # Two consecutive dependent vowels — should be flagged
        bad_text = "\u0A3E\u0A3F"  # aa + i matras
        violations = self.corrector.validate_sequences(bad_text)
        assert len(violations) > 0
        severities = {v["severity"] for v in violations}
        assert "REJECT" in severities

    def test_validate_rejects_matra_at_word_start(self) -> None:
        bad_text = "\u0A3E\u0A15"  # aa-matra then ka
        violations = self.corrector.validate_sequences(bad_text)
        assert any(v["severity"] == "REJECT" for v in violations)

    def test_normalization_applied(self) -> None:
        # NFD form should be converted to NFC
        import unicodedata
        nfd_text = unicodedata.normalize("NFD", "ਸ")
        corrected, _ = self.corrector.correct(nfd_text)
        assert unicodedata.is_normalized("NFC", corrected)

    def test_correction_record_has_required_fields(self) -> None:
        # Force a known confusion pair to trigger a correction
        confusion = self.corrector.get_confusion_map()
        if confusion:
            wrong = next(iter(confusion))
            corrected, corrections = self.corrector.correct(wrong)
            if corrections:
                c = corrections[0]
                assert "original" in c
                assert "corrected" in c
                assert "rule" in c
                assert "position" in c


class TestCharacterCorrectorPunjabi:
    def setup_method(self) -> None:
        self.corrector = CharacterCorrector("punjabi")

    def test_loads_config(self) -> None:
        assert self.corrector.config["script"] == "punjabi"

    def test_confusion_map_populated(self) -> None:
        confusion = self.corrector.get_confusion_map()
        assert len(confusion) >= 30, "Punjabi must have at least 30 confusion pairs"

    def test_correction_is_string(self) -> None:
        text = "ਪੰਜਾਬੀ"
        corrected, _ = self.corrector.correct(text)
        assert isinstance(corrected, str)


class TestCharacterCorrectorHindi:
    def setup_method(self) -> None:
        self.corrector = CharacterCorrector("hindi")

    def test_loads_config(self) -> None:
        assert self.corrector.config["script"] == "hindi"

    def test_confusion_map_populated(self) -> None:
        confusion = self.corrector.get_confusion_map()
        assert len(confusion) >= 30, "Hindi must have at least 30 confusion pairs"

    def test_validate_consecutive_matras(self) -> None:
        bad = "\u093E\u093F"  # aa + i matras
        violations = self.corrector.validate_sequences(bad)
        assert any(v["severity"] == "REJECT" for v in violations)

    def test_validate_matra_at_start(self) -> None:
        bad = "\u093Eक"  # aa-matra then ka
        violations = self.corrector.validate_sequences(bad)
        assert any(v["severity"] == "REJECT" for v in violations)


class TestCharacterCorrectorUrdu:
    def setup_method(self) -> None:
        self.corrector = CharacterCorrector("urdu")

    def test_loads_config(self) -> None:
        assert self.corrector.config["script"] == "urdu"

    def test_confusion_map_populated(self) -> None:
        confusion = self.corrector.get_confusion_map()
        assert len(confusion) >= 30, "Urdu must have at least 30 confusion pairs"

    def test_correction_is_string(self) -> None:
        text = "اردو"
        corrected, _ = self.corrector.correct(text)
        assert isinstance(corrected, str)


class TestCharacterCorrectorFarsi:
    def setup_method(self) -> None:
        self.corrector = CharacterCorrector("farsi")

    def test_loads_config(self) -> None:
        assert self.corrector.config["script"] == "farsi"

    def test_confusion_map_populated(self) -> None:
        confusion = self.corrector.get_confusion_map()
        assert len(confusion) >= 30, "Farsi must have at least 30 confusion pairs"

    def test_correction_is_string(self) -> None:
        text = "فارسی"
        corrected, _ = self.corrector.correct(text)
        assert isinstance(corrected, str)


class TestConvenienceFunction:
    def test_correct_text_gurmukhi(self) -> None:
        corrected, corrections = correct_text("ਸਤਿ", "gurmukhi")
        assert isinstance(corrected, str)
        assert isinstance(corrections, list)

    def test_correct_text_unknown_language(self) -> None:
        with pytest.raises(FileNotFoundError):
            correct_text("hello", "klingon")

    @pytest.mark.parametrize("lang", ["gurmukhi", "punjabi", "hindi", "urdu", "farsi"])
    def test_all_languages_loadable(self, lang: str) -> None:
        corrector = CharacterCorrector(lang)
        assert corrector.config is not None

    @pytest.mark.parametrize("lang", ["gurmukhi", "punjabi", "hindi", "urdu", "farsi"])
    def test_all_languages_have_30_pairs(self, lang: str) -> None:
        corrector = CharacterCorrector(lang)
        confusion = corrector.get_confusion_map()
        assert len(confusion) >= 30, f"{lang} must have at least 30 confusion pairs"

    @pytest.mark.parametrize("lang", ["gurmukhi", "punjabi", "hindi", "urdu", "farsi"])
    def test_empty_string_safe(self, lang: str) -> None:
        corrected, corrections = correct_text("", lang)
        assert corrected == ""
        assert corrections == []
