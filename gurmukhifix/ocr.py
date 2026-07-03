"""OCR-engine-agnostic input layer.

gurmukhifix corrects OCR *output*; it does not care which engine produced it. This
module normalises the output of several engines into one internal shape — a list of
word records ``{text, conf, bbox, alternatives}`` with confidence on a 0–100 scale —
so the correction pipeline is decoupled from any single OCR tool.

Supported formats (auto-detected, or requested explicitly):

======================  ==========================================================
``tesseract_json``      Tesseract ``--output-type json`` (also nested ``pages``)
``tesseract_tsv``       Tesseract ``tsv`` / ``image_to_data`` (what stock Tesseract
                        actually emits — the reliable on-ramp)
``hocr``                hOCR (Tesseract, OCRopus, Kraken, …)
``alto``                ALTO XML (common in library/heritage digitisation)
``surya``               Surya OCR JSON (``text_lines``)
``google_vision``       Google Cloud Vision / Gemini document JSON
``text``                plain UTF-8 text (no confidence — routed to correction)
``generic``             a Python list of ``{text, conf, bbox}`` dicts
======================  ==========================================================

Because transformer OCR (Surya, Gemini, TrOCR) now beats Tesseract on Indic and
Nastaliq scripts, keeping this layer engine-agnostic means the correction engine
survives the shift away from Tesseract.
"""

from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

# Confidence assigned to text-only sources so they enter the correction band
# (>= flag_only and < pass_through) rather than being passed through untouched.
DEFAULT_CONF = 75.0


def _clean_conf(value: Any, default: float = DEFAULT_CONF) -> float:
    """Coerce a confidence to a non-negative float, else *default*.

    A negative confidence (Tesseract emits -1 for "no confidence") becomes the
    default so the word still enters the correction band.
    """
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return default
    return default if conf < 0 else conf


def _auto_conf(value: Any, default: float = DEFAULT_CONF) -> float:
    """As :func:`_clean_conf`, but rescale a 0–1 confidence to 0–100."""
    conf = _clean_conf(value, default)
    return conf * 100.0 if 0.0 < conf <= 1.0 else conf


def _word(text: str, conf: Any, bbox: Any = None, alternatives: Any = None) -> dict[str, Any]:
    """Build a normalised word record; *conf* is expected already on a 0–100 scale."""
    return {
        "text": text,
        "conf": _clean_conf(conf),
        "bbox": list(bbox) if bbox else [],
        "alternatives": list(alternatives) if alternatives else [],
    }


def _poly_to_bbox(poly: Any) -> list[int]:
    """Convert a Google Vision boundingPoly to ``[x, y, w, h]``."""
    if not isinstance(poly, dict):
        return []
    verts = poly.get("vertices") or poly.get("normalizedVertices") or []
    xs = [v.get("x", 0) for v in verts if isinstance(v, dict)]
    ys = [v.get("y", 0) for v in verts if isinstance(v, dict)]
    if not xs or not ys:
        return []
    x0, y0 = min(xs), min(ys)
    return [int(x0), int(y0), int(max(xs) - x0), int(max(ys) - y0)]


class OCRDocument:
    """A normalised OCR result: a flat list of word records plus its source engine."""

    def __init__(self, words: list[dict[str, Any]], *, engine: str = "unknown", raw: Any = None) -> None:
        self.words = words
        self.engine = engine
        self.raw = raw

    def __len__(self) -> int:
        return len(self.words)

    # ------------------------------------------------------------------
    # Adapters
    # ------------------------------------------------------------------

    @classmethod
    def from_tesseract_json(cls, data: Any) -> "OCRDocument":
        """Tesseract JSON: ``{"words": [...]}``, ``{"pages": [{"words": [...]}]}``, or a flat word."""
        if not isinstance(data, dict):
            raise ValueError(
                f"Tesseract output must be a JSON object, got {type(data).__name__}"
            )
        raw_words: list[dict[str, Any]] = []
        if "words" in data:
            if not isinstance(data["words"], list):
                raise ValueError("'words' must be a list of word objects")
            raw_words = [w for w in data["words"] if isinstance(w, dict)]
        elif "pages" in data:
            for page in data.get("pages", []):
                for word in page.get("words", []):
                    if isinstance(word, dict):
                        raw_words.append(word)
        elif "text" in data:
            raw_words = [data]

        words = [
            _word(
                w.get("text", ""),
                w.get("conf", w.get("confidence", DEFAULT_CONF)),
                w.get("bbox", w.get("bounding_box", [])),
                w.get("alternatives", []),
            )
            for w in raw_words
        ]
        return cls(words, engine="tesseract-json", raw=data)

    @classmethod
    def from_tesseract_tsv(cls, text: str) -> "OCRDocument":
        """Tesseract TSV (``--output-type tsv`` / ``image_to_data``)."""
        lines = text.splitlines()
        if not lines:
            return cls([], engine="tesseract-tsv")
        header = lines[0].split("\t")
        idx = {name: i for i, name in enumerate(header)}
        if "text" not in idx or "level" not in idx:
            # No recognisable header — fall back to treating it as plain text.
            return cls.from_plain_text(text)
        words: list[dict[str, Any]] = []
        for row in lines[1:]:
            cols = row.split("\t")
            if len(cols) <= idx["text"]:
                continue
            try:
                if int(cols[idx["level"]]) != 5:  # 5 == word level
                    continue
            except ValueError:
                continue
            txt = cols[idx["text"]].strip()
            if not txt:
                continue
            conf = cols[idx["conf"]] if "conf" in idx and len(cols) > idx["conf"] else DEFAULT_CONF
            bbox: list[int] = []
            try:
                bbox = [int(cols[idx[k]]) for k in ("left", "top", "width", "height")]
            except (KeyError, ValueError, IndexError):
                bbox = []
            words.append(_word(txt, conf, bbox))
        return cls(words, engine="tesseract-tsv")

    @classmethod
    def from_hocr(cls, text: str) -> "OCRDocument":
        """hOCR (HTML with ``ocrx_word`` spans carrying ``bbox`` and ``x_wconf``)."""
        words: list[dict[str, Any]] = []
        # Anchor on spans whose own tag carries ocrx_word, so a wrapping ocr_line
        # span is never mistaken for a word (and never swallows the first word).
        for m in re.finditer(r"<span\b([^>]*ocrx_word[^>]*)>(.*?)</span>", text, re.S):
            attrs, inner = m.group(1), m.group(2)
            txt = html.unescape(re.sub(r"<[^>]+>", "", inner)).strip()
            if not txt:
                continue
            title_m = re.search(r"title=['\"]([^'\"]*)['\"]", attrs)
            title = title_m.group(1) if title_m else ""
            bbox: list[int] = []
            bm = re.search(r"bbox\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", title)
            if bm:
                x0, y0, x1, y1 = (int(g) for g in bm.groups())
                bbox = [x0, y0, x1 - x0, y1 - y0]
            cm = re.search(r"x_wconf\s+(\d+(?:\.\d+)?)", title)
            conf = float(cm.group(1)) if cm else DEFAULT_CONF
            words.append(_word(txt, conf, bbox))
        return cls(words, engine="hocr")

    @classmethod
    def from_alto(cls, text: str) -> "OCRDocument":
        """ALTO XML (``<String CONTENT= WC= HPOS= VPOS= WIDTH= HEIGHT=/>``)."""
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            raise ValueError(f"not valid ALTO XML ({exc})") from exc
        words: list[dict[str, Any]] = []
        for el in root.iter():
            if el.tag.rsplit("}", 1)[-1] != "String":
                continue
            txt = (el.get("CONTENT") or "").strip()
            if not txt:
                continue
            wc = el.get("WC")
            conf = _auto_conf(wc) if wc is not None else DEFAULT_CONF
            bbox: list[int] = []
            try:
                bbox = [int(float(el.get(k))) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT")]  # type: ignore[arg-type]
            except (TypeError, ValueError):
                bbox = []
            words.append(_word(txt, conf, bbox))
        return cls(words, engine="alto")

    @classmethod
    def from_surya(cls, data: Any) -> "OCRDocument":
        """Surya OCR JSON (pages of ``text_lines`` with ``text``/``confidence``/``bbox``)."""
        pages: list[dict[str, Any]] = []
        if isinstance(data, dict):
            if "text_lines" in data:
                pages = [data]
            else:
                for value in data.values():
                    if isinstance(value, list):
                        pages.extend(p for p in value if isinstance(p, dict) and "text_lines" in p)
        elif isinstance(data, list):
            pages = [p for p in data if isinstance(p, dict) and "text_lines" in p]

        words: list[dict[str, Any]] = []
        for page in pages:
            for line in page.get("text_lines", []):
                if not isinstance(line, dict):
                    continue
                conf = _auto_conf(line.get("confidence"))
                box = line.get("bbox") or []
                bbox = (
                    [int(box[0]), int(box[1]), int(box[2] - box[0]), int(box[3] - box[1])]
                    if len(box) == 4
                    else []
                )
                for token in (line.get("text") or "").split():
                    words.append(_word(token, conf, bbox))
        return cls(words, engine="surya")

    @classmethod
    def from_google_vision(cls, data: Any) -> "OCRDocument":
        """Google Cloud Vision / Gemini document JSON."""
        resp = data
        if isinstance(data, dict) and isinstance(data.get("responses"), list) and data["responses"]:
            resp = data["responses"][0]
        if not isinstance(resp, dict):
            return cls([], engine="google-vision")

        words: list[dict[str, Any]] = []
        fta = resp.get("fullTextAnnotation")
        if isinstance(fta, dict):
            for page in fta.get("pages", []):
                for block in page.get("blocks", []):
                    for para in block.get("paragraphs", []):
                        for w in para.get("words", []):
                            txt = "".join(s.get("text", "") for s in w.get("symbols", []))
                            if not txt.strip():
                                continue
                            words.append(
                                _word(txt, _auto_conf(w.get("confidence")), _poly_to_bbox(w.get("boundingBox")))
                            )
            if words:
                return cls(words, engine="google-vision")

        for ta in resp.get("textAnnotations", [])[1:]:  # [0] is the whole-image text
            txt = (ta.get("description") or "").strip()
            if txt:
                words.append(_word(txt, DEFAULT_CONF, _poly_to_bbox(ta.get("boundingPoly"))))
        return cls(words, engine="google-vision")

    @classmethod
    def from_plain_text(cls, text: str, conf: float = DEFAULT_CONF) -> "OCRDocument":
        """Plain UTF-8 text — whitespace tokenised, given a correction-band confidence."""
        return cls([_word(tok, conf, []) for tok in text.split()], engine="plain-text")

    @classmethod
    def from_words(cls, items: list[dict[str, Any]]) -> "OCRDocument":
        """A generic list of ``{text, conf, bbox, alternatives}`` word dicts."""
        words = [
            _word(
                it.get("text", ""),
                _auto_conf(it.get("conf", it.get("confidence"))),
                it.get("bbox", it.get("bounding_box", [])),
                it.get("alternatives", []),
            )
            for it in items
            if isinstance(it, dict) and it.get("text")
        ]
        return cls(words, engine="generic")


_STRING_ADAPTERS = {
    "tesseract_json": lambda s: OCRDocument.from_tesseract_json(json.loads(s)),
    "tesseract_tsv": OCRDocument.from_tesseract_tsv,
    "hocr": OCRDocument.from_hocr,
    "alto": OCRDocument.from_alto,
    "surya": lambda s: OCRDocument.from_surya(json.loads(s)),
    "google_vision": lambda s: OCRDocument.from_google_vision(json.loads(s)),
    "text": OCRDocument.from_plain_text,
}

# Map common file extensions to a format hint.
_EXT_FORMAT = {
    ".json": None,          # inspect JSON contents to pick the engine
    ".tsv": "tesseract_tsv",
    ".hocr": "hocr",
    ".html": "hocr",
    ".htm": "hocr",
    ".alto": "alto",
    ".xml": "alto",
    ".txt": "text",
}


def _detect_json(data: Any) -> str:
    if isinstance(data, list):
        if data and isinstance(data[0], dict) and "text_lines" in data[0]:
            return "surya"
        return "generic"
    if isinstance(data, dict):
        if "text_lines" in data or any(
            isinstance(v, list) and v and isinstance(v[0], dict) and "text_lines" in v[0]
            for v in data.values()
        ):
            return "surya"
        if "responses" in data or "fullTextAnnotation" in data or "textAnnotations" in data:
            return "google_vision"
        if "words" in data or "pages" in data or "text" in data:
            return "tesseract_json"
    return "tesseract_json"


def _detect_string(text: str) -> str:
    stripped = text.lstrip()
    if stripped[:1] in "{[":
        try:
            return _detect_json(json.loads(text))
        except json.JSONDecodeError:
            pass
    low = stripped[:512].lower()
    if "<alto" in low or "alto/ns" in low:
        return "alto"
    if "ocrx_word" in text or "ocr_page" in text or "<html" in low or "<!doctype html" in low:
        return "hocr"
    if "<?xml" in low or "<string " in low:
        return "alto"
    first_line = text.splitlines()[0] if text.splitlines() else ""
    if "\t" in first_line and "level" in first_line and "text" in first_line:
        return "tesseract_tsv"
    return "text"


def load_ocr(source: Any, fmt: str = "auto") -> OCRDocument:
    """Load OCR output from *source* into a normalised :class:`OCRDocument`.

    *source* may be an :class:`OCRDocument` (returned as-is), a ``dict``/``list`` of
    already-parsed OCR data, a :class:`pathlib.Path` to a file, or a ``str`` holding
    either a filesystem path or the OCR payload itself. *fmt* forces a specific
    format; the default ``"auto"`` detects it from the content or file extension.
    """
    if isinstance(source, OCRDocument):
        return source

    if isinstance(source, (list,)):
        return OCRDocument.from_words(source)

    if isinstance(source, dict):
        chosen = fmt if fmt != "auto" else _detect_json(source)
        return {
            "tesseract_json": OCRDocument.from_tesseract_json,
            "surya": OCRDocument.from_surya,
            "google_vision": OCRDocument.from_google_vision,
            "generic": lambda d: OCRDocument.from_words(d.get("words", [])),
        }.get(chosen, OCRDocument.from_tesseract_json)(source)

    if isinstance(source, Path):
        return _load_path(source, fmt)

    if isinstance(source, str):
        # A leading brace/bracket marks inline JSON; XML/TSV/text markers are handled
        # by detection. Otherwise treat the string as a filesystem path.
        stripped = source.lstrip()
        if stripped[:1] in "{[" or "\n" in source or "<" in stripped[:64]:
            return _load_text(source, fmt)
        path = Path(source)
        if path.exists():
            return _load_path(path, fmt)
        return _load_text(source, fmt)

    raise TypeError(f"unsupported OCR source type: {type(source).__name__}")


def _load_path(path: Path, fmt: str) -> OCRDocument:
    text = path.read_text(encoding="utf-8")
    if fmt == "auto":
        ext_fmt = _EXT_FORMAT.get(path.suffix.lower(), "missing")
        if ext_fmt not in (None, "missing"):
            return _load_text(text, ext_fmt)
    return _load_text(text, fmt)


def _load_text(text: str, fmt: str) -> OCRDocument:
    chosen = fmt if fmt != "auto" else _detect_string(text)
    adapter = _STRING_ADAPTERS.get(chosen)
    if adapter is None:
        return OCRDocument.from_plain_text(text)
    return adapter(text)
