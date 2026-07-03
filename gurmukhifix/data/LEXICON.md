# Gurbani / Punjabi lexicon data

`gurbani.txt.gz` and `punjabi.txt.gz` are gzipped, newline-delimited, NFC-normalised
Gurmukhi word lists used by [`gurmukhifix.lexicon`](../lexicon.py) for evidence-gated
correction and the sacred-text lock (see [`gurmukhifix.evidence`](../evidence.py)).

| File | Words | Contents |
|------|------:|----------|
| `gurbani.txt.gz` | 67,515 | Verbatim scripture word-forms only (the *locked* set) |
| `punjabi.txt.gz` | 70,986 | Gurmukhi teeka vocabulary (the broader evidence set; `freq ≥ 2`) |

## Source & provenance

Derived from the **Shabad OS database** — <https://github.com/shabados/database>
(package `@shabados/database`, version **5.0.0-next.0**), which compiles:

- **Sri Guru Granth Sahib Ji** (verbatim Gurmukhi)
- **Sri Dasam Granth**
- the **Vaaran of Bhai Gurdas** and **Kabit Sawaiye**
- the works of **Bhai Nand Lal** (Gurmukhi transcriptions)
- published Punjabi commentaries (teekas): Prof. Sahib Singh's *Darpan*, the
  *Faridkot Wala Teeka*, *Shabadaarth*, and others.

The Gurbani text itself is in the **public domain**. The Shabad OS database
compilation is distributed under its own permissive licence; gurmukhifix ships only
derived word lists (no line text, translations, or annotations).

`gurbani.txt.gz` is drawn from the `primary` (verbatim scripture) lines only.
`punjabi.txt.gz` additionally harvests Gurmukhi-script `translation`/`note` lines
(the teekas), dropping hapax forms (`freq ≥ 2`) to suppress commentary OCR noise.

## Regenerating

```bash
python tools/build_lexicon.py            # downloads @shabados/database via npm
```

The build tool is deterministic: the same database version yields byte-identical
word lists (sorted, NFC-normalised). Bump the pinned version in `tools/build_lexicon.py`
to refresh.
