"""Intelligence layer: independent external source adapters.

``run_intel_lookups`` is the single entry point used by the analysis
pipeline. Each adapter is queried independently, failures are fail-open
(analysis never breaks), and results are normalized and deduplicated.

Sources:
  * ``i4c``           - official I4C advisories / Daily Digest listings at
                        cybercrime.gov.in (advisory similarity, weight 0).
  * ``safebrowsing``  - Google Safe Browsing Lookup API v4 (confirmed
                        threat-list matches, weight 40, key required).

Absence of findings from either source is never proof of safety.
"""
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.intel import i4c, safebrowsing
from app.services.intel.base import (
    CheckTuple,
    dedupe_findings,
    failure_check,
    make_check,
    recount_checks,
)


class IntelOutcome:
    """Findings (shaped like indicators) plus one source-check per source."""

    def __init__(self, findings: List[Dict[str, Any]], checks: List[Dict[str, Any]]):
        self.findings = findings
        self.checks = checks

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"IntelOutcome(findings={len(self.findings)}, checks={len(self.checks)})"


def _run(adapter_lookup, check_kwargs, *args, **kwargs) -> CheckTuple:
    """Run one adapter, converting any unexpected error into a source check."""
    try:
        return adapter_lookup(*args, **kwargs)
    except Exception as exc:  # pragma: no cover - adapters already fail open
        source = check_kwargs["source"]
        return [], failure_check(source, exc)


def run_intel_lookups(
    *,
    text: str = "",
    urls: Optional[List[str]] = None,
    indicator_ids: Optional[List[str]] = None,
) -> IntelOutcome:
    """Query both sources independently; never raises.

    When ``settings.intel_lookups_enabled`` is false, both sources report
    "disabled" without any outbound request.
    """
    if not settings.intel_lookups_enabled:
        detail = "external lookups disabled (INTEL_LOOKUPS_ENABLED=false)"
        return IntelOutcome(
            [],
            [
                make_check(i4c.SOURCE_I4C, "disabled", detail=detail),
                make_check(safebrowsing.SOURCE_SAFEBROWSING, "disabled", detail=detail),
            ],
        )

    i4c_findings, i4c_check = _run(
        i4c.lookup,
        {"source": i4c.SOURCE_I4C},
        text=text,
        indicator_ids=indicator_ids or [],
    )
    sb_findings, sb_check = _run(
        safebrowsing.lookup,
        {"source": safebrowsing.SOURCE_SAFEBROWSING},
        urls=urls,
    )

    findings = dedupe_findings(i4c_findings + sb_findings)
    checks = recount_checks([i4c_check, sb_check], findings)
    return IntelOutcome(findings, checks)


__all__ = ["IntelOutcome", "run_intel_lookups", "i4c", "safebrowsing"]
