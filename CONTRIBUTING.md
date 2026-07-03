# Contributing to gurmukhifix

Thank you for helping improve gurmukhifix. This project corrects sacred and
heritage text, including Gurbani, so contributions are held to one
**non-negotiable** standard before anything else: **no change may corrupt valid
text.** Everything below serves that guarantee.

Please also read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).

---

## The correctness invariant (read this first)

> **A correction may never turn correct text into different text.** Verbatim
> scripture (Gurbani) is locked and is never altered automatically. Any other
> substitution must be backed by evidence. Turning one valid word into a
> *different* valid word is the worst possible failure, and no feature, speed, or
> coverage improvement is worth it.

This is not a guideline — it is the reason the project exists, and it is
[property-tested](tests/test_zero_corruption.py) across every supported script and
against the whole Gurbani corpus. A pull request that regresses those tests will
not be merged.

### The evidence gate

Every automatic codepoint change flows through the single rule in
[`gurmukhifix/evidence.py`](gurmukhifix/evidence.py), judged at the level of the
individual word it touches:

- **Scripture is locked.** A verbatim Gurbani word is never changed automatically
  (`scripture_locked`). Only a human-confirmed review correction may touch it.
- **An edit may never worsen validity.** A change that increases a word's
  script-validity "badness" is refused (`worsens_validity`).
- **Substitutions demand positive evidence.** A codepoint substitution (the
  multiset of codepoints changes) is allowed only if it strictly lowers badness
  (`validity_improved`) **or** turns a non-word into a known dictionary word
  (`lexicon_confirmed`). A blind swap between two valid characters with no
  dictionary support is refused (`no_evidence`) — that guess is exactly what
  silently corrupts good OCR output.
- **Re-orderings are safe.** Moving the same codepoints into canonical order
  (e.g. a sihari after its base consonant) is allowed as long as it does not
  worsen validity (`reorder`).

**Any new correction path — a new rule, a new confusion pair, a learner-promoted
pair — must route its changes through the evidence gate.** Do not add a code path
that mutates text without a `judge_word` / `judge_edit` verdict behind it.

---

## Development setup

```bash
git clone https://github.com/jsdosanj/gurmukhifix
cd gurmukhifix
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Python 3.10–3.12 are supported. No system OCR libraries are required — gurmukhifix
processes OCR *output*, so your OCR engine is a peer, not a runtime dependency.

## Running the checks

Everything CI runs, you can run locally. A pull request must be green on all of
these before review:

```bash
pytest                      # full suite, incl. the property-based zero-corruption battery
python -m tests.benchmark   # accuracy benchmark + no-corruption gate on real Gurbani
ruff check .                # lint
mypy gurmukhifix            # types
```

The benchmark doubles as a safety gate: the clean SGGS lines must keep a corrected
Character Error Rate of `0.0000`. If your change corrupts clean text, the benchmark
fails.

---

## The hard rule: every bug fix ships a regression test

**A fix without a test that reproduces the original bug will not be merged.** The
test must use the **exact triggering input** — the OCR text (and its
script/language) that produced the wrong output — asserted against the correct
result. This is how a fixed bug stays fixed and how we prove the fix does not
introduce new corruption.

When you file a bug, the [issue template](.github/ISSUE_TEMPLATE/bug_report.md)
asks for that exact input for the same reason: it becomes the regression test.

---

## Adding or changing language rules

Per-language behaviour lives in [`gurmukhifix/configs/*.yaml`](gurmukhifix/configs/)
(`gurmukhi.yaml`, `punjabi.yaml`, `hindi.yaml`, `devanagari.yaml`, `urdu.yaml`,
`farsi.yaml`). To add or refine a rule:

1. Edit the relevant config. A config may `extends` a base (e.g. Hindi layers on
   the shared Devanagari rules), so add a rule at the most specific level that is
   correct and avoid duplicating pairs across a base and its extension.
2. Add a regression test with a real triggering input and its expected output.
3. Confirm the rule fires **only** through the evidence gate — a new confusion
   pair must not corrupt any valid word or any scripture word. Run
   `python -m tests.benchmark` and the zero-corruption tests to verify.

Urdu and Farsi are **experimental (structural validation only)**; do not add
diacritic heuristics that fire without a validity or dictionary signal, and do not
claim accuracy that is not benchmarked.

## Regenerating the lexicons

The Gurbani and Punjabi word lists in `gurmukhifix/data/*.txt.gz` power the
scripture lock and the dictionary evidence. They are **generated, not
hand-edited** — regenerate them reproducibly with
[`tools/build_lexicon.py`](tools/build_lexicon.py):

```bash
python tools/build_lexicon.py            # downloads the pinned Shabad OS database via npm
python tools/build_lexicon.py --db path/to/master.sqlite   # or point at a local copy
```

The output is deterministic (sorted, NFC-normalised) for a given, pinned database
version. Bump `SHABADOS_PKG` in the tool to refresh the corpus, and record the
provenance in [`gurmukhifix/data/LEXICON.md`](gurmukhifix/data/LEXICON.md).

---

## Submitting a pull request

1. Branch off `main`.
2. Make the change, add the regression test, keep the diff focused.
3. Run `pytest`, `python -m tests.benchmark`, `ruff check .`, and
   `mypy gurmukhifix` — all green.
4. Fill in the [pull request checklist](.github/pull_request_template.md),
   including the line every reviewer looks for: **no change can corrupt valid or
   scripture text.**

Small, well-tested changes that respect the evidence gate get merged fastest.
