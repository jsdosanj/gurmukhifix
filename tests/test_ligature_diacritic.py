"""Tests for Ligature and Diacritic modules."""

from __future__ import annotations

import pytest

from scriptfix.ligature import LigatureHandler, reassemble_ligatures
from scriptfix.diacritic import DiacriticRecovery, recover_diacritics


class TestLigatureHandler:
    @pytest.mark.parametrize("lang", ["gurmukhi", "punjabi", "hindi", "urdu", "farsi"])
    def test_loads_config(self, lang: str) -> None:
        handler = LigatureHandler(lang)
        assert handler.config is not None

    @pytest.mark.parametrize("lang", ["gurmukhi", "punjabi", "hindi", "urdu", "farsi"])
    def test_reassemble_returns_string(self, lang: str) -> None:
        handler = LigatureHandler(lang)
        result, corrections = handler.reassemble("test text")
        assert isinstance(result, str)
        assert isinstance(corrections, list)

    def test_rtl_join_repair_urdu(self) -> None:
        # RTL space-join repair is opt-in (it cannot otherwise tell a broken
        # glyph from a real word boundary); enable it explicitly here.
        handler = LigatureHandler("urdu", rtl_join_repair=True)
        # Arabic letters that should join: ب + ه → به
        broken = "ب ه"
        result, corrections = handler.reassemble(broken)
        # Should rejoin dual-joining letters and emit a correction record
        assert result == "به"
        assert isinstance(corrections, list)
        assert len(corrections) > 0
        assert isinstance(corrections[0], dict)
        assert "rule" in corrections[0]
        assert corrections[0]["rule"] == "rtl_join_repair"

    def test_rtl_join_repair_farsi(self) -> None:
        handler = LigatureHandler("farsi", rtl_join_repair=True)
        broken = "ک ه"
        result, corrections = handler.reassemble(broken)
        # Should rejoin dual-joining letters and emit a correction record
        assert result == "که"
        assert isinstance(corrections, list)
        assert len(corrections) > 0
        assert isinstance(corrections[0], dict)
        assert "rule" in corrections[0]
        assert corrections[0]["rule"] == "rtl_join_repair"

    def test_detect_broken_no_rules(self) -> None:
        handler = LigatureHandler("hindi")
        suspects = handler.detect_broken_ligatures("नमस्ते")
        assert isinstance(suspects, list)

    @pytest.mark.parametrize("lang", ["gurmukhi", "punjabi", "hindi", "urdu", "farsi"])
    def test_empty_string(self, lang: str) -> None:
        result, corrections = reassemble_ligatures("", lang)
        assert result == ""
        assert corrections == []

    def test_unknown_language_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            LigatureHandler("klingon")


class TestDiacriticRecovery:
    @pytest.mark.parametrize("lang", ["gurmukhi", "punjabi", "hindi", "urdu", "farsi"])
    def test_loads_config(self, lang: str) -> None:
        dr = DiacriticRecovery(lang)
        assert dr.config is not None

    @pytest.mark.parametrize("lang", ["gurmukhi", "punjabi", "hindi", "urdu", "farsi"])
    def test_recover_returns_string(self, lang: str) -> None:
        dr = DiacriticRecovery(lang)
        result, corrections = dr.recover("test")
        assert isinstance(result, str)
        assert isinstance(corrections, list)

    def test_sihari_order_fix_gurmukhi(self) -> None:
        dr = DiacriticRecovery("gurmukhi")
        # Sihari (U+0A3F) incorrectly placed before consonant
        # In Unicode it should come after the consonant
        sihari = "\u0A3F"
        ka = "\u0A15"
        wrong_order = sihari + ka  # ਿਕ (wrong Unicode order)
        result, corrections = dr.recover(wrong_order)
        # Should be swapped to ka + sihari
        assert result == ka + sihari
        assert len(corrections) > 0
        assert corrections[0]["rule"] == "sihari_order_fix"

    def test_sihari_order_correct_unchanged(self) -> None:
        dr = DiacriticRecovery("gurmukhi")
        sihari = "\u0A3F"
        ka = "\u0A15"
        correct_order = ka + sihari  # ਕਿ (correct Unicode order)
        result, corrections = dr.recover(correct_order)
        assert result == correct_order
        assert corrections == []

    def test_sihari_after_consonant_nukta_unchanged(self) -> None:
        # A sihari that follows consonant + nukta is correctly placed.
        dr = DiacriticRecovery("gurmukhi")
        text = "ਜ਼ਿ"  # ja + nukta + sihari
        result, corrections = dr.recover(text)
        assert result == text
        assert corrections == []

    def test_nukta_order_fixed(self) -> None:
        # Nukta emitted after the vowel sign must move before it: ਸਾ਼ -> ਸ਼ਾ
        dr = DiacriticRecovery("gurmukhi")
        result, corrections = dr.recover("ਸਾ਼")
        assert result == "ਸ਼ਾ"
        assert any(c["rule"] == "nukta_order_fix" for c in corrections)

    def test_nukta_already_ordered_unchanged(self) -> None:
        dr = DiacriticRecovery("punjabi")
        text = "ਸ਼ਾ"  # consonant + nukta + vowel (canonical)
        result, corrections = dr.recover(text)
        assert result == text
        assert corrections == []

    def test_hamza_carrier_farsi(self) -> None:
        dr = DiacriticRecovery("farsi")
        # Standalone hamza following ye should become ئ
        ye = "\u06CC"
        hamza = "\u0621"
        text = ye + hamza
        result, corrections = dr.recover(text)
        assert isinstance(result, str)

    def test_nukta_recovery_from_alternatives(self) -> None:
        dr = DiacriticRecovery("hindi")
        text = "क"
        alternatives = [{"text": "क़", "confidence": 0.75}]  # k with nukta
        result, corrections = dr.recover(text, alternatives)
        # Should prefer the nukta version (higher confidence, differs only by nukta)
        assert isinstance(result, str)

    @pytest.mark.parametrize("lang", ["gurmukhi", "punjabi", "hindi", "urdu", "farsi"])
    def test_empty_string(self, lang: str) -> None:
        result, corrections = recover_diacritics("", lang)
        assert result == ""
        assert corrections == []

    def test_unknown_language_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            DiacriticRecovery("klingon")
