"""Script Integrity Validator for scriptfix.

Validates OCR output against script grammar rules defined in YAML configs.
Flags violations with severity levels: REJECT, WARN, REVIEW.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Any

import regex
import yaml

_CONFIG_DIR = Path(__file__).parent.parent / "configs"

SEVERITY_REJECT = "REJECT"
SEVERITY_WARN = "WARN"
SEVERITY_REVIEW = "REVIEW"


def _load_config(language: str) -> dict[str, Any]:
    path = _CONFIG_DIR / f"{language}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No config found for language '{language}' at {path}")
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


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

            # Sihari (U+0A3F) must follow a base consonant in Unicode order
            sihari = "\u0A3F"
            for i, ch in enumerate(text):
                if ch == sihari:
                    if i == 0 or not consonant_range.match(text[i - 1]):
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
                if pos == 0 or not consonant_range.match(text[pos - 1]):
                    violations.append(
                        {
                            "rule": "orphaned_matra",
                            "description": "dependent vowel with no preceding base consonant",
                            "severity": SEVERITY_WARN,
                            "match": m.group(),
                            "position": pos,
                        }
                    )

        elif self.language == "hindi":
            # Devanagari matras: U+093E–U+094C
            matra_range = regex.compile(r"[\u093E-\u094C]")
            consonant_range = regex.compile(r"[\u0915-\u0939\u0958-\u095F]")
            for m in matra_range.finditer(text):
                pos = m.start()
                if pos == 0 or not consonant_range.match(text[pos - 1]):
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


def validate_text(text: str, language: str) -> list[dict[str, Any]]:
    """Convenience function: validate *text* for the given *language*."""
    return ScriptValidator(language).validate(text)
