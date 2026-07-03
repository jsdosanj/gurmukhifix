"""gurmukhifix — OCR post-processing engine for Gurmukhi and other Indic scripts.

Quick start::

    from gurmukhifix import process_document

    tesseract_json = {"words": [{"text": "ਿਸੰਘ", "conf": 72}]}
    result = process_document(tesseract_json, "gurmukhi")
    print(result["corrected_text"])
"""

from __future__ import annotations

from .corrector import CharacterCorrector, correct_text
from .diacritic import DiacriticRecovery, recover_diacritics
from .integration import DocumentProcessor, TesseractOutput, process_document
from .learner import CorrectionStore
from .lexicon import Lexicon
from .validator import ScriptValidator, validate_text

__version__ = "0.1.0"

__all__ = [
    "process_document",
    "DocumentProcessor",
    "TesseractOutput",
    "CharacterCorrector",
    "correct_text",
    "ScriptValidator",
    "validate_text",
    "DiacriticRecovery",
    "recover_diacritics",
    "Lexicon",
    "CorrectionStore",
    "__version__",
]
