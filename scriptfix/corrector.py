"""Character Correction Engine for scriptfix.

Loads per-script correction rules from YAML config files and applies
character-level confusion and diacritic substitutions to Tesseract OCR
output. Provides optional validation of impossible character sequences
using configurable regular-expression patterns.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Any

import regex
import yaml

_CONFIG_DIR = Path(__file__).parent / "configs"


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

        # Precompile combined substitution patterns for efficiency
        self._confusion_pattern: regex.Pattern[str] | None = self._compile_map_pattern(
            self._confusion_map
        )
        self._diacritic_pattern: regex.Pattern[str] | None = self._compile_map_pattern(
            self._diacritic_map
        )

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

        text, c = self._apply_compiled(text, self._confusion_map, self._confusion_pattern, "confusion_pair")
        corrections.extend(c)

        text, c = self._apply_compiled(text, self._diacritic_map, self._diacritic_pattern, "diacritic_pair")
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
    def _compile_map_pattern(mapping: dict[str, str]) -> "regex.Pattern[str] | None":
        """Compile a combined regex pattern for all keys in *mapping*, longest first."""
        if not mapping:
            return None
        sorted_keys = sorted(mapping.keys(), key=len, reverse=True)
        escaped = [regex.escape(k) for k in sorted_keys]
        return regex.compile("|".join(escaped))

    @staticmethod
    def _apply_compiled(
        text: str,
        mapping: dict[str, str],
        pattern: "regex.Pattern[str] | None",
        rule_name: str,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Replace occurrences of mapping keys using a precompiled *pattern*."""
        corrections: list[dict[str, Any]] = []
        if not mapping or pattern is None:
            return text, corrections

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
