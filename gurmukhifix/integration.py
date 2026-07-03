"""Integration Layer for gurmukhifix.

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
from .lexicon import Lexicon
from .ligature import LigatureHandler
from .ocr import OCRDocument, load_ocr
from .validator import ScriptValidator

# Confidence band thresholds (can be overridden per language via config)
DEFAULT_PASS_THROUGH = 85.0
DEFAULT_FLAG_ONLY = 60.0


class TesseractOutput(OCRDocument):
    """Backward-compatible wrapper: a Tesseract-JSON :class:`~gurmukhifix.ocr.OCRDocument`.

    New code should prefer :func:`gurmukhifix.ocr.load_ocr`, which accepts every
    supported OCR format (Tesseract JSON/TSV/hOCR, ALTO, Surya, Google Vision, …).
    """

    def __init__(self, data: dict[str, Any]) -> None:
        doc = OCRDocument.from_tesseract_json(data)
        super().__init__(doc.words, engine="tesseract-json", raw=data)

    @classmethod
    def from_file(cls, path: Path | str) -> "TesseractOutput":
        try:
            with Path(path).open(encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: not valid JSON ({exc})") from exc
        return cls(data)

    @classmethod
    def from_string(cls, text: str) -> "TesseractOutput":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"input is not valid JSON ({exc})") from exc
        return cls(data)


class DocumentProcessor:
    """Orchestrates the full correction pipeline for a single document."""

    def __init__(self, language: str, store: Any = None) -> None:
        self.language = language
        # One validator + lexicon shared across the pipeline (avoids rebuilding).
        self._validator = ScriptValidator(language)
        self._lexicon = Lexicon(language)
        # Corpus-learned promoted corrections, with the context in which each was
        # confirmed, if a CorrectionStore is provided.
        promoted = store.get_promoted_rules(language) if store is not None else None
        self._corrector = CharacterCorrector(
            language, promoted=promoted, validator=self._validator, lexicon=self._lexicon
        )
        self._ligature = LigatureHandler(language)
        self._diacritic = DiacriticRecovery(
            language, validator=self._validator, lexicon=self._lexicon
        )

        cfg = self._corrector.config
        thresholds = cfg.get("confidence_thresholds", {})
        self._pass_through: float = thresholds.get("pass_through", DEFAULT_PASS_THROUGH)
        self._flag_only: float = thresholds.get("flag_only", DEFAULT_FLAG_ONLY)

    def _run_pass(
        self,
        fn: Any,
        text: str,
        corrections: list[dict[str, Any]],
    ) -> tuple[str, list[dict[str, Any]]]:
        """Apply one correction pass, keeping it only if it does not worsen validity."""
        before = self._validator.badness(text)
        new_text, new_corrections = fn(text)
        if new_text != text and self._validator.badness(new_text) > before:
            return text, corrections  # this pass regressed validity — discard it
        return new_text, corrections + new_corrections

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, tess_output: OCRDocument) -> dict[str, Any]:
        """Run the full pipeline on *tess_output* (any :class:`~gurmukhifix.ocr.OCRDocument`).

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
            # A non-numeric confidence must not abort the whole document.
            try:
                conf = float(word.get("conf", word.get("confidence", 50.0)))
            except (TypeError, ValueError):
                conf = 50.0
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
            # Each pass is gated independently: a pass that would make the word
            # *less* well-formed than it was before that pass is discarded on its
            # own, so a correct earlier fix is never thrown away because a later,
            # unrelated pass regressed. gurmukhifix must never make Tesseract worse.
            corrections_for_word: list[dict[str, Any]] = []
            text, corrections_for_word = self._run_pass(
                self._corrector.correct, text, corrections_for_word
            )
            text, corrections_for_word = self._run_pass(
                self._ligature.reassemble, text, corrections_for_word
            )
            text, corrections_for_word = self._run_pass(
                lambda t: self._diacritic.recover(t, alternatives),
                text,
                corrections_for_word,
            )

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
            # A residual REJECT means the word is still structurally impossible
            # after correction — surface it for manual review.
            has_rejections = self._validator.has_rejections(violations)
            region_meta["status"] = "corrected"
            region_meta["corrected"] = text
            region_meta["num_corrections"] = len(corrections_for_word)
            region_meta["violations"] = violations
            region_meta["has_rejections"] = has_rejections
            if has_rejections:
                flagged.append(region_meta)
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
    source: dict[str, Any] | str | Path | OCRDocument | list[dict[str, Any]],
    language: str,
    output_dir: Path | str | None = None,
    store: Any = None,
    fmt: str = "auto",
) -> dict[str, Any]:
    """High-level function: correct OCR output from any supported engine.

    Args:
        source: OCR output — a dict/JSON string/file path (Tesseract JSON, TSV,
            hOCR, ALTO, Surya, Google Vision), a plain-text string, a list of word
            dicts, or an already-built :class:`~gurmukhifix.ocr.OCRDocument`.
        language: Target language/script.
        output_dir: If provided, write output artifacts to this directory.
        store: Optional CorrectionStore; its promoted corrections are applied.
        fmt: OCR format hint; ``"auto"`` (default) detects it from the content or
            file extension. See :mod:`gurmukhifix.ocr` for the supported values.

    Returns:
        Result dict (see DocumentProcessor.process).
    """
    document = load_ocr(source, fmt=fmt)
    processor = DocumentProcessor(language, store=store)
    result = processor.process(document)

    if output_dir is not None:
        processor.write_outputs(result, output_dir)

    return result
