"""Tests for the CLI interface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from scriptfix.cli import cli


SAMPLE_JSON = {
    "words": [
        {"text": "ਸਤਿ", "conf": 70.0, "bbox": [0, 0, 50, 20], "alternatives": []},
        {"text": "ਸ੍ਰੀ", "conf": 90.0, "bbox": [55, 0, 100, 20], "alternatives": []},
    ]
}


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def sample_json_file(tmp_path: Path) -> Path:
    f = tmp_path / "input.json"
    f.write_text(json.dumps(SAMPLE_JSON), encoding="utf-8")
    return f


class TestCorrectCommand:
    def test_correct_basic(self, runner: CliRunner, sample_json_file: Path, tmp_path: Path) -> None:
        out_dir = str(tmp_path / "output")
        result = runner.invoke(cli, [
            "correct",
            "--input", str(sample_json_file),
            "--lang", "gurmukhi",
            "--output", out_dir,
        ])
        assert result.exit_code == 0, result.output
        assert "Done" in result.output

    def test_correct_creates_output_files(self, runner: CliRunner, sample_json_file: Path, tmp_path: Path) -> None:
        out_dir = tmp_path / "output"
        runner.invoke(cli, [
            "correct",
            "--input", str(sample_json_file),
            "--lang", "gurmukhi",
            "--output", str(out_dir),
        ])
        assert (out_dir / "corrected_text.txt").exists()
        assert (out_dir / "correction_report.json").exists()
        assert (out_dir / "metadata.json").exists()

    def test_correct_invalid_lang(self, runner: CliRunner, sample_json_file: Path, tmp_path: Path) -> None:
        result = runner.invoke(cli, [
            "correct",
            "--input", str(sample_json_file),
            "--lang", "klingon",
            "--output", str(tmp_path),
        ])
        assert result.exit_code != 0


class TestBatchCommand:
    def test_batch_basic(self, runner: CliRunner, tmp_path: Path) -> None:
        # Create two input files
        for i in range(2):
            f = tmp_path / f"page{i}.json"
            f.write_text(json.dumps(SAMPLE_JSON), encoding="utf-8")

        out_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            "batch",
            "--input-dir", str(tmp_path),
            "--lang", "gurmukhi",
            "--output-dir", str(out_dir),
            "--workers", "1",
        ])
        assert result.exit_code == 0, result.output
        assert "complete" in result.output.lower()

    def test_batch_empty_dir(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(cli, [
            "batch",
            "--input-dir", str(tmp_path),
            "--lang", "gurmukhi",
        ])
        assert result.exit_code != 0


class TestReportCommand:
    def test_report_no_db(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(cli, [
            "report",
            "--corrections", str(tmp_path / "nonexistent.db"),
            "--lang", "hindi",
        ])
        assert result.exit_code != 0

    def test_report_with_db(self, runner: CliRunner, tmp_path: Path) -> None:
        from scriptfix.learner import CorrectionStore
        db_path = tmp_path / "test.db"
        store = CorrectionStore(db_path)
        store.record_correction(
            script="hindi",
            original_sequence="क",
            corrected_sequence="ख",
        )
        store.close()

        result = runner.invoke(cli, [
            "report",
            "--corrections", str(db_path),
            "--lang", "hindi",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["script"] == "hindi"


class TestReviewCommand:
    def test_review_with_flagged_list(self, runner: CliRunner, tmp_path: Path) -> None:
        """review command accepts a bare list (flagged.json)."""
        flagged_file = tmp_path / "flagged.json"
        flagged_file.write_text(
            json.dumps([
                {"word_index": 0, "original": "ਸਤਿ", "original_confidence": 30.0,
                 "alternatives": [], "script": "gurmukhi"}
            ]),
            encoding="utf-8",
        )
        # Simulate pressing Enter to skip
        result = runner.invoke(cli, [
            "review",
            "--flagged", str(flagged_file),
            "--corrections", str(tmp_path / "test.db"),
        ], input="\n")
        assert result.exit_code == 0

    def test_review_with_metadata_json(self, runner: CliRunner, tmp_path: Path) -> None:
        """review command accepts a metadata.json with embedded 'flagged' key."""
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text(
            json.dumps({
                "language": "gurmukhi",
                "flagged": [
                    {"word_index": 0, "original": "ਸਤਿ", "original_confidence": 30.0,
                     "alternatives": [], "script": "gurmukhi"}
                ]
            }),
            encoding="utf-8",
        )
        result = runner.invoke(cli, [
            "review",
            "--flagged", str(meta_file),
            "--corrections", str(tmp_path / "test.db"),
        ], input="\n")
        assert result.exit_code == 0

    def test_review_empty_list(self, runner: CliRunner, tmp_path: Path) -> None:
        flagged_file = tmp_path / "flagged.json"
        flagged_file.write_text("[]", encoding="utf-8")
        result = runner.invoke(cli, [
            "review",
            "--flagged", str(flagged_file),
            "--corrections", str(tmp_path / "test.db"),
        ])
        assert result.exit_code == 0
        assert "No flagged regions" in result.output


class TestCLIGeneral:
    def test_version(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "scriptfix" in result.output.lower()
