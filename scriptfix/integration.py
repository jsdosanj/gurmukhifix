"""Integration Layer for scriptfix.

Accepts Tesseract JSON/hOCR output, applies all correction passes,
and produces the four output artifacts:
  - corrected_text.txt
  - correction_report.json
  - metadata.json
  - flagged.json
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .corrector import CharacterCorrector
from .diacritic import DiacriticRecovery
from .ligature import LigatureHandler
from .validator import ScriptValidator

# Confidence band thresholds (can be overridden per language via config)
DEFAULT_PASS_THROUGH = 85.0
DEFAULT_FLAG_ONLY = 60.0


class TesseractOutput:
    """Parses and wraps Tesseract JSON output."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.raw = data
        # Support both flat and nested Tesseract JSON formats
        self.words: list[dict[str, Any]] = self._extract_words(data)

    @classmethod
    def from_file(cls, path: Path | str) -> "TesseractOutput":
        with Path(path).open(encoding="utf-8") as fh:
            data = json.load(fh)
        return cls(data)

    @classmethod
    def from_string(cls, text: str) -> "TesseractOutput":
        return cls(json.loads(text))

    @staticmethod
    def _extract_words(data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract a flat list of word records from various Tesseract JSON formats."""
        words: list[dict[str, Any]] = []

        # Format 1: {"words": [{text, conf, bbox, alternatives}, ...]}
        if "words" in data:
            return data["words"]

        # Format 2: {"pages": [{"words": [...]}]}
        if "pages" in data:
            for page in data["pages"]:
                for word in page.get("words", []):
                    words.append(word)
            return words

        # Format 3: flat keys — treat whole JSON as one word
        if "text" in data:
            return [data]

        return words


class DocumentProcessor:
    """Orchestrates the full correction pipeline for a single document."""

    def __init__(self, language: str) -> None:
        self.language = language
        self._corrector = CharacterCorrector(language)
        self._validator = ScriptValidator(language)
        self._ligature = LigatureHandler(language)
        self._diacritic = DiacriticRecovery(language)

        cfg = self._corrector.config
        thresholds = cfg.get("confidence_thresholds", {})
        self._pass_through: float = thresholds.get("pass_through", DEFAULT_PASS_THROUGH)
        self._flag_only: float = thresholds.get("flag_only", DEFAULT_FLAG_ONLY)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, tess_output: TesseractOutput) -> dict[str, Any]:
        """Run the full pipeline on *tess_output*.

        Returns a dict with keys:
          - corrected_text: str
          - correction_report: list of correction records
          - metadata: per-region confidence and flag information
          - flagged: list of word records that fell below flag_only threshold
        """
        start = time.perf_counter()

        corrected_words: list[str] = []
        all_corrections: list[dict[str, Any]] = []
        all_violations: list[dict[str, Any]] = []
        flagged: list[dict[str, Any]] = []
        metadata_regions: list[dict[str, Any]] = []

        for word_idx, word in enumerate(tess_output.words):
            text: str = word.get("text", "")
            conf: float = float(word.get("conf", word.get("confidence", 50.0)))
            bbox: list[int] = word.get("bbox", word.get("bounding_box", []))
            alternatives: list[dict[str, Any]] = word.get("alternatives", [])

            region_meta: dict[str, Any] = {
                "word_index": word_idx,
                "original": text,
                "bbox": bbox,
                "original_confidence": conf,
                "alternatives": alternatives,
                "script": self.language,
            }

            # --- Confidence-based routing ---
            if conf >= self._pass_through:
                # High-confidence: pass through unchanged
                corrected_words.append(text)
                region_meta["status"] = "pass_through"
                region_meta["corrected"] = text
                region_meta["corrected_confidence"] = conf
                metadata_regions.append(region_meta)
                continue

            if conf < self._flag_only:
                # Very low confidence: flag and preserve Tesseract alternatives
                corrected_words.append(text)
                region_meta["status"] = "flagged"
                region_meta["corrected"] = text
                region_meta["corrected_confidence"] = conf
                flagged.append(region_meta)
                metadata_regions.append(region_meta)
                continue

            # --- Full correction pipeline (60–85% confidence band) ---
            corrections_for_word: list[dict[str, Any]] = []

            # Step 1: character correction
            text, c = self._corrector.correct(text)
            corrections_for_word.extend(c)

            # Step 2: ligature reassembly
            text, c = self._ligature.reassemble(text)
            corrections_for_word.extend(c)

            # Step 3: diacritic recovery
            text, c = self._diacritic.recover(text, alternatives)
            corrections_for_word.extend(c)

            # Step 4: validation
            violations = self._validator.validate(text)
            all_violations.extend(violations)

            # Tag each correction with word index and bbox
            for corr in corrections_for_word:
                corr["word_index"] = word_idx
                corr["bbox"] = bbox
                corr["original_confidence"] = conf
            all_corrections.extend(corrections_for_word)

            corrected_words.append(text)
            region_meta["status"] = "corrected"
            region_meta["corrected"] = text
            region_meta["num_corrections"] = len(corrections_for_word)
            region_meta["violations"] = violations
            metadata_regions.append(region_meta)

        elapsed = time.perf_counter() - start
        corrected_text = " ".join(corrected_words)

        return {
            "corrected_text": corrected_text,
            "correction_report": all_corrections,
            "violations": all_violations,
            "flagged": flagged,
            "metadata": {
                "language": self.language,
                "processing_time_seconds": round(elapsed, 4),
                "total_words": len(tess_output.words),
                "pass_through_count": sum(
                    1 for r in metadata_regions if r.get("status") == "pass_through"
                ),
                "corrected_count": sum(
                    1 for r in metadata_regions if r.get("status") == "corrected"
                ),
                "flagged_count": len(flagged),
                "regions": metadata_regions,
            },
        }

    def write_outputs(self, result: dict[str, Any], output_dir: Path | str) -> None:
        """Write the four output artifacts to *output_dir*."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        (output_dir / "corrected_text.txt").write_text(
            result["corrected_text"], encoding="utf-8"
        )
        (output_dir / "correction_report.json").write_text(
            json.dumps(result["correction_report"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "metadata.json").write_text(
            json.dumps(result["metadata"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "flagged.json").write_text(
            json.dumps(result["flagged"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def process_document(
    tess_json: dict[str, Any] | str | Path,
    language: str,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    """High-level function: process a Tesseract JSON document.

    Args:
        tess_json: Tesseract JSON as a dict, a JSON string, or a file path.
        language: Target language/script.
        output_dir: If provided, write output artifacts to this directory.

    Returns:
        Result dict (see DocumentProcessor.process).
    """
    if isinstance(tess_json, (str, Path)):
        path = Path(tess_json)
        # Only attempt path resolution for short strings that could be file paths
        is_file = False
        try:
            is_file = path.exists()
        except OSError:
            # Path.exists() raises OSError when the string is too long to be a
            # valid filesystem path (e.g. when tess_json is a raw JSON string).
            # In that case, treat the input as a JSON string rather than a path.
            pass

        if is_file:
            tess_output = TesseractOutput.from_file(path)
        else:
            tess_output = TesseractOutput.from_string(str(tess_json))
    else:
        tess_output = TesseractOutput(tess_json)

    processor = DocumentProcessor(language)
    result = processor.process(tess_output)

    if output_dir is not None:
        processor.write_outputs(result, output_dir)

    return result
