"""Character Correction Engine for gurmukhifix.

Loads per-script correction rules from YAML config files and applies
character-level confusion and diacritic substitutions to Tesseract OCR
output.

Corrections are **evidence-gated**: a confusion/diacritic substitution is only
applied when it strictly lowers the script-validity "badness" of the
surrounding word (see :class:`gurmukhifix.validator.ScriptValidator`). Well-formed
text scores zero badness, so it is never modified — this is what stops the blind
bidirectional find-replace that would otherwise corrupt correct OCR output.
Substitutions between two individually-valid characters (e.g. an aspirated-pair
confusion) carry no validity evidence and are therefore left untouched rather
than guessed at.
"""

from __future__ import annotations

import unicodedata
from typing import Any, cast

import regex

from .config import load_config as _load_config
from .evidence import BLOCKING_REASONS, EvidenceGate, word_span
from .lexicon import Lexicon
from .validator import ScriptValidator


def _normalize(text: str, form: str = "NFC") -> str:
    """Normalize Unicode text to the specified form."""
    return unicodedata.normalize(cast("Any", form), text)


class _PromotedRule:
    """A corpus-learned, human-confirmed correction, optionally scoped to a context."""

    __slots__ = ("wrong", "correct", "context_before", "context_after")

    def __init__(self, wrong: str, correct: str, context_before: str = "", context_after: str = "") -> None:
        self.wrong = wrong
        self.correct = correct
        self.context_before = context_before
        self.context_after = context_after

    @property
    def has_context(self) -> bool:
        return bool(self.context_before or self.context_after)

    def context_matches(self, text: str, start: int) -> bool:
        """Whether the confirmed context surrounds the match at *start* in *text*."""
        if not self.has_context:
            return False
        before = text[:start]
        after = text[start + len(self.wrong):]
        before_ok = not self.context_before or before.endswith(self.context_before)
        after_ok = not self.context_after or after.startswith(self.context_after)
        return before_ok and after_ok


class CharacterCorrector:
    """Applies confusion-pair and diacritic corrections for a given script."""

    def __init__(
        self,
        language: str,
        promoted: list[tuple[str, str]] | list[dict[str, Any]] | None = None,
        validator: ScriptValidator | None = None,
        lexicon: Lexicon | None = None,
    ) -> None:
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

        # Corpus-learned, human-confirmed corrections promoted by the learner.
        # Each may carry the context in which it was confirmed. They are still run
        # through the evidence gate (never touch scripture, never worsen validity);
        # a matching confirmed context counts as the positive evidence that lets a
        # same-validity swap apply.
        self._promoted_rules: list[_PromotedRule] = self._build_promoted_rules(promoted)

        # Validator + lexicon shared with the rest of the pipeline when injected,
        # to avoid rebuilding them per module.
        self._validator = validator or ScriptValidator(language)
        self._lexicon = lexicon if lexicon is not None else Lexicon(language)
        self._gate = EvidenceGate(self._validator, self._lexicon)

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

        # 1. Corpus-learned promoted corrections (gated: never touch a locked
        #    scripture word, never worsen validity; a confirmed context or a
        #    dictionary hit is the evidence that authorises a same-validity swap).
        text = self._apply_promoted(text, corrections)

        if not self._candidates:
            return text, corrections

        # 2. Built-in confusion/diacritic repair, evidence-gated word by word by
        #    :class:`~gurmukhifix.evidence.EvidenceGate`. A substitution is accepted
        #    only if it strictly lowers script-validity badness OR turns a non-word
        #    into a known dictionary word, and never on a locked scripture word.
        #    Each accepted edit strictly reduces either badness or the non-word
        #    count, so the loop terminates; the cap is a defensive backstop only.
        max_iterations = len(text) + 8
        for _ in range(max_iterations):
            base = self._validator.badness(text)
            # Fast path: an already-valid, known word carries no evidence to change.
            if base <= 0 and self._lexicon.is_word(text):
                break

            best: tuple[tuple[int, float], int, str, str, str] | None = None
            for key, repl, rule in self._candidates:
                start = text.find(key)
                while start != -1:
                    candidate = text[:start] + repl + text[start + len(key):]
                    verdict = self._gate.judge_edit(text, candidate, start)
                    if verdict.allowed:
                        delta = base - self._validator.badness(candidate)
                        # Prefer validity-improving edits (delta > 0) over
                        # lexicon-only edits (delta == 0); ties keep the first found.
                        rank = (1 if delta > 0 else 0, delta)
                        if best is None or rank > best[0]:
                            best = (rank, start, key, repl, rule)
                    start = text.find(key, start + 1)

            if best is None:
                break  # no permitted substitution — stop guessing

            _, pos, key, repl, rule = best
            corrections.append(
                {"original": key, "corrected": repl, "rule": rule, "position": pos}
            )
            text = text[:pos] + repl + text[pos + len(key):]

        return text, corrections

    def _apply_promoted(
        self, text: str, corrections: list[dict[str, Any]]
    ) -> str:
        """Apply promoted corrections through the evidence gate.

        Scripture-locked words and validity-worsening edits are always refused; an
        otherwise-permitted edit applies either on gate evidence (validity/lexicon)
        or when the correction's confirmed context surrounds the match.
        """
        for promoted in self._promoted_rules:
            wrong, correct = promoted.wrong, promoted.correct
            start = text.find(wrong)
            while start != -1:
                candidate = text[:start] + correct + text[start + len(wrong):]
                verdict = self._gate.judge_edit(text, candidate, start)
                if verdict.reason in BLOCKING_REASONS:
                    accept = False
                elif verdict.allowed:
                    accept = True
                else:
                    # A confirmed context may authorise a same-validity swap, but
                    # never on a word that is already a known dictionary word — that
                    # is the one path a poisoned corrections DB could otherwise use
                    # to silently turn one valid word into a different valid word.
                    s, e = word_span(text, start)
                    accept = promoted.context_matches(text, start) and not self._lexicon.is_word(text[s:e])
                if accept:
                    corrections.append(
                        {
                            "original": wrong,
                            "corrected": correct,
                            "rule": "promoted_correction",
                            "position": start,
                        }
                    )
                    text = candidate
                    start = text.find(wrong, start + len(correct))
                else:
                    start = text.find(wrong, start + 1)
        return text

    def _build_promoted_rules(
        self, promoted: list[tuple[str, str]] | list[dict[str, Any]] | None
    ) -> list[_PromotedRule]:
        """Normalise promoted input (legacy tuples or context-carrying dicts)."""
        rules: list[_PromotedRule] = []
        for item in promoted or []:
            if isinstance(item, dict):
                wrong = _normalize(item.get("original_sequence", ""), self.norm_form)
                correct = _normalize(item.get("corrected_sequence", ""), self.norm_form)
                cb = _normalize(item.get("context_before", "") or "", self.norm_form)
                ca = _normalize(item.get("context_after", "") or "", self.norm_form)
            else:
                wrong = _normalize(item[0], self.norm_form)
                correct = _normalize(item[1], self.norm_form)
                cb = ca = ""
            if wrong and wrong != correct:
                rules.append(_PromotedRule(wrong, correct, cb, ca))
        return rules

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
