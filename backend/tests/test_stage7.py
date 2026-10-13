"""Stage 7: integration journeys, edge cases, rate limiting, privacy
regressions, and score/explanation fidelity against the real API."""

import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import app.api.scans as scans_api
from app.config import settings
from app.main import app
from app.services import ocr as ocr_service
from app.services.fusion import get_recommendations, score_to_band
from tests.test_upload import leftover_temp_files, noisy_png_bytes, png_bytes

SCAM_TEXT = "Pay 5000 registration fee immediately to confirm your internship slot, guaranteed selection."

LEGIT_TEXT = """
Dear Candidate,

Thank you for applying to Software Engineer position at Example Corp.
We have received your application and will review it within 5 business days.
You can check status at careers.example.com

Best regards,
HR Team
Example Corp
"""

requires_tesseract = pytest.mark.skipif(
    not ocr_service.tesseract_available(),
    reason="Tesseract OCR binary not available",
)


@pytest_asyncio.fixture
async def no_raise_client():
    """Client that returns the 500 response instead of re-raising."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_post_scan_rate_limited_with_standard_error_shape(
        self, async_client, monkeypatch
    ):
        monkeypatch.setattr(settings, "rate_limit", "3/minute")

        for i in range(3):
            response = await async_client.post(
                "/api/v1/scans", json={"text": f"within limit request {i}"}
            )
            assert response.status_code == 201, response.text

        blocked = await async_client.post(
            "/api/v1/scans",
            json={"text": "one request too many"},
            headers={"Origin": "http://localhost:5173"},
        )
        assert blocked.status_code == 429
        body = blocked.json()
        assert body["error"]["code"] == "RATE_LIMITED"
        assert "Too many requests" in body["error"]["message"]
        # The 429 still passes through CORS middleware.
        assert blocked.headers.get("access-control-allow-origin") == "http://localhost:5173"

    @pytest.mark.asyncio
    async def test_rate_limit_is_isolated_between_tests(self, async_client):
        """After the conftest reset, a fresh test starts below the limit."""
        response = await async_client.post(
            "/api/v1/scans", json={"text": "fresh test after a limited one"}
        )
        assert response.status_code == 201


class TestIntegrationJourneys:
    @pytest.mark.asyncio
    async def test_text_scan_full_journey(self, async_client):
        # 1. Analyse text
        created = await async_client.post("/api/v1/scans", json={"text": SCAM_TEXT})
        assert created.status_code == 201
        scan = created.json()
        scan_id = scan["id"]

        # Score is exactly the bounded sum of returned evidence weights.
        weight_sum = sum(item["weight"] for item in scan["evidence"])
        assert scan["risk_score"] == min(100, max(0, weight_sum))
        assert 0 <= scan["risk_score"] <= 100
        # With evidence present, the band matches the configured thresholds.
        assert scan["risk_band"] == score_to_band(scan["risk_score"])
        assert scan["category"] is not None
        assert scan["recommendations"] == get_recommendations(scan["risk_band"])
        assert "provisional" in scan["score_note"]
        assert "not proof of fraud" in scan["disclaimer"]
        assert scan["mode"] == "rules+ml"
        assert scan["ocr_text"] is None

        # 2. Appears in history
        history = await async_client.get("/api/v1/scans")
        assert history.status_code == 200
        assert any(item["id"] == scan_id for item in history.json())

        # 3. Detail matches the fresh response (deterministic derivation)
        detail = await async_client.get(f"/api/v1/scans/{scan_id}")
        assert detail.status_code == 200
        stored = detail.json()
        assert stored["risk_band"] == scan["risk_band"]
        assert stored["risk_score"] == scan["risk_score"]
        assert stored["recommendations"] == scan["recommendations"]
        assert stored["disclaimer"] == scan["disclaimer"]
        assert {e["id"] for e in stored["evidence"]} == {e["id"] for e in scan["evidence"]}

        # 4. Feedback
        feedback = await async_client.post(
            f"/api/v1/scans/{scan_id}/feedback",
            json={"helpful": True, "comment": "looks right"},
        )
        assert feedback.status_code == 200
        assert feedback.json()["message"] == "Feedback submitted"

        # 5. Delete, then gone from database
        deleted = await async_client.delete(f"/api/v1/scans/{scan_id}")
        assert deleted.status_code == 204
        gone = await async_client.get(f"/api/v1/scans/{scan_id}")
        assert gone.status_code == 404
        history_after = await async_client.get("/api/v1/scans")
        assert not any(item["id"] == scan_id for item in history_after.json())

    @pytest.mark.asyncio
    async def test_url_scan_journey(self, async_client):
        url = "http://192.168.1.1/login/verify/account?redirect=paypal"
        created = await async_client.post("/api/v1/scans", json={"url": url})
        assert created.status_code == 201
        scan = created.json()

        assert scan["input_types"] == ["url"]
        assert scan["modules"]["url"] > 0
        assert any(item["id"].startswith("URL_") for item in scan["evidence"])
        assert url in scan["extracted"]["urls"]
        assert scan["risk_score"] == min(
            100, max(0, sum(item["weight"] for item in scan["evidence"]))
        )

    @pytest.mark.asyncio
    async def test_combined_text_and_url_submission(self, async_client):
        created = await async_client.post(
            "/api/v1/scans",
            json={"text": SCAM_TEXT, "url": "http://bit.ly/x9fk2"},
        )
        assert created.status_code == 201
        scan = created.json()
        assert set(scan["input_types"]) == {"text", "url"}
        assert scan["modules"]["text"] > 0
        assert scan["modules"]["url"] > 0

    @requires_tesseract
    @pytest.mark.asyncio
    async def test_image_upload_ocr_journey(self, async_client):
        created = await async_client.post(
            "/api/v1/scans/upload",
            files={"file": ("offer.png", png_bytes(text=SCAM_TEXT), "image/png")},
        )
        assert created.status_code == 201, created.text
        scan = created.json()

        assert "image" in scan["input_types"]
        assert isinstance(scan["ocr_text"], str) and len(scan["ocr_text"]) > 0
        assert scan["modules"]["ocr_confidence"] is not None
        assert 0.0 <= scan["modules"]["ocr_confidence"] <= 1.0
        assert scan["risk_score"] == min(
            100, max(0, sum(item["weight"] for item in scan["evidence"]))
        )
        assert leftover_temp_files() == []

        # Raw OCR text is not retrievable from history.
        detail = await async_client.get(f"/api/v1/scans/{scan['id']}")
        assert detail.status_code == 200
        assert detail.json()["ocr_text"] is None
        assert detail.json()["modules"]["ocr_confidence"] is None

    @pytest.mark.asyncio
    async def test_delete_unknown_scan_404(self, async_client):
        response = await async_client.delete(f"/api/v1/scans/{uuid.uuid4()}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "HTTP_ERROR"


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_hindi_unicode_text(self, async_client):
        response = await async_client.post(
            "/api/v1/scans",
            json={"text": "नौकरी के लिए तुरंत 5000 रुपये भेजें, guaranteed selection अभी!"},
        )
        assert response.status_code == 201
        scan = response.json()
        assert scan["risk_band"] in {"LOW", "MODERATE", "HIGH", "VERY_HIGH", "UNCERTAIN"}
        assert 0 <= scan["risk_score"] <= 100

    @pytest.mark.asyncio
    async def test_emoji_and_mixed_script(self, async_client):
        response = await async_client.post(
            "/api/v1/scans",
            json={"text": "_win a prize 🎁💰 send fee now! \u062a\u062d\u0642\u0642 \u0627\u0644\u0623\u0646\u0635\u0631"},
        )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_sql_like_string_keeps_database_intact(self, async_client):
        created = await async_client.post(
            "/api/v1/scans",
            json={"text": "'; DROP TABLE scans; --"},
        )
        assert created.status_code == 201

        history = await async_client.get("/api/v1/scans")
        assert history.status_code == 200
        assert any(item["id"] == created.json()["id"] for item in history.json())

        detail = await async_client.get(f"/api/v1/scans/{created.json()['id']}")
        assert detail.status_code == 200

    @pytest.mark.asyncio
    async def test_text_over_10000_chars_rejected(self, async_client):
        response = await async_client.post(
            "/api/v1/scans", json={"text": "a" * 10001}
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_url_over_2048_chars_rejected(self, async_client):
        response = await async_client.post(
            "/api/v1/scans", json={"url": "http://example.com/" + "a" * 2100}
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_empty_json_object_rejected(self, async_client):
        response = await async_client.post("/api/v1/scans", json={})
        assert response.status_code == 422
        body = response.json()
        assert "error" in body
        assert "at least one" in body["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_whitespace_only_text_rejected(self, async_client):
        response = await async_client.post("/api/v1/scans", json={"text": "   "})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_path_traversal_filename_is_ignored(self, async_client):
        content = png_bytes(text="hello")
        created = await async_client.post(
            "/api/v1/scans/upload",
            files={"file": ("../../../evil.png", content, "image/png")},
        )
        assert created.status_code == 201
        # The filename must never influence where bytes are written.
        backend_dir = Path(__file__).resolve().parent.parent
        assert not (backend_dir / "evil.png").exists()
        assert not (backend_dir.parent / "evil.png").exists()
        assert leftover_temp_files() == []

    @requires_tesseract
    @pytest.mark.asyncio
    async def test_noisy_image_does_not_crash(self, async_client):
        response = await async_client.post(
            "/api/v1/scans/upload",
            files={"file": ("noise.png", noisy_png_bytes(), "image/png")},
        )
        assert response.status_code == 201, response.text
        scan = response.json()
        assert scan["risk_band"] in {"LOW", "MODERATE", "HIGH", "VERY_HIGH", "UNCERTAIN"}
        assert scan["uncertainty"]["level"] in {"low", "medium", "high"}
        assert leftover_temp_files() == []

    @pytest.mark.asyncio
    async def test_gif_rejected_415(self, async_client):
        from tests.test_upload import gif_bytes
        response = await async_client.post(
            "/api/v1/scans/upload",
            files={"file": ("anim.gif", gif_bytes(), "image/gif")},
        )
        assert response.status_code == 415
        assert response.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"

    @pytest.mark.asyncio
    async def test_unhandled_error_returns_clean_500_without_stack_trace(
        self, no_raise_client, monkeypatch
    ):
        def boom(**_kwargs):
            raise RuntimeError("secret internal detail that must not leak")

        monkeypatch.setattr(scans_api, "analyze_input", boom)
        response = await no_raise_client.post(
            "/api/v1/scans", json={"text": "anything at all"}
        )
        assert response.status_code == 500
        body = response.json()
        assert body["error"]["code"] == "INTERNAL_ERROR"
        assert body["error"]["message"] == "An unexpected error occurred"
        assert "secret internal detail" not in response.text
        assert "Traceback" not in response.text


class TestLegitimateContentNotOverFlagged:
    @pytest.mark.asyncio
    async def test_legitimate_internship_email_stays_low(self, async_client):
        created = await async_client.post("/api/v1/scans", json={"text": LEGIT_TEXT})
        assert created.status_code == 201
        scan = created.json()
        assert scan["risk_band"] not in {"HIGH", "VERY_HIGH"}
        high_risk_ids = {"CREDENTIAL_REQUEST", "UPFRONT_PAYMENT", "GUARANTEED_SELECTION"}
        assert not high_risk_ids & {e["id"] for e in scan["evidence"]}

    @pytest.mark.asyncio
    async def test_urgent_but_legitimate_deadline_not_extreme(self, async_client):
        text = (
            "Applications close tomorrow at 5 PM. Submit your resume through "
            "the official portal at example.com/careers. No fees are required."
        )
        created = await async_client.post("/api/v1/scans", json={"text": text})
        assert created.status_code == 201
        scan = created.json()
        assert scan["risk_band"] not in {"HIGH", "VERY_HIGH"}

    @pytest.mark.asyncio
    async def test_tiny_input_yields_uncertain(self, async_client):
        created = await async_client.post("/api/v1/scans", json={"text": "ok"})
        assert created.status_code == 201
        scan = created.json()
        assert scan["risk_band"] == "UNCERTAIN"
        assert scan["uncertainty"]["level"] == "high"
        assert any("short" in reason.lower() for reason in scan["uncertainty"]["reasons"])
        assert scan["recommendations"] == get_recommendations("UNCERTAIN")


class TestPrivacyRegression:
    def test_store_content_default_is_false(self):
        assert settings.store_content is False

    def test_env_example_documents_store_content_false(self):
        env_example = Path(__file__).resolve().parents[2] / ".env.example"
        content = env_example.read_text(encoding="utf-8")
        assert "STORE_CONTENT=false" in content

    @pytest.mark.asyncio
    async def test_pii_masked_before_persistence_and_history_readback(
        self, async_client
    ):
        phone = "+91 9876543210"
        text = (
            f"Contact me on WhatsApp at {phone} and deposit the fee today, "
            "guaranteed selection for the internship, pay now to confirm!"
        )
        created = await async_client.post("/api/v1/scans", json={"text": text})
        assert created.status_code == 201
        scan_id = created.json()["id"]

        # Phone digits must not survive into stored evidence.
        from app.db.session import SessionLocal
        from app.db.models import Scan
        db = SessionLocal()
        try:
            row = db.query(Scan).filter(Scan.id == scan_id).one()
            # Raw text is not stored when STORE_CONTENT=false.
            assert row.masked_text is None
            stored_snippets = " ".join(e.snippet_masked for e in row.evidence)
        finally:
            db.close()
        assert "9876543210" not in stored_snippets

        # History readback serves the masked snippets.
        detail = await async_client.get(f"/api/v1/scans/{scan_id}")
        assert detail.status_code == 200
        assert "9876543210" not in detail.text
        # The response never contains a raw-text field.
        assert "masked_text" not in detail.json()
