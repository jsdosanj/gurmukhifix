"""Tests for the Integration Layer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scriptfix.integration import DocumentProcessor, TesseractOutput, process_document


# ── Sample Tesseract-style JSON ──────────────────────────────────────────────

SAMPLE_GURMUKHI_JSON = {
    "words": [
        {"text": "ਸਤਿ", "conf": 70.0, "bbox": [0, 0, 50, 20], "alternatives": []},
        {"text": "ਸ੍ਰੀ", "conf": 90.0, "bbox": [55, 0, 100, 20], "alternatives": []},
        {"text": "ਅਕਾਲ", "conf": 45.0, "bbox": [105, 0, 160, 20], "alternatives": []},
    ]
}

SAMPLE_HINDI_JSON = {
    "words": [
        {"text": "नमस्ते", "conf": 75.0, "bbox": [0, 0, 80, 20], "alternatives": []},
        {"text": "दुनिया", "conf": 88.0, "bbox": [85, 0, 160, 20], "alternatives": []},
    ]
}

SAMPLE_FLAT_JSON = {
    "text": "اردو",
    "conf": 72.0,
    "bbox": [0, 0, 40, 20],
}


class TestTesseractOutput:
    def test_parse_words_format(self) -> None:
        tess = TesseractOutput(SAMPLE_GURMUKHI_JSON)
        assert len(tess.words) == 3

    def test_parse_pages_format(self) -> None:
        data = {"pages": [{"words": SAMPLE_GURMUKHI_JSON["words"]}]}
        tess = TesseractOutput(data)
        assert len(tess.words) == 3

    def test_parse_flat_format(self) -> None:
        tess = TesseractOutput(SAMPLE_FLAT_JSON)
        assert len(tess.words) == 1
        assert tess.words[0]["text"] == "اردو"

    def test_from_string(self) -> None:
        tess = TesseractOutput.from_string(json.dumps(SAMPLE_GURMUKHI_JSON))
        assert len(tess.words) == 3

    def test_from_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.json"
        f.write_text(json.dumps(SAMPLE_GURMUKHI_JSON), encoding="utf-8")
        tess = TesseractOutput.from_file(f)
        assert len(tess.words) == 3


class TestDocumentProcessor:
    def test_process_gurmukhi_returns_dict(self) -> None:
        tess = TesseractOutput(SAMPLE_GURMUKHI_JSON)
        proc = DocumentProcessor("gurmukhi")
        result = proc.process(tess)
        assert "corrected_text" in result
        assert "correction_report" in result
        assert "metadata" in result
        assert "flagged" in result

    def test_high_confidence_pass_through(self) -> None:
        data = {"words": [{"text": "ਸਤਿ", "conf": 95.0, "bbox": [], "alternatives": []}]}
        tess = TesseractOutput(data)
        proc = DocumentProcessor("gurmukhi")
        result = proc.process(tess)
        regions = result["metadata"]["regions"]
        assert regions[0]["status"] == "pass_through"
        assert result["metadata"]["pass_through_count"] == 1

    def test_low_confidence_flagged(self) -> None:
        data = {"words": [{"text": "ਸਤਿ", "conf": 30.0, "bbox": [], "alternatives": []}]}
        tess = TesseractOutput(data)
        proc = DocumentProcessor("gurmukhi")
        result = proc.process(tess)
        assert len(result["flagged"]) == 1
        assert result["metadata"]["flagged_count"] == 1

    def test_mid_confidence_corrected(self) -> None:
        data = {"words": [{"text": "ਸਤਿ", "conf": 70.0, "bbox": [], "alternatives": []}]}
        tess = TesseractOutput(data)
        proc = DocumentProcessor("gurmukhi")
        result = proc.process(tess)
        regions = result["metadata"]["regions"]
        assert regions[0]["status"] == "corrected"

    def test_corrected_text_is_string(self) -> None:
        tess = TesseractOutput(SAMPLE_GURMUKHI_JSON)
        proc = DocumentProcessor("gurmukhi")
        result = proc.process(tess)
        assert isinstance(result["corrected_text"], str)

    def test_metadata_fields(self) -> None:
        tess = TesseractOutput(SAMPLE_GURMUKHI_JSON)
        proc = DocumentProcessor("gurmukhi")
        result = proc.process(tess)
        meta = result["metadata"]
        assert "language" in meta
        assert "processing_time_seconds" in meta
        assert "total_words" in meta
        assert meta["total_words"] == 3

    def test_write_outputs(self, tmp_path: Path) -> None:
        tess = TesseractOutput(SAMPLE_GURMUKHI_JSON)
        proc = DocumentProcessor("gurmukhi")
        result = proc.process(tess)
        proc.write_outputs(result, tmp_path)
        assert (tmp_path / "corrected_text.txt").exists()
        assert (tmp_path / "correction_report.json").exists()
        assert (tmp_path / "metadata.json").exists()

    def test_correction_report_is_list(self) -> None:
        tess = TesseractOutput(SAMPLE_GURMUKHI_JSON)
        proc = DocumentProcessor("gurmukhi")
        result = proc.process(tess)
        assert isinstance(result["correction_report"], list)

    def test_processing_time_positive(self) -> None:
        tess = TesseractOutput(SAMPLE_GURMUKHI_JSON)
        proc = DocumentProcessor("gurmukhi")
        result = proc.process(tess)
        assert result["metadata"]["processing_time_seconds"] >= 0

    def test_hindi_pipeline(self) -> None:
        tess = TesseractOutput(SAMPLE_HINDI_JSON)
        proc = DocumentProcessor("hindi")
        result = proc.process(tess)
        assert isinstance(result["corrected_text"], str)


class TestProcessDocumentConvenience:
    def test_process_from_dict(self) -> None:
        result = process_document(SAMPLE_GURMUKHI_JSON, "gurmukhi")
        assert "corrected_text" in result

    def test_process_from_json_string(self) -> None:
        result = process_document(json.dumps(SAMPLE_GURMUKHI_JSON), "gurmukhi")
        assert "corrected_text" in result

    def test_process_from_file(self, tmp_path: Path) -> None:
        f = tmp_path / "input.json"
        f.write_text(json.dumps(SAMPLE_GURMUKHI_JSON), encoding="utf-8")
        result = process_document(f, "gurmukhi")
        assert "corrected_text" in result

    def test_process_writes_outputs(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "output"
        process_document(SAMPLE_GURMUKHI_JSON, "gurmukhi", output_dir=out_dir)
        assert (out_dir / "corrected_text.txt").exists()
        assert (out_dir / "correction_report.json").exists()
        assert (out_dir / "metadata.json").exists()

    @pytest.mark.parametrize("lang", ["gurmukhi", "punjabi", "hindi", "urdu", "farsi"])
    def test_all_languages(self, lang: str) -> None:
        result = process_document({"words": []}, lang)
        assert result["metadata"]["language"] == lang
