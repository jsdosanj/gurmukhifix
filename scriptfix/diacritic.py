"""Diacritic and Nukta Recovery for scriptfix.

Runs after the initial correction pass to recover dropped or misplaced
diacritics using context-based heuristics and bounding-box proximity data
from Tesseract's alternatives array.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Any

import regex
import yaml

_CONFIG_DIR = Path(__file__).parent.parent / "configs"

# Unicode diacritic codepoints per script
_GURMUKHI_MATRAS = "\u0A3E\u0A3F\u0A40\u0A41\u0A42\u0A47\u0A48\u0A4B\u0A4C"
_GURMUKHI_NASALS = "\u0A02\u0A70\u0A71"  # bindi, tippi, addak

_DEVANAGARI_MATRAS = "\u093E\u093F\u0940\u0941\u0942\u0943\u0944\u0947\u0948\u094B\u094C"
_DEVANAGARI_NASALS = "\u0901\u0902"  # chandrabindu, anusvara

_ARABIC_AERAB = "\u064B\u064C\u064D\u064E\u064F\u0650\u0651\u0652"  # harakat + shadda + sukun


def _load_config(language: str) -> dict[str, Any]:
    path = _CONFIG_DIR / f"{language}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No config found for language '{language}' at {path}")
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class DiacriticRecovery:
    """Recovers dropped or misplaced diacritics for a given script."""

    def __init__(self, language: str) -> None:
        self.language = language
        self.config = _load_config(language)
        self.norm_form: str = self.config.get("normalization", "NFC")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recover(self, text: str, alternatives: list[dict[str, Any]] | None = None) -> tuple[str, list[dict[str, Any]]]:
        """Run the diacritic recovery pass on *text*.

        Args:
            text: Input text (already corrected by CharacterCorrector).
            alternatives: Optional list of Tesseract alternative readings,
                          each as {"text": str, "confidence": float, "bbox": [x,y,w,h]}.

        Returns:
            recovered_text: Text with diacritics recovered.
            corrections: List of correction records.
        """
        text = unicodedata.normalize(self.norm_form, text)
        corrections: list[dict[str, Any]] = []

        if self.language in ("gurmukhi", "punjabi"):
            text, c = self._recover_sihari_order(text)
            corrections.extend(c)

        if self.language in ("urdu", "farsi"):
            text, c = self._recover_hamza_carrier(text)
            corrections.extend(c)

        # Nukta recovery from Tesseract alternatives
        if alternatives:
            text, c = self._recover_nukta_from_alternatives(text, alternatives)
            corrections.extend(c)

        return text, corrections

    # ------------------------------------------------------------------
    # Script-specific recovery methods
    # ------------------------------------------------------------------

    def _recover_sihari_order(self, text: str) -> tuple[str, list[dict[str, Any]]]:
        """Ensure sihari (U+0A3F) follows its base consonant in Unicode order.

        Visually sihari appears before the consonant, but Unicode requires it
        after. Tesseract sometimes outputs it before; we swap it back.
        """
        corrections: list[dict[str, Any]] = []
        sihari = "\u0A3F"
        gurmukhi_consonant = regex.compile(r"[\u0A15-\u0A39\u0A59-\u0A5E]")

        result = []
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == sihari and i + 1 < len(text) and gurmukhi_consonant.match(text[i + 1]):
                # Sihari before consonant — swap
                consonant = text[i + 1]
                original = ch + consonant
                corrected = consonant + ch
                corrections.append(
                    {
                        "original": original,
                        "corrected": corrected,
                        "rule": "sihari_order_fix",
                        "position": i,
                    }
                )
                result.append(corrected)
                i += 2
            else:
                result.append(ch)
                i += 1

        return "".join(result), corrections

    def _recover_hamza_carrier(self, text: str) -> tuple[str, list[dict[str, Any]]]:
        """Ensure standalone hamza (U+0621) has an appropriate carrier in context."""
        corrections: list[dict[str, Any]] = []
        hamza = "\u0621"
        ye = "\u06CC"      # Farsi ye
        alef = "\u0627"

        result = list(text)
        i = 0
        while i < len(result):
            if result[i] == hamza:
                # If hamza follows a long vowel ye, it should use ئ (U+0626)
                if i > 0 and result[i - 1] == ye:
                    original = result[i - 1] + result[i]
                    corrected = "\u0626"  # ئ
                    corrections.append(
                        {
                            "original": original,
                            "corrected": corrected,
                            "rule": "hamza_carrier_fix",
                            "position": i - 1,
                        }
                    )
                    result[i - 1 : i + 1] = [corrected]
                    # Don't advance i since we merged two chars into one
                    continue
                # If hamza at word start followed by a vowel, use أ
                elif i == 0 or result[i - 1] == " ":
                    if i + 1 < len(result) and result[i + 1] in "\u0627\u0648\u06CC":
                        original = result[i] + result[i + 1]
                        corrected = "\u0623" + result[i + 1]  # أ
                        corrections.append(
                            {
                                "original": original,
                                "corrected": corrected,
                                "rule": "hamza_carrier_fix",
                                "position": i,
                            }
                        )
                        result[i : i + 2] = list(corrected)
            i += 1

        return "".join(result), corrections

    def _recover_nukta_from_alternatives(
        self,
        text: str,
        alternatives: list[dict[str, Any]],
    ) -> tuple[str, list[dict[str, Any]]]:
        """Use Tesseract alternatives to recover dropped nukta dots.

        For each alternative reading that differs only by the presence of a nukta,
        prefer the reading with higher confidence that also satisfies script rules.
        """
        corrections: list[dict[str, Any]] = []
        nukta = "\u093C"  # Devanagari nukta (also used in Gurmukhi as U+0A3C)
        gurmukhi_nukta = "\u0A3C"

        for alt in alternatives:
            alt_text = alt.get("text", "")
            alt_conf = alt.get("confidence", 0.0)
            if not alt_text:
                continue
            # If alternative differs from current text only by a nukta, consider it
            stripped_alt = alt_text.replace(nukta, "").replace(gurmukhi_nukta, "")
            stripped_cur = text.replace(nukta, "").replace(gurmukhi_nukta, "")
            if stripped_alt == stripped_cur and alt_conf > 0.6:
                corrections.append(
                    {
                        "original": text,
                        "corrected": alt_text,
                        "rule": "nukta_recovery_from_alternatives",
                        "position": 0,
                        "confidence": alt_conf,
                    }
                )
                text = alt_text
                break

        return text, corrections


def recover_diacritics(
    text: str,
    language: str,
    alternatives: list[dict[str, Any]] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Convenience function: run diacritic recovery on *text*."""
    return DiacriticRecovery(language).recover(text, alternatives)
