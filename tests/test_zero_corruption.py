"""The zero-silent-corruption invariants — the most important tests in the suite.

For a tool that touches Gurbani and heritage manuscripts, silently turning valid
text into *different* valid text is the worst possible failure. These tests prove,
rather than hope, that:

* a correction pass never makes any input's script-validity badness *worse*
  (property-fuzzed across every supported script);
* verbatim scripture word-forms are locked — never altered automatically, even
  with an adversarial corrections database attached;
* the two historical silent-corruption bugs (blind hamza rewrite of valid
  Arabic-script text; a promoted pair globally rewriting clean scripture) stay
  fixed.
"""

from __future__ import annotations

import random

from hypothesis import given, settings
from hypothesis import strategies as st

from gurmukhifix.corrector import CharacterCorrector
from gurmukhifix.diacritic import DiacriticRecovery, recover_diacritics
from gurmukhifix.integration import process_document
from gurmukhifix.learner import CorrectionStore
from gurmukhifix.lexicon import Lexicon
from gurmukhifix.validator import ScriptValidator

# A representative Gurmukhi alphabet (consonants, independent + dependent vowels,
# nukta, addak, tippi, bindi, virama) plus a space, for property generation.
_GURMUKHI_ALPHABET = "ਕਖਗਘਙਚਛਜਝਞਟਠਡਢਣਤਥਦਧਨਪਫਬਭਮਯਰਲਵਸਹੜ" "ਾਿੀੁੂੇੈੋੌ" "ਸ਼ਖ਼ਗ਼ਜ਼ਫ਼ਲ਼" "ੰੱਂਿੑ ਅਆਇਈਉਊਏਐਓਔ"
_DEVANAGARI_ALPHABET = "कखगघचछजझटठडढणतथदधनपफबभमयरलवशषसह" "ािीुूेैोौं्ृ अआइईउऊएऐओऔ"
_ARABIC_ALPHABET = "ابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهیءئأإآة "

_gurmukhi_text = st.text(alphabet=_GURMUKHI_ALPHABET, min_size=0, max_size=14)
_devanagari_text = st.text(alphabet=_DEVANAGARI_ALPHABET, min_size=0, max_size=14)
_arabic_text = st.text(alphabet=_ARABIC_ALPHABET, min_size=0, max_size=14)


def _pipeline_word(text: str, language: str, store=None) -> str:
    """Run a single word through the mutating correction passes and return it."""
    data = {"words": [{"text": text, "conf": 70.0, "bbox": [], "alternatives": []}]}
    return process_document(data, language, store=store)["corrected_text"]


# ---------------------------------------------------------------------------
# Property: no pass ever worsens script-validity badness.
# ---------------------------------------------------------------------------


class TestNeverWorsensBadness:
    @settings(max_examples=200, deadline=None)
    @given(_gurmukhi_text)
    def test_gurmukhi(self, s: str) -> None:
        self._check(s, "gurmukhi")

    @settings(max_examples=200, deadline=None)
    @given(_gurmukhi_text)
    def test_punjabi(self, s: str) -> None:
        self._check(s, "punjabi")

    @settings(max_examples=200, deadline=None)
    @given(_devanagari_text)
    def test_hindi(self, s: str) -> None:
        self._check(s, "hindi")

    @settings(max_examples=150, deadline=None)
    @given(_devanagari_text)
    def test_devanagari(self, s: str) -> None:
        self._check(s, "devanagari")

    @settings(max_examples=150, deadline=None)
    @given(_arabic_text)
    def test_urdu(self, s: str) -> None:
        self._check(s, "urdu")

    @settings(max_examples=150, deadline=None)
    @given(_arabic_text)
    def test_farsi(self, s: str) -> None:
        self._check(s, "farsi")

    @staticmethod
    def _check(s: str, language: str) -> None:
        v = ScriptValidator(language)
        before = v.badness(s)
        corrected, _ = CharacterCorrector(language).correct(s)
        assert v.badness(corrected) <= before, f"corrector worsened {s!r} -> {corrected!r}"
        recovered, _ = DiacriticRecovery(language).recover(s)
        assert v.badness(recovered) <= before, f"diacritic worsened {s!r} -> {recovered!r}"


# ---------------------------------------------------------------------------
# Scripture lock: verbatim Gurbani word-forms are never altered automatically.
# ---------------------------------------------------------------------------


def _sample_scripture(n: int, seed: int = 0) -> list[str]:
    words = sorted(Lexicon("gurmukhi")._scripture)  # noqa: SLF001 - test introspection
    rng = random.Random(seed)
    # Bias toward real multi-letter words (single marks/letters are trivially stable).
    candidates = [w for w in words if len(w) >= 3]
    return rng.sample(candidates, min(n, len(candidates)))


class TestScriptureLock:
    def test_sampled_scripture_words_unchanged(self) -> None:
        for word in _sample_scripture(400):
            out, _ = CharacterCorrector("gurmukhi").correct(word)
            assert out == word, f"scripture word mutated: {word!r} -> {out!r}"

    def test_scripture_unchanged_through_pipeline(self) -> None:
        for word in _sample_scripture(200, seed=1):
            assert _pipeline_word(word, "gurmukhi") == word

    def test_scripture_locked_against_adversarial_promotions(self) -> None:
        # An attacker-supplied / poisoned corrections DB full of same-class swaps
        # must still never rewrite a verbatim scripture word.
        store = CorrectionStore(":memory:")
        poison = [("ਕ", "ਖ"), ("ਸ", "ਸ਼"), ("ਨ", "ਗ"), ("ਤ", "ਥ"), ("ਬ", "ਭ")]
        for wrong, right in poison:
            for _ in range(10):
                store.record_correction(
                    script="gurmukhi", original_sequence=wrong, corrected_sequence=right
                )
        for word in _sample_scripture(200, seed=2):
            assert _pipeline_word(word, "gurmukhi", store=store) == word
        store.close()


# ---------------------------------------------------------------------------
# Regressions for the two historical silent-corruption bugs.
# ---------------------------------------------------------------------------


class TestHistoricalCorruptionBugs:
    def test_hamza_does_not_rewrite_valid_arabic_script(self) -> None:
        # Bug 1: `_recover_hamza_carrier` rewrote valid یء -> ئ with no evidence.
        for language in ("farsi", "urdu"):
            out, corrections = recover_diacritics("یء", language)
            assert out == "یء"
            assert corrections == []

    def test_promoted_pair_does_not_rewrite_clean_scripture(self) -> None:
        # Bug 2: a promoted (ਕ,ਖ) globally rewrote clean ਕਾਲ ਕਰ -> ਖਾਲ ਖਰ.
        c = CharacterCorrector("gurmukhi", promoted=[("ਕ", "ਖ")])
        out, corrections = c.correct("ਕਾਲ ਕਰ")
        assert out == "ਕਾਲ ਕਰ"
        assert corrections == []

    def test_diacritic_removal_does_not_delete_load_bearing_mark(self) -> None:
        # A removal-to-'' rule must not strip a meaningful mark from a valid word.
        v = ScriptValidator("gurmukhi")
        word = "ਭਾਸ਼ਾ"  # contains a load-bearing nukta (ਸ਼)
        out, _ = CharacterCorrector("gurmukhi").correct(word)
        assert v.badness(out) <= v.badness(word)
        assert "਼" in out or out == word


# ---------------------------------------------------------------------------
# Config hygiene: extends must not produce duplicate correction candidates.
# ---------------------------------------------------------------------------


def test_no_duplicate_confusion_pairs_after_merge() -> None:
    from gurmukhifix.config import load_config

    for language in ("gurmukhi", "punjabi", "hindi", "devanagari", "urdu", "farsi"):
        cfg = load_config(language)
        pairs = [(p["wrong"], p["correct"]) for p in cfg.get("confusion_pairs", [])]
        assert len(pairs) == len(set(pairs)), f"{language} has duplicate confusion pairs"
