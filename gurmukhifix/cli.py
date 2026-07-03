"""CLI Interface for gurmukhifix.

Usage:
    gurmukhifix correct --input tesseract_output.json --lang gurmukhi --output ./results
    gurmukhifix batch --input-dir ./pages --lang urdu --workers 4
    gurmukhifix review --flagged ./results/flagged.json --corrections ./corrections.db
    gurmukhifix report --corrections ./corrections.db --lang hindi
"""

from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import click

from .integration import DocumentProcessor, process_document
from .learner import CorrectionStore
from .ocr import load_ocr

SUPPORTED_LANGUAGES = ["gurmukhi", "punjabi", "hindi", "devanagari", "urdu", "farsi"]
OCR_FORMATS = [
    "auto",
    "tesseract_json",
    "tesseract_tsv",
    "hocr",
    "alto",
    "surya",
    "google_vision",
    "text",
]
_SAMPLES_DIR = Path(__file__).parent / "samples"

# Errors that mean "bad input", to be reported as a one-line message (not a traceback).
_INPUT_ERRORS = (ValueError, json.JSONDecodeError, FileNotFoundError, OSError)


@click.group()
@click.version_option()
def cli() -> None:
    """gurmukhifix — Tesseract OCR post-processing for South Asian and Persian scripts."""


# ---------------------------------------------------------------------------
# correct
# ---------------------------------------------------------------------------

@cli.command()
@click.option(
    "--input", "input_file", required=True, type=click.Path(exists=True),
    help="Path to Tesseract JSON output file."
)
@click.option(
    "--lang", required=True,
    type=click.Choice(SUPPORTED_LANGUAGES, case_sensitive=False),
    help="Script/language to correct."
)
@click.option(
    "--output", "output_dir", default="./results", show_default=True,
    type=click.Path(),
    help="Directory for output artifacts."
)
@click.option(
    "--format", "fmt", default="auto", show_default=True,
    type=click.Choice(OCR_FORMATS, case_sensitive=False),
    help="OCR output format ('auto' detects it)."
)
@click.option(
    "--corrections", "db_path", default=None, type=click.Path(exists=True),
    help="Optional corrections database; its promoted corrections are applied."
)
def correct(input_file: str, lang: str, output_dir: str, fmt: str, db_path: str | None) -> None:
    """Correct a single OCR output file (Tesseract JSON/TSV/hOCR, ALTO, Surya, …)."""
    click.echo(f"Processing {input_file} [{lang}] …")
    store = CorrectionStore(db_path) if db_path else None
    try:
        result = process_document(Path(input_file), lang, output_dir=output_dir, store=store, fmt=fmt)
    except _INPUT_ERRORS as exc:
        # Never dump a traceback for a bad input file — one actionable line + exit 1.
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from None
    finally:
        if store is not None:
            store.close()
    n_corr = len(result["correction_report"])
    n_flag = len(result["flagged"])
    elapsed = result["metadata"]["processing_time_seconds"]
    click.echo(
        f"Done. {n_corr} correction(s), {n_flag} flagged region(s). "
        f"Time: {elapsed:.3f}s"
    )
    click.echo(f"Output written to: {output_dir}/ (corrected_text.txt, correction_report.json, …)")
    if n_flag:
        click.echo(f"Next: review flagged regions with  gurmukhifix review --flagged {output_dir}/flagged.json")


# ---------------------------------------------------------------------------
# batch
# ---------------------------------------------------------------------------

# Each worker process builds one DocumentProcessor (and optional store) and
# reuses it across every file it handles — avoids re-parsing YAML and
# recompiling regex per file.
_WORKER: dict[str, Any] = {}


def _worker_init(language: str, db_path: str | None, fmt: str) -> None:
    store = CorrectionStore(db_path) if db_path else None
    _WORKER["processor"] = DocumentProcessor(language, store=store)
    _WORKER["fmt"] = fmt


def _process_file_worker(args: tuple[str, str]) -> dict[str, Any]:
    """Worker function for parallel batch processing."""
    input_file, output_dir = args
    try:
        processor = _WORKER["processor"]
        result = processor.process(load_ocr(Path(input_file), _WORKER["fmt"]))
        processor.write_outputs(result, output_dir)
        return {
            "file": input_file,
            "status": "ok",
            "corrections": len(result["correction_report"]),
            "flagged": len(result["flagged"]),
            "time": result["metadata"]["processing_time_seconds"],
        }
    except (FileNotFoundError, json.JSONDecodeError, ValueError, OSError) as exc:
        return {"file": input_file, "status": "error", "error": str(exc)}


@cli.command()
@click.option(
    "--input-dir", required=True, type=click.Path(exists=True),
    help="Directory containing Tesseract JSON files."
)
@click.option(
    "--lang", required=True,
    type=click.Choice(SUPPORTED_LANGUAGES, case_sensitive=False),
    help="Script/language to correct."
)
@click.option(
    "--output-dir", "output_dir", default="./results", show_default=True,
    type=click.Path(),
    help="Base directory for output artifacts."
)
@click.option(
    "--workers", default=None, type=int,
    help="Number of parallel workers (default: CPU count - 1)."
)
@click.option(
    "--pattern", default="*.json", show_default=True,
    help="Glob pattern for input files."
)
@click.option(
    "--format", "fmt", default="auto", show_default=True,
    type=click.Choice(OCR_FORMATS, case_sensitive=False),
    help="OCR output format ('auto' detects it)."
)
@click.option(
    "--corrections", "db_path", default=None, type=click.Path(exists=True),
    help="Optional corrections database; its promoted corrections are applied."
)
def batch(
    input_dir: str,
    lang: str,
    output_dir: str,
    workers: int | None,
    pattern: str,
    fmt: str,
    db_path: str | None,
) -> None:
    """Process a directory of Tesseract JSON files in parallel."""
    input_path = Path(input_dir)
    files = sorted(input_path.glob(pattern))
    if not files:
        click.echo(f"No files matching '{pattern}' found in {input_dir}.", err=True)
        sys.exit(1)

    if workers is None:
        workers = max(1, (os.cpu_count() or 2) - 1)

    click.echo(f"Batch processing {len(files)} file(s) with {workers} worker(s) [{lang}] …")

    # Mirror each input's path *relative to the input dir* into the output dir, so
    # files that share a stem in different subfolders don't clobber each other.
    tasks: list[tuple[str, str]] = []
    for f in files:
        try:
            rel = f.relative_to(input_path).with_suffix("")
        except ValueError:
            rel = Path(f.stem)
        tasks.append((str(f), str(Path(output_dir) / rel)))

    results: list[dict[str, Any]] = []
    with ProcessPoolExecutor(
        max_workers=workers, initializer=_worker_init, initargs=(lang, db_path, fmt)
    ) as pool:
        futures = {pool.submit(_process_file_worker, t): t for t in tasks}
        for future in as_completed(futures):
            res = future.result()
            results.append(res)
            if res["status"] == "ok":
                click.echo(f"  ✓ {Path(res['file']).name}")
            else:
                # Surface the reason so a failure in a large run is triageable.
                click.echo(f"  ✗ {Path(res['file']).name}: {res.get('error', 'unknown error')}", err=True)

    ok = sum(1 for r in results if r["status"] == "ok")
    failed = [r for r in results if r["status"] != "ok"]
    click.echo(f"\nBatch complete: {ok} succeeded, {len(failed)} failed.")
    if failed:
        click.echo("Failed files:", err=True)
        for r in failed:
            click.echo(f"  {Path(r['file']).name}: {r.get('error', 'unknown error')}", err=True)


# ---------------------------------------------------------------------------
# review
# ---------------------------------------------------------------------------

@cli.command()
@click.option(
    "--flagged", "flagged_path", required=True, type=click.Path(exists=True),
    help="Path to flagged.json or metadata.json with flagged regions."
)
@click.option(
    "--corrections", "db_path", default="./corrections.db", show_default=True,
    type=click.Path(),
    help="Path to corrections database."
)
def review(flagged_path: str, db_path: str) -> None:
    """Interactive review of flagged OCR regions."""
    path = Path(flagged_path)
    with path.open(encoding="utf-8") as fh:
        raw: Any = json.load(fh)

    # Support both a bare list of flagged regions (flagged.json)
    # and a metadata.json-style object with an embedded flagged list.
    if isinstance(raw, list):
        flagged_data: list[dict[str, Any]] = raw
    elif isinstance(raw, dict):
        if isinstance(raw.get("flagged"), list):
            flagged_data = raw["flagged"]
        else:
            click.echo(
                "No flagged regions found in JSON file. "
                "Expected a list or a dict with a 'flagged' key.",
                err=True,
            )
            sys.exit(1)
    else:
        click.echo(
            "Unsupported JSON structure; expected a list or object.",
            err=True,
        )
        sys.exit(1)

    if not flagged_data:
        click.echo("No flagged regions to review.")
        return

    store = CorrectionStore(db_path)
    reviewed = 0

    for region in flagged_data:
        click.echo("\n" + "─" * 60)
        click.echo(f"Word [{region.get('word_index', '?')}]: {region.get('original', '')!r}")
        click.echo(f"Confidence: {region.get('original_confidence', '?')}")
        if region.get("alternatives"):
            click.echo("Alternatives:")
            for alt in region["alternatives"]:
                click.echo(f"  • {alt.get('text', '')!r} ({alt.get('confidence', '?')})")

        corrected = click.prompt(
            "Enter corrected text (or press Enter to skip)", default="", show_default=False
        )
        if corrected:
            store.record_correction(
                script=region.get("script", "unknown"),
                original_sequence=region.get("original", ""),
                corrected_sequence=corrected,
                source_document=region.get("source_document", ""),
                reviewer_id="cli_review",
                rule_applied="manual_review",
            )
            reviewed += 1
            click.echo(f"Saved correction: {region.get('original', '')!r} → {corrected!r}")

    store.close()
    click.echo(f"\nReview complete. {reviewed} correction(s) saved.")


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

@cli.command()
@click.option(
    "--corrections", "db_path", default="./corrections.db", show_default=True,
    type=click.Path(),
    help="Path to corrections database."
)
@click.option(
    "--lang", required=True,
    type=click.Choice(SUPPORTED_LANGUAGES, case_sensitive=False),
    help="Script/language to report on."
)
@click.option(
    "--output", "output_file", default=None, type=click.Path(),
    help="Write report to this JSON file (default: stdout)."
)
def report(db_path: str, lang: str, output_file: str | None) -> None:
    """Generate a corrections report for a language."""
    if not Path(db_path).exists():
        click.echo(f"Database not found: {db_path}", err=True)
        sys.exit(1)

    store = CorrectionStore(db_path)
    rep = store.generate_report(lang)
    store.close()

    output = json.dumps(rep, ensure_ascii=False, indent=2)

    if output_file:
        Path(output_file).write_text(output, encoding="utf-8")
        click.echo(f"Report written to {output_file}")
    else:
        click.echo(output)


# ---------------------------------------------------------------------------
# demo / formats
# ---------------------------------------------------------------------------

@cli.command()
@click.option(
    "--lang", default="gurmukhi", show_default=True,
    type=click.Choice(SUPPORTED_LANGUAGES, case_sensitive=False),
    help="Which bundled sample to run."
)
def demo(lang: str) -> None:
    """Run gurmukhifix on a bundled OCR sample and show the before/after."""
    sample = _SAMPLES_DIR / f"{lang}.json"
    if not sample.exists():
        available = ", ".join(p.stem for p in sorted(_SAMPLES_DIR.glob("*.json")))
        click.echo(f"No bundled sample for '{lang}'. Available: {available}", err=True)
        raise SystemExit(1)
    doc = load_ocr(sample)
    original = " ".join(w["text"] for w in doc.words)
    result = process_document(sample, lang)
    click.echo(f"Sample [{lang}]: {sample.name}")
    click.echo(f"  OCR input : {original}")
    click.echo(f"  Corrected : {result['corrected_text']}")
    report = result["correction_report"]
    if report:
        fixes = ", ".join(f"{c['original']!r}→{c['corrected']!r} ({c['rule']})" for c in report)
        click.echo(f"  {len(report)} fix(es) : {fixes}")
    else:
        click.echo("  (no corrections needed)")
    click.echo(f"\nRun it on your own OCR:  gurmukhifix correct --input your_ocr.tsv --lang {lang}")


@cli.command(name="formats")
def formats_cmd() -> None:
    """List the OCR output formats gurmukhifix can read."""
    click.echo("gurmukhifix reads OCR output from any of these (auto-detected):\n")
    for fmt in OCR_FORMATS:
        if fmt != "auto":
            click.echo(f"  • {fmt}")
    click.echo(
        "\nStock-Tesseract on-ramp (no special build needed):\n"
        "  tesseract page.png out tsv\n"
        "  gurmukhifix correct --input out.tsv --lang gurmukhi"
    )


if __name__ == "__main__":
    cli()
