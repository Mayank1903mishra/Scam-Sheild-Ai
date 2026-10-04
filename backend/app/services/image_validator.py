"""Secure validation for uploaded images.

All checks are content-based: filename extensions and client-provided
MIME types are never trusted. Validates size, real format, dimensions,
and malformed files, then returns an EXIF-free sanitized image.
"""
import struct
from io import BytesIO
from typing import Optional

from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import settings, get_max_upload_bytes
from app.exceptions import AppError

ALLOWED_FORMATS = frozenset({"PNG", "JPEG", "WEBP"})

_UNSUPPORTED_MESSAGE = (
    "Unsupported file type. Only PNG, JPEG, and WebP images are allowed."
)


def sniff_format(data: bytes) -> Optional[str]:
    """Detect the real image format from file content (magic bytes)."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if data[:3] == b"\xff\xd8\xff":
        return "JPEG"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "WEBP"
    return None


def validate_and_sanitize(data: bytes) -> Image.Image:
    """Validate upload bytes and return a sanitized, EXIF-free RGB image.

    Raises AppError:
        400 INVALID_IMAGE - empty, corrupt, or unidentifiable file
        413 FILE_TOO_LARGE - byte size over the configured limit
        413 IMAGE_TOO_LARGE - pixel dimensions over the configured limit
        415 UNSUPPORTED_FILE_TYPE - real content is not PNG/JPEG/WebP
    """
    if not data:
        raise AppError("INVALID_IMAGE", "Uploaded file is empty", 400)

    max_bytes = get_max_upload_bytes()
    if len(data) > max_bytes:
        raise AppError(
            "FILE_TOO_LARGE",
            f"File exceeds the {settings.max_upload_mb} MB upload limit",
            413,
        )

    sniffed = sniff_format(data)
    if sniffed is None:
        raise AppError("UNSUPPORTED_FILE_TYPE", _UNSUPPORTED_MESSAGE, 415)

    # Header-only pass: dimensions and format are known before any full
    # decode, so oversized images are rejected without decompressing them.
    try:
        header = Image.open(BytesIO(data))
        fmt = header.format
        width, height = header.size
        if (
            width > settings.max_image_dimension
            or height > settings.max_image_dimension
            or width * height > settings.max_image_pixels
        ):
            raise AppError(
                "IMAGE_TOO_LARGE",
                f"Image dimensions {width}x{height} exceed the allowed limit",
                413,
            )
        header.verify()
    except AppError:
        raise
    except Image.DecompressionBombError:
        raise AppError(
            "IMAGE_TOO_LARGE", "Image exceeds the allowed pixel limit", 413
        )
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError,
            struct.error, EOFError):
        raise AppError(
            "INVALID_IMAGE", "File is not a valid image or is corrupted", 400
        )

    if fmt not in ALLOWED_FORMATS or fmt != sniffed:
        raise AppError("UNSUPPORTED_FILE_TYPE", _UNSUPPORTED_MESSAGE, 415)

    # Full decode; catches truncated/corrupt payloads the header scan missed.
    try:
        image = Image.open(BytesIO(data))
        image.load()
    except Image.DecompressionBombError:
        raise AppError(
            "IMAGE_TOO_LARGE", "Image exceeds the allowed pixel limit", 413
        )
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError,
            struct.error, EOFError):
        raise AppError(
            "INVALID_IMAGE", "File is corrupted or truncated", 400
        )

    # Apply orientation, flatten alpha, then re-encode without metadata:
    # PNG output carries no EXIF, so GPS/camera metadata is stripped.
    image = ImageOps.exif_transpose(image) or image
    if "A" in image.getbands():
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.getchannel("A"))
        image = background
    else:
        image = image.convert("RGB")

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    sanitized = Image.open(buffer)
    sanitized.load()
    return sanitized
