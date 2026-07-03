"""Tests for the developer-experience CLI surface (demo, formats, error handling)."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from gurmukhifix.cli import cli


def test_demo_runs_and_shows_before_after() -> None:
    result = CliRunner().invoke(cli, ["demo", "--lang", "gurmukhi"])
    assert result.exit_code == 0
    assert "Corrected" in result.output
    assert "OCR input" in result.output


def test_formats_lists_engines() -> None:
    result = CliRunner().invoke(cli, ["formats"])
    assert result.exit_code == 0
    assert "tesseract_tsv" in result.output
    assert "surya" in result.output


def test_correct_bad_json_is_one_line_error_not_traceback(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{ this is not valid json", encoding="utf-8")
    result = CliRunner().invoke(cli, ["correct", "--input", str(bad), "--lang", "gurmukhi"])
    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "Traceback" not in result.output


def test_correct_from_tsv_on_ramp(tmp_path: Path) -> None:
    tsv = tmp_path / "page.tsv"
    tsv.write_text(
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t0\t0\t9\t9\t72\tਿਸਮਰ\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    result = CliRunner().invoke(
        cli, ["correct", "--input", str(tsv), "--lang", "gurmukhi", "--output", str(out)]
    )
    assert result.exit_code == 0
    assert (out / "corrected_text.txt").read_text(encoding="utf-8").strip() == "ਸਿਮਰ"
