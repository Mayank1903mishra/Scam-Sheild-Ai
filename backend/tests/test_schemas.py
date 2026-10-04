import pytest
from app.schemas.request import ScanTextRequest, ScanUploadRequest, FeedbackRequest
from app.schemas.response import (
    ScanResponse,
    ScanListItem,
    HealthResponse,
    FeedbackResponse,
    EvidenceItem,
    ExtractedData,
    UncertaintyInfo,
    ModuleScores,
)
from uuid import uuid4
from datetime import datetime


class TestScanTextRequest:
    def test_valid_text_only(self):
        req = ScanTextRequest(text="Hello world")
        assert req.text == "Hello world"
        assert req.url is None
        assert req.has_input() is True

    def test_valid_url_only(self):
        req = ScanTextRequest(url="https://example.com")
        assert req.text is None
        assert req.url == "https://example.com"
        assert req.has_input() is True

    def test_valid_both(self):
        req = ScanTextRequest(text="Check this", url="https://example.com")
        assert req.has_input() is True

    def test_empty_text_becomes_none(self):
        req = ScanTextRequest(text="   ")
        assert req.text is None
        assert req.has_input() is False

    def test_empty_url_becomes_none(self):
        req = ScanTextRequest(url="   ")
        assert req.url is None
        assert req.has_input() is False

    def test_both_empty_raises_validation_error(self):
        with pytest.raises(ValueError):
            ScanTextRequest(text="", url="")

    def test_whitespace_only_becomes_none(self):
        req = ScanTextRequest(text="   ", url="  ")
        assert req.text is None
        assert req.url is None
        assert req.has_input() is False

    def test_text_too_long(self):
        with pytest.raises(ValueError):
            ScanTextRequest(text="x" * 10001)

    def test_url_too_long(self):
        with pytest.raises(ValueError):
            ScanTextRequest(url="x" * 2049)


class TestFeedbackRequest:
    def test_valid(self):
        req = FeedbackRequest(helpful=True, comment="Great!")
        assert req.helpful is True
        assert req.comment == "Great!"

    def test_comment_too_long(self):
        with pytest.raises(ValueError):
            FeedbackRequest(helpful=True, comment="x" * 1001)


class TestResponseSchemas:
    def test_health_response(self):
        resp = HealthResponse(status="ok", mode="rules")
        assert resp.status == "ok"
        assert resp.mode == "rules"

    def test_evidence_item(self):
        item = EvidenceItem(
            id="UPFRONT_PAYMENT",
            source="text",
            reason="Requests payment before starting",
            snippet="pay $50 to secure",
            weight=25,
        )
        assert item.id == "UPFRONT_PAYMENT"
        assert item.weight == 25

    def test_scan_response_minimal(self):
        resp = ScanResponse(
            id=uuid4(),
            created_at=datetime.now(),
            input_types=["text"],
            risk_score=10,
            risk_band="LOW",
            score_note="Heuristic score, not a probability; thresholds provisional.",
            uncertainty=UncertaintyInfo(level="low", reasons=[]),
            modules=ModuleScores(),
            extracted=ExtractedData(),
            recommendations=["Verify independently"],
            disclaimer="Risk indicators are not proof of fraud.",
            mode="rules",
        )
        assert resp.risk_score == 10
        assert resp.risk_band == "LOW"