from sqlalchemy import (
    Column, Integer, String, DateTime, Float, Text, ForeignKey, Index, Boolean
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base
from datetime import datetime, timedelta
from typing import Optional
import uuid


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Scan(Base):
    __tablename__ = "scans"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    input_types = Column(Text, nullable=False)
    risk_score = Column(Integer, nullable=False)
    risk_band = Column(String(20), nullable=False)
    category = Column(String(50), nullable=True)
    uncertainty_json = Column(Text, nullable=True)
    mode = Column(String(20), nullable=False, default="rules")
    masked_text = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=False)

    evidence = relationship("Evidence", back_populates="scan", cascade="all, delete-orphan")
    feedback = relationship("Feedback", back_populates="scan", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_scans_created_at", "created_at"),
        Index("ix_scans_expires_at", "expires_at"),
    )

    def __init__(self, **kwargs):
        if "expires_at" not in kwargs:
            retention_days = 30
            from app.config import settings
            retention_days = settings.retention_days
            kwargs["expires_at"] = datetime.utcnow() + timedelta(days=retention_days)
        super().__init__(**kwargs)


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_id = Column(String(36), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)
    indicator_id = Column(String(100), nullable=False)
    source = Column(String(20), nullable=False)
    reason = Column(Text, nullable=False)
    snippet_masked = Column(Text, nullable=False)
    weight = Column(Integer, nullable=False)

    scan = relationship("Scan", back_populates="evidence")

    __table_args__ = (
        Index("ix_evidence_scan_id", "scan_id"),
    )


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_id = Column(String(36), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)
    helpful = Column(Boolean, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    scan = relationship("Scan", back_populates="feedback")

    __table_args__ = (
        Index("ix_feedback_scan_id", "scan_id"),
    )