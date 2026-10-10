from typing import List, Dict, Any
from app.services.fusion import RECOMMENDATIONS


# Human-readable explanations for each indicator
INDICATOR_EXPLANATIONS = {
    "URGENCY_LANGUAGE": "The message uses urgent language to pressure you into acting quickly without thinking.",
    "UPFRONT_PAYMENT": "The message requests payment, fees, or deposits before you start work or receive an offer.",
    "GUARANTEED_SELECTION": "The message promises guaranteed selection, placement, or acceptance - legitimate employers rarely guarantee outcomes.",
    "UNREALISTIC_SALARY": "The promised salary or earnings are unusually high for the role described.",
    "CREDENTIAL_REQUEST": "The message asks for passwords, OTPs, bank details, or other sensitive credentials.",
    "BRAND_IMPERSONATION": "The message references well-known companies in a way that suggests impersonation.",
    "FREEMAIL_SENDER": "Official communications from companies typically use corporate email domains, not free email providers.",
    "PAYMENT_PRESSURE": "The message pressures you to pay via specific methods like UPI, wallet, or wire transfer.",
    "OFF_PLATFORM_CONTACT": "The message tries to move communication off official platforms to less traceable channels.",
    "REWARD_PROMISE": "The message promises rewards, certificates, or gifts in exchange for payment.",
    "FAKE_INTERNSHIP": "The message shows patterns typical of fake internship offers requiring fees.",
    "FAKE_SCHOLARSHIP": "The message requests fees or bank details to 'release' a scholarship - legitimate scholarships don't require payment.",
    "FAKE_AMBASSADOR": "The ambassador program requires deposits or kit purchases - legitimate programs don't ask for money.",
    "FAKE_TRAINING": "Paid training with guaranteed placement promises is a common scam pattern.",
    "FAKE_JOB": "The message shows patterns typical of fake job offers, such as fees before joining or no interview.",
    "FAKE_PLACEMENT": "The message shows patterns typical of fake placement drives, such as mass recruitment requiring an upfront fee.",
    "URL_IP_HOST": "The URL uses an IP address instead of a domain name, which is uncommon for legitimate sites.",
    "URL_PUNYCODE": "The URL uses punycode (xn--) which can be used for homograph attacks (lookalike domains).",
    "URL_MANY_SUBDOMAINS": "The URL has an unusual number of subdomains, a technique used to mimic legitimate domains.",
    "URL_AT_SYMBOL": "The URL contains an @ symbol, which can be used to embed credentials or mislead about the true destination.",
    "URL_SUSPICIOUS_TLD": "The URL uses a top-level domain commonly associated with abusive or spammy websites.",
    "URL_BRAND_LOOKALIKE": "The domain name resembles a well-known brand, suggesting typosquatting or impersonation.",
    "URL_SHORTENER": "The URL uses a shortening service, which hides the true destination.",
    "URL_HIGH_ENTROPY": "The domain name appears randomly generated, which is typical of malicious infrastructure.",
    "URL_SUSPICIOUS_TOKENS": "The URL path contains words commonly used in phishing (login, verify, secure, etc.).",
    "URL_LONG_LENGTH": "The URL is unusually long, which can indicate obfuscation or tracking parameters.",
    "OFFICIAL_DOMAIN": "The communication uses an official company domain, which is a positive signal.",
    "VERIFIABLE_CONTACT": "The message provides verifiable contact information for the organization.",
    # External intelligence findings (normally carry their own explanation).
    "I4C_ADVISORY": "An official I4C advisory describes a similar fraud pattern (advisory similarity only - not a confirmed match).",
    "SB_URL_MATCH": "The URL appears on a Google Safe Browsing threat list (confirmed match).",
}


def explain_indicators(indicators: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert raw indicators to user-readable explanations.
    Returns list with id, reason (explanation), snippet, weight, source.

    Indicators that already carry a rich "explanation" (external intelligence
    findings cite their source, timestamp, and reference URL) keep it as-is.
    """
    explained = []
    for ind in indicators:
        ind_id = ind.get("id", "UNKNOWN")
        explanation = ind.get("explanation") or INDICATOR_EXPLANATIONS.get(
            ind_id,
            f"Risk indicator: {ind.get('reason', ind_id)}"
        )
        entry = {
            "id": ind_id,
            "source": ind.get("source", "text"),
            "reason": explanation,
            "snippet": ind.get("snippet", ""),
            "weight": ind.get("weight", 0),
        }
        # Preserve intel metadata (None for rule-based indicators).
        if "match_type" in ind:
            entry["match_type"] = ind.get("match_type")
        if "retrieved_at" in ind:
            entry["retrieved_at"] = ind.get("retrieved_at")
        explained.append(entry)
    return explained


def generate_summary(risk_band: str, category: str, evidence_count: int) -> str:
    """Generate a one-line summary for the result."""
    if risk_band == "UNCERTAIN":
        return "Unable to reliably assess risk due to insufficient or conflicting information."
    
    cat_desc = {
        "FAKE_INTERNSHIP": "fake internship offer",
        "FAKE_JOB": "fake job offer",
        "FAKE_OFFER_LETTER": "fake offer letter",
        "FAKE_AMBASSADOR": "fake ambassador program",
        "FAKE_SCHOLARSHIP": "fake scholarship offer",
        "FAKE_TRAINING": "fake training program",
        "FAKE_PLACEMENT": "fake placement drive",
        "PHISHING": "phishing attempt",
        "PAYMENT_SCAM": "payment scam",
        "LEGITIMATE_LIKELY": "likely legitimate",
    }.get(category, "suspicious content")

    return f"Risk indicators suggest a {risk_band.lower()} likelihood of {cat_desc} ({evidence_count} indicator(s) found)."


def get_disclaimer() -> str:
    """Standard disclaimer."""
    return "Risk indicators are not proof of fraud. Legitimate opportunities may be flagged (false positive); novel scams may be missed (false negative). Always verify independently."


def format_evidence_for_display(indicators: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format evidence for frontend display with highlighting hints."""
    formatted = []
    for ind in indicators:
        formatted.append({
            "id": ind["id"],
            "source": ind["source"],
            "reason": ind["reason"],
            "snippet": ind["snippet"],
            "weight": ind["weight"],
            "is_risk": ind["weight"] > 0,
        })
    return formatted