from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from app.services.ml_classifier import classify_with_ml, MLResult


@dataclass
class ModuleResult:
    """Result from a single analysis module."""
    name: str
    score: int
    indicators: List[Dict[str, Any]]
    metadata: Dict[str, Any]


@dataclass
class FusionResult:
    """Final fused result."""
    risk_score: int
    risk_band: str
    category: Optional[str]
    uncertainty: Dict[str, Any]
    evidence: List[Dict[str, Any]]
    module_scores: Dict[str, int]
    recommendations: List[str]


# Risk band thresholds (provisional, configurable)
RISK_BANDS = {
    "LOW": (0, 30),
    "MODERATE": (31, 60),
    "HIGH": (61, 80),
    "VERY_HIGH": (81, 100),
}


# Category mapping from indicator categories to scam types
CATEGORY_INDICATORS = {
    "FAKE_INTERNSHIP": ["FAKE_INTERNSHIP"],
    "FAKE_JOB": ["FAKE_JOB", "GUARANTEED_SELECTION", "UNREALISTIC_SALARY"],
    "FAKE_OFFER_LETTER": ["BRAND_IMPERSONATION", "FREEMAIL_SENDER"],
    "FAKE_AMBASSADOR": ["FAKE_AMBASSADOR"],
    "FAKE_SCHOLARSHIP": ["FAKE_SCHOLARSHIP"],
    "FAKE_TRAINING": ["FAKE_TRAINING"],
    "FAKE_PLACEMENT": ["FAKE_PLACEMENT"],
    "PHISHING": ["PHISHING", "CREDENTIAL_REQUEST", "URL_IP_HOST", "URL_PUNYCODE", "URL_BRAND_LOOKALIKE"],
    "PAYMENT_SCAM": ["PAYMENT_SCAM", "UPFRONT_PAYMENT", "PAYMENT_PRESSURE"],
    "LEGITIMATE_LIKELY": ["OFFICIAL_DOMAIN", "VERIFIABLE_CONTACT"],
}


# Default recommendations by risk band
RECOMMENDATIONS = {
    "LOW": [
        "Stay cautious with any requests for personal information or payment.",
        "Verify the sender through official channels if unsure."
    ],
    "MODERATE": [
        "Exercise caution. Do not share personal or financial information.",
        "Verify the opportunity through the company's official website or contact details.",
        "Consult your college placement cell or career advisor."
    ],
    "HIGH": [
        "High risk detected. Do not make any payments or share credentials.",
        "Verify independently through the organization's official website (not links in the message).",
        "Report to your college placement cell and cybercrime portal if applicable."
    ],
    "VERY_HIGH": [
        "Very high risk. Do not engage, pay, or share any information.",
        "This exhibits multiple strong scam indicators.",
        "Report to authorities (cybercrime.gov.in) and your college placement cell immediately."
    ],
    "UNCERTAIN": [
        "Unable to determine risk level reliably (insufficient input or conflicting signals).",
        "Exercise caution and verify independently before taking any action.",
        "If this is a job/internship offer, confirm through the company's official career page."
    ],
}


def score_to_band(score: int) -> str:
    """Convert numeric score to risk band."""
    for band, (low, high) in RISK_BANDS.items():
        if low <= score <= high:
            return band
    return "UNCERTAIN"


def calculate_uncertainty(
    text_length: int,
    ocr_confidence: float,
    module_scores: Dict[str, int],
    indicators: List[Dict[str, Any]],
    ocr_text_length: Optional[int] = None,
) -> Dict[str, Any]:
    """Calculate uncertainty level and reasons.

    ocr_text_length: length of OCR output when an image was submitted,
    or None when no image was part of the input. Low/empty OCR output
    raises uncertainty (limits certainty) but never raises the score.
    """
    reasons = []
    level = "low"

    # Very short input
    if text_length < 20:
        reasons.append("Very short input text")
        level = "high"

    # Low OCR confidence
    if ocr_confidence > 0 and ocr_confidence < 0.5:
        reasons.append(f"Low OCR confidence ({ocr_confidence:.0%})")
        if level == "low":
            level = "medium"

    # Image submitted but OCR produced little or no usable text
    if ocr_text_length is not None:
        if ocr_text_length == 0:
            reasons.append("No text could be extracted from the image; analysis is limited")
            level = "high"
        elif ocr_text_length < 20:
            reasons.append("Very little text was extracted from the image; analysis is limited")
            if level == "low":
                level = "medium"

    # Conflicting modules (one high, one low)
    scores = [s for s in module_scores.values() if s > 0]
    if len(scores) >= 2:
        if max(scores) - min(scores) > 50:
            reasons.append("Conflicting signals from different analysis modules")
            if level == "low":
                level = "medium"

    # No indicators found
    if not indicators:
        reasons.append("No risk indicators detected")
        # Do not downgrade: level stays "low" for adequate-length input,
        # but remains "high"/"medium" when set by short input or low OCR confidence.

    return {
        "level": level,
        "reasons": reasons,
    }


def select_category(
    indicators: List[Dict[str, Any]],
    module_scores: Dict[str, int]
) -> Optional[str]:
    """
    Select scam category based on triggered indicators.
    Returns the category with highest total weight among matching indicators.
    """
    category_weights = {}

    for ind in indicators:
        ind_id = ind["id"]
        weight = ind["weight"]

        for category, ind_ids in CATEGORY_INDICATORS.items():
            if ind_id in ind_ids:
                category_weights[category] = category_weights.get(category, 0) + weight

    if not category_weights:
        # Check for legitimate signals
        legit_weight = sum(
            ind["weight"] for ind in indicators
            if ind["weight"] < 0
        )
        if legit_weight < -5:
            return "LEGITIMATE_LIKELY"
        return None

    # Return category with highest weight
    return max(category_weights.items(), key=lambda x: x[1])[0]


def get_recommendations(risk_band: str) -> List[str]:
    """Get recommendations for a risk band."""
    return RECOMMENDATIONS.get(risk_band, RECOMMENDATIONS["MODERATE"])


def fuse_results(
    text_result: Dict[str, Any],
    url_result: Dict[str, Any],
    ocr_confidence: float = 0.0,
    input_text: str = "",
    ocr_text_length: Optional[int] = None,
    intel_indicators: Optional[List[Dict[str, Any]]] = None,
    ml_result: Optional[MLResult] = None,
) -> FusionResult:
    """
    Fuse results from multiple analysis modules.
    Uses bounded weighted sum for final score.

    intel_indicators: normalized findings from external source adapters
    (weight 0 advisory similarities, positive weights for confirmed
    threat-list matches). They join the evidence list, so the documented
    invariant risk_score == min(100, max(0, sum(evidence weights)))
    keeps holding without double-counting rule-based indicators.

    ml_result: ML classifier result (probability scaled to 0-100).
    Added as a module score and evidence item with weight derived from probability.
    """
    # Combine all indicators with source tracking
    all_indicators = []

    for ind in text_result.get("indicators", []):
        ind_copy = ind.copy()
        ind_copy["source"] = ind.get("source", "text")
        all_indicators.append(ind_copy)

    for ind in url_result.get("indicators", []):
        ind_copy = ind.copy()
        ind_copy["source"] = ind.get("source", "url")
        all_indicators.append(ind_copy)

    # External intelligence findings (already carry their own
    # match_type, retrieved_at, and explanation). They are reported under
    # the single "intel" source so the API evidence Literal stays stable
    # while the reason text still names the originating source.
    for ind in intel_indicators or []:
        ind_copy = ind.copy()
        ind_copy["source"] = "intel"
        all_indicators.append(ind_copy)

    # ML classifier result - add as evidence with weight = probability * 30 (max 30 points)
    # This gives ML a meaningful but not dominant voice
    if ml_result and ml_result.probability > 0:
        ml_weight = int(ml_result.probability * 30)  # 0-30 points based on confidence
        ml_indicator = {
            "id": "ML_CLASSIFIER",
            "name": f"ML classifier: {ml_result.label} ({ml_result.probability:.0%})",
            "weight": ml_weight,
            "category": "ML_SIGNAL",
            "reason": f"ML model predicts {ml_result.label} with {ml_result.probability:.0%} probability",
            "snippet": f"Probability: {ml_result.probability:.2f}, Confidence: {ml_result.confidence:.2f}",
            "source": "ml",
        }
        all_indicators.append(ml_indicator)

    # Module scores
    module_scores = {
        "text": text_result.get("score", 0),
        "url": url_result.get("score", 0),
        "ocr_confidence": ocr_confidence,
        "ml": ml_result.score if ml_result else 0,
    }

    # Calculate total weighted score
    # Using bounded weighted sum: sum of weights, capped at 100
    total_weight = sum(ind["weight"] for ind in all_indicators)
    risk_score = min(100, max(0, total_weight))

    # Rule-based (text/url/ocr) indicators only: advisory intel findings
    # must not mask "no indicators" conditions below.
    rule_indicators = [
        ind for ind in all_indicators if ind.get("source") in ("text", "url", "ocr")
    ]

    # Determine risk band
    risk_band = score_to_band(risk_score)

    # Special case: if no indicators and very short input -> UNCERTAIN
    if not rule_indicators and len(input_text.strip()) < 20:
        risk_band = "UNCERTAIN"

    # Select category
    category = select_category(all_indicators, module_scores)

    # Calculate uncertainty
    uncertainty = calculate_uncertainty(
        text_length=len(input_text),
        ocr_confidence=ocr_confidence,
        module_scores=module_scores,
        indicators=rule_indicators,
        ocr_text_length=ocr_text_length,
    )

    # Get recommendations
    recommendations = get_recommendations(risk_band)

    return FusionResult(
        risk_score=risk_score,
        risk_band=risk_band,
        category=category,
        uncertainty=uncertainty,
        evidence=all_indicators,
        module_scores=module_scores,
        recommendations=recommendations,
    )