"""Tests for the OCR-engine-agnostic input layer (gurmukhifix.ocr)."""

from __future__ import annotations

import json

import pytest

from gurmukhifix.integration import process_document
from gurmukhifix.ocr import OCRDocument, load_ocr

TSV = (
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
    "1\t1\t0\t0\t0\t0\t0\t0\t100\t100\t-1\t\n"  # page-level row, ignored
    "5\t1\t1\t1\t1\t1\t10\t20\t50\t30\t92\tਸਿੰਘ\n"
    "5\t1\t1\t1\t1\t2\t70\t20\t40\t30\t-1\tਖਾਲਸਾ\n"  # conf -1 -> default
)

HOCR = (
    "<div class='ocr_page'><span class='ocr_line'>"
    "<span class='ocrx_word' id='w1' title='bbox 10 20 60 50; x_wconf 90'>ਸਿੰਘ</span> "
    "<span class='ocrx_word' id='w2' title='bbox 70 20 110 50; x_wconf 61'>ਖਾਲਸਾ</span>"
    "</span></div>"
)

ALTO = (
    "<alto xmlns='http://www.loc.gov/standards/alto/ns-v3#'><Layout><Page><PrintSpace>"
    "<TextLine><String CONTENT='ਸਿੰਘ' WC='0.95' HPOS='10' VPOS='20' WIDTH='50' HEIGHT='30'/>"
    "<String CONTENT='ਖਾਲਸਾ' WC='0.6' HPOS='70' VPOS='20' WIDTH='40' HEIGHT='30'/>"
    "</TextLine></PrintSpace></Page></Layout></alto>"
)

SURYA = {"page1": [{"text_lines": [{"text": "ਸਿੰਘ ਖਾਲਸਾ", "confidence": 0.97, "bbox": [10, 20, 110, 50]}]}]}

VISION = {
    "responses": [
        {
            "fullTextAnnotation": {
                "pages": [
                    {
                        "blocks": [
                            {
                                "paragraphs": [
                                    {
                                        "words": [
                                            {"confidence": 0.99, "symbols": [{"text": "ਸਿੰਘ"}]},
                                            {"confidence": 0.8, "symbols": [{"text": "ਖ"}, {"text": "ਾਲਸਾ"}]},
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        }
    ]
}


def _texts(doc: OCRDocument) -> list[str]:
    return [w["text"] for w in doc.words]


class TestAdapters:
    def test_tesseract_tsv(self) -> None:
        doc = load_ocr(TSV)
        assert doc.engine == "tesseract-tsv"
        assert _texts(doc) == ["ਸਿੰਘ", "ਖਾਲਸਾ"]
        assert doc.words[0]["conf"] == 92.0
        assert doc.words[0]["bbox"] == [10, 20, 50, 30]
        assert doc.words[1]["conf"] == 75.0  # -1 mapped to default

    def test_hocr(self) -> None:
        doc = load_ocr(HOCR)
        assert doc.engine == "hocr"
        assert _texts(doc) == ["ਸਿੰਘ", "ਖਾਲਸਾ"]
        assert doc.words[0]["conf"] == 90.0
        assert doc.words[0]["bbox"] == [10, 20, 50, 30]

    def test_alto(self) -> None:
        doc = load_ocr(ALTO)
        assert doc.engine == "alto"
        assert _texts(doc) == ["ਸਿੰਘ", "ਖਾਲਸਾ"]
        assert doc.words[0]["conf"] == 95.0  # 0.95 rescaled to 0-100
        assert doc.words[0]["bbox"] == [10, 20, 50, 30]

    def test_surya(self) -> None:
        doc = load_ocr(json.dumps(SURYA))
        assert doc.engine == "surya"
        assert _texts(doc) == ["ਸਿੰਘ", "ਖਾਲਸਾ"]
        assert doc.words[0]["conf"] == 97.0

    def test_google_vision(self) -> None:
        doc = load_ocr(json.dumps(VISION))
        assert doc.engine == "google-vision"
        assert _texts(doc) == ["ਸਿੰਘ", "ਖਾਲਸਾ"]
        assert doc.words[0]["conf"] == 99.0

    def test_plain_text(self) -> None:
        doc = load_ocr("ਸਿੰਘ ਖਾਲਸਾ")
        assert doc.engine == "plain-text"
        assert _texts(doc) == ["ਸਿੰਘ", "ਖਾਲਸਾ"]
        assert doc.words[0]["conf"] == 75.0

    def test_generic_word_list(self) -> None:
        doc = load_ocr([{"text": "ਸਿੰਘ", "conf": 0.9}, {"text": "ਖਾਲਸਾ", "confidence": 88}])
        assert doc.engine == "generic"
        assert doc.words[0]["conf"] == 90.0  # 0.9 rescaled
        assert doc.words[1]["conf"] == 88.0

    def test_tesseract_json_still_works(self) -> None:
        doc = load_ocr({"words": [{"text": "ਸਿੰਘ", "conf": 70}]})
        assert doc.engine == "tesseract-json"
        assert _texts(doc) == ["ਸਿੰਘ"]


class TestAutoDetection:
    @pytest.mark.parametrize(
        "source,expected",
        [
            (TSV, "tesseract-tsv"),
            (HOCR, "hocr"),
            (ALTO, "alto"),
            (json.dumps(SURYA), "surya"),
            (json.dumps(VISION), "google-vision"),
            ("just some ਸਿੰਘ text", "plain-text"),
        ],
    )
    def test_format_detected(self, source: str, expected: str) -> None:
        assert load_ocr(source).engine == expected

    def test_passthrough_ocrdocument(self) -> None:
        doc = OCRDocument.from_plain_text("ਸਿੰਘ")
        assert load_ocr(doc) is doc


class TestEndToEndThroughAnyEngine:
    def test_correction_runs_from_every_format(self) -> None:
        # A word-initial-sihari error fed in via each engine format is repaired.
        assert process_document("ਿਸਮਰ", "gurmukhi")["corrected_text"] == "ਸਿਮਰ"
        tsv = (
            "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
            "5\t1\t1\t1\t1\t1\t0\t0\t9\t9\t70\tਿਸਮਰ\n"
        )
        assert process_document(tsv, "gurmukhi")["corrected_text"] == "ਸਿਮਰ"
        assert process_document([{"text": "ਿਸਮਰ", "conf": 70}], "gurmukhi")["corrected_text"] == "ਸਿਮਰ"
