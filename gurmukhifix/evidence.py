"""The evidence gate — the single rule that keeps gurmukhifix from corrupting text.

Every automatic codepoint change in the pipeline is judged, at the level of the
individual word it touches, by :class:`EvidenceGate`. The rule:

* A verbatim scripture (Gurbani) word is **locked** — never altered automatically.
  Only human-confirmed review corrections may change it.
* An edit may never **increase** a word's script-validity badness.
* A codepoint **substitution** (the multiset of codepoints changes) requires
  positive external evidence: it must either strictly lower badness *or* turn a
  non-word into a known dictionary word. A same-validity swap between two valid
  characters (badness 0 → 0) with no dictionary support is refused — that blind
  guess is exactly what silently corrupts correct OCR output.
* A pure **re-ordering** (same multiset of codepoints — e.g. moving a sihari after
  its base consonant) is a safe canonicalization and is allowed as long as it does
  not worsen validity.

Centralising the rule here means the corrector, the diacritic pass, and any future
pass all enforce the identical invariant, and it can be property-tested in one
place.
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from typing import NamedTuple

from .lexicon import Lexicon
from .validator import ScriptValidator


class Verdict(NamedTuple):
    allowed: bool
    reason: str


# Reasons that block an edit no matter what other evidence exists.
BLOCKING_REASONS = frozenset({"scripture_locked", "worsens_validity"})


def word_span(text: str, pos: int) -> tuple[int, int]:
    """Return the [start, end) span of the whitespace-delimited word containing *pos*."""
    start = pos
    while start > 0 and not text[start - 1].isspace():
        start -= 1
    end = pos
    while end < len(text) and not text[end].isspace():
        end += 1
    return start, end


class EvidenceGate:
    """Judges whether a proposed codepoint change to a word is permitted."""

    def __init__(self, validator: ScriptValidator, lexicon: Lexicon | None = None) -> None:
        self._validator = validator
        self._lexicon = lexicon if lexicon is not None else Lexicon(validator.language)

    @property
    def lexicon(self) -> Lexicon:
        return self._lexicon

    def judge_word(self, before: str, after: str) -> Verdict:
        """Judge replacing the single word *before* with *after*."""
        before = unicodedata.normalize("NFC", before)
        after = unicodedata.normalize("NFC", after)
        if before == after:
            return Verdict(True, "noop")
        # Sacred-text lock: a verbatim scripture word is never touched automatically.
        if self._lexicon.is_scripture(before):
            return Verdict(False, "scripture_locked")
        b_before = self._validator.badness(before)
        b_after = self._validator.badness(after)
        if b_after > b_before:
            return Verdict(False, "worsens_validity")
        # Re-ordering the same codepoints is a safe canonicalization.
        if Counter(before) == Counter(after):
            return Verdict(True, "reorder")
        # Substitution: demands positive evidence.
        if b_after < b_before:
            return Verdict(True, "validity_improved")
        if (
            self._lexicon.available
            and self._lexicon.is_word(after)
            and not self._lexicon.is_word(before)
        ):
            return Verdict(True, "lexicon_confirmed")
        return Verdict(False, "no_evidence")

    def judge_edit(self, text: str, candidate: str, pos: int) -> Verdict:
        """Judge an edit that turned *text* into *candidate*, changing the word at *pos*.

        Only the affected word is judged, so a correction is evaluated against the
        token it actually changes rather than the whole line.
        """
        s0, e0 = word_span(text, pos)
        s1, e1 = word_span(candidate, pos)
        return self.judge_word(text[s0:e0], candidate[s1:e1])
