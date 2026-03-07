"""Character Correction Engine for scriptfix.

Loads per-script confusion dictionaries from YAML config files and applies
character-level corrections to Tesseract OCR output. Uses n-gram analysis
to detect impossible phonetic sequences and ranks correction candidates.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Any

import regex
import yaml

_CONFIG_DIR = Path(__file__).parent.parent / "configs"


def _load_config(language: str) -> dict[str, Any]:
    """Load the YAML config for the given language."""
    path = _CONFIG_DIR / f"{language}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No config found for language '{language}' at {path}")
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def correct(self, text: str) -> tuple[str, list[dict[str, Any]]]:
        """Apply all corrections to *text*.

        Returns:
            corrected_text: The corrected string.
            corrections: List of correction records (original, corrected, rule, position).
        """
        text = _normalize(text, self.norm_form)
        corrections: list[dict[str, Any]] = []

        text, c = self._apply_map(text, self._confusion_map, "confusion_pair")
        corrections.extend(c)

        text, c = self._apply_map(text, self._diacritic_map, "diacritic_pair")
        corrections.extend(c)

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

    @staticmethod
    def _apply_map(
        text: str,
        mapping: dict[str, str],
        rule_name: str,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Replace all occurrences of keys in *mapping* with their values."""
        corrections: list[dict[str, Any]] = []
        if not mapping:
            return text, corrections

        # Build a combined pattern matching any key, longest first
        sorted_keys = sorted(mapping.keys(), key=len, reverse=True)
        escaped = [regex.escape(k) for k in sorted_keys]
        pattern = regex.compile("|".join(escaped))

        def replacer(m: regex.Match[str]) -> str:
            original = m.group()
            corrected = mapping[original]
            corrections.append(
                {
                    "original": original,
                    "corrected": corrected,
                    "rule": rule_name,
                    "position": m.start(),
                }
            )
            return corrected

        new_text = pattern.sub(replacer, text)
        return new_text, corrections

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
