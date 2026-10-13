"""Stage 5 tests: secure upload and local OCR.

Unit tests mock the OCR engine where appropriate; one integration test
runs the real Tesseract engine when it is installed (skipped otherwise).
"""
import glob
import os
import random
import tempfile
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont, features

from app.config import settings, get_max_upload_bytes
from app.exceptions import AppError
from app.services.image_validator import validate_and_sanitize, sniff_format
from app.services.ocr import (
    OCRResult,
    run_ocr,
    resolve_tesseract,
    rows_to_text_and_confidence,
    temporary_image_file,
    tesseract_available,
)

requires_tesseract = pytest.mark.skipif(
    not tesseract_available(),
    reason="Tesseract OCR binary not installed",
)

SCAM_OCR_TEXT = (
    "Urgent! Guaranteed job offer! Pay the registration fee of 200 dollars "
    "before joining. Contact jobs@gmail.com or WhatsApp +1-555-123-4567"
)

_FONT = None
for _font_path in (
    r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
):
    if os.path.isfile(_font_path):
        _FONT = ImageFont.truetype(_font_path, 36)
        break
if _FONT is None:
    _FONT = ImageFont.load_default()


# ---------------------------------------------------------------- helpers

def png_bytes(text=None, size=(700, 180), color="white") -> bytes:
    image = Image.new("RGB", size, color)
    if text:
        ImageDraw.Draw(image).text((20, size[1] // 2 - 10), text, fill="black", font=_FONT)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def noisy_png_bytes() -> bytes:
    random.seed(42)
    image = Image.new("RGB", (400, 400))
    image.putdata(
        [(random.randrange(256), random.randrange(256), random.randrange(256))
         for _ in range(400 * 400)]
    )
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def gif_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (10, 10), "red").convert("P").save(buffer, format="GIF")
    return buffer.getvalue()


def jpeg_with_exif() -> bytes:
    exif = Image.Exif()
    exif[271] = "SecretCamMake"
    exif[272] = "SecretModel"
    image = Image.new("RGB", (50, 50), "white")
    buffer = BytesIO()
    image.save(buffer, format="JPEG", exif=exif.tobytes())
    return buffer.getvalue()


def leftover_temp_files():
    return glob.glob(os.path.join(tempfile.gettempdir(), "scamshield_ocr_*"))


def make_fake_ocr(text, confidence=0.9):
    def fake_run_ocr(image):
        return OCRResult(text=text, confidence=confidence)
    return fake_run_ocr


async def upload(client, content, filename="shot.png",
                 content_type="image/png", text=None, url=None, headers=None):
    files = {"file": (filename, content, content_type)}
    data = {}
    if text is not None:
        data["text"] = text
    if url is not None:
        data["url"] = url
    return await client.post(
        "/api/v1/scans/upload", files=files, data=data, headers=headers or {}
    )


# --------------------------------------------------------------- fixtures

@pytest.fixture
def db_session():
    from app.db.session import SessionLocal, init_db
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture(autouse=True)
def cleanup_db(db_session):
    yield
    from app.db.models import Evidence, Feedback, Scan
    db_session.query(Evidence).delete()
    db_session.query(Feedback).delete()
    db_session.query(Scan).delete()
    db_session.commit()


@pytest.fixture
def mock_ocr(monkeypatch):
    """Replace the OCR engine with a deterministic fake."""
    def _install(text, confidence=0.9):
        monkeypatch.setattr(
            "app.services.ocr.run_ocr", make_fake_ocr(text, confidence)
        )
    return _install


# ------------------------------------------------------- image validation

class TestImageValidator:
    def test_valid_png_accepted(self):
        image = validate_and_sanitize(png_bytes("hello"))
        assert image.format == "PNG"
        assert image.mode == "RGB"

    def test_valid_jpeg_accepted(self):
        image = validate_and_sanitize(jpeg_with_exif())
        assert image.format == "PNG"  # re-encoded, metadata stripped

    def test_valid_webp_accepted(self):
        if not features.check("webp"):
            pytest.skip("Pillow built without WebP support")
        buffer = BytesIO()
        Image.new("RGB", (30, 30), "blue").save(buffer, format="WEBP")
        image = validate_and_sanitize(buffer.getvalue())
        assert image.format == "PNG"

    def test_alpha_channel_flattened(self):
        buffer = BytesIO()
        Image.new("RGBA", (40, 40), (255, 0, 0, 128)).save(buffer, format="PNG")
        image = validate_and_sanitize(buffer.getvalue())
        assert image.mode == "RGB"

    def test_empty_file_rejected(self):
        with pytest.raises(AppError) as exc:
            validate_and_sanitize(b"")
        assert exc.value.code == "INVALID_IMAGE"
        assert exc.value.status_code == 400

    def test_text_bytes_rejected_as_unsupported_type(self):
        with pytest.raises(AppError) as exc:
            validate_and_sanitize(b"this is definitely not an image")
        assert exc.value.code == "UNSUPPORTED_FILE_TYPE"
        assert exc.value.status_code == 415

    def test_gif_rejected(self):
        with pytest.raises(AppError) as exc:
            validate_and_sanitize(gif_bytes())
        assert exc.value.code == "UNSUPPORTED_FILE_TYPE"
        assert exc.value.status_code == 415

    def test_png_magic_with_garbage_rejected(self):
        with pytest.raises(AppError) as exc:
            validate_and_sanitize(b"\x89PNG\r\n\x1a\n" + b"garbagegarbage")
        assert exc.value.code == "INVALID_IMAGE"
        assert exc.value.status_code == 400

    def test_truncated_png_rejected(self):
        data = noisy_png_bytes()
        truncated = data[: len(data) // 2]
        with pytest.raises(AppError) as exc:
            validate_and_sanitize(truncated)
        assert exc.value.code == "INVALID_IMAGE"
        assert exc.value.status_code == 400

    def test_oversized_bytes_rejected(self):
        payload = b"\x89PNG\r\n\x1a\n" + b"a" * (get_max_upload_bytes() + 1)
        with pytest.raises(AppError) as exc:
            validate_and_sanitize(payload)
        assert exc.value.code == "FILE_TOO_LARGE"
        assert exc.value.status_code == 413

    def test_pixel_limit_enforced(self, monkeypatch):
        monkeypatch.setattr(settings, "max_image_pixels", 1000)
        with pytest.raises(AppError) as exc:
            validate_and_sanitize(png_bytes(size=(200, 200)))
        assert exc.value.code == "IMAGE_TOO_LARGE"
        assert exc.value.status_code == 413

    def test_dimension_limit_enforced(self, monkeypatch):
        monkeypatch.setattr(settings, "max_image_dimension", 10)
        with pytest.raises(AppError) as exc:
            validate_and_sanitize(png_bytes(size=(100, 100)))
        assert exc.value.code == "IMAGE_TOO_LARGE"
        assert exc.value.status_code == 413

    def test_exif_stripped(self):
        image = validate_and_sanitize(jpeg_with_exif())
        assert len(image.getexif()) == 0

    def test_sniff_format_content_based(self):
        assert sniff_format(png_bytes()) == "PNG"
        assert sniff_format(gif_bytes()) is None
        assert sniff_format(b"\xff\xd8\xff\xe0JFIF") == "JPEG"


# ----------------------------------------------------- temp file handling

class TestTemporaryFile:
    def test_temp_file_deleted_after_success(self):
        seen = {}
        with temporary_image_file(validate_and_sanitize(png_bytes())) as path:
            seen["path"] = path
            assert os.path.isfile(path)
            assert os.path.basename(path).startswith("scamshield_ocr_")
        assert not os.path.exists(seen["path"])

    def test_temp_file_deleted_on_error(self):
        seen = {}
        with pytest.raises(RuntimeError):
            with temporary_image_file(validate_and_sanitize(png_bytes())) as path:
                seen["path"] = path
                raise RuntimeError("OCR exploded")
        assert not os.path.exists(seen["path"])


# ------------------------------------------------------------ OCR service

class TestOCRService:
    def test_rows_to_text_and_confidence(self):
        data = {
            "text": ["Urgent", "", "Pay", "now"],
            "conf": ["95", "-1", "80", "60"],
            "block_num": [1, 1, 2, 2],
            "par_num": [1, 1, 2, 2],
            "line_num": [1, 1, 2, 2],
            "word_num": [1, 2, 1, 2],
        }
        text, confidence = rows_to_text_and_confidence(data)
        assert text == "Urgent\nPay now"
        assert confidence == pytest.approx(0.7833, abs=0.001)

    def test_rows_empty(self):
        text, confidence = rows_to_text_and_confidence({"text": [], "conf": []})
        assert text == ""
        assert confidence == 0.0

    def test_run_ocr_unavailable_returns_clear_error(self, monkeypatch):
        monkeypatch.setattr("app.services.ocr.resolve_tesseract", lambda: None)
        with pytest.raises(AppError) as exc:
            run_ocr(validate_and_sanitize(png_bytes()))
        assert exc.value.code == "OCR_UNAVAILABLE"
        assert exc.value.status_code == 503
        assert "Install Tesseract" in exc.value.message

    def test_run_ocr_failure_deletes_temp_file(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.ocr.resolve_tesseract", lambda: "C:/fake/tesseract.exe"
        )
        import pytesseract

        def boom(*args, **kwargs):
            raise RuntimeError("Tesseract process timeout")

        monkeypatch.setattr(pytesseract, "image_to_data", boom)
        with pytest.raises(AppError) as exc:
            run_ocr(validate_and_sanitize(png_bytes()))
        assert exc.value.code == "OCR_FAILED"
        assert exc.value.status_code == 500
        assert leftover_temp_files() == []

    @requires_tesseract
    def test_run_ocr_real_engine(self):
        image = validate_and_sanitize(
            png_bytes(
                "Urgent! Pay registration fee of 500 dollars now!",
                size=(1000, 200),
            )
        )
        result = run_ocr(image)
        assert "registration fee" in result.text.lower()
        assert result.confidence > 0.3
        assert leftover_temp_files() == []


# ------------------------------------------------------------- upload API

class TestUploadAPI:
    @pytest.mark.asyncio
    async def test_valid_upload_returns_full_analysis(
        self, async_client, db_session, mock_ocr
    ):
        mock_ocr(SCAM_OCR_TEXT, confidence=0.87)
        response = await upload(async_client, png_bytes())
        assert response.status_code == 201
        body = response.json()

        assert body["input_types"] == ["image"]
        assert body["ocr_text"] == SCAM_OCR_TEXT
        assert body["modules"]["ocr_confidence"] == 0.87
        assert 0 <= body["risk_score"] <= 100
        assert body["risk_band"] in ("LOW", "MODERATE", "HIGH", "VERY_HIGH", "UNCERTAIN")
        assert body["mode"] == "rules+ml"
        assert body["score_note"]
        assert body["disclaimer"]
        assert body["recommendations"]
        assert body["uncertainty"]["level"] in ("low", "medium", "high")
        # OCR-derived evidence carries the "ocr" source
        sources = {e["source"] for e in body["evidence"]}
        assert "ocr" in sources
        assert "ml" in sources
        assert any(e["id"] == "UPFRONT_PAYMENT" for e in body["evidence"])
        assert body["risk_score"] >= 25  # upfront payment indicator at minimum

        # persisted scan is retrievable
        stored = await async_client.get(f"/api/v1/scans/{body['id']}")
        assert stored.status_code == 200

    @pytest.mark.asyncio
    async def test_combined_text_and_image(
        self, async_client, db_session, mock_ocr
    ):
        mock_ocr("Pay the registration fee immediately.", confidence=0.9)
        response = await upload(
            async_client, png_bytes(), text="Urgent! Send your OTP now."
        )
        assert response.status_code == 201
        body = response.json()
        assert body["input_types"] == ["text", "image"]
        sources = {e["source"] for e in body["evidence"]}
        assert "text" in sources  # from pasted text
        assert "ocr" in sources   # from image

    @pytest.mark.asyncio
    async def test_image_with_url_field(self, async_client, db_session, mock_ocr):
        mock_ocr("Urgent! Verify your account immediately.", confidence=0.9)
        response = await upload(
            async_client, png_bytes(), url="https://bit.ly/verify-account"
        )
        assert response.status_code == 201
        body = response.json()
        assert body["input_types"] == ["url", "image"]
        assert "https://bit.ly/verify-account" in body["extracted"]["urls"]

    @pytest.mark.asyncio
    async def test_urls_inside_image_are_extracted_and_analyzed(
        self, async_client, db_session, mock_ocr
    ):
        mock_ocr(
            "Urgent! Login now at http://192.168.1.1/login?redirect=paypal.com",
            confidence=0.9,
        )
        response = await upload(async_client, png_bytes())
        assert response.status_code == 201
        body = response.json()
        assert any("192.168.1.1" in u for u in body["extracted"]["urls"])
        url_evidence = [e for e in body["evidence"] if e["source"] == "url"]
        assert any(e["id"] == "URL_IP_HOST" for e in url_evidence)

    @pytest.mark.asyncio
    async def test_missing_file_returns_422(self, async_client):
        response = await async_client.post(
            "/api/v1/scans/upload", data={"text": "hello"}
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_oversized_file_endpoint_rejects_413(self, async_client, mock_ocr):
        mock_ocr("text")
        # Small enough to pass the pre-parse middleware, too big for the
        # endpoint's content check.
        payload = b"\x89PNG\r\n\x1a\n" + b"a" * (get_max_upload_bytes() + 10 * 1024)
        response = await upload(async_client, payload)
        assert response.status_code == 413
        error = response.json()["error"]
        assert error["code"] == "FILE_TOO_LARGE"
        assert "MB" in error["message"]

    @pytest.mark.asyncio
    async def test_huge_upload_rejected_before_parsing(
        self, async_client, mock_ocr
    ):
        mock_ocr("text")
        payload = b"x" * (get_max_upload_bytes() + 1024 * 1024)
        response = await upload(
            async_client,
            payload,
            headers={"Origin": "http://localhost:5173"},
        )
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
        # Middleware response still goes through CORS and request-id
        assert response.headers.get("access-control-allow-origin") == (
            "http://localhost:5173"
        )
        assert "x-request-id" in response.headers

    @pytest.mark.asyncio
    async def test_wrong_type_with_spoofed_extension_415(
        self, async_client, mock_ocr
    ):
        mock_ocr("text")
        response = await upload(
            async_client, gif_bytes(), filename="totally_a_screenshot.png"
        )
        assert response.status_code == 415
        assert response.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"

    @pytest.mark.asyncio
    async def test_extension_ignored_when_content_is_valid(
        self, async_client, db_session, mock_ocr
    ):
        """Content decides, not the filename: a real PNG named .txt works."""
        mock_ocr("Urgent! Pay the fee now.")
        response = await upload(
            async_client, png_bytes(), filename="notes.txt",
            content_type="text/plain",
        )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_corrupt_image_400(self, async_client, mock_ocr):
        mock_ocr("text")
        response = await upload(async_client, noisy_png_bytes()[:10000])
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_IMAGE"

    @pytest.mark.asyncio
    async def test_empty_file_400(self, async_client, mock_ocr):
        mock_ocr("text")
        response = await upload(async_client, b"")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_IMAGE"

    @pytest.mark.asyncio
    async def test_ocr_unavailable_returns_503_and_no_fake_result(
        self, async_client, db_session, monkeypatch
    ):
        monkeypatch.setattr("app.services.ocr.resolve_tesseract", lambda: None)
        # Real run_ocr (not mocked): must fail clearly, never invent text
        response = await upload(async_client, png_bytes())
        assert response.status_code == 503
        body = response.json()
        assert body["error"]["code"] == "OCR_UNAVAILABLE"
        assert "Install Tesseract" in body["error"]["message"]
        # No scan row created, no temp files left behind
        scans = await async_client.get("/api/v1/scans")
        assert scans.status_code == 200
        assert len(scans.json()) == 0
        assert leftover_temp_files() == []

    @pytest.mark.asyncio
    async def test_empty_ocr_reports_limited_analysis(
        self, async_client, db_session, mock_ocr
    ):
        mock_ocr("", confidence=0.0)
        response = await upload(async_client, png_bytes())
        assert response.status_code == 201
        body = response.json()
        assert body["ocr_text"] == ""
        assert body["risk_band"] == "UNCERTAIN"
        assert any(
            "No text could be extracted" in r
            for r in body["uncertainty"]["reasons"]
        )

    @pytest.mark.asyncio
    async def test_tiny_ocr_text_reports_limited_analysis(
        self, async_client, db_session, mock_ocr
    ):
        mock_ocr("Hi", confidence=0.4)
        response = await upload(async_client, png_bytes())
        assert response.status_code == 201
        body = response.json()
        assert body["risk_band"] == "UNCERTAIN"
        reasons = body["uncertainty"]["reasons"]
        assert any("Very little text" in r for r in reasons)

    @pytest.mark.asyncio
    async def test_low_ocr_confidence_raises_uncertainty_not_risk(
        self, async_client, db_session, mock_ocr
    ):
        mock_ocr(
            "Congratulations! You have been awarded the Merit Scholarship "
            "for the current academic year. No action is required.",
            confidence=0.2,
        )
        response = await upload(async_client, png_bytes())
        assert response.status_code == 201
        body = response.json()
        assert body["modules"]["ocr_confidence"] == 0.2
        assert body["uncertainty"]["level"] in ("medium", "high")
        assert any("OCR confidence" in r for r in body["uncertainty"]["reasons"])
        # Low confidence must not push the score up by itself
        assert body["risk_score"] <= 30
        assert body["risk_band"] == "LOW"

    @pytest.mark.asyncio
    async def test_oversized_text_form_field_422(self, async_client, mock_ocr):
        mock_ocr("text")
        response = await upload(
            async_client, png_bytes(), text="a" * 10001
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_get_after_upload_hides_raw_ocr_text(
        self, async_client, db_session, mock_ocr
    ):
        mock_ocr(SCAM_OCR_TEXT, confidence=0.9)
        response = await upload(async_client, png_bytes())
        body = response.json()
        stored = await async_client.get(f"/api/v1/scans/{body['id']}")
        assert stored.status_code == 200
        stored_body = stored.json()
        assert "image" in stored_body["input_types"]
        # Raw OCR text is not persisted by default
        assert stored_body["ocr_text"] is None


# ------------------------------------------------------------- privacy

class TestUploadPrivacy:
    @pytest.mark.asyncio
    async def test_no_content_stored_by_default(
        self, async_client, db_session, mock_ocr
    ):
        mock_ocr(SCAM_OCR_TEXT, confidence=0.9)
        response = await upload(async_client, png_bytes())
        assert response.status_code == 201

        from app.db.models import Scan
        scan = db_session.query(Scan).one()
        assert scan.masked_text is None  # STORE_CONTENT=false

    @pytest.mark.asyncio
    async def test_stored_evidence_snippets_are_masked(
        self, async_client, db_session, mock_ocr
    ):
        mock_ocr(
            "Urgent! Call +91 98765 43210 or mail job@gmail.com to pay the fee.",
            confidence=0.9,
        )
        response = await upload(async_client, png_bytes())
        scan_id = response.json()["id"]

        stored = await async_client.get(f"/api/v1/scans/{scan_id}")
        for item in stored.json()["evidence"]:
            assert "98765 43210" not in item["snippet"]
            assert "9876543210" not in item["snippet"]
            assert "job@gmail.com" not in item["snippet"]

    @pytest.mark.asyncio
    async def test_no_image_files_persisted(
        self, async_client, db_session, mock_ocr
    ):
        mock_ocr("Urgent pay now", confidence=0.9)
        response = await upload(async_client, png_bytes())
        assert response.status_code == 201
        # Our temp files are gone; raw upload never written anywhere else
        assert leftover_temp_files() == []
        backend_dir = Path(__file__).parent.parent
        assert not list(backend_dir.glob("*.png"))
        assert not list(backend_dir.glob("*.jpg"))


# ---------------------------------------------------------- no network

class TestNoNetworkAccess:
    def test_analysis_services_contain_no_network_clients(self):
        """The analysis/OCR path must never fetch URLs or call APIs."""
        services_dir = Path(__file__).parent.parent / "app" / "services"
        forbidden = (
            "import requests",
            "import httpx",
            "urllib.request",
            "import socket",
            "from socket",
        )
        for source_file in services_dir.glob("*.py"):
            content = source_file.read_text(encoding="utf-8")
            for needle in forbidden:
                assert needle not in content, (
                    f"{source_file.name} must not use '{needle}'"
                )


# ------------------------------------------------- real OCR integration

@requires_tesseract
class TestRealOCRIntegration:
    @pytest.mark.asyncio
    async def test_screenshot_roundtrip_with_real_ocr(
        self, async_client, db_session
    ):
        """Reproducible end-to-end verification with the real Tesseract engine."""
        image_bytes = png_bytes(
            "Urgent! Pay registration fee of 500 dollars before joining!",
            size=(1100, 220),
        )
        response = await upload(async_client, image_bytes)
        assert response.status_code == 201
        body = response.json()

        assert "registration fee" in body["ocr_text"].lower()
        assert body["modules"]["ocr_confidence"] > 0.3
        evidence_ids = {e["id"] for e in body["evidence"]}
        assert "UPFRONT_PAYMENT" in evidence_ids
        assert "URGENCY_LANGUAGE" in evidence_ids
        assert body["risk_score"] >= 40
        assert body["risk_band"] in ("MODERATE", "HIGH", "VERY_HIGH")
        assert leftover_temp_files() == []
