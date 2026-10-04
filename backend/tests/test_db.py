import pytest
from sqlalchemy.orm import Session
from sqlalchemy import inspect
from datetime import timedelta

from app.db.models import Scan, Evidence, Feedback, utcnow
from app.db.repository import (
    create_scan,
    get_scan,
    list_scans,
    delete_scan,
    submit_feedback,
    cleanup_expired_scans,
)
from app.db.session import SessionLocal, init_db, engine
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
    db_session.query(Evidence).delete()
    db_session.query(Feedback).delete()
    db_session.query(Scan).delete()
    db_session.commit()


class TestDatabaseModels:
    def test_scan_creation(self, db_session: Session):
        scan = Scan(
            input_types='["text"]',
            risk_score=50,
            risk_band="MODERATE",
            category="FAKE_JOB",
            uncertainty_json='{"level": "low", "reasons": []}',
            mode="rules",
            masked_text="masked content",
            expires_at=utcnow() + timedelta(days=30),
        )
        db_session.add(scan)
        db_session.commit()
        db_session.refresh(scan)

        assert scan.id is not None
        assert scan.created_at is not None
        assert scan.risk_score == 50
        assert scan.risk_band == "MODERATE"

    def test_evidence_relationship(self, db_session: Session):
        scan = Scan(
            input_types='["text"]',
            risk_score=50,
            risk_band="MODERATE",
            mode="rules",
            expires_at=utcnow() + timedelta(days=30),
        )
        db_session.add(scan)
        db_session.flush()

        evidence = Evidence(
            scan_id=scan.id,
            indicator_id="UPFRONT_PAYMENT",
            source="text",
            reason="Requests payment",
            snippet_masked="pay $50",
            weight=25,
        )
        db_session.add(evidence)
        db_session.commit()

        assert len(scan.evidence) == 1
        assert scan.evidence[0].indicator_id == "UPFRONT_PAYMENT"

    def test_feedback_relationship(self, db_session: Session):
        scan = Scan(
            input_types='["text"]',
            risk_score=50,
            risk_band="MODERATE",
            mode="rules",
            expires_at=utcnow() + timedelta(days=30),
        )
        db_session.add(scan)
        db_session.flush()

        feedback = Feedback(scan_id=scan.id, helpful=True, comment="Good")
        db_session.add(feedback)
        db_session.commit()

        assert len(scan.feedback) == 1
        assert scan.feedback[0].helpful is True

    def test_cascade_delete_evidence(self, db_session: Session):
        scan = Scan(
            input_types='["text"]',
            risk_score=50,
            risk_band="MODERATE",
            mode="rules",
            expires_at=utcnow() + timedelta(days=30),
        )
        db_session.add(scan)
        db_session.flush()

        evidence = Evidence(
            scan_id=scan.id,
            indicator_id="UPFRONT_PAYMENT",
            source="text",
            reason="Requests payment",
            snippet_masked="pay $50",
            weight=25,
        )
        db_session.add(evidence)
        db_session.commit()

        db_session.delete(scan)
        db_session.commit()

        remaining = db_session.query(Evidence).filter(Evidence.scan_id == scan.id).all()
        assert len(remaining) == 0

    def test_cascade_delete_feedback(self, db_session: Session):
        scan = Scan(
            input_types='["text"]',
            risk_score=50,
            risk_band="MODERATE",
            mode="rules",
            expires_at=utcnow() + timedelta(days=30),
        )
        db_session.add(scan)
        db_session.flush()

        feedback = Feedback(scan_id=scan.id, helpful=True)
        db_session.add(feedback)
        db_session.commit()

        db_session.delete(scan)
        db_session.commit()

        remaining = db_session.query(Feedback).filter(Feedback.scan_id == scan.id).all()
        assert len(remaining) == 0


class TestRepository:
    def test_create_scan(self, db_session: Session):
        original_store = settings.store_content
        settings.store_content = True
        try:
            scan = create_scan(
                db_session,
                input_types=["text", "url"],
                risk_score=75,
                risk_band="HIGH",
                category="PHISHING",
                uncertainty={"level": "low", "reasons": []},
                mode="rules",
                masked_text="masked",
                evidence_list=[
                    {"id": "PHISHING_LINK", "source": "url", "reason": "Suspicious link", "snippet": "http://evil.com", "weight": 30},
                ],
            )

            assert scan.id is not None
            assert scan.risk_score == 75
            assert scan.risk_band == "HIGH"
            assert scan.category == "PHISHING"
            assert scan.masked_text == "masked"
            assert len(scan.evidence) == 1
            assert scan.evidence[0].indicator_id == "PHISHING_LINK"
        finally:
            settings.store_content = original_store

    def test_create_scan_respects_store_content_false(self, db_session: Session):
        original_store = settings.store_content
        settings.store_content = False
        try:
            scan = create_scan(
                db_session,
                input_types=["text"],
                risk_score=50,
                risk_band="MODERATE",
                category=None,
                uncertainty={"level": "low", "reasons": []},
                mode="rules",
                masked_text="should not be stored",
            )
            assert scan.masked_text is None
        finally:
            settings.store_content = original_store

    def test_create_scan_respects_store_content_true(self, db_session: Session):
        original_store = settings.store_content
        settings.store_content = True
        try:
            scan = create_scan(
                db_session,
                input_types=["text"],
                risk_score=50,
                risk_band="MODERATE",
                category=None,
                uncertainty={"level": "low", "reasons": []},
                mode="rules",
                masked_text="should be stored",
            )
            assert scan.masked_text == "should be stored"
        finally:
            settings.store_content = original_store

    def test_get_scan(self, db_session: Session):
        scan = create_scan(
            db_session,
            input_types=["text"],
            risk_score=50,
            risk_band="MODERATE",
            category="FAKE_JOB",
            uncertainty={"level": "low", "reasons": []},
            mode="rules",
        )

        retrieved = get_scan(db_session, scan.id)
        assert retrieved is not None
        assert retrieved.id == scan.id
        assert retrieved.risk_score == 50

    def test_get_scan_not_found(self, db_session: Session):
        retrieved = get_scan(db_session, "non-existent-id")
        assert retrieved is None

    def test_list_scans(self, db_session: Session):
        create_scan(db_session, input_types=["text"], risk_score=10, risk_band="LOW", category=None, uncertainty={"level": "low", "reasons": []}, mode="rules")
        create_scan(db_session, input_types=["url"], risk_score=50, risk_band="MODERATE", category="PHISHING", uncertainty={"level": "low", "reasons": []}, mode="rules")
        create_scan(db_session, input_types=["image"], risk_score=90, risk_band="VERY_HIGH", category="FAKE_OFFER_LETTER", uncertainty={"level": "high", "reasons": ["low OCR confidence"]}, mode="rules")

        scans = list_scans(db_session, limit=10, offset=0)
        assert len(scans) == 3
        assert scans[0].risk_score == 90
        assert scans[1].risk_score == 50
        assert scans[2].risk_score == 10

    def test_list_scans_pagination(self, db_session: Session):
        for i in range(5):
            create_scan(db_session, input_types=["text"], risk_score=i*10, risk_band="LOW", category=None, uncertainty={"level": "low", "reasons": []}, mode="rules")

        scans = list_scans(db_session, limit=2, offset=0)
        assert len(scans) == 2

        scans = list_scans(db_session, limit=2, offset=2)
        assert len(scans) == 2

    def test_delete_scan(self, db_session: Session):
        scan = create_scan(db_session, input_types=["text"], risk_score=50, risk_band="MODERATE", category=None, uncertainty={"level": "low", "reasons": []}, mode="rules")

        result = delete_scan(db_session, scan.id)
        assert result is True

        retrieved = get_scan(db_session, scan.id)
        assert retrieved is None

    def test_delete_scan_not_found(self, db_session: Session):
        result = delete_scan(db_session, "non-existent-id")
        assert result is False

    def test_submit_feedback(self, db_session: Session):
        scan = create_scan(db_session, input_types=["text"], risk_score=50, risk_band="MODERATE", category=None, uncertainty={"level": "low", "reasons": []}, mode="rules")

        feedback = submit_feedback(db_session, scan.id, True, "Very helpful")
        assert feedback is not None
        assert feedback.helpful is True
        assert feedback.comment == "Very helpful"

    def test_submit_feedback_scan_not_found(self, db_session: Session):
        feedback = submit_feedback(db_session, "non-existent-id", True, "Test")
        assert feedback is None

    def test_cleanup_expired_scans(self, db_session: Session):
        scan = create_scan(db_session, input_types=["text"], risk_score=50, risk_band="MODERATE", category=None, uncertainty={"level": "low", "reasons": []}, mode="rules")
        scan.expires_at = utcnow() - timedelta(days=1)
        db_session.commit()

        scan2 = create_scan(db_session, input_types=["text"], risk_score=10, risk_band="LOW", category=None, uncertainty={"level": "low", "reasons": []}, mode="rules")

        deleted = cleanup_expired_scans(db_session)
        assert deleted == 1

        remaining = get_scan(db_session, scan.id)
        assert remaining is None

        remaining2 = get_scan(db_session, scan2.id)
        assert remaining2 is not None


class TestDatabaseInit:
    def test_init_db_creates_tables(self):
        init_db()
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "scans" in tables
        assert "evidence" in tables
        assert "feedback" in tables