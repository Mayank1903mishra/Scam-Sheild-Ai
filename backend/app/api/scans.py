from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
import json

from app.schemas.request import ScanTextRequest, ScanUploadRequest, FeedbackRequest
from app.schemas.response import ScanResponse, ScanListItem, FeedbackResponse, EvidenceItem, ExtractedData, UncertaintyInfo, ModuleScores
from app.db import get_db_session
from app.db.repository import create_scan, get_scan, list_scans, delete_scan, submit_feedback
from app.services import analyze_input


router = APIRouter(prefix="/scans", tags=["scans"])


def get_db():
    db = next(get_db_session())
    try:
        yield db
    finally:
        db.close()


@router.post("", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
async def create_scan_endpoint(request: ScanTextRequest, db: Session = Depends(get_db)):
    if not request.has_input():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one of 'text' or 'url' must be provided"
        )

    # Run analysis
    result = analyze_input(text=request.text, url=request.url)

    # Save to database
    scan = create_scan(
        db,
        input_types=result.module_scores.keys() if False else ["text"] + (["url"] if request.url else []),
        risk_score=result.risk_score,
        risk_band=result.risk_band,
        category=result.category,
        uncertainty=result.uncertainty,
        mode=result.mode,
        masked_text=result.masked_text,
        evidence_list=[
            {
                "id": e["id"],
                "source": e["source"],
                "reason": e["reason"],
                "snippet": e["snippet"],
                "weight": e["weight"],
            }
            for e in result.evidence
        ],
    )

    # Build response
    input_types = []
    if request.text:
        input_types.append("text")
    if request.url:
        input_types.append("url")

    return ScanResponse(
        id=scan.id,
        created_at=scan.created_at,
        input_types=input_types,
        risk_score=result.risk_score,
        risk_band=result.risk_band,
        score_note="Heuristic score, not a probability; thresholds provisional.",
        category=result.category,
        uncertainty=UncertaintyInfo(**result.uncertainty),
        modules=ModuleScores(
            text=result.module_scores.get("text", 0),
            url=result.module_scores.get("url", 0),
            ocr_confidence=result.module_scores.get("ocr_confidence", 0.0),
        ),
        evidence=[
            EvidenceItem(
                id=e["id"],
                source=e["source"],
                reason=e["reason"],
                snippet=e["snippet"],
                weight=e["weight"],
            )
            for e in result.evidence
        ],
        extracted=ExtractedData(
            urls=result.extracted.get("urls", []),
            emails=result.extracted.get("emails", []),
            phones=result.extracted.get("phones", []),
            domains=result.extracted.get("domains", []),
        ),
        recommendations=result.recommendations,
        disclaimer=result.disclaimer,
        mode=result.mode,
    )


@router.post("/upload", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
async def upload_scan(
    file: UploadFile = File(...),
    text: Optional[str] = Form(None),
    url: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    # OCR not implemented yet - will be added in Stage 5
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Upload/OCR not implemented yet")


@router.get("", response_model=list[ScanListItem])
async def list_scans_endpoint(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    scans = list_scans(db, limit=limit, offset=offset)
    result = []
    for scan in scans:
        input_types = json.loads(scan.input_types) if scan.input_types else []
        result.append(ScanListItem(
            id=scan.id,
            created_at=scan.created_at,
            input_types=input_types,
            risk_score=scan.risk_score,
            risk_band=scan.risk_band,
            category=scan.category,
        ))
    return result


@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan_endpoint(scan_id: UUID, db: Session = Depends(get_db)):
    scan = get_scan(db, str(scan_id))
    if not scan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")

    input_types = json.loads(scan.input_types) if scan.input_types else []
    uncertainty = json.loads(scan.uncertainty_json) if scan.uncertainty_json else {"level": "low", "reasons": []}
    evidence = scan.evidence
    evidence_items = [
        EvidenceItem(
            id=e.indicator_id,
            source=e.source,
            reason=e.reason,
            snippet=e.snippet_masked,
            weight=e.weight,
        )
        for e in evidence
    ]

    return ScanResponse(
        id=scan.id,
        created_at=scan.created_at,
        input_types=input_types,
        risk_score=scan.risk_score,
        risk_band=scan.risk_band,
        score_note="Heuristic score, not a probability; thresholds provisional.",
        category=scan.category,
        uncertainty=UncertaintyInfo(**uncertainty),
        modules=ModuleScores(),
        evidence=evidence_items,
        extracted=ExtractedData(),
        recommendations=["Verify independently"],
        disclaimer="Risk indicators are not proof of fraud.",
        mode=scan.mode,
    )


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scan_endpoint(scan_id: UUID, db: Session = Depends(get_db)):
    deleted = delete_scan(db, str(scan_id))
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    return None


@router.post("/{scan_id}/feedback", response_model=FeedbackResponse)
async def submit_feedback_endpoint(scan_id: UUID, request: FeedbackRequest, db: Session = Depends(get_db)):
    feedback = submit_feedback(db, str(scan_id), request.helpful, request.comment)
    if not feedback:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    return FeedbackResponse(message="Feedback submitted")