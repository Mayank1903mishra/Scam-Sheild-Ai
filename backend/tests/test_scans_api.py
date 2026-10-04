import pytest
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal, init_db
from app.db.repository import create_scan
from app.config import settings


@pytest.fixture
def db_session():
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


class TestScansAPI:
    @pytest.mark.asyncio
    async def test_list_scans_empty(self, async_client, db_session):
        response = await async_client.get("/api/v1/scans")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_list_scans_with_data(self, async_client, db_session):
        create_scan(db_session, input_types=["text"], risk_score=10, risk_band="LOW", category=None, uncertainty={"level": "low", "reasons": []}, mode="rules")
        create_scan(db_session, input_types=["url"], risk_score=50, risk_band="MODERATE", category="PHISHING", uncertainty={"level": "low", "reasons": []}, mode="rules")

        response = await async_client.get("/api/v1/scans")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["risk_score"] == 50
        assert data[1]["risk_score"] == 10

    @pytest.mark.asyncio
    async def test_list_scans_pagination(self, async_client, db_session):
        for i in range(5):
            create_scan(db_session, input_types=["text"], risk_score=i*10, risk_band="LOW", category=None, uncertainty={"level": "low", "reasons": []}, mode="rules")

        response = await async_client.get("/api/v1/scans?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        response = await async_client.get("/api/v1/scans?limit=2&offset=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_get_scan_not_found(self, async_client):
        import uuid
        response = await async_client.get(f"/api/v1/scans/{uuid.uuid4()}")
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "HTTP_ERROR"
        assert "not found" in data["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_get_scan(self, async_client, db_session):
        scan = create_scan(db_session, input_types=["text", "url"], risk_score=75, risk_band="HIGH", category="PHISHING", uncertainty={"level": "low", "reasons": []}, mode="rules", evidence_list=[
            {"id": "PHISHING_LINK", "source": "url", "reason": "Suspicious link", "snippet": "http://evil.com", "weight": 30},
            {"id": "URGENCY_LANGUAGE", "source": "text", "reason": "Urgency", "snippet": "act now", "weight": 25},
            {"id": "UPFRONT_PAYMENT", "source": "ocr", "reason": "Fee", "snippet": "pay fee", "weight": 35},
        ])

        response = await async_client.get(f"/api/v1/scans/{scan.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == scan.id
        assert data["risk_score"] == 75
        assert data["risk_band"] == "HIGH"
        assert data["category"] == "PHISHING"
        assert len(data["evidence"]) == 3
        assert data["evidence"][0]["id"] == "PHISHING_LINK"
        # Module scores recomputed from persisted evidence weights:
        # text = 25 (text) + 35 (ocr) = 60, url = 30
        assert data["modules"]["text"] == 60
        assert data["modules"]["url"] == 30
        # OCR confidence is not persisted; must be null, not a fake 0.0
        assert data["modules"]["ocr_confidence"] is None
        # Recommendations/disclaimer derived from the same functions the
        # analysis used (no placeholder strings)
        from app.services.fusion import get_recommendations
        from app.services.explain import get_disclaimer
        assert data["recommendations"] == get_recommendations("HIGH")
        assert data["disclaimer"] == get_disclaimer()
        assert "Verify" in " ".join(data["recommendations"])

    @pytest.mark.asyncio
    async def test_history_detail_matches_fresh_result(self, async_client, db_session):
        """GET after POST returns the same recommendations and disclaimer
        as the original analysis response (deterministic derivation)."""
        payload = {"text": "Pay 5000 registration fee immediately to confirm your internship slot, guaranteed selection."}
        created = await async_client.post("/api/v1/scans", json=payload)
        assert created.status_code == 201
        body = created.json()

        fetched = await async_client.get(f"/api/v1/scans/{body['id']}")
        assert fetched.status_code == 200
        data = fetched.json()
        assert data["recommendations"] == body["recommendations"]
        assert data["disclaimer"] == body["disclaimer"]
        assert data["modules"]["text"] == body["modules"]["text"]
        assert data["modules"]["url"] == body["modules"]["url"]

    @pytest.mark.asyncio
    async def test_delete_scan(self, async_client, db_session):
        scan = create_scan(db_session, input_types=["text"], risk_score=50, risk_band="MODERATE", category=None, uncertainty={"level": "low", "reasons": []}, mode="rules")

        response = await async_client.delete(f"/api/v1/scans/{scan.id}")
        assert response.status_code == 204

        response = await async_client.get(f"/api/v1/scans/{scan.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_scan_not_found(self, async_client):
        import uuid
        response = await async_client.delete(f"/api/v1/scans/{uuid.uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_submit_feedback(self, async_client, db_session):
        scan = create_scan(db_session, input_types=["text"], risk_score=50, risk_band="MODERATE", category=None, uncertainty={"level": "low", "reasons": []}, mode="rules")

        response = await async_client.post(
            f"/api/v1/scans/{scan.id}/feedback",
            json={"helpful": True, "comment": "Great tool!"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Feedback submitted"

    @pytest.mark.asyncio
    async def test_submit_feedback_scan_not_found(self, async_client):
        import uuid
        response = await async_client.post(
            f"/api/v1/scans/{uuid.uuid4()}/feedback",
            json={"helpful": True}
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_submit_feedback_validation(self, async_client, db_session):
        scan = create_scan(db_session, input_types=["text"], risk_score=50, risk_band="MODERATE", category=None, uncertainty={"level": "low", "reasons": []}, mode="rules")

        response = await async_client.post(
            f"/api/v1/scans/{scan.id}/feedback",
            json={"helpful": "not a boolean"}
        )
        assert response.status_code == 422