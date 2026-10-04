from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from app.services.text_analyzer import analyze_text
from app.services.url_analyzer import analyze_urls, extract_url_features
from app.services.evidence import extract_entities_combined
from app.services.fusion import fuse_results, FusionResult
from app.services.explain import explain_indicators, generate_summary, get_disclaimer, format_evidence_for_display
from app.services.privacy import mask_pii
from app.config import settings


@dataclass
class AnalysisInput:
    text: Optional[str] = None
    url: Optional[str] = None
    ocr_text: Optional[str] = None
    ocr_confidence: float = 0.0


@dataclass
class AnalysisOutput:
    risk_score: int
    risk_band: str
    category: Optional[str]
    uncertainty: Dict[str, Any]
    evidence: List[Dict[str, Any]]
    module_scores: Dict[str, int]
    extracted: Dict[str, Any]
    recommendations: List[str]
    disclaimer: str
    summary: str
    mode: str
    masked_text: Optional[str] = None


def _merge_text_results(*results: Dict[str, Any]) -> Dict[str, Any]:
    """Merge text-analysis results, keeping per-result evidence sources."""
    merged: Dict[str, Any] = {"indicators": [], "score": 0, "categories": {}}
    for result in results:
        merged["indicators"].extend(result.get("indicators", []))
        for category, weight in result.get("categories", {}).items():
            merged["categories"][category] = merged["categories"].get(category, 0) + weight
    total = sum(ind.get("weight", 0) for ind in merged["indicators"])
    merged["score"] = min(100, max(0, total))
    return merged


class InputManager:
    """Coordinates input processing and analysis pipeline."""

    def __init__(self):
        pass

    def validate_input(self, text: Optional[str], url: Optional[str], ocr_text: Optional[str]) -> List[str]:
        """Validate inputs and return list of input types present."""
        input_types = []
        if text and text.strip():
            input_types.append("text")
        if url and url.strip():
            input_types.append("url")
        if ocr_text and ocr_text.strip():
            input_types.append("image")
        return input_types

    def analyze(self, input_data: AnalysisInput) -> AnalysisOutput:
        """Run full analysis pipeline."""
        input_types = self.validate_input(input_data.text, input_data.url, input_data.ocr_text)

        # Combine all text for analysis
        all_text_parts = []
        if input_data.text:
            all_text_parts.append(input_data.text)
        if input_data.ocr_text:
            all_text_parts.append(input_data.ocr_text)
        combined_text = "\n".join(all_text_parts)

        # Extract URLs from text/OCR if not provided directly
        urls = []
        if input_data.url:
            urls.append(input_data.url)

        # Also extract URLs from text and OCR
        from app.services.evidence import extract_urls
        if input_data.text:
            urls.extend(extract_urls(input_data.text))
        if input_data.ocr_text:
            urls.extend(extract_urls(input_data.ocr_text))

        # Deduplicate URLs
        urls = list(dict.fromkeys(urls))

        # Analyze user text and OCR text separately so each evidence item
        # carries the correct source ("text" vs "ocr"), then merge results.
        user_result = {"indicators": [], "score": 0, "categories": {}}
        if input_data.text and input_data.text.strip():
            user_result = analyze_text(input_data.text, source="text")

        ocr_result = {"indicators": [], "score": 0, "categories": {}}
        if input_data.ocr_text and input_data.ocr_text.strip():
            ocr_result = analyze_text(input_data.ocr_text, source="ocr")

        text_result = _merge_text_results(user_result, ocr_result)

        # Analyze URLs
        url_result = {"indicators": [], "score": 0, "features": []}
        if urls:
            url_result = analyze_urls(urls)

        # Extract entities (include the submitted URL so it appears in results)
        extracted = extract_entities_combined(
            [t for t in [input_data.text, input_data.ocr_text, input_data.url] if t]
        )

        # Length of OCR output only (None when no image was submitted)
        ocr_text_length = None
        if input_data.ocr_text is not None:
            ocr_text_length = len(input_data.ocr_text.strip())

        # Fuse results
        fusion_result = fuse_results(
            text_result=text_result,
            url_result=url_result,
            ocr_confidence=input_data.ocr_confidence,
            input_text=combined_text,
            ocr_text_length=ocr_text_length,
        )

        # Explain indicators
        explained_evidence = explain_indicators(fusion_result.evidence)

        # Generate summary
        summary = generate_summary(
            fusion_result.risk_band,
            fusion_result.category or "UNCERTAIN",
            len(explained_evidence)
        )

        # Handle privacy - mask PII if storing
        masked_text = None
        if settings.store_content and combined_text:
            masked_text, _ = mask_pii(combined_text)

        return AnalysisOutput(
            risk_score=fusion_result.risk_score,
            risk_band=fusion_result.risk_band,
            category=fusion_result.category,
            uncertainty=fusion_result.uncertainty,
            evidence=explained_evidence,
            module_scores=fusion_result.module_scores,
            extracted=extracted,
            recommendations=fusion_result.recommendations,
            disclaimer=get_disclaimer(),
            summary=summary,
            mode="rules",
            masked_text=masked_text,
        )


def analyze_input(
    text: Optional[str] = None,
    url: Optional[str] = None,
    ocr_text: Optional[str] = None,
    ocr_confidence: float = 0.0,
) -> AnalysisOutput:
    """Convenience function for analysis."""
    manager = InputManager()
    input_data = AnalysisInput(
        text=text,
        url=url,
        ocr_text=ocr_text,
        ocr_confidence=ocr_confidence,
    )
    return manager.analyze(input_data)