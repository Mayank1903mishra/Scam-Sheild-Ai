"""TinyFish web-agent adapter: optional live URL assessment.

Sends only the submitted URL (never the user's message text) to the TinyFish
agent, which visits the page and reports scam indicators as structured JSON.
The key lives only in the environment (``TINYFISH_API_KEY``); when absent the
source reports "disabled" and no request is made.

Findings are ADVISORY (weight 0): an agent's page assessment is a second
opinion, never proof of fraud and never a confirmed threat-list match. Absence
of findings is not proof of safety.
"""
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.services.intel.base import (
    MATCH_ADVISORY,
    SOURCE_TINYFISH,
    CheckTuple,
    dedupe_findings,
    make_check,
    make_finding,
    utc_iso,
)

GOAL = (
    "Assess this webpage for scam or phishing indicators. Report whether it "
    "requests passwords/OTPs, upfront fees or unusual payments, impersonates "
    "a known brand, uses urgency pressure, or shows fake job/offer patterns. "
    "Return JSON with: verdict (one of scam, suspicious, legitimate, unclear) "
    "and reasons (a short list of concrete findings)."
)
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string"},
        "reasons": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["verdict", "reasons"],
}
SUSPICIOUS = {"scam", "suspicious", "phishing", "fraud", "likely_scam", "high_risk", "high risk"}


def build_payload(url: str) -> Dict[str, Any]:
    return {
        "url": url,
        "goal": GOAL,
        "output_schema": OUTPUT_SCHEMA,
        "agent_config": {"mode": "strict"},
    }


def _host(url: str) -> str:
    try:
        return urlparse(url).hostname or url
    except Exception:
        return url


def _parse_result(payload: Dict[str, Any]) -> tuple:
    """Return (verdict, reasons) from a TinyFish run response."""
    raw = payload.get("result")
    if isinstance(raw, str):
        import json

        try:
            raw = json.loads(raw)
        except ValueError:
            raw = {}
    if not isinstance(raw, dict):
        raw = {}

    verdict = str(
        raw.get("verdict") or raw.get("assessment") or raw.get("classification") or ""
    ).strip().lower()

    values = raw.get("reasons") or raw.get("signals") or raw.get("evidence") or []
    if isinstance(values, str):
        values = [values]
    reasons: List[str] = []
    for item in values if isinstance(values, list) else []:
        if isinstance(item, dict):
            text = item.get("reason") or item.get("detail") or item.get("description") or ""
        else:
            text = str(item)
        text = str(text).strip()[:240]
        if text:
            reasons.append(text)
    return verdict, reasons[:4]


def lookup(
    *,
    urls: Optional[List[str]] = None,
    client: Optional[httpx.Client] = None,
) -> CheckTuple:
    """Assess up to ``settings.tinyfish_max_urls`` URLs. Never raises."""
    checked_at = utc_iso()
    api_key = settings.tinyfish_api_key.strip()

    if not settings.tinyfish_enabled or not api_key:
        return [], make_check(
            SOURCE_TINYFISH,
            "disabled",
            checked_at=checked_at,
            detail="TINYFISH_API_KEY not configured or TINYFISH_ENABLED=false; no URLs were sent",
        )

    candidates = [
        u for u in dict.fromkeys(urls or [])
        if u.strip().lower().startswith(("http://", "https://"))
    ][: settings.tinyfish_max_urls]
    if not candidates:
        return [], make_check(
            SOURCE_TINYFISH,
            "skipped",
            checked_at=checked_at,
            detail="no URL in this submission to assess",
        )

    if client is None:
        client = httpx.Client(timeout=settings.tinyfish_timeout_seconds)
        owns_client = True
    else:
        owns_client = False

    try:
        response = client.post(
            settings.tinyfish_endpoint,
            json=build_payload(candidates[0]),
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        )
    except httpx.TimeoutException:
        return [], make_check(
            SOURCE_TINYFISH,
            "unavailable",
            checked_at=checked_at,
            detail="TinyFish request timed out; no assessment was returned",
        )
    except httpx.HTTPError as exc:
        return [], make_check(
            SOURCE_TINYFISH,
            "unavailable",
            checked_at=checked_at,
            detail=f"TinyFish network error ({(str(exc) or type(exc).__name__)[:120]})",
        )
    finally:
        if owns_client:
            client.close()

    if response.status_code != 200:
        try:
            body = response.json()
            message = str((body.get("error") or {}).get("message", ""))[:200]
        except (ValueError, AttributeError):
            message = ""
        return [], make_check(
            SOURCE_TINYFISH,
            "error",
            checked_at=checked_at,
            detail=f"TinyFish rejected the request: {message or f'HTTP {response.status_code}'}",
        )

    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    status = str(payload.get("status", "")).upper()
    if status and status != "COMPLETED":
        error = payload.get("error") or {}
        message = str(error.get("message") or "")[:200] or status
        return [], make_check(
            SOURCE_TINYFISH,
            "error",
            checked_at=checked_at,
            detail=f"TinyFish run {status}: {message}",
        )

    verdict, reasons = _parse_result(payload)
    if verdict in SUSPICIOUS:
        reason_text = "; ".join(reasons) if reasons else "the page showed scam-like indicators"
        finding = make_finding(
            indicator_id="TINYFISH_URL_ASSESSMENT",
            source=SOURCE_TINYFISH,
            reason=f"TinyFish web agent assessed this URL as {verdict}: {reason_text}",
            snippet=_host(candidates[0]),
            weight=0,
            match_type=MATCH_ADVISORY,
            retrieved_at=checked_at,
            explanation=(
                f"TinyFish visited {_host(candidates[0])} and reported '{verdict}': "
                f"{reason_text} (checked {checked_at}). This is an automated page "
                f"assessment (advisory, weight 0) - not proof of fraud; verify independently."
            ),
            reference_url=candidates[0],
        )
        findings = dedupe_findings([finding])
        detail = f"assessed {len(candidates)} URL(s): {verdict} reported"
    else:
        findings = []
        detail = (
            f"assessed {len(candidates)} URL(s): verdict '{verdict or 'unclear'}' - "
            "no scam indicators reported, which is not proof of safety"
        )

    return findings, make_check(
        SOURCE_TINYFISH,
        "checked",
        checked_at=checked_at,
        detail=detail,
    )
