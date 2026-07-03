<!--
Thanks for contributing to gurmukhifix. Please fill in the summary and the
checklist. See CONTRIBUTING.md for the full workflow and the correctness invariant.
-->

## Summary

<!-- What does this PR change, and why? Link any issue it closes (e.g. "Closes #12"). -->

## Type of change

- [ ] Bug fix
- [ ] New / changed language rule (`gurmukhifix/configs/*.yaml`)
- [ ] New feature (script, OCR format, CLI/API)
- [ ] Docs / governance only
- [ ] Lexicon regeneration (`tools/build_lexicon.py`)

## Checklist

- [ ] **Added a regression test with the exact triggering input** (for a bug fix
      or a new rule), asserted against the correct output.
- [ ] **`pytest` is green**, including the property-based zero-corruption tests.
- [ ] **`python -m tests.benchmark` passes** — clean text stays at CER `0.0000`.
- [ ] **`ruff check .` and `mypy gurmukhifix` are clean.**
- [ ] **No change can corrupt valid or scripture text.** Every new correction path
      routes through the evidence gate; verbatim Gurbani stays locked and
      substitutions are backed by a validity gain or a dictionary hit.
- [ ] Docs / CHANGELOG updated if user-facing behaviour changed.
- [ ] Lexicons, if changed, were regenerated with `tools/build_lexicon.py` (not
      hand-edited) and provenance is recorded.

## Notes for reviewers

<!-- Anything that needs extra attention: the exact input your regression test
uses, edge cases, or a rationale for why an edit clears the evidence gate. -->
