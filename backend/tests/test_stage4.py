"""Stage 4 tests: false positives, uncertainty band, score boundaries,
evidence traceability, malformed input, conflicting signals."""
import pytest

from app.services.fusion import (
    RISK_BANDS,
    score_to_band,
    calculate_uncertainty,
    fuse_results,
)
from app.services.input_manager import analyze_input
from app.services.text_analyzer import analyze_text, TextAnalyzer
from app.services.explain import INDICATOR_EXPLANATIONS


class TestScoreBoundaries:
    @pytest.mark.parametrize(
        "score,expected",
        [
            (0, "LOW"),
            (15, "LOW"),
            (30, "LOW"),
            (31, "MODERATE"),
            (60, "MODERATE"),
            (61, "HIGH"),
            (80, "HIGH"),
            (81, "VERY_HIGH"),
            (100, "VERY_HIGH"),
        ],
    )
    def test_band_boundaries(self, score, expected):
        assert score_to_band(score) == expected

    def test_bands_are_contiguous(self):
        # Full coverage 0-100 with no gaps between bands
        for score in range(0, 101):
            band = score_to_band(score)
            assert band in ("LOW", "MODERATE", "HIGH", "VERY_HIGH", "UNCERTAIN")

    def test_band_thresholds_match_spec(self):
        assert RISK_BANDS["LOW"] == (0, 30)
        assert RISK_BANDS["MODERATE"] == (31, 60)
        assert RISK_BANDS["HIGH"] == (61, 80)
        assert RISK_BANDS["VERY_HIGH"] == (81, 100)


class TestFalsePositives:
    """Legitimate-but-urgent messages must not be labeled HIGH/VERY_HIGH."""

    def test_urgent_internship_followup_stays_low(self):
        text = (
            "Dear Student, this is urgent - we need your response by 5 PM today "
            "regarding your application for the Software Engineering internship at TechCorp. "
            "Please confirm your availability for a brief call tomorrow. "
            "Best regards, HR Team, hr@techcorp.com"
        )
        result = analyze_input(text=text)
        assert result.risk_band in ("LOW", "MODERATE")
        assert result.risk_score <= 60

    def test_legitimate_scholarship_award_is_low(self):
        text = (
            "Congratulations! You have been awarded the Merit Scholarship for "
            "Academic Year 2024-25. The amount of Rs. 50,000 will be credited "
            "directly to your university account. No action is required from your side. "
            "Regards, Scholarship Office, University Name"
        )
        result = analyze_input(text=text)
        assert result.risk_band == "LOW"
        assert result.risk_score <= 30

    def test_legitimate_deadline_notice_not_extreme(self):
        text = (
            "Reminder: Your internship application deadline is tomorrow. "
            "Submit your documents through the college placement portal before 11:59 PM. "
            "Placement Cell, University of Technology, placement@university.edu"
        )
        result = analyze_input(text=text)
        assert result.risk_band != "VERY_HIGH"
        assert result.risk_band != "HIGH"

    def test_benign_daily_message_is_low(self):
        text = (
            "Hi team, the standup meeting is moved to 3 PM. "
            "Please update your task board before the sprint review on Friday. "
            "Thanks, Project Manager"
        )
        result = analyze_input(text=text)
        assert result.risk_band == "LOW"
        assert result.risk_score <= 30


class TestUncertainBand:
    def test_empty_input_is_uncertain(self):
        result = analyze_input()
        assert result.risk_band == "UNCERTAIN"

    def test_whitespace_only_input_is_uncertain(self):
        result = analyze_input(text="   \n\t  ")
        assert result.risk_band == "UNCERTAIN"

    def test_very_short_input_is_uncertain(self):
        result = analyze_input(text="Hi")
        assert result.risk_band == "UNCERTAIN"

    def test_short_input_no_indicators_high_uncertainty(self):
        # Reasons must be consistent with the reported level (bug fixed in Stage 4)
        uncertainty = calculate_uncertainty(
            text_length=3,
            ocr_confidence=0.0,
            module_scores={"text": 0, "url": 0, "ocr_confidence": 0.0},
            indicators=[],
        )
        assert uncertainty["level"] == "high"
        assert "Very short input text" in uncertainty["reasons"]

    def test_adequate_benign_input_low_uncertainty(self):
        text = (
            "Thank you for your application. We have received your documents "
            "and will get back to you after the review process is complete."
        )
        result = analyze_input(text=text)
        assert result.uncertainty["level"] == "low"
        assert result.risk_band == "LOW"

    def test_low_ocr_confidence_raises_uncertainty(self):
        uncertainty = calculate_uncertainty(
            text_length=200,
            ocr_confidence=0.3,
            module_scores={"text": 10, "url": 0, "ocr_confidence": 0.3},
            indicators=[{"id": "URGENCY_LANGUAGE", "weight": 15}],
        )
        assert uncertainty["level"] in ("medium", "high")
        assert any("OCR confidence" in r for r in uncertainty["reasons"])


class TestConflictingSignals:
    def test_conflicting_module_scores_reported(self):
        uncertainty = calculate_uncertainty(
            text_length=300,
            ocr_confidence=0.0,
            module_scores={"text": 70, "url": 10, "ocr_confidence": 0.0},
            indicators=[{"id": "URGENCY_LANGUAGE", "weight": 15}],
        )
        assert uncertainty["level"] in ("medium", "high")
        assert any("Conflicting" in r for r in uncertainty["reasons"])

    def test_conflicting_signals_do_not_crash_fusion(self):
        text_result = {"indicators": [{"id": "URGENCY_LANGUAGE", "weight": 15,
                                       "reason": "Urgency", "snippet": "urgent"}],
                       "score": 15, "categories": {}}
        url_result = {"indicators": [{"id": "URL_SHORTENER", "weight": 15,
                                      "reason": "Shortener", "snippet": "bit.ly"}],
                      "score": 15, "features": []}
        fusion = fuse_results(text_result=text_result, url_result=url_result,
                              ocr_confidence=0.0, input_text="x" * 100)
        assert 0 <= fusion.risk_score <= 100
        assert fusion.risk_band in ("LOW", "MODERATE", "HIGH", "VERY_HIGH", "UNCERTAIN")


class TestEvidenceTraceability:
    def _full_scan(self):
        return analyze_input(
            text=(
                "Urgent! Guaranteed job offer with no interview! "
                "Earn $10000 per week. Pay registration fee of $200 before joining. "
                "Contact jobs@gmail.com or WhatsApp +1-555-123-4567"
            ),
            url="http://192.168.1.1/login?redirect=paypal.com",
        )

    def test_every_evidence_has_explanation(self):
        result = self._full_scan()
        assert len(result.evidence) > 0
        for item in result.evidence:
            assert item["id"] in INDICATOR_EXPLANATIONS, (
                f"Missing explanation for {item['id']}"
            )

    def test_every_evidence_has_required_fields(self):
        result = self._full_scan()
        for item in result.evidence:
            assert set(item.keys()) >= {"id", "source", "reason", "snippet", "weight"}
            assert item["source"] in ("text", "url", "ocr", "ml")
            assert isinstance(item["weight"], int)
            assert item["reason"]

    def test_every_text_evidence_maps_to_yaml_rule(self):
        analyzer = TextAnalyzer()
        yaml_ids = {ind.id for ind in analyzer.indicators}
        result = self._full_scan()
        for item in result.evidence:
            if item["source"] == "text":
                assert item["id"] in yaml_ids, (
                    f"Evidence {item['id']} not traceable to indicators.yaml"
                )

    def test_new_indicators_have_explanations(self):
        assert "FAKE_JOB" in INDICATOR_EXPLANATIONS
        assert "FAKE_PLACEMENT" in INDICATOR_EXPLANATIONS

class TestStoragePrivacy:
    @pytest.mark.asyncio
    async def test_stored_snippets_mask_pii_before_storage(self, async_client):
        """Spec section 8: PII masked before storage - stored evidence must
        never contain raw phone numbers or emails."""
        text = (
            "Urgent! WhatsApp me at +91 98765 43210 or mail job@gmail.com "
            "to pay the registration fee immediately."
        )
        response = await async_client.post("/api/v1/scans", json={"text": text})
        assert response.status_code == 201
        scan_id = response.json()["id"]

        stored = await async_client.get(f"/api/v1/scans/{scan_id}")
        assert stored.status_code == 200
        body = stored.json()

        for item in body["evidence"]:
            assert "98765 43210" not in item["snippet"]
            assert "9876543210" not in item["snippet"]
            assert "job@gmail.com" not in item["snippet"]

    @pytest.mark.asyncio
    async def test_immediate_response_contains_highlight_snippets(self, async_client):
        """Response echoes matched snippets for highlighting user's own content."""
        text = "Pay the registration fee now, urgent!"
        response = await async_client.post("/api/v1/scans", json={"text": text})
        assert response.status_code == 201
        body = response.json()
        assert len(body["evidence"]) > 0
        assert any("fee" in item["snippet"] for item in body["evidence"])


class TestNewIndicators:
    def test_fake_job_triggers(self):
        result = analyze_input(
            text="No interview needed. Pay the joining fee of $500 to confirm your job."
        )
        assert any(e["id"] == "FAKE_JOB" for e in result.evidence)

    def test_fake_placement_triggers(self):
        result = analyze_input(
            text="Mass recruitment drive! Pay the placement fee of Rs. 1000 to participate."
        )
        assert any(e["id"] == "FAKE_PLACEMENT" for e in result.evidence)

    def test_fake_job_text_analyzer(self):
        result = analyze_text("No interview needed, payment before joining required.")
        assert any(i["id"] == "FAKE_JOB" for i in result["indicators"])


class TestMalformedInput:
    def test_no_input_no_exception(self):
        result = analyze_input()
        assert 0 <= result.risk_score <= 100
        assert result.risk_band in ("LOW", "MODERATE", "HIGH", "VERY_HIGH", "UNCERTAIN")

    def test_invalid_url_no_exception(self):
        result = analyze_input(url="not a url at all")
        assert 0 <= result.risk_score <= 100

    def test_empty_url_no_exception(self):
        result = analyze_input(url="   ")
        assert 0 <= result.risk_score <= 100

    def test_control_characters_no_exception(self):
        result = analyze_input(text=" \x00\x01\x02 urgent \x03")
        assert 0 <= result.risk_score <= 100

    def test_score_always_bounded(self):
        spammy = "urgent fee deposit " * 50
        result = analyze_input(text=spammy)
        assert 0 <= result.risk_score <= 100

    def test_recommendations_present_for_any_band(self):
        result = analyze_input(text="Hi")
        assert len(result.recommendations) > 0
        assert result.disclaimer
        assert result.summary
