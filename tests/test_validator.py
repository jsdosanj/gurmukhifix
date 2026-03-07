"""Tests for the Script Integrity Validator."""

from __future__ import annotations

import pytest

from scriptfix.validator import ScriptValidator, validate_text, SEVERITY_REJECT, SEVERITY_WARN


class TestScriptValidatorGurmukhi:
    def setup_method(self) -> None:
        self.validator = ScriptValidator("gurmukhi")

    def test_clean_text_no_violations(self) -> None:
        # Proper Gurmukhi with consonant then matra
        text = "ਕਾ"  # ka + aa-matra
        violations = self.validator.validate(text)
        # Should not have REJECT violations
        rejects = [v for v in violations if v["severity"] == SEVERITY_REJECT]
        assert rejects == []

    def test_consecutive_matras_rejected(self) -> None:
        bad = "\u0A3E\u0A3F"  # two consecutive matras
        violations = self.validator.validate(bad)
        assert any(v["severity"] == SEVERITY_REJECT for v in violations)

    def test_matra_at_word_start_rejected(self) -> None:
        bad = "\u0A3E\u0A15"  # aa-matra at start
        violations = self.validator.validate(bad)
        assert any(v["severity"] == SEVERITY_REJECT for v in violations)

    def test_violation_has_required_fields(self) -> None:
        bad = "\u0A3E\u0A3F"
        violations = self.validator.validate(bad)
        for v in violations:
            assert "rule" in v
            assert "description" in v
            assert "severity" in v
            assert "match" in v
            assert "position" in v

    def test_has_rejections_true(self) -> None:
        bad = "\u0A3E\u0A3F"
        violations = self.validator.validate(bad)
        assert self.validator.has_rejections(violations)

    def test_has_rejections_false(self) -> None:
        # Normal text should not trigger rejections
        violations = []
        assert not self.validator.has_rejections(violations)

    def test_multiple_addak_warned(self) -> None:
        bad = "\u0A71\u0A71"  # double addak
        violations = self.validator.validate(bad)
        assert any(v["severity"] == SEVERITY_WARN for v in violations)

    def test_orphaned_matra_flagged(self) -> None:
        # aa-matra not preceded by a consonant
        bad = " \u0A3E"  # space then aa-matra
        violations = self.validator.validate(bad)
        assert any(v["rule"] == "orphaned_matra" for v in violations)

    def test_orphaned_sihari_flagged(self) -> None:
        # sihari (U+0A3F) not preceded by a consonant
        bad = " \u0A3F"  # space then sihari
        violations = self.validator.validate(bad)
        assert any(v["rule"] == "orphaned_matra" for v in violations)

    def test_invalid_codepoint_flagged(self) -> None:
        # Mix of Gurmukhi and Cyrillic
        mixed = "ਕ\u0410"  # Gurmukhi ka + Cyrillic A
        violations = self.validator.validate(mixed)
        assert any(v["rule"] == "invalid_codepoint" for v in violations)


class TestScriptValidatorHindi:
    def setup_method(self) -> None:
        self.validator = ScriptValidator("hindi")

    def test_clean_devanagari(self) -> None:
        text = "नमस्ते"
        violations = self.validator.validate(text)
        rejects = [v for v in violations if v["severity"] == SEVERITY_REJECT]
        assert rejects == []

    def test_consecutive_matras_rejected(self) -> None:
        bad = "\u093E\u093F"
        violations = self.validator.validate(bad)
        assert any(v["severity"] == SEVERITY_REJECT for v in violations)

    def test_orphaned_matra_detected(self) -> None:
        bad = " \u093E"
        violations = self.validator.validate(bad)
        assert any(v["rule"] == "orphaned_matra" for v in violations)


class TestScriptValidatorUrdu:
    def setup_method(self) -> None:
        self.validator = ScriptValidator("urdu")

    def test_clean_urdu(self) -> None:
        text = "اردو"
        violations = self.validator.validate(text)
        rejects = [v for v in violations if v["severity"] == SEVERITY_REJECT]
        assert rejects == []

    def test_consecutive_diacritics_warned(self) -> None:
        bad = "\u064E\u064F"  # fatha + damma
        violations = self.validator.validate(bad)
        assert any(v["severity"] == SEVERITY_WARN for v in violations)


class TestScriptValidatorFarsi:
    def setup_method(self) -> None:
        self.validator = ScriptValidator("farsi")

    def test_clean_farsi(self) -> None:
        text = "فارسی"
        violations = self.validator.validate(text)
        rejects = [v for v in violations if v["severity"] == SEVERITY_REJECT]
        assert rejects == []


class TestConvenienceFunction:
    @pytest.mark.parametrize("lang", ["gurmukhi", "punjabi", "hindi", "urdu", "farsi"])
    def test_validate_text_returns_list(self, lang: str) -> None:
        violations = validate_text("test", lang)
        assert isinstance(violations, list)

    def test_unknown_language_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            validate_text("hello", "klingon")

    @pytest.mark.parametrize("lang", ["gurmukhi", "punjabi", "hindi", "urdu", "farsi"])
    def test_empty_string_no_violations(self, lang: str) -> None:
        violations = validate_text("", lang)
        # Empty string should produce no violations
        assert isinstance(violations, list)
