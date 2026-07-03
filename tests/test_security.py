"""Security-hardening regressions (from the threat model in docs/SECURITY_DESIGN_REVIEW.md)."""

from __future__ import annotations

import pytest

from gurmukhifix.corrector import CharacterCorrector
from gurmukhifix.lexicon import Lexicon
from gurmukhifix.ocr import load_ocr


def test_poisoned_context_promotion_cannot_rewrite_a_known_word() -> None:
    """A forged-context promoted rule must not turn one valid dictionary word into
    another (TM-001). Scripture is already locked; this covers ordinary known words."""
    lex = Lexicon("punjabi")
    # A known dictionary word that is NOT verbatim scripture.
    word = next(w for w in sorted(lex._words) if len(w) >= 3 and not lex.is_scripture(w))  # noqa: SLF001
    assert lex.is_word(word) and not lex.is_scripture(word)

    swap_to = "ਸ" if word[-1] != "ਸ" else "ਹ"
    rule = {
        "original_sequence": word[-1],
        "corrected_sequence": swap_to,
        "context_before": word[:-1],  # a context that DOES match this word
        "context_after": "",
    }
    out, _ = CharacterCorrector("punjabi", promoted=[rule]).correct(word)
    assert out == word


def test_alto_with_entity_declarations_is_rejected() -> None:
    """Entity-expansion (billion-laughs) DoS vector is refused before parsing (TM-005)."""
    billion_laughs = (
        '<?xml version="1.0"?>'
        '<!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;">]>'
        "<alto><String CONTENT='&lol2;'/></alto>"
    )
    with pytest.raises(ValueError, match="DTD or entity"):
        load_ocr(billion_laughs, fmt="alto")
