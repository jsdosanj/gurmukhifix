"""Script Integrity Validator for scriptfix.

Validates OCR output against script grammar rules defined in YAML configs.
Flags violations with severity levels: REJECT, WARN, REVIEW.
"""

from __future__ import annotations

import unicodedata
from typing import Any

import regex

from .config import load_config as _load_config

SEVERITY_REJECT = "REJECT"
SEVERITY_WARN = "WARN"
SEVERITY_REVIEW = "REVIEW"

# Relative cost of each severity, used to score how "wrong" a string is.
# A REJECT (structurally impossible) outweighs any number of REVIEW flags so
# that evidence-gated correction always prefers eliminating hard violations.
SEVERITY_WEIGHTS = {
    SEVERITY_REJECT: 100.0,
    SEVERITY_WARN: 10.0,
    SEVERITY_REVIEW: 1.0,
}


class ScriptValidator:
    """Validates text against script-grammar rules for a specific language."""

    def __init__(self, language: str) -> None:
        self.language = language
        self.config = _load_config(language)
        self.norm_form: str = self.config.get("normalization", "NFC")

        # Compile impossible-sequence patterns from config
        self._rules: list[dict[str, Any]] = []
        for rule in self.config.get("impossible_sequences", []):
            self._rules.append(
                {
                    "pattern": regex.compile(rule["pattern"]),
                    "description": rule["description"],
                    "severity": rule.get("severity", SEVERITY_WARN),
                }
            )

        # Valid codepoint ranges
        self._valid_ranges: list[tuple[int, int]] = [
            tuple(r) for r in self.config.get("valid_ranges", [])  # type: ignore[misc]
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(self, text: str) -> list[dict[str, Any]]:
        """Run all validation rules against *text*.

        Returns a list of violation dicts, each containing:
        - rule: str
        - description: str
        - severity: REJECT | WARN | REVIEW
        - match: str (the offending text fragment)
        - position: int
        """
        text = unicodedata.normalize(self.norm_form, text)
        violations: list[dict[str, Any]] = []

        # Pattern-based rules from config
        for rule in self._rules:
            for m in rule["pattern"].finditer(text):
                violations.append(
                    {
                        "rule": "impossible_sequence",
                        "description": rule["description"],
                        "severity": rule["severity"],
                        "match": m.group(),
                        "position": m.start(),
                    }
                )

        # Script-specific structural checks
        violations.extend(self._check_orphaned_matras(text))
        violations.extend(self._check_invalid_codepoints(text))

        return violations

    # ------------------------------------------------------------------
    # Structural checks
    # ------------------------------------------------------------------

    def _check_orphaned_matras(self, text: str) -> list[dict[str, Any]]:
        """Detect dependent vowel signs with no preceding base consonant."""
        violations: list[dict[str, Any]] = []

        if self.language in ("gurmukhi", "punjabi"):
            consonant_range = regex.compile(r"[\u0A15-\u0A39\u0A59-\u0A5E]")
            nukta = "\u0A3C"

            # Sihari (U+0A3F) must follow a base consonant in Unicode order
            sihari = "\u0A3F"
            for i, ch in enumerate(text):
                if ch == sihari and not self._has_base_consonant(
                    text, i, consonant_range, nukta
                ):
                    violations.append(
                        {
                            "rule": "orphaned_matra",
                            "description": "sihari (ਿ) with no preceding base consonant",
                            "severity": SEVERITY_WARN,
                            "match": ch,
                            "position": i,
                        }
                    )

            # Other Gurmukhi dependent vowels: U+0A3E, U+0A40–U+0A4C
            matra_range = regex.compile(r"[\u0A3E\u0A40-\u0A4C]")
            for m in matra_range.finditer(text):
                pos = m.start()
                if not self._has_base_consonant(text, pos, consonant_range, nukta):
                    violations.append(
                        {
                            "rule": "orphaned_matra",
                            "description": "dependent vowel with no preceding base consonant",
                            "severity": SEVERITY_WARN,
                            "match": m.group(),
                            "position": pos,
                        }
                    )

        elif self.language in ("hindi", "devanagari", "marathi", "nepali", "sanskrit"):
            # Devanagari matras: U+093E–U+094C
            matra_range = regex.compile(r"[\u093E-\u094C]")
            consonant_range = regex.compile(r"[\u0915-\u0939\u0958-\u095F]")
            nukta = "\u093C"
            for m in matra_range.finditer(text):
                pos = m.start()
                if not self._has_base_consonant(text, pos, consonant_range, nukta):
                    violations.append(
                        {
                            "rule": "orphaned_matra",
                            "description": "Devanagari matra with no preceding consonant",
                            "severity": SEVERITY_WARN,
                            "match": m.group(),
                            "position": pos,
                        }
                    )

        return violations

    def _check_invalid_codepoints(self, text: str) -> list[dict[str, Any]]:
        """Flag characters that fall outside the expected Unicode blocks for this script."""
        if not self._valid_ranges:
            return []

        violations: list[dict[str, Any]] = []
        for i, ch in enumerate(text):
            cp = ord(ch)
            # Whitespace and control characters are always allowed
            if cp <= 0x001F or cp == 0x0020:
                continue
            in_range = any(lo <= cp <= hi for lo, hi in self._valid_ranges)
            if not in_range:
                violations.append(
                    {
                        "rule": "invalid_codepoint",
                        "description": f"character U+{cp:04X} ({unicodedata.name(ch, '?')}) "
                        f"outside expected script blocks",
                        "severity": SEVERITY_REVIEW,
                        "match": ch,
                        "position": i,
                    }
                )
        return violations

    def has_rejections(self, violations: list[dict[str, Any]]) -> bool:
        """Return True if any violation has REJECT severity."""
        return any(v["severity"] == SEVERITY_REJECT for v in violations)

    def badness(self, text: str) -> float:
        """Score how badly *text* violates this script's grammar.

        Returns a non-negative weighted count of violations (0.0 means the text
        is fully well-formed). This is the evidence signal used to gate
        corrections: a substitution is only worth applying if it *lowers* the
        badness of the surrounding word. Well-formed text scores 0, so blind
        same-class character swaps (which never reduce badness) are rejected.
        """
        return sum(
            SEVERITY_WEIGHTS.get(v["severity"], 1.0) for v in self.validate(text)
        )

    @staticmethod
    def _has_base_consonant(
        text: str, pos: int, consonant_range: "regex.Pattern[str]", nukta: str
    ) -> bool:
        """Whether the dependent sign at *pos* has a valid base consonant.

        A nukta (U+0A3C / U+093C) may legitimately sit between a consonant and
        its dependent vowel (e.g. ਸ + ਼ + ਾ in ਭਾਸ਼ਾ), so we look past a single
        intervening nukta when searching backwards for the base consonant.
        """
        j = pos - 1
        if j >= 0 and text[j] == nukta:
            j -= 1
        return j >= 0 and bool(consonant_range.match(text[j]))


def validate_text(text: str, language: str) -> list[dict[str, Any]]:
    """Convenience function: validate *text* for the given *language*."""
    return ScriptValidator(language).validate(text)
