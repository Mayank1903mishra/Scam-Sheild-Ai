"""Google Safe Browsing Lookup API v4 adapter.

Documented endpoint (verified against Google's public reference docs):
    POST https://safebrowsing.googleapis.com/v4/threatMatches:find?key=API_KEY

A server-side API key is read from the environment
(``GOOGLE_SAFE_BROWSING_API_KEY`` / settings.google_safe_browsing_api_key)
and is never committed to Git. When the key is absent the source reports
"disabled" and no request is made.

A returned match is a CONFIRMED threat-list hit (match_type="confirmed",
weight 40). An empty response means only that the submitted URLs are not on
the lists that were checked - it is never treated as proof of safety.
"""
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.services.intel.base import (
    MATCH_CONFIRMED,
    SOURCE_SAFEBROWSING,
    CheckTuple,
    dedupe_findings,
    make_check,
    make_finding,
    utc_iso,
)

ENDPOINT = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
CLIENT_ID = "scamshield-ai"
CLIENT_VERSION = "0.1.0"
THREAT_TYPES = [
    "MALWARE",
    "SOCIAL_ENGINEERING",
    "UNWANTED_SOFTWARE",
    "POTENTIALLY_HARMFUL_APPLICATION",
]
# Well below the documented 500-URL limit; enough for a single submission.
MAX_URLS = 10
# Confirmed threat-list match weight (independent of heuristic URL rules).
MATCH_WEIGHT = 40


def build_payload(urls: List[str]) -> Dict[str, Any]:
    """Request body per the v4 Lookup API reference."""
    return {
        "client": {"clientId": CLIENT_ID, "clientVersion": CLIENT_VERSION},
        "threatInfo": {
            "threatTypes": THREAT_TYPES,
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url} for url in urls],
        },
    }


def parse_matches(payload: Dict[str, Any]) -> Dict[str, List[str]]:
    """Map each matched URL to the sorted list of its threat types."""
    matched: Dict[str, set] = {}
    for match in payload.get("matches", []) or []:
        threat_type = str(match.get("threatType", "UNKNOWN"))
        for entry in match.get("threatEntries", []) or []:
            url = str(entry.get("url", "")).strip()
            if not url:
                continue
            matched.setdefault(url, set()).add(threat_type)
    return {url: sorted(types) for url, types in matched.items()}


def _short_host(url: str) -> str:
    try:
        return urlparse(url).hostname or url
    except Exception:
        return url


def lookup(
    *,
    urls: Optional[List[str]] = None,
    client: Optional[httpx.Client] = None,
) -> CheckTuple:
    """Check submitted URLs against Google Safe Browsing threat lists.

    Never raises. Returns (findings, source_check).
    """
    checked_at = utc_iso()
    api_key = settings.google_safe_browsing_api_key.strip()

    if not api_key:
        return [], make_check(
            SOURCE_SAFEBROWSING,
            "disabled",
            checked_at=checked_at,
            detail="GOOGLE_SAFE_BROWSING_API_KEY not configured; URLs were not checked against threat lists",
        )

    candidates = [u for u in dict.fromkeys(urls or []) if u.strip()][:MAX_URLS]
    if not candidates:
        return [], make_check(
            SOURCE_SAFEBROWSING,
            "skipped",
            checked_at=checked_at,
            detail="no URL in this submission to check",
        )

    if client is None:
        client = httpx.Client(timeout=settings.intel_timeout_seconds)
        owns_client = True
    else:
        owns_client = False

    try:
        response = client.post(f"{ENDPOINT}?key={api_key}", json=build_payload(candidates))
    except httpx.TimeoutException:
        return [], make_check(
            SOURCE_SAFEBROWSING,
            "unavailable",
            checked_at=checked_at,
            detail="request timed out; URLs were not checked against threat lists",
        )
    except httpx.HTTPError as exc:
        return [], make_check(
            SOURCE_SAFEBROWSING,
            "unavailable",
            checked_at=checked_at,
            detail=f"network error ({(str(exc) or type(exc).__name__)[:120]}); URLs were not checked",
        )
    finally:
        if owns_client:
            client.close()

    if response.status_code == 200:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        matched = parse_matches(payload if isinstance(payload, dict) else {})

        findings = []
        for url, threat_types in matched.items():
            types_text = ", ".join(threat_types)
            findings.append(
                make_finding(
                    indicator_id="SB_URL_MATCH",
                    source=SOURCE_SAFEBROWSING,
                    reason=f"URL confirmed on Google Safe Browsing ({types_text})",
                    snippet=url,
                    weight=MATCH_WEIGHT,
                    match_type=MATCH_CONFIRMED,
                    retrieved_at=checked_at,
                    explanation=(
                        f"Google Safe Browsing reports {_short_host(url)} on: "
                        f"{types_text}. This is a confirmed threat-list match "
                        f"(checked {checked_at}). Avoid this URL."
                    ),
                )
            )
        findings = dedupe_findings(findings)

        if matched:
            detail = (
                f"checked {len(candidates)} URL(s): {len(matched)} confirmed "
                f"threat-list match(es)"
            )
        else:
            detail = (
                f"checked {len(candidates)} URL(s): not found on the checked "
                f"lists - absence from a threat list is not proof of safety"
            )
        return findings, make_check(
            SOURCE_SAFEBROWSING,
            "checked",
            checked_at=checked_at,
            detail=detail,
        )

    # Non-200: surface the API's own error message when present.
    message = ""
    try:
        body = response.json()
        message = str((body.get("error") or {}).get("message", ""))[:200]
    except (ValueError, AttributeError):
        message = ""
    if not message:
        message = f"HTTP {response.status_code}"
    return [], make_check(
        SOURCE_SAFEBROWSING,
        "error",
        checked_at=checked_at,
        detail=f"Safe Browsing API rejected the request: {message}",
    )
