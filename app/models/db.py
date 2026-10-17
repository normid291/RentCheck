"""
Database models for RentCheck.
Three tables: agreements (raw uploaded docs), analyses (AI output per agreement),
clause_reference (curated seed data of Nigerian rental norms — the backbone of
the whole analysis pipeline).
"""
import uuid
import enum
from datetime import datetime

from sqlalchemy import Column, String, Text, Integer, Enum, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class SourceType(str, enum.Enum):
    pdf = "pdf"
    docx = "docx"
    text = "text"
    image = "image"


class Severity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Agreement(Base):
    __tablename__ = "agreements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type = Column(Enum(SourceType), nullable=False)
    raw_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    analyses = relationship("Analysis", back_populates="agreement")


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agreement_id = Column(UUID(as_uuid=True), ForeignKey("agreements.id"), nullable=False)
    flagged_clauses = Column(JSONB, nullable=False, default=list)
    missing_protections = Column(JSONB, nullable=False, default=list)
    questions_to_ask = Column(JSONB, nullable=False, default=list)
    risk_score = Column(Integer, default=0)
    summary_text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    agreement = relationship("Agreement", back_populates="analyses")


class ClauseReference(Base):
    """
    Curated seed data: the known norms and red-flag patterns for common
    Nigerian tenancy clause types. This is what grounds the small AI model's
    judgments instead of asking it to reason about rental law cold.
    """
    __tablename__ = "clause_reference"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clause_type = Column(String, nullable=False, index=True)
    norm_description = Column(Text, nullable=False)
    red_flag_pattern = Column(Text, nullable=False)
    severity_default = Column(Enum(Severity), default=Severity.medium)
    keywords = Column(JSONB, nullable=False, default=list)  # for simple matching
