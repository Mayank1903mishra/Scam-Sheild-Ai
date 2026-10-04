from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
import json

from app.db.models import Scan, Evidence, Feedback
from app.config import settings


def create_scan(
    db: Session,
    *,
    input_types: List[str],
    risk_score: int,
    risk_band: str,
    category: Optional[str],
    uncertainty: Dict[str, Any],
    mode: str,
    masked_text: Optional[str] = None,
    evidence_list: Optional[List[Dict[str, Any]]] = None,
) -> Scan:
    expires_at = datetime.utcnow() + timedelta(days=settings.retention_days)

    scan = Scan(
        input_types=json.dumps(input_types),
        risk_score=risk_score,
        risk_band=risk_band,
        category=category,
        uncertainty_json=json.dumps(uncertainty) if uncertainty else None,
        mode=mode,
        masked_text=masked_text if settings.store_content else None,
        expires_at=expires_at,
    )
    db.add(scan)
    db.flush()

    if evidence_list:
        for ev in evidence_list:
            evidence = Evidence(
                scan_id=scan.id,
                indicator_id=ev["id"],
                source=ev["source"],
                reason=ev["reason"],
                snippet_masked=ev["snippet"],
                weight=ev["weight"],
            )
            db.add(evidence)

    db.commit()
    db.refresh(scan)
    return scan


def get_scan(db: Session, scan_id: str) -> Optional[Scan]:
    return db.query(Scan).filter(Scan.id == scan_id).first()


def list_scans(db: Session, limit: int = 50, offset: int = 0) -> List[Scan]:
    return (
        db.query(Scan)
        .order_by(Scan.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )


def delete_scan(db: Session, scan_id: str) -> bool:
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        return False
    db.delete(scan)
    db.commit()
    return True


def submit_feedback(db: Session, scan_id: str, helpful: bool, comment: Optional[str]) -> Optional[Feedback]:
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        return None

    feedback = Feedback(scan_id=scan_id, helpful=helpful, comment=comment)
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def cleanup_expired_scans(db: Session) -> int:
    now = datetime.utcnow()
    expired = db.query(Scan).filter(Scan.expires_at < now).all()
    count = len(expired)
    for scan in expired:
        db.delete(scan)
    db.commit()
    return count