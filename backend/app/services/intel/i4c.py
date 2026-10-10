"""I4C / National Cyber Crime Reporting Portal advisory adapter.

Verified access method (checked 2026-10-04): the official public resource
pages at cybercrime.gov.in are plain HTTPS GETs with no authentication:

  * ``Webform/Advisory.aspx``    - official I4C advisory list with fraud
    pattern titles, publication dates, summaries, and PDF links.
  * ``Webform/daily-digest.aspx`` - Daily Digest listing (digest IDs like
    "CD- 958" with dates).

The suspect-repository search pages are deliberately NOT used: they are
interactive web forms (CAPTCHA-protected search) with no documented public
API, and bypassing them is out of scope by policy. Digest detail bodies are
served via ASP.NET postback, so only the public listing metadata is read.

Matching is advisory similarity only (weight 0): the submitted text and the
rule-based indicator IDs are matched against real advisory titles/summaries
fetched from the portal. Nothing about the user's input is sent to I4C -
our server only fetches public pages; matching happens locally.
"""
import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin

import httpx

from app.config import settings
from app.services.intel.base import (
    MATCH_ADVISORY,
    SOURCE_I4C,
    CheckTuple,
    dedupe_findings,
    make_check,
    make_finding,
    utc_iso,
)

# Advisory block: <a href="...pdf" ...><h3>Title</h3></a> ... <p class="title">Date</p>
# <p ...>Summary</p>
_ADVISORY_RE = re.compile(
    r'<a href="(?P<href>[^"]+)"[^>]*>\s*<h3>(?P<title>.*?)</h3>.*?'
    r'<p class="title">\s*(?P<date>[^<]+?)\s*</p>\s*'
    r'<p class="[^"]*">\s*(?P<desc>.*?)</p>',
    re.S,
)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# Daily Digest listing anchors and IDs.
_DIGEST_TITLE_RE = re.compile(
    r'<a[^>]*lnktitle[^>]*>\s*(?P<title>.*?)\s*</a>', re.S | re.I
)
_DIGEST_ID_RE = re.compile(r"<p>\s*(?P<id>CD-\s*\d+)\s*</p>", re.I)

# Topic keywords used for advisory similarity. Each keyword must appear as a
# word (optionally plural) in an advisory title or summary to match.
INDICATOR_TOPICS: Dict[str, Set[str]] = {
    "FAKE_JOB": {"job"},
    "FAKE_INTERNSHIP": {"job", "internship"},
    "FAKE_PLACEMENT": {"job", "placement"},
    "FAKE_SCHOLARSHIP": {"scholarship"},
    "FAKE_TRAINING": {"job"},
    "FAKE_AMBASSADOR": {"job", "investment"},
    "GUARANTEED_SELECTION": {"job"},
    "UNREALISTIC_SALARY": {"job", "salary"},
    "UPFRONT_PAYMENT": {"job", "payment"},
    "PAYMENT_PRESSURE": {"payment", "upi"},
    "PAYMENT_SCAM": {"payment", "upi"},
    "CREDENTIAL_REQUEST": {"password", "otp", "credential"},
    "PHISHING": {"phishing", "credential"},
    "BRAND_IMPERSONATION": {"impersonation", "spoofing"},
    "OFF_PLATFORM_CONTACT": {"whatsapp", "telegram"},
    "REWARD_PROMISE": {"lottery", "reward", "gift"},
    "URGENCY_LANGUAGE": {"digital arrest"},
    "URL_BRAND_LOOKALIKE": {"phishing"},
}

# Topics detected directly from submitted text (case-insensitive whole words).
TEXT_TOPICS = [
    "job", "internship", "scholarship", "otp", "kyc", "digital arrest",
    "captcha", "upi", "investment", "lottery", "sextortion", "phishing",
    "impersonation", "salary", "placement",
]

_MAX_FINDINGS = 3

# Success/error cache: url -> (expires_monotonic, entries_or_None).
# Errors are cached briefly so a failing portal does not slow every scan.
_CACHE: Dict[str, tuple] = {}


def _clean(fragment: str) -> str:
    """Strip inner tags, unescape entities, collapse whitespace."""
    text = _TAG_RE.sub(" ", fragment)
    text = (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&#39;", "'")
        .replace("&quot;", '"')
        .replace("&nbsp;", " ")
    )
    return _WS_RE.sub(" ", text).strip()


def parse_advisories(html: str, base_url: str) -> List[Dict[str, str]]:
    """Parse advisory entries (title, date, summary, url) from the public page."""
    entries: List[Dict[str, str]] = []
    for match in _ADVISORY_RE.finditer(html):
        title = _clean(match.group("title"))
        if not title:
            continue
        href = match.group("href").strip()
        entries.append(
            {
                "title": title,
                "date": _clean(match.group("date")),
                "summary": _clean(match.group("desc")),
                "url": urljoin(base_url, href) if href else base_url,
            }
        )
    return entries


def parse_digests(html: str) -> List[Dict[str, str]]:
    """Parse Daily Digest listing entries (title with date, digest ID)."""
    titles = [_clean(m.group("title")) for m in _DIGEST_TITLE_RE.finditer(html)]
    ids = [_WS_RE.sub("", m.group("id")) for m in _DIGEST_ID_RE.finditer(html)]
    digests = []
    for index, title in enumerate(titles):
        digests.append(
            {
                "title": title,
                "digest_id": ids[index] if index < len(ids) else "",
            }
        )
    return digests


def topics_for(indicator_ids: List[str], text: str) -> Set[str]:
    """Topic keywords derived from triggered indicators plus the input text."""
    topics: Set[str] = set()
    for indicator_id in indicator_ids:
        topics |= INDICATOR_TOPICS.get(indicator_id, set())
    lowered = (text or "").lower()
    for topic in TEXT_TOPICS:
        if re.search(r"\b" + re.escape(topic) + r"s?\b", lowered):
            topics.add(topic)
    return topics


def _topic_matches(topic: str, blob: str) -> bool:
    return re.search(r"\b" + re.escape(topic) + r"s?\b", blob) is not None


def match_advisories(
    advisories: List[Dict[str, str]], topics: Set[str]
) -> List[Dict[str, str]]:
    """Advisories whose title or summary mentions one of the topics."""
    if not topics:
        return []
    matched = []
    for advisory in advisories:
        blob = f"{advisory['title']} {advisory['summary']}".lower()
        if any(_topic_matches(topic, blob) for topic in topics):
            matched.append(advisory)
    return matched[:_MAX_FINDINGS]


def _fetch(url: str, client: httpx.Client) -> Optional[str]:
    """GET a public portal page; returns None on any failure."""
    try:
        response = client.get(
            url, headers={"User-Agent": "ScamShield-AI/0.1 (public advisory reader)"}
        )
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    return response.text


def _cached_fetch(url: str, client: httpx.Client) -> Optional[str]:
    """Fetch with a TTL cache; failures are cached for 60 seconds."""
    import time

    now = time.monotonic()
    cached = _CACHE.get(url)
    if cached and cached[0] > now:
        return cached[1]
    html = _fetch(url, client)
    ttl = settings.intel_cache_seconds if html else 60.0
    _CACHE[url] = (now + ttl, html)
    return html


def clear_cache() -> None:
    """Reset the advisory cache (used by tests)."""
    _CACHE.clear()


def lookup(
    *,
    text: str = "",
    indicator_ids: Optional[List[str]] = None,
    client: Optional[httpx.Client] = None,
) -> CheckTuple:
    """Fetch official I4C advisories and match them against the input.

    Never raises. Returns (findings, source_check). Findings are advisory
    similarities with weight 0 (they explain context, they never change the
    risk score, so existing indicators are not double-counted).
    """
    checked_at = utc_iso()
    if client is None:
        client = httpx.Client(timeout=settings.intel_timeout_seconds)
        owns_client = True
    else:
        owns_client = False

    try:
        advisory_html = _cached_fetch(settings.i4c_advisory_url, client)
        digest_html = _cached_fetch(settings.i4c_digest_url, client)

        if advisory_html is None and digest_html is None:
            return [], make_check(
                SOURCE_I4C,
                "unavailable",
                checked_at=checked_at,
                detail="cybercrime.gov.in could not be reached (timeout or error); no advisory context was added",
            )

        advisories = parse_advisories(advisory_html or "", settings.i4c_advisory_url)
        digests = parse_digests(digest_html or "")

        if advisory_html is not None and not advisories:
            # Page reachable but structure changed: do not pretend to match.
            return [], make_check(
                SOURCE_I4C,
                "error",
                checked_at=checked_at,
                detail="advisory page reached but no advisories could be parsed",
            )

        topics = topics_for(indicator_ids or [], text)
        matched = match_advisories(advisories, topics)

        findings = []
        for advisory in matched:
            findings.append(
                make_finding(
                    indicator_id="I4C_ADVISORY",
                    source=SOURCE_I4C,
                    reason=f"I4C advisory: {advisory['title']}",
                    snippet=f"{advisory['title']} ({advisory['date']})",
                    weight=0,
                    match_type=MATCH_ADVISORY,
                    retrieved_at=checked_at,
                    reference_url=advisory["url"],
                    explanation=(
                        f'Official I4C advisory "{advisory["title"]}" '
                        f'({advisory["date"]}) describes a similar fraud pattern. '
                        f"Advisory similarity only - not a confirmed threat-list "
                        f"match and not proof of fraud. Reference: {advisory['url']}"
                    ),
                )
            )
        findings = dedupe_findings(findings)

        detail_parts = [f"checked {len(advisories)} official advisories"]
        if digests:
            latest = digests[0]
            detail_parts.append(
                f'latest Daily Digest {latest["digest_id"]} ({latest["title"]})'
            )
        if topics:
            detail_parts.append(
                f"{len(matched)} similar to detected topics ({', '.join(sorted(topics))})"
            )
        return findings, make_check(
            SOURCE_I4C,
            "checked",
            checked_at=checked_at,
            detail="; ".join(detail_parts),
        )
    except Exception as exc:  # pragma: no cover - defensive fail-open
        return [], make_check(
            SOURCE_I4C,
            "error",
            checked_at=checked_at,
            detail=f"adapter error: {(str(exc) or type(exc).__name__)[:200]}",
        )
    finally:
        if owns_client:
            client.close()
