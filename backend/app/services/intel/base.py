"""Shared types and helpers for the intelligence source adapters.

Every source adapter is independent: it never raises out of its ``lookup``
function, always returns normalized findings plus a source-check record so
the API can report exactly what was checked, when, and what it contributed.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# Source identifiers (stable API values)
SOURCE_I4C = "i4c"
SOURCE_SAFEBROWSING = "safebrowsing"

# Status values for a source check:
#   checked     - the source was queried successfully
#   disabled    - feature or credential not configured (no request made)
#   skipped     - source applicable only to some inputs; nothing to check
#   unavailable - network/timeout failure (fail-open, analysis continued)
#   error       - the source rejected the request (auth, quota, bad input)
CHECK_STATUSES = ("checked", "disabled", "skipped", "unavailable", "error")

# match_type distinguishes a confirmed threat-list hit from an advisory
# similarity: only "confirmed" means the source asserted a match.
MATCH_CONFIRMED = "confirmed"
MATCH_ADVISORY = "advisory"


def utc_iso() -> str:
    """Current UTC time in ISO-8601 (seconds), e.g. 2026-10-04T12:00:00+00:00."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_check(
    source: str,
    status: str,
    detail: str = "",
    evidence_count: int = 0,
    checked_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Normalized source-check record (serialized into ScanResponse.sources)."""
    return {
        "source": source,
        "status": status,
        "checked_at": checked_at or utc_iso(),
        "detail": detail,
        "evidence_count": evidence_count,
    }


def make_finding(
    *,
    indicator_id: str,
    source: str,
    reason: str,
    snippet: str,
    weight: int,
    match_type: str,
    explanation: str,
    retrieved_at: Optional[str] = None,
    reference_url: str = "",
) -> Dict[str, Any]:
    """Normalized evidence finding shaped like an analysis indicator, plus
    source, retrieval timestamp, and confirmed/advisory match type."""
    finding = {
        "id": indicator_id,
        "source": source,
        "reason": reason,
        "snippet": snippet,
        "weight": weight,
        "match_type": match_type,
        "retrieved_at": retrieved_at or utc_iso(),
        "explanation": explanation,
    }
    if reference_url:
        finding["reference_url"] = reference_url
    return finding


def dedupe_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop duplicate findings for the same (id, snippet) pair, preserving
    first-seen order. Prevents double-counting when the same advisory or
    threat-list match is returned more than once."""
    seen = set()
    unique: List[Dict[str, Any]] = []
    for finding in findings:
        key = (finding.get("id", ""), finding.get("snippet", ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique


def recount_checks(
    checks: List[Dict[str, Any]], findings: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Set evidence_count on each check from the final (deduplicated) findings."""
    for check in checks:
        check["evidence_count"] = sum(
            1 for f in findings if f.get("source") == check.get("source")
        )
    return checks


def failure_check(source: str, exc: Exception) -> Dict[str, Any]:
    """Last-resort record when an adapter itself fails unexpectedly."""
    message = str(exc).strip() or type(exc).__name__
    return make_check(source, "error", detail=f"adapter error: {message[:200]}")


CheckTuple = Tuple[List[Dict[str, Any]], Dict[str, Any]]
