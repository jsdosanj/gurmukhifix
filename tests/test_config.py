"""Tests for centralised config loading and `extends` resolution."""

from __future__ import annotations

import pytest

from scriptfix.config import load_config
from scriptfix.corrector import CharacterCorrector
from scriptfix.integration import process_document

ALL_LANGUAGES = ["gurmukhi", "punjabi", "hindi", "devanagari", "urdu", "farsi"]


class TestExtends:
    def test_punjabi_inherits_gurmukhi_rules(self) -> None:
        gur = load_config("gurmukhi")
        pun = load_config("punjabi")
        # Punjabi declares `extends: gurmukhi`, so its merged rule set must be a
        # superset of Gurmukhi's confusion pairs.
        assert len(pun["confusion_pairs"]) > len(gur["confusion_pairs"])
        assert pun["script"] == "punjabi"

    def test_devanagari_inherits_hindi_rules(self) -> None:
        hin = load_config("hindi")
        dev = load_config("devanagari")
        assert dev["script"] == "devanagari"
        # Inherits every Hindi confusion pair plus its own additions.
        assert len(dev["confusion_pairs"]) > len(hin["confusion_pairs"])

    def test_unknown_language_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_config("klingon")


class TestAllLanguages:
    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_loadable(self, lang: str) -> None:
        assert load_config(lang)["script"]

    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_has_30_confusion_pairs(self, lang: str) -> None:
        assert len(CharacterCorrector(lang).get_confusion_map()) >= 30


class TestDevanagariPipeline:
    def test_clean_devanagari_unchanged(self) -> None:
        for word in ["हिंदी", "भारत", "नमस्ते"]:
            out = process_document(
                {"words": [{"text": word, "conf": 70.0, "bbox": [], "alternatives": []}]},
                "devanagari",
            )["corrected_text"]
            assert out == word

    def test_matra_at_start_is_flagged(self) -> None:
        # A dependent vowel at word start is a REJECT and must be surfaced.
        result = process_document(
            {"words": [{"text": "ाक", "conf": 70.0, "bbox": [], "alternatives": []}]},
            "devanagari",
        )
        assert result["flagged"], "matra-initial word should be flagged for review"
