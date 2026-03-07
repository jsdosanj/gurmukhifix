"""CLI Interface for scriptfix.

Usage:
    scriptfix correct --input tesseract_output.json --lang gurmukhi --output ./results
    scriptfix batch --input-dir ./pages --lang urdu --workers 4
    scriptfix review --flagged ./results/flagged.json --corrections ./corrections.db
    scriptfix report --corrections ./corrections.db --lang hindi
"""

from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import click

from .integration import process_document
from .learner import CorrectionStore

SUPPORTED_LANGUAGES = ["gurmukhi", "punjabi", "hindi", "urdu", "farsi"]


@click.group()
@click.version_option()
def cli() -> None:
    """scriptfix — Tesseract OCR post-processing for South Asian and Persian scripts."""


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
def correct(input_file: str, lang: str, output_dir: str) -> None:
    """Correct a single Tesseract JSON file."""
    click.echo(f"Processing {input_file} [{lang}] …")
    result = process_document(Path(input_file), lang, output_dir=output_dir)
    n_corr = len(result["correction_report"])
    n_flag = len(result["flagged"])
    elapsed = result["metadata"]["processing_time_seconds"]
    click.echo(
        f"Done. {n_corr} correction(s), {n_flag} flagged region(s). "
        f"Time: {elapsed:.3f}s"
    )
    click.echo(f"Output written to: {output_dir}")


# ---------------------------------------------------------------------------
# batch
# ---------------------------------------------------------------------------

def _process_file_worker(args: tuple[str, str, str]) -> dict[str, Any]:
    """Worker function for parallel batch processing."""
    input_file, lang, output_dir = args
    try:
        result = process_document(Path(input_file), lang, output_dir=output_dir)
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
def batch(
    input_dir: str,
    lang: str,
    output_dir: str,
    workers: int | None,
    pattern: str,
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

    tasks: list[tuple[str, str, str]] = []
    for f in files:
        file_output = str(Path(output_dir) / f.stem)
        tasks.append((str(f), lang, file_output))

    results: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_process_file_worker, t): t for t in tasks}
        for future in as_completed(futures):
            res = future.result()
            results.append(res)
            status = "✓" if res["status"] == "ok" else "✗"
            click.echo(f"  {status} {Path(res['file']).name}")

    ok = sum(1 for r in results if r["status"] == "ok")
    err = len(results) - ok
    click.echo(f"\nBatch complete: {ok} succeeded, {err} failed.")


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


if __name__ == "__main__":
    cli()
