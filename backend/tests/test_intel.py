"""External intelligence layer (I4C advisories + Google Safe Browsing).

No test here touches the network: adapters get stubbed transports or pages,
and the autouse conftest fixture keeps lookups disabled unless a test
explicitly opts back in.
"""
import httpx
import pytest

from app.config import settings
from app.services.explain import explain_indicators
from app.services.intel import IntelOutcome, i4c, run_intel_lookups, safebrowsing
from app.services.intel import base as intel_base


ADVISORY_HTML = """
<div class="advisory">
  <a href="/Webform/PDF/fake-job-advisory.pdf" target="_blank">
    <h3>Fake job offer fraud</h3>
  </a>
  <p class="title">01/10/2026</p>
  <p class="summary-text">Fake job offers that demand an upfront payment.</p>
</div>
"""


class StubResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


class StubClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.closed = False
        self.urls = []

    def post(self, url, json=None):
        self.urls.append(url)
        if self.error is not None:
            raise self.error
        return self.response

    def close(self):
        self.closed = True


def _advisory_finding():
    return intel_base.make_finding(
        indicator_id="I4C_ADVISORY",
        source=intel_base.SOURCE_I4C,
        reason="I4C advisory: Fake job offer fraud",
        snippet="Fake job offer fraud (01/10/2026)",
        weight=0,
        match_type=intel_base.MATCH_ADVISORY,
        explanation="Official I4C advisory describes a similar fraud pattern.",
        reference_url="https://cybercrime.gov.in/pdf.pdf",
    )


class TestRunIntelLookups:
    def test_disabled_reports_both_sources_without_calling_adapters(self, monkeypatch):
        def explode(**kwargs):  # pragma: no cover - failure would be a bug
            raise AssertionError("adapter must not run when lookups are disabled")

        monkeypatch.setattr(i4c, "lookup", explode)
        monkeypatch.setattr(safebrowsing, "lookup", explode)

        outcome = run_intel_lookups(text="anything", urls=["http://example.com"])

        assert outcome.findings == []
        assert [check["source"] for check in outcome.checks] == ["i4c", "safebrowsing"]
        assert {check["status"] for check in outcome.checks} == {"disabled"}

    def test_enabled_runs_both_adapters_and_recounts_evidence(self, monkeypatch):
        monkeypatch.setattr(settings, "intel_lookups_enabled", True)
        monkeypatch.setattr(
            i4c,
            "lookup",
            lambda **kwargs: (
                [_advisory_finding()],
                intel_base.make_check("i4c", "checked", detail="checked 1 advisories"),
            ),
        )
        monkeypatch.setattr(
            safebrowsing,
            "lookup",
            lambda **kwargs: (
                [],
                intel_base.make_check("safebrowsing", "disabled", detail="no key"),
            ),
        )

        outcome = run_intel_lookups(text="fake job offer")

        assert len(outcome.findings) == 1
        by_source = {check["source"]: check for check in outcome.checks}
        assert by_source["i4c"]["status"] == "checked"
        assert by_source["i4c"]["evidence_count"] == 1
        assert by_source["safebrowsing"]["evidence_count"] == 0

    def test_adapter_exception_becomes_a_failed_check(self, monkeypatch):
        monkeypatch.setattr(settings, "intel_lookups_enabled", True)

        def boom(**kwargs):
            raise RuntimeError("portal down")

        monkeypatch.setattr(i4c, "lookup", boom)
        monkeypatch.setattr(safebrowsing, "lookup", boom)

        outcome = run_intel_lookups(text="hello")

        assert outcome.findings == []
        assert {check["status"] for check in outcome.checks} == {"error"}
        assert all("portal down" in check["detail"] for check in outcome.checks)


class TestI4CAdapter:
    def test_matches_advisory_by_topic_with_weight_zero(self, monkeypatch):
        monkeypatch.setattr(settings, "intel_lookups_enabled", True)
        monkeypatch.setattr(
            i4c,
            "_cached_fetch",
            lambda url, client: ADVISORY_HTML if "Advisory" in url else "",
        )

        findings, check = i4c.lookup(text="fake job offer asking for payment")

        assert check["status"] == "checked"
        assert len(findings) == 1
        assert findings[0]["id"] == "I4C_ADVISORY"
        assert findings[0]["weight"] == 0
        assert findings[0]["match_type"] == "advisory"
        assert findings[0]["source"] == "i4c"
        assert "Reference:" in findings[0]["explanation"]

    def test_unreachable_portal_fails_open(self, monkeypatch):
        monkeypatch.setattr(i4c, "_cached_fetch", lambda url, client: None)

        findings, check = i4c.lookup(text="fake job offer")

        assert findings == []
        assert check["status"] == "unavailable"
        assert "could not be reached" in check["detail"]

    def test_page_reached_but_unparseable_reports_error_not_silence(self, monkeypatch):
        monkeypatch.setattr(i4c, "_cached_fetch", lambda url, client: "<html></html>")

        findings, check = i4c.lookup(text="fake job offer")

        assert findings == []
        assert check["status"] == "error"

    def test_topic_extraction_from_indicators_and_text(self):
        topics = i4c.topics_for(["CREDENTIAL_REQUEST"], "send the otp now")
        assert "otp" in topics
        assert "password" in topics


class TestSafeBrowsingAdapter:
    def test_missing_api_key_reports_disabled_without_request(self):
        findings, check = safebrowsing.lookup(urls=["http://example.com"])

        assert findings == []
        assert check["status"] == "disabled"
        assert "not configured" in check["detail"]

    def test_confirmed_match_carries_weight_and_match_type(self, monkeypatch):
        monkeypatch.setattr(settings, "google_safe_browsing_api_key", "test-key")
        client = StubClient(
            StubResponse(
                200,
                {
                    "matches": [
                        {
                            "threatType": "SOCIAL_ENGINEERING",
                            "threatEntries": [{"url": "http://bad.example/x"}],
                        }
                    ]
                },
            )
        )

        findings, check = safebrowsing.lookup(
            urls=["http://bad.example/x"], client=client
        )

        assert check["status"] == "checked"
        assert len(findings) == 1
        assert findings[0]["id"] == "SB_URL_MATCH"
        assert findings[0]["weight"] == safebrowsing.MATCH_WEIGHT
        assert findings[0]["match_type"] == "confirmed"
        assert client.urls and client.urls[0].startswith(safebrowsing.ENDPOINT)

    def test_no_match_is_never_reported_as_proof_of_safety(self, monkeypatch):
        monkeypatch.setattr(settings, "google_safe_browsing_api_key", "test-key")
        client = StubClient(StubResponse(200, {}))

        findings, check = safebrowsing.lookup(
            urls=["http://fine.example/"], client=client
        )

        assert findings == []
        assert check["status"] == "checked"
        assert "not proof of safety" in check["detail"]

    def test_network_error_fails_open(self, monkeypatch):
        monkeypatch.setattr(settings, "google_safe_browsing_api_key", "test-key")
        client = StubClient(error=httpx.ConnectError("no route to host"))

        findings, check = safebrowsing.lookup(urls=["http://x.example/"], client=client)

        assert findings == []
        assert check["status"] == "unavailable"


class TestIntelInAnalysisPipeline:
    def test_explain_keeps_source_specific_explanation(self):
        explained = explain_indicators([_advisory_finding()])

        assert explained[0]["source"] == "i4c"
        assert explained[0]["reason"] == (
            "Official I4C advisory describes a similar fraud pattern."
        )
        assert explained[0]["match_type"] == "advisory"

    @pytest.mark.asyncio
    async def test_scan_reports_sources_when_lookups_disabled(
        self, async_client, monkeypatch
    ):
        response = await async_client.post(
            "/api/v1/scans", json={"text": "please send the otp to confirm your account"}
        )

        assert response.status_code == 201
        scan = response.json()
        assert [source["source"] for source in scan["sources"]] == [
            "i4c",
            "safebrowsing",
        ]
        assert {source["status"] for source in scan["sources"]} == {"disabled"}
        assert all(item["source"] != "intel" for item in scan["evidence"])

    @pytest.mark.asyncio
    async def test_intel_finding_joins_evidence_and_keeps_score_invariant(
        self, async_client, monkeypatch
    ):
        monkeypatch.setattr(settings, "intel_lookups_enabled", True)
        findings = [_advisory_finding()]
        checks = intel_base.recount_checks(
            [
                intel_base.make_check("i4c", "checked", detail="checked 1 advisories"),
                intel_base.make_check("safebrowsing", "disabled", detail="no key"),
            ],
            findings,
        )
        monkeypatch.setattr(
            "app.services.input_manager.run_intel_lookups",
            lambda **kwargs: IntelOutcome(findings, checks),
        )

        response = await async_client.post(
            "/api/v1/scans",
            json={"text": "guaranteed job offer, pay the training fee today"},
        )

        assert response.status_code == 201
        scan = response.json()

        intel_items = [item for item in scan["evidence"] if item["source"] == "intel"]
        assert len(intel_items) == 1
        assert intel_items[0]["id"] == "I4C_ADVISORY"
        # Advisory findings are weight 0, so the documented score invariant
        # (score == bounded sum of evidence weights) still holds.
        weight_sum = sum(item["weight"] for item in scan["evidence"])
        assert scan["risk_score"] == min(100, max(0, weight_sum))

        checks = {source["source"]: source for source in scan["sources"]}
        assert checks["i4c"]["status"] == "checked"
        assert checks["i4c"]["evidence_count"] == 1

        # Source checks are reported on creation only, not on history reads.
        detail = await async_client.get(f"/api/v1/scans/{scan['id']}")
        assert detail.status_code == 200
        assert detail.json()["sources"] == []
        assert {e["source"] for e in detail.json()["evidence"]} == set(
            e["source"] for e in scan["evidence"]
        )
