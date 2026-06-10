"""Character Correction Engine for scriptfix.

Loads per-script correction rules from YAML config files and applies
character-level confusion and diacritic substitutions to Tesseract OCR
output.

Corrections are **evidence-gated**: a confusion/diacritic substitution is only
applied when it strictly lowers the script-validity "badness" of the
surrounding word (see :class:`scriptfix.validator.ScriptValidator`). Well-formed
text scores zero badness, so it is never modified — this is what stops the blind
bidirectional find-replace that would otherwise corrupt correct OCR output.
Substitutions between two individually-valid characters (e.g. an aspirated-pair
confusion) carry no validity evidence and are therefore left untouched rather
than guessed at.
"""

from __future__ import annotations

import unicodedata
from typing import Any

import regex

from .config import load_config as _load_config
from .validator import ScriptValidator


def _normalize(text: str, form: str = "NFC") -> str:
    """Normalize Unicode text to the specified form."""
    return unicodedata.normalize(form, text)


class CharacterCorrector:
    """Applies confusion-pair and diacritic corrections for a given script."""

    def __init__(self, language: str) -> None:
        self.language = language
        self.config = _load_config(language)
        self.norm_form: str = self.config.get("normalization", "NFC")

        # Build correction maps
        self._confusion_map: dict[str, str] = {}
        for pair in self.config.get("confusion_pairs", []):
            wrong = _normalize(pair["wrong"], self.norm_form)
            correct = _normalize(pair["correct"], self.norm_form)
            if wrong != correct:
                self._confusion_map[wrong] = correct

        self._diacritic_map: dict[str, str] = {}
        for pair in self.config.get("diacritic_pairs", []):
            wrong = _normalize(pair["wrong"], self.norm_form)
            correct = _normalize(pair.get("correct", ""), self.norm_form)
            if wrong != correct:
                self._diacritic_map[wrong] = correct

        # Compile impossible-sequence patterns
        self._impossible: list[tuple[regex.Pattern[str], str, str]] = []
        for rule in self.config.get("impossible_sequences", []):
            pat = regex.compile(rule["pattern"])
            self._impossible.append((pat, rule["description"], rule.get("severity", "WARN")))

        # Combined candidate list (key -> replacement, rule) used by the
        # evidence-gated search, longest keys first so multi-codepoint
        # substitutions are considered before single-codepoint ones.
        self._candidates: list[tuple[str, str, str]] = [
            (k, v, "confusion_pair") for k, v in self._confusion_map.items()
        ] + [(k, v, "diacritic_pair") for k, v in self._diacritic_map.items()]
        self._candidates.sort(key=lambda t: len(t[0]), reverse=True)

        # Validator used to score the badness of candidate corrections.
        self._validator = ScriptValidator(language)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def correct(self, text: str) -> tuple[str, list[dict[str, Any]]]:
        """Apply evidence-gated corrections to *text*.

        Greedily applies the single confusion/diacritic substitution that most
        reduces the script-validity badness of *text*, repeating until no
        substitution improves it. Well-formed text (badness 0) is returned
        unchanged, so correct OCR output is never corrupted.

        Returns:
            corrected_text: The corrected string.
            corrections: List of correction records (original, corrected, rule, position).
        """
        text = _normalize(text, self.norm_form)
        corrections: list[dict[str, Any]] = []
        if not self._candidates:
            return text, corrections

        # Each accepted substitution strictly lowers badness (bounded below by
        # 0), so the loop terminates; the cap is a defensive backstop only.
        max_iterations = len(text) + 8
        for _ in range(max_iterations):
            base = self._validator.badness(text)
            if base <= 0:
                break  # already well-formed — no evidence to correct against

            best: tuple[float, int, str, str, str] | None = None  # delta,pos,key,repl,rule
            for pos in range(len(text)):
                for key, repl, rule in self._candidates:
                    if not text.startswith(key, pos):
                        continue
                    candidate = text[:pos] + repl + text[pos + len(key):]
                    delta = base - self._validator.badness(candidate)
                    if delta > 0 and (best is None or delta > best[0]):
                        best = (delta, pos, key, repl, rule)

            if best is None:
                break  # no substitution provides positive evidence — stop guessing

            _, pos, key, repl, rule = best
            corrections.append(
                {"original": key, "corrected": repl, "rule": rule, "position": pos}
            )
            text = text[:pos] + repl + text[pos + len(key):]

        return text, corrections

    def validate_sequences(self, text: str) -> list[dict[str, Any]]:
        """Check *text* for impossible sequences defined in the config.

        Returns a list of violation dicts with keys: description, severity, match, position.
        """
        violations: list[dict[str, Any]] = []
        for pat, description, severity in self._impossible:
            for m in pat.finditer(text):
                violations.append(
                    {
                        "description": description,
                        "severity": severity,
                        "match": m.group(),
                        "position": m.start(),
                    }
                )
        return violations

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def get_confusion_map(self) -> dict[str, str]:
        """Return a copy of the confusion mapping."""
        return dict(self._confusion_map)

    def get_diacritic_map(self) -> dict[str, str]:
        """Return a copy of the diacritic mapping."""
        return dict(self._diacritic_map)


def correct_text(text: str, language: str) -> tuple[str, list[dict[str, Any]]]:
    """Convenience function: correct *text* for the given *language*."""
    corrector = CharacterCorrector(language)
    return corrector.correct(text)
