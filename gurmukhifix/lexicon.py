"""Gurbani + Punjabi lexicons for evidence-gated correction and scripture locking.

The word lists are derived from the **Shabad OS database**
(https://github.com/shabados/database), which compiles the verbatim Gurmukhi text
of Sri Guru Granth Sahib Ji, Sri Dasam Granth, the Vaaran of Bhai Gurdas, and the
works of Bhai Nand Lal, together with published Punjabi commentaries (teekas). The
Gurbani text itself is in the public domain. See ``gurmukhifix/data/LEXICON.md``
for full provenance and the regeneration command.

Two tiers are shipped:

* **gurbani** — verbatim scripture word-forms only. High precision. Used to *lock*
  scripture tokens against automatic mutation (the sacred-text invariant) and as
  the strongest correction evidence.
* **punjabi** — the gurbani tier plus word-forms harvested from Gurmukhi-script
  teekas. Broader recall. Used as general dictionary evidence when gating a
  same-validity confusion correction (does the edit turn a non-word into a real
  word?).

Only the Gurmukhi scripts (``gurmukhi``/``punjabi``) have lexicons; for every other
language the lexicon is empty and :attr:`Lexicon.available` is ``False``, so
lexicon-gated corrections simply never fire there.
"""

from __future__ import annotations

import gzip
import unicodedata
from functools import lru_cache
from pathlib import Path

_DATA_DIR = Path(__file__).parent / "data"

# Languages whose text is Gurmukhi and therefore share the Gurmukhi word lists.
_GURMUKHI_LANGS = frozenset({"gurmukhi", "punjabi"})


@lru_cache(maxsize=None)
def _load(name: str) -> frozenset[str]:
    """Load a gzipped, newline-delimited word list into a normalized frozenset."""
    path = _DATA_DIR / f"{name}.txt.gz"
    if not path.exists():  # pragma: no cover - data always shipped in the wheel
        return frozenset()
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return frozenset(
            unicodedata.normalize("NFC", line.strip())
            for line in fh
            if line.strip()
        )


class Lexicon:
    """Membership queries over the Gurbani / Punjabi word lists for one language."""

    def __init__(self, language: str) -> None:
        self.language = language
        if language in _GURMUKHI_LANGS:
            self._scripture = _load("gurbani")
            # ``punjabi`` is a superset that already contains every gurbani word.
            self._words = _load("punjabi") | self._scripture
        else:
            self._scripture = frozenset()
            self._words = frozenset()

    @property
    def available(self) -> bool:
        """Whether any dictionary evidence exists for this language."""
        return bool(self._words)

    def is_word(self, token: str) -> bool:
        """True if *token* is a known Gurmukhi/Punjabi word-form (any tier)."""
        if not token:
            return False
        return unicodedata.normalize("NFC", token) in self._words

    def is_scripture(self, token: str) -> bool:
        """True if *token* is a verbatim Gurbani (scripture) word-form.

        Scripture word-forms are *locked*: the pipeline must never alter them
        automatically. Because only already-correct verbatim tokens are members,
        this locks correct text while leaving genuinely mangled OCR (which is not
        a member) free to be repaired.
        """
        if not token:
            return False
        return unicodedata.normalize("NFC", token) in self._scripture
