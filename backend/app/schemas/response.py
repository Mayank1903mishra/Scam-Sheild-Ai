from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from uuid import UUID


class EvidenceItem(BaseModel):
    id: str
    source: Literal["text", "url", "ocr"]
    reason: str
    snippet: str
    weight: int


class ExtractedData(BaseModel):
    urls: List[str] = []
    emails: List[str] = []
    phones: List[str] = []
    domains: List[str] = []


class UncertaintyInfo(BaseModel):
    level: Literal["low", "medium", "high"]
    reasons: List[str] = []


class ModuleScores(BaseModel):
    text: int = 0
    url: int = 0
    ocr_confidence: float = 0.0


class ScanResponse(BaseModel):
    id: UUID
    created_at: datetime
    input_types: List[Literal["text", "url", "image"]]
    risk_score: int = Field(ge=0, le=100)
    risk_band: Literal["LOW", "MODERATE", "HIGH", "VERY_HIGH", "UNCERTAIN"]
    score_note: str
    category: Optional[str] = None
    uncertainty: UncertaintyInfo
    modules: ModuleScores
    evidence: List[EvidenceItem] = []
    extracted: ExtractedData
    recommendations: List[str] = []
    disclaimer: str
    mode: Literal["rules", "ml", "demo"]


class ScanListItem(BaseModel):
    id: UUID
    created_at: datetime
    input_types: List[Literal["text", "url", "image"]]
    risk_score: int
    risk_band: Literal["LOW", "MODERATE", "HIGH", "VERY_HIGH", "UNCERTAIN"]
    category: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"
    mode: Literal["rules", "ml", "demo"]


class FeedbackResponse(BaseModel):
    message: str