from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from typing import List, Optional
from typing_extensions import Annotated
from uuid import UUID
from sqlalchemy.orm import Session
import json

from app.config import settings, get_max_upload_bytes
from app.exceptions import AppError
from app.schemas.request import ScanTextRequest, ScanUploadRequest, FeedbackRequest
from app.schemas.response import ScanResponse, ScanListItem, FeedbackResponse, EvidenceItem, ExtractedData, UncertaintyInfo, ModuleScores
from app.db import get_db_session
from app.db.repository import create_scan, get_scan, list_scans, delete_scan, submit_feedback
from app.services import analyze_input
from app.services.privacy import mask_pii
from app.services.image_validator import validate_and_sanitize
from app.services import ocr as ocr_service


router = APIRouter(prefix="/scans", tags=["scans"])


def get_db():
    db = next(get_db_session())
    try:
        yield db
    finally:
        db.close()


def _evidence_for_storage(result) -> List[dict]:
    """Evidence rows with PII masked before storage (spec section 8)."""
    return [
        {
            "id": e["id"],
            "source": e["source"],
            "reason": e["reason"],
            "snippet": mask_pii(e["snippet"])[0] if e["snippet"] else "",
            "weight": e["weight"],
        }
        for e in result.evidence
    ]


def _build_scan_response(scan, result, input_types: List[str], ocr_text: Optional[str] = None) -> ScanResponse:
    """Build the standard scan response from an analysis result."""
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
        ocr_text=ocr_text,
    )


@router.post("", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
async def create_scan_endpoint(request: ScanTextRequest, db: Session = Depends(get_db)):
    if not request.has_input():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one of 'text' or 'url' must be provided"
        )

    # Run analysis
    result = analyze_input(text=request.text, url=request.url)

    input_types = []
    if request.text:
        input_types.append("text")
    if request.url:
        input_types.append("url")

    # Save to database (PII masked before storage, per spec section 8)
    scan = create_scan(
        db,
        input_types=input_types,
        risk_score=result.risk_score,
        risk_band=result.risk_band,
        category=result.category,
        uncertainty=result.uncertainty,
        mode=result.mode,
        masked_text=result.masked_text,
        evidence_list=_evidence_for_storage(result),
    )

    return _build_scan_response(scan, result, input_types)


@router.post("/upload", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
async def upload_scan(
    file: Annotated[UploadFile, File(...)],
    text: Annotated[Optional[str], Form(max_length=10000)] = None,
    url: Annotated[Optional[str], Form(max_length=2048)] = None,
    db: Session = Depends(get_db),
):
    """Accept an image screenshot (PNG/JPEG/WebP), OCR it locally, and
    run the standard analysis pipeline on the extracted text.

    The image is validated by content (never by filename/extension),
    never executed, never served back, and never persisted.
    """
    # Read at most limit + 1 bytes so oversized files are rejected
    # without buffering them entirely (an earlier middleware rejects
    # clearly oversized requests before multipart parsing).
    data = await file.read(get_max_upload_bytes() + 1)
    if len(data) > get_max_upload_bytes():
        raise AppError(
            "FILE_TOO_LARGE",
            f"File exceeds the {settings.max_upload_mb} MB upload limit",
            413,
        )

    image = validate_and_sanitize(data)

    # Local OCR; temporary file is deleted inside run_ocr, even on errors.
    ocr_result = ocr_service.run_ocr(image)

    text = text.strip() if text else None
    url = url.strip() if url else None
    if text == "":
        text = None
    if url == "":
        url = None

    result = analyze_input(
        text=text,
        url=url,
        ocr_text=ocr_result.text,
        ocr_confidence=ocr_result.confidence,
    )

    input_types = []
    if text:
        input_types.append("text")
    if url:
        input_types.append("url")
    input_types.append("image")

    scan = create_scan(
        db,
        input_types=input_types,
        risk_score=result.risk_score,
        risk_band=result.risk_band,
        category=result.category,
        uncertainty=result.uncertainty,
        mode=result.mode,
        masked_text=result.masked_text,
        evidence_list=_evidence_for_storage(result),
    )

    return _build_scan_response(scan, result, input_types, ocr_text=ocr_result.text)


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
        ocr_text=None,  # raw OCR text is not persisted by default
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
