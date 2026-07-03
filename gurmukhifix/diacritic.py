"""Diacritic and Nukta Recovery for gurmukhifix.

Runs after the initial correction pass to recover dropped or misplaced
diacritics using context-based heuristics and, when provided, text and
confidence information from Tesseract's alternatives array.
"""

from __future__ import annotations

import unicodedata
from typing import Any

import regex

from .config import load_config as _load_config
from .evidence import EvidenceGate
from .lexicon import Lexicon
from .validator import ScriptValidator


class DiacriticRecovery:
    """Recovers dropped or misplaced diacritics for a given script."""

    def __init__(
        self,
        language: str,
        validator: ScriptValidator | None = None,
        lexicon: Lexicon | None = None,
    ) -> None:
        self.language = language
        self.config = _load_config(language)
        self.norm_form: str = self.config.get("normalization", "NFC")
        self._validator = validator or ScriptValidator(language)
        self._gate = EvidenceGate(self._validator, lexicon)

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
        original = text
        baseline_badness = self._validator.badness(text)
        corrections: list[dict[str, Any]] = []

        if self.language in ("gurmukhi", "punjabi"):
            text, c = self._recover_sihari_order(text)
            corrections.extend(c)
            text, c = self._fix_nukta_order(text)
            corrections.extend(c)

        if self.language in ("hindi", "devanagari", "marathi", "nepali", "sanskrit"):
            text, c = self._recover_devanagari_imatra(text)
            corrections.extend(c)

        if self.language in ("urdu", "farsi"):
            candidate, c = self._recover_hamza_carrier(text)
            # The hamza rewrite substitutes codepoints, so it must clear the
            # evidence gate: it applies only on a strict validity gain or a
            # dictionary hit, never silently on already-valid Arabic-script text.
            if candidate != text and self._gate.judge_word(text, candidate).allowed:
                text = candidate
                corrections.extend(c)

        # Nukta recovery from Tesseract alternatives
        if alternatives:
            text, c = self._recover_nukta_from_alternatives(text, alternatives)
            corrections.extend(c)

        # Safety net: heuristic recovery must never make a word *less* valid than
        # it was. If it did, discard the changes and keep the original text.
        if text != original and self._validator.badness(text) > baseline_badness:
            return original, []

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
            # Only reorder a sihari that is genuinely misplaced: it appears
            # *before* a consonant (its visual position) without already
            # following a base consonant. A sihari that already follows a
            # consonant is correctly encoded and must be left alone — swapping
            # it would corrupt valid words such as ਸਾਹਿਬ.
            # Look past an attached nukta when checking for a base consonant —
            # a sihari after C + nukta is correctly placed.
            j = i - 1
            if j >= 0 and text[j] == "਼":
                j -= 1
            preceded_by_consonant = j >= 0 and bool(gurmukhi_consonant.match(text[j]))
            if (
                ch == sihari
                and not preceded_by_consonant
                and i + 1 < len(text)
                and gurmukhi_consonant.match(text[i + 1])
            ):
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

    # Gurmukhi dependent vowel signs (matras), including sihari.
    _GURMUKHI_MATRAS = frozenset(
        "ਾਿੀੁੂੇੈੋੌ"
    )

    def _fix_nukta_order(self, text: str) -> tuple[str, list[dict[str, Any]]]:
        """Put a nukta (U+0A3C) before the dependent vowel on the same consonant.

        The canonical Gurmukhi order is consonant + nukta + vowel sign (e.g. ਸ਼ਾ),
        but OCR sometimes emits the vowel before the nukta (ਸਾ਼). Unicode NFC does
        not reorder these (the vowel sign has combining class 0 and blocks
        reordering), so we swap an adjacent ``matra + nukta`` pair into
        ``nukta + matra``. The recover() safety net guards against any pair whose
        swap would lower validity.
        """
        corrections: list[dict[str, Any]] = []
        nukta = "਼"
        chars = list(text)
        i = 1
        while i < len(chars):
            if chars[i] == nukta and chars[i - 1] in self._GURMUKHI_MATRAS:
                chars[i - 1], chars[i] = chars[i], chars[i - 1]
                corrections.append(
                    {
                        "original": chars[i] + chars[i - 1],
                        "corrected": chars[i - 1] + chars[i],
                        "rule": "nukta_order_fix",
                        "position": i - 1,
                    }
                )
            i += 1
        return "".join(chars), corrections

    def _recover_devanagari_imatra(self, text: str) -> tuple[str, list[dict[str, Any]]]:
        """Reorder a misplaced Devanagari i-matra (ि U+093F) after its consonant.

        Like the Gurmukhi sihari, the i-matra is drawn to the left of its
        consonant but must be encoded after it. OCR that emits visual order
        produces ``ि + consonant``; we swap it to ``consonant + ि`` only when the
        i-matra is genuinely orphaned (not already following a consonant, looking
        past an attached nukta).
        """
        corrections: list[dict[str, Any]] = []
        imatra = "ि"
        consonant = regex.compile(r"[क-हक़-य़]")
        nukta = "़"

        result: list[str] = []
        i = 0
        while i < len(text):
            ch = text[i]
            j = i - 1
            if j >= 0 and text[j] == nukta:
                j -= 1
            preceded_by_consonant = j >= 0 and bool(consonant.match(text[j]))
            if (
                ch == imatra
                and not preceded_by_consonant
                and i + 1 < len(text)
                and consonant.match(text[i + 1])
            ):
                cons = text[i + 1]
                corrections.append(
                    {
                        "original": ch + cons,
                        "corrected": cons + ch,
                        "rule": "imatra_order_fix",
                        "position": i,
                    }
                )
                result.append(cons + ch)
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
