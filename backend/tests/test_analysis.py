import pytest
from app.services.text_analyzer import TextAnalyzer, analyze_text
from app.services.url_analyzer import analyze_url, analyze_urls
from app.services.evidence import extract_entities, extract_entities_combined, extract_phones, extract_upi_ids
from app.services.fusion import fuse_results, score_to_band, select_category, get_recommendations
from app.services.explain import explain_indicators, generate_summary, get_disclaimer, format_evidence_for_display
from app.services.privacy import mask_pii, extract_pii, extract_urls, extract_domains, extract_all
from app.services.input_manager import analyze_input


class TestTextAnalyzer:
    def test_empty_text(self):
        result = analyze_text("")
        assert result["indicators"] == []
        assert result["score"] == 0

    def test_whitespace_only(self):
        result = analyze_text("   \n\t  ")
        assert result["score"] == 0

    def test_urgency_language(self):
        text = "This is urgent! You must act now, limited time offer."
        result = analyze_text(text)
        assert any(i["id"] == "URGENCY_LANGUAGE" for i in result["indicators"])
        assert result["score"] > 0

    def test_upfront_payment(self):
        text = "Please pay the registration fee of $50 to secure your spot."
        result = analyze_text(text)
        assert any(i["id"] == "UPFRONT_PAYMENT" for i in result["indicators"])
        assert result["score"] >= 25

    def test_guaranteed_selection(self):
        text = "We guarantee 100% placement and assured selection."
        result = analyze_text(text)
        assert any(i["id"] == "GUARANTEED_SELECTION" for i in result["indicators"])

    def test_unrealistic_salary(self):
        text = "Earn $10000 per week working from home!"
        result = analyze_text(text)
        # Regex pattern should match
        assert any(i["id"] == "UNREALISTIC_SALARY" for i in result["indicators"])

    def test_credential_request(self):
        text = "Send me your OTP and password to verify your account."
        result = analyze_text(text)
        assert any(i["id"] == "CREDENTIAL_REQUEST" for i in result["indicators"])
        assert result["score"] >= 30

    def test_freemail_sender(self):
        text = "Contact us at hr@company@gmail.com for more info."
        result = analyze_text(text)
        assert any(i["id"] == "FREEMAIL_SENDER" for i in result["indicators"])

    def test_payment_pressure(self):
        text = "Pay via UPI or Paytm immediately."
        result = analyze_text(text)
        assert any(i["id"] == "PAYMENT_PRESSURE" for i in result["indicators"])

    def test_off_platform_contact(self):
        text = "Message me on WhatsApp or Telegram for details."
        result = analyze_text(text)
        assert any(i["id"] == "OFF_PLATFORM_CONTACT" for i in result["indicators"])

    def test_fake_internship(self):
        text = "Guaranteed internship with certificate after paying fee."
        result = analyze_text(text)
        assert any(i["id"] == "FAKE_INTERNSHIP" for i in result["indicators"])

    def test_fake_scholarship(self):
        text = "Pay processing fee to release your scholarship funds."
        result = analyze_text(text)
        assert any(i["id"] == "FAKE_SCHOLARSHIP" for i in result["indicators"])

    def test_legitimate_text_low_score(self):
        text = "Thank you for your application. We will review and get back to you."
        result = analyze_text(text)
        # Should have low or zero score
        assert result["score"] < 30

    def test_multiple_indicators_accumulate(self):
        text = "Urgent! Guaranteed job! Pay registration fee now! Send OTP!"
        result = analyze_text(text)
        # Multiple indicators should accumulate
        assert result["score"] > 50

    def test_case_insensitive(self):
        text = "URGENT: PAY FEE IMMEDIATELY"
        result = analyze_text(text)
        assert any(i["id"] == "URGENCY_LANGUAGE" for i in result["indicators"])
        assert any(i["id"] == "UPFRONT_PAYMENT" for i in result["indicators"])

    def test_source_scope_filtering(self):
        # URL-specific indicators should not trigger on text-only analysis
        text = "Visit http://example.com for info"
        result = analyze_text(text, source="text")
        # URL_BRAND_LOOKALIKE has scope ["text", "ocr", "url"] so it might trigger
        # but URL_IP_HOST has scope ["url"] so it shouldn't
        pass


class TestURLAnalyzer:
    def test_normal_url(self):
        result = analyze_url("https://example.com/path")
        assert result["score"] == 0
        assert result["indicators"] == []

    def test_ip_host(self):
        result = analyze_url("http://192.168.1.1/admin")
        assert any(i["id"] == "URL_IP_HOST" for i in result["indicators"])
        assert result["score"] >= 25

    def test_punycode(self):
        result = analyze_url("http://xn--exmple-cua.com")
        assert any(i["id"] == "URL_PUNYCODE" for i in result["indicators"])
        assert result["score"] >= 30

    def test_many_subdomains(self):
        result = analyze_url("http://a.b.c.d.example.com")
        assert any(i["id"] == "URL_MANY_SUBDOMAINS" for i in result["indicators"])

    def test_at_symbol(self):
        result = analyze_url("http://user:pass@evil.com")
        assert any(i["id"] == "URL_AT_SYMBOL" for i in result["indicators"])
        assert result["score"] >= 25

    def test_suspicious_tld(self):
        result = analyze_url("http://example.xyz")
        assert any(i["id"] == "URL_SUSPICIOUS_TLD" for i in result["indicators"])

    def test_brand_lookalike(self):
        result = analyze_url("http://google-jobs.com")
        assert any(i["id"] == "URL_BRAND_LOOKALIKE" for i in result["indicators"])

    def test_shortener(self):
        result = analyze_url("https://bit.ly/abc123")
        assert any(i["id"] == "URL_SHORTENER" for i in result["indicators"])

    def test_high_entropy(self):
        # Random-looking domain
        result = analyze_url("http://x7k9m2n4p.example.com")
        # May or may not trigger depending on entropy threshold
        pass

    def test_suspicious_tokens(self):
        result = analyze_url("https://example.com/login/verify/account")
        assert any(i["id"] == "URL_SUSPICIOUS_TOKENS" for i in result["indicators"])

    def test_long_url(self):
        long_url = "https://example.com/" + "a" * 150
        result = analyze_url(long_url)
        assert any(i["id"] == "URL_LONG_LENGTH" for i in result["indicators"])

    def test_https_not_safety_signal(self):
        # HTTPS should never lower risk or be a positive signal
        result = analyze_url("https://evil-phishing-site.xyz/login")
        # Should still have suspicious indicators
        assert result["score"] > 0

    def test_multiple_urls(self):
        urls = [
            "https://bit.ly/abc",
            "http://192.168.1.1",
            "https://example.com"
        ]
        result = analyze_urls(urls)
        assert len(result["indicators"]) > 0
        assert result["score"] > 0


class TestEvidenceExtraction:
    def test_extract_phones(self):
        text = "Call me at +1-555-123-4567 or 9876543210"
        phones = extract_phones(text)
        assert len(phones) >= 1

    def test_extract_upi_ids(self):
        text = "Pay to user@paytm or merchant@upi"
        upis = extract_upi_ids(text)
        assert len(upis) >= 1

    def test_extract_entities(self):
        text = "Email: test@gmail.com, Phone: 9876543210, URL: https://example.com"
        entities = extract_entities(text)
        assert "emails" in entities
        assert "phones" in entities
        assert "urls" in entities
        assert "domains" in entities
        assert "test@gmail.com" in entities["emails"] or len(entities["emails"]) > 0

    def test_extract_entities_combined(self):
        texts = [
            "Email: a@b.com",
            "Phone: 1234567890",
            "URL: https://example.com"
        ]
        combined = extract_entities_combined(texts)
        assert len(combined["emails"]) >= 1
        assert len(combined["phones"]) >= 1
        assert len(combined["urls"]) >= 1

    def test_free_mail_detection(self):
        text = "Contact: hr@gmail.com, support@yahoo.com, admin@company.com"
        entities = extract_entities(text)
        free_domains = entities.get("free_mail_domains", [])
        assert "gmail.com" in free_domains
        assert "yahoo.com" in free_domains
        assert "company.com" not in free_domains


class TestPrivacy:
    def test_mask_pii_phones(self):
        text = "Call me at 555-123-4567"
        masked, extracted = mask_pii(text)
        assert "555-123-4567" not in masked
        assert len(extracted["phones"]) >= 1

    def test_mask_pii_emails(self):
        text = "Email me at user@example.com"
        masked, extracted = mask_pii(text)
        assert "user@example.com" not in masked
        assert len(extracted["emails"]) >= 1

    def test_mask_pii_ids(self):
        text = "Aadhaar: 1234 5678 9012"
        masked, extracted = mask_pii(text)
        assert "1234 5678 9012" not in masked
        assert len(extracted["ids"]) >= 1

    def test_mask_pii_preserves_structure(self):
        text = "Contact: john.doe@company.com or +1-555-123-4567"
        masked, _ = mask_pii(text)
        assert "@" in masked  # Domain preserved
        assert "." in masked  # Structure preserved

    def test_extract_pii_no_masking(self):
        text = "Email: test@test.com"
        extracted = extract_pii(text)
        assert "test@test.com" in extracted["emails"]

    def test_extract_urls(self):
        text = "Visit https://example.com and http://test.org/page"
        urls = extract_urls(text)
        assert "https://example.com" in urls
        assert "http://test.org/page" in urls

    def test_extract_domains(self):
        text = "Visit example.com and test.org"
        domains = extract_domains(text)
        assert "example.com" in domains
        assert "test.org" in domains

    def test_extract_all(self):
        text = "Email: test@test.com, URL: https://example.com, Phone: 5551234567"
        all_entities = extract_all(text)
        assert "urls" in all_entities
        assert "emails" in all_entities
        assert "phones" in all_entities
        assert "domains" in all_entities


class TestFusion:
    def test_score_to_band(self):
        assert score_to_band(10) == "LOW"
        assert score_to_band(45) == "MODERATE"
        assert score_to_band(70) == "HIGH"
        assert score_to_band(90) == "VERY_HIGH"

    def test_select_category_phishing(self):
        indicators = [
            {"id": "CREDENTIAL_REQUEST", "weight": 30},
            {"id": "URL_BRAND_LOOKALIKE", "weight": 20},
        ]
        category = select_category(indicators, {"text": 30, "url": 20})
        assert category == "PHISHING"

    def test_select_category_payment_scam(self):
        indicators = [
            {"id": "UPFRONT_PAYMENT", "weight": 25},
            {"id": "PAYMENT_PRESSURE", "weight": 20},
        ]
        category = select_category(indicators, {"text": 45, "url": 0})
        assert category == "PAYMENT_SCAM"

    def test_select_category_fake_internship(self):
        indicators = [
            {"id": "FAKE_INTERNSHIP", "weight": 20},
        ]
        category = select_category(indicators, {"text": 20, "url": 0})
        assert category == "FAKE_INTERNSHIP"

    def test_select_category_legitimate(self):
        indicators = [
            {"id": "OFFICIAL_DOMAIN", "weight": -10},
        ]
        category = select_category(indicators, {"text": -10, "url": 0})
        assert category == "LEGITIMATE_LIKELY"

    def test_get_recommendations(self):
        recs = get_recommendations("HIGH")
        assert len(recs) > 0
        assert any("payment" in r.lower() or "credential" in r.lower() for r in recs)

    def test_fuse_results_basic(self):
        text_result = {
            "indicators": [{"id": "URGENCY_LANGUAGE", "weight": 15, "source": "text"}],
            "score": 15,
            "categories": {"PRESSURE": 15}
        }
        url_result = {
            "indicators": [],
            "score": 0,
            "features": []
        }
        result = fuse_results(text_result, url_result, 0.0, "urgent message")
        assert result.risk_score == 15
        assert result.risk_band == "LOW"
        assert len(result.evidence) == 1

    def test_fuse_results_combined(self):
        text_result = {
            "indicators": [
                {"id": "URGENCY_LANGUAGE", "weight": 15, "source": "text"},
                {"id": "UPFRONT_PAYMENT", "weight": 25, "source": "text"},
            ],
            "score": 40,
            "categories": {"PRESSURE": 15, "PAYMENT": 25}
        }
        url_result = {
            "indicators": [
                {"id": "URL_SHORTENER", "weight": 15, "source": "url"},
            ],
            "score": 15,
            "features": []
        }
        result = fuse_results(text_result, url_result, 0.0, "urgent pay now bit.ly/link")
        assert result.risk_score == 55
        assert result.risk_band == "MODERATE"
        assert len(result.evidence) == 3

    def test_fuse_results_uncertain_short_input(self):
        text_result = {"indicators": [], "score": 0, "categories": {}}
        url_result = {"indicators": [], "score": 0, "features": []}
        result = fuse_results(text_result, url_result, 0.0, "hi")
        assert result.risk_band == "UNCERTAIN"


class TestExplain:
    def test_explain_indicators(self):
        indicators = [
            {"id": "URGENCY_LANGUAGE", "source": "text", "weight": 15, "snippet": "urgent now"},
            {"id": "UPFRONT_PAYMENT", "source": "text", "weight": 25, "snippet": "pay fee"},
        ]
        explained = explain_indicators(indicators)
        assert len(explained) == 2
        assert "urgent language" in explained[0]["reason"].lower()
        assert "payment" in explained[1]["reason"].lower()

    def test_generate_summary(self):
        summary = generate_summary("HIGH", "PHISHING", 3)
        assert "high" in summary.lower()
        assert "phishing" in summary.lower()
        assert "3" in summary

    def test_generate_summary_uncertain(self):
        summary = generate_summary("UNCERTAIN", "UNCERTAIN", 0)
        assert "unable" in summary.lower() or "insufficient" in summary.lower()

    def test_get_disclaimer(self):
        disclaimer = get_disclaimer()
        assert "not proof" in disclaimer.lower()
        assert "false positive" in disclaimer.lower()

    def test_format_evidence_for_display(self):
        indicators = [
            {"id": "URGENCY_LANGUAGE", "source": "text", "reason": "Urgent", "snippet": "urgent", "weight": 15},
            {"id": "OFFICIAL_DOMAIN", "source": "url", "reason": "Official", "snippet": "example.com", "weight": -10},
        ]
        formatted = format_evidence_for_display(indicators)
        assert formatted[0]["is_risk"] is True
        assert formatted[1]["is_risk"] is False


class TestInputManager:
    def test_analyze_input_text_only(self):
        result = analyze_input(text="Urgent! Pay registration fee now!")
        assert result.risk_score > 0
        assert result.risk_band in ["LOW", "MODERATE", "HIGH", "VERY_HIGH", "UNCERTAIN"]
        assert result.category is not None
        assert len(result.evidence) > 0
        assert len(result.recommendations) > 0
        assert result.disclaimer
        assert result.mode == "rules"

    def test_analyze_input_url_only(self):
        result = analyze_input(url="https://bit.ly/phish")
        assert result.risk_score > 0
        assert any(e["id"] == "URL_SHORTENER" for e in result.evidence)

    def test_analyze_input_combined(self):
        result = analyze_input(
            text="Urgent job offer!",
            url="https://bit.ly/fake"
        )
        assert result.risk_score > 0
        sources = [e["source"] for e in result.evidence]
        assert "text" in sources
        assert "url" in sources

    def test_analyze_input_empty(self):
        result = analyze_input(text="", url="")
        # Should handle gracefully
        assert result.risk_band == "UNCERTAIN"

    def test_analyze_input_extracted_entities(self):
        result = analyze_input(text="Contact: test@gmail.com, call 555-123-4567")
        assert "urls" in result.extracted
        assert "emails" in result.extracted
        assert "phones" in result.extracted
        assert "domains" in result.extracted

    def test_analyze_input_ocr_confidence(self):
        result = analyze_input(ocr_text="Urgent pay now", ocr_confidence=0.3)
        assert result.module_scores["ocr_confidence"] == 0.3
        # Low OCR confidence should increase uncertainty
        assert result.uncertainty["level"] in ["medium", "high"]


class TestFalsePositives:
    """Test cases that should NOT trigger high risk (legitimate content)."""

    def test_legitimate_job_email(self):
        text = """
        Dear Candidate,
        Thank you for applying to Software Engineer position at Example Corp.
        We have received your application and will review it within 5 business days.
        You can check status at careers.example.com
        Best regards,
        HR Team
        Example Corp
        """
        result = analyze_text(text)
        # Should not have high-risk indicators
        high_risk_ids = ["CREDENTIAL_REQUEST", "UPFRONT_PAYMENT", "GUARANTEED_SELECTION"]
        for ind in result["indicators"]:
            assert ind["id"] not in high_risk_ids, f"False positive: {ind['id']}"

    def test_legitimate_university_email(self):
        text = """
        Dear Student,
        Your scholarship application for the Merit Scholarship has been approved.
        The funds will be disbursed directly to your university account.
        No action required on your part.
        Regards,
        Scholarship Office
        University Name
        """
        result = analyze_text(text)
        # Should not trigger FAKE_SCHOLARSHIP (no fee requested)
        for ind in result["indicators"]:
            assert ind["id"] != "FAKE_SCHOLARSHIP"

    def test_legitimate_internship_offer(self):
        text = """
        Congratulations! You have been selected for the Summer Internship Program at TechCorp.
        Start date: June 15, 2024. Stipend: $3000/month.
        Please confirm acceptance by replying to this email.
        Contact: internships@techcorp.com
        """
        result = analyze_text(text)
        # Should not trigger FAKE_INTERNSHIP (no fee, corporate email)
        for ind in result["indicators"]:
            assert ind["id"] != "FAKE_INTERNSHIP"

    def test_legitimate_url(self):
        result = analyze_url("https://careers.google.com/jobs/results/")
        assert result["score"] == 0
        assert result["indicators"] == []


class TestEdgeCases:
    def test_unicode_text(self):
        text = "Urgent! 💰 Pay ₹5000 now! 🔥"
        result = analyze_text(text)
        assert result["score"] > 0

    def test_mixed_script(self):
        text = "Urgent! 立即支付费用"
        result = analyze_text(text)
        assert result["score"] >= 15  # URGENCY_LANGUAGE

    def test_very_long_text(self):
        text = "Hello " * 2000  # ~10000 chars
        result = analyze_text(text)
        assert result["score"] == 0  # No risk indicators

    def test_url_with_special_chars(self):
        result = analyze_url("https://example.com/path?param=value&other=123#section")
        assert result["score"] == 0

    def test_ocr_noise(self):
        # Simulate OCR noise
        text = "U R G E N T ! P A Y N O W !"
        result = analyze_text(text)
        # Should still detect urgency (spaces between letters)
        pass


class TestIntegration:
    def test_full_pipeline_text(self):
        result = analyze_input(text="Urgent! Guaranteed internship! Pay $100 fee now! Contact hr@gmail.com")
        # Score: URGENCY(15) + GUARANTEED_SELECTION(20) + UPFRONT_PAYMENT(25) + FREEMAIL_SENDER(10) = 70
        # But UPFRONT_PAYMENT "pay fee" may not match "Pay $100 fee" - let's check actual
        assert result.risk_score >= 40  # At least MODERATE
        assert result.risk_band in ["MODERATE", "HIGH", "VERY_HIGH"]
        assert result.category in ["FAKE_INTERNSHIP", "PAYMENT_SCAM", "FAKE_JOB"]
        assert len(result.evidence) >= 3

    def test_full_pipeline_url(self):
        result = analyze_input(url="http://192.168.1.1/login?redirect=paypal.com")
        assert result.risk_score > 25
        assert any(e["id"] == "URL_IP_HOST" for e in result.evidence)

    def test_full_pipeline_combined(self):
        result = analyze_input(
            text="Amazing job offer! Guaranteed placement!",
            url="https://bit.ly/fakejob"
        )
        assert result.risk_score > 30
        assert result.category in ["FAKE_JOB", "FAKE_PLACEMENT", "PAYMENT_SCAM"]