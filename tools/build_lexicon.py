#!/usr/bin/env python3
"""Regenerate the Gurbani / Punjabi lexicons shipped in ``gurmukhifix/data/``.

Downloads the Shabad OS database (``@shabados/database``) via ``npm pack``, extracts
the verbatim Gurmukhi scripture text and the Gurmukhi-script teekas, tokenises them,
and writes two gzipped word lists:

* ``gurbani.txt.gz`` — verbatim scripture word-forms (the locked set)
* ``punjabi.txt.gz`` — scripture + teeka vocabulary with ``freq >= PUNJABI_MIN_FREQ``

The output is deterministic (sorted, NFC-normalised) for a given database version,
so re-running on the same version produces byte-identical files. See
``gurmukhifix/data/LEXICON.md`` for provenance.

Usage:
    python tools/build_lexicon.py [--db path/to/master.sqlite]
"""

from __future__ import annotations

import argparse
import collections
import gzip
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import unicodedata
from pathlib import Path

import regex

# Pin the database version so builds are reproducible. Bump to refresh the data.
SHABADOS_PKG = "@shabados/database@5.0.0-next.0"
PUNJABI_MIN_FREQ = 2  # drop hapax teeka forms to suppress commentary OCR noise

_ROOT = Path(__file__).resolve().parent.parent
_OUT_DIR = _ROOT / "gurmukhifix" / "data"

# A Gurmukhi word: one or more letters/marks from the Gurmukhi block, excluding the
# digit range U+0A66–U+0A6F (verse numbers) which are filtered per-token below.
_WORD = regex.compile(r"[ਁ-ੵ]+")
_DIGITS = set(range(0x0A66, 0x0A70))


def _tokens(line: str):
    for m in _WORD.finditer(line):
        w = m.group()
        if any(ord(ch) in _DIGITS for ch in w):
            continue
        yield unicodedata.normalize("NFC", w)


def _is_gurmukhi(s: str) -> bool:
    return any("਀" <= ch <= "੿" for ch in s)


def _download_db(workdir: Path) -> Path:
    print(f"Downloading {SHABADOS_PKG} via npm …", file=sys.stderr)
    subprocess.run(
        ["npm", "pack", SHABADOS_PKG], cwd=workdir, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    tgz = next(workdir.glob("*.tgz"))
    with tarfile.open(tgz) as tf:
        member = next(m for m in tf.getmembers() if m.name.endswith("master.sqlite"))
        tf.extract(member, workdir)
    return workdir / member.name


def build(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    gurbani: collections.Counter[str] = collections.Counter()
    punjabi: collections.Counter[str] = collections.Counter()

    for (data,) in conn.execute(
        "SELECT data FROM asset_lines WHERE type='primary' AND data IS NOT NULL AND data!=''"
    ):
        for w in _tokens(data):
            gurbani[w] += 1
            punjabi[w] += 1

    for (data,) in conn.execute(
        "SELECT data FROM asset_lines WHERE type IN ('translation','note') "
        "AND data IS NOT NULL AND data!=''"
    ):
        if _is_gurmukhi(data):
            for w in _tokens(data):
                punjabi[w] += 1

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    _write(_OUT_DIR / "gurbani.txt.gz", {w for w in gurbani})
    _write(_OUT_DIR / "punjabi.txt.gz", {w for w, n in punjabi.items() if n >= PUNJABI_MIN_FREQ})
    print(f"gurbani.txt.gz: {len(gurbani)} words", file=sys.stderr)
    print(
        f"punjabi.txt.gz: {sum(1 for n in punjabi.values() if n >= PUNJABI_MIN_FREQ)} words",
        file=sys.stderr,
    )


def _write(path: Path, words: set[str]) -> None:
    payload = "\n".join(sorted(words)) + "\n"
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as fh:
        fh.write(payload)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=None, help="path to an existing master.sqlite")
    args = ap.parse_args()

    if args.db:
        build(args.db)
        return
    if shutil.which("npm") is None:
        sys.exit("npm not found; install Node.js or pass --db path/to/master.sqlite")
    with tempfile.TemporaryDirectory() as tmp:
        build(_download_db(Path(tmp)))


if __name__ == "__main__":
    main()
