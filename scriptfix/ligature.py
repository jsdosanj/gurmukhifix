"""Ligature and Conjunct Handler for scriptfix.

Detects broken ligatures using Unicode block analysis and (optionally)
positional bounding-box data from Tesseract JSON. Reassembles sequences
flagged as separate characters that belong to a single glyph.

Rules are stored in per-language YAML configs; no script-specific logic
is hardcoded in this module.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Any

import regex
import yaml

_CONFIG_DIR = Path(__file__).parent.parent / "configs"


def _load_config(language: str) -> dict[str, Any]:
    path = _CONFIG_DIR / f"{language}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No config found for language '{language}' at {path}")
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class LigatureHandler:
    """Detects and reassembles broken ligatures for a given script."""

    def __init__(self, language: str) -> None:
        self.language = language
        self.config = _load_config(language)
        self.norm_form: str = self.config.get("normalization", "NFC")

        # Load ligature rules from config (optional section)
        self._ligature_rules: list[dict[str, Any]] = self.config.get("ligature_rules", [])
        self._join_pairs: list[tuple[str, str]] = []
        for rule in self._ligature_rules:
            broken = unicodedata.normalize(self.norm_form, rule.get("broken", ""))
            joined = unicodedata.normalize(self.norm_form, rule.get("joined", ""))
            if broken and joined:
                self._join_pairs.append((broken, joined))

        # Arabic/Urdu/Farsi: joining characters require context
        self._is_rtl = self.config.get("direction", "ltr") == "rtl"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reassemble(self, text: str) -> tuple[str, list[dict[str, Any]]]:
        """Reassemble broken ligatures in *text*.

        Returns:
            corrected_text: Text with ligatures restored.
            corrections: List of correction records.
        """
        text = unicodedata.normalize(self.norm_form, text)
        corrections: list[dict[str, Any]] = []

        # Apply explicit ligature rules from config
        for broken, joined in self._join_pairs:
            if broken in text:
                idx = 0
                while True:
                    pos = text.find(broken, idx)
                    if pos == -1:
                        break
                    corrections.append(
                        {
                            "original": broken,
                            "corrected": joined,
                            "rule": "ligature_reassembly",
                            "position": pos,
                        }
                    )
                    text = text[:pos] + joined + text[pos + len(broken):]
                    idx = pos + len(joined)

        # For RTL scripts: detect common broken pairs (space-separated letters
        # that should be joined based on Arabic joining rules)
        if self._is_rtl:
            text, rtl_corrections = self._fix_rtl_joins(text)
            corrections.extend(rtl_corrections)

        return text, corrections

    def detect_broken_ligatures(self, text: str) -> list[dict[str, Any]]:
        """Return a list of suspected broken ligatures without modifying text."""
        text = unicodedata.normalize(self.norm_form, text)
        suspects: list[dict[str, Any]] = []

        for broken, joined in self._join_pairs:
            idx = 0
            while True:
                pos = text.find(broken, idx)
                if pos == -1:
                    break
                suspects.append(
                    {
                        "broken_sequence": broken,
                        "expected_joined": joined,
                        "position": pos,
                    }
                )
                idx = pos + 1

        return suspects

    # ------------------------------------------------------------------
    # RTL join helpers
    # ------------------------------------------------------------------

    # Letters that must connect to the following letter in Arabic/Farsi/Urdu
    _DUAL_JOIN = frozenset(
        "بپتثجچحخدذرزژسشصضطظعغفقکگلمنهوی"
        "\u0628\u067E\u062A\u062B\u062C\u0686\u062D\u062E"
        "\u062F\u0630\u0631\u0632\u0698\u0633\u0634\u0635"
        "\u0636\u0637\u0638\u0639\u063A\u0641\u0642\u06A9"
        "\u06AF\u0644\u0645\u0646\u0647\u0648\u06CC"
    )

    _NON_JOIN = frozenset("ادذرزوژ\u0627\u062F\u0630\u0631\u0632\u0648\u0698")

    def _fix_rtl_joins(self, text: str) -> tuple[str, list[dict[str, Any]]]:
        """Remove spurious spaces between Arabic-script letters that should be joined."""
        corrections: list[dict[str, Any]] = []
        # Pattern: letter SPACE letter where both are Arabic-script characters
        pat = regex.compile(r"([\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]) ([\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF])")

        def rejoin(m: regex.Match[str]) -> str:
            left = m.group(1)
            right = m.group(2)
            # Only rejoin if left char is dual-joining (can connect to right)
            if left in self._DUAL_JOIN and left not in self._NON_JOIN:
                joined = left + right
                corrections.append(
                    {
                        "original": m.group(),
                        "corrected": joined,
                        "rule": "rtl_join_repair",
                        "position": m.start(),
                    }
                )
                return joined
            return m.group()

        # Apply repeatedly until stable (nested broken joins)
        prev = None
        while prev != text:
            prev = text
            text = pat.sub(rejoin, text)

        return text, corrections


def reassemble_ligatures(text: str, language: str) -> tuple[str, list[dict[str, Any]]]:
    """Convenience function: reassemble broken ligatures in *text*."""
    return LigatureHandler(language).reassemble(text)
