"""Local OCR using Tesseract via pytesseract.

Runs entirely on this machine: no paid APIs, no API keys, and no
network requests. The uploaded image is written to a random-named
temporary file that is always deleted, including on errors.
"""
import os
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, Iterator, Optional, Tuple

from PIL import Image
import pytesseract
from pytesseract import TesseractError, TesseractNotFoundError

from app.config import settings
from app.exceptions import AppError

TEMP_PREFIX = "scamshield_ocr_"

_WINDOWS_CANDIDATES = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)

_UNAVAILABLE_MESSAGE = (
    "OCR engine is not available. Install Tesseract OCR "
    "(https://github.com/UB-Mannheim/tesseract/wiki), ensure it is on PATH, "
    "or set the TESSERACT_CMD environment variable to the executable path."
)


@dataclass
class OCRResult:
    text: str
    confidence: float  # 0.0 - 1.0


def resolve_tesseract() -> Optional[str]:
    """Locate the Tesseract executable without relying on a fresh PATH."""
    if settings.tesseract_cmd:
        return settings.tesseract_cmd
    found = shutil.which("tesseract")
    if found:
        return found
    local = os.path.join(
        os.environ.get("LOCALAPPDATA", ""), "Tesseract-OCR", "tesseract.exe"
    )
    for path in (*_WINDOWS_CANDIDATES, local):
        if path and os.path.isfile(path):
            return path
    return None


def tesseract_available() -> bool:
    return resolve_tesseract() is not None


@contextmanager
def temporary_image_file(image: Image.Image) -> Iterator[str]:
    """Write the image to a random-named temp file; always delete it."""
    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=TEMP_PREFIX, suffix=".png", delete=False
        ) as handle:
            tmp_path = handle.name
            image.save(handle, format="PNG")
        yield tmp_path
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass


def rows_to_text_and_confidence(data: Dict) -> Tuple[str, float]:
    """Build text and mean confidence (0-1) from Tesseract TSV output."""
    raw_texts = data.get("text") or []
    raw_confs = data.get("conf") or []
    lines: Dict[Tuple, list] = {}
    confidences = []

    for idx, raw in enumerate(raw_texts):
        word = (raw or "").strip()
        if not word:
            continue
        try:
            conf = float(raw_confs[idx])
        except (IndexError, TypeError, ValueError):
            continue
        if conf < 0:  # tesseract emits -1 for non-word rows
            continue
        confidences.append(conf)
        key = (
            data.get("block_num", [0] * len(raw_texts))[idx],
            data.get("par_num", [0] * len(raw_texts))[idx],
            data.get("line_num", [0] * len(raw_texts))[idx],
        )
        word_num = data.get("word_num", [0] * len(raw_texts))[idx]
        lines.setdefault(key, []).append((word_num, word))

    text = "\n".join(
        " ".join(word for _, word in sorted(words))
        for _, words in sorted(lines.items())
    )
    confidence = (
        round(sum(confidences) / len(confidences) / 100.0, 4)
        if confidences
        else 0.0
    )
    return text, confidence


def run_ocr(image: Image.Image) -> OCRResult:
    """Extract text and confidence from an image using local Tesseract.

    Raises AppError:
        503 OCR_UNAVAILABLE - Tesseract binary not installed/found
        500 OCR_FAILED - OCR process failed or timed out
    """
    executable = resolve_tesseract()
    if not executable:
        raise AppError("OCR_UNAVAILABLE", _UNAVAILABLE_MESSAGE, 503)
    pytesseract.pytesseract.tesseract_cmd = executable

    try:
        with temporary_image_file(image) as path:
            data = pytesseract.image_to_data(
                path,
                lang="eng",
                output_type=pytesseract.Output.DICT,
                timeout=settings.ocr_timeout_seconds,
            )
    except TesseractNotFoundError:
        raise AppError("OCR_UNAVAILABLE", _UNAVAILABLE_MESSAGE, 503)
    except (TesseractError, RuntimeError, FileNotFoundError) as exc:
        raise AppError(
            "OCR_FAILED",
            "OCR processing failed or timed out. The image could not be read.",
            500,
        ) from exc

    text, confidence = rows_to_text_and_confidence(data)
    return OCRResult(text=text, confidence=confidence)
