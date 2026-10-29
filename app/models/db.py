"""
Database models for Tenura.

Tables:
  agreements        - raw text of a submitted agreement (analysed content lives
                      in analyses; deleted with it so the text never outlives
                      the analysis it belongs to)
  analyses          - the result of one run, optionally owned by a user
  clause_reference  - curated seed data of Nigerian rental norms (the backbone of
                      the analysis pipeline)
  users             - accounts, with argon2 password hashes (NULL when the
                      account was created through Google sign-in)
  otp_codes         - hashed, single-use email codes for verification and reset

Ownership notes:
  - `analyses.user_id` is NULL for rows created before accounts existed. Those
    rows are unreachable (nothing selects them) and are kept rather than deleted.
  - Guest analyses are not stored at all: persistence happens only when a user
    is authenticated (see app/routers/agreements.py).
  - We never store the uploaded file, only the text extracted from it.
"""
import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# How a clause norm is grounded.
#   market_norm - common market practice. Honest about what it is: we do NOT
#                 claim it is law. Current seed data is ALL market_norm and its
#                 sources are unverified pending human legal review.
#   statute     - a specific provision of a named law. Reserved for norms a
#                 qualified reviewer has confirmed; the seed data contains none.
LEGAL_BASIS_MARKET_NORM = "market_norm"
LEGAL_BASIS_STATUTE = "statute"
LEGAL_BASIS_VALUES = (LEGAL_BASIS_MARKET_NORM, LEGAL_BASIS_STATUTE)


class SourceType(str, enum.Enum):
    pdf = "pdf"
    docx = "docx"
    text = "text"
    image = "image"


class Severity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class OtpPurpose(str, enum.Enum):
    """What a one-time code is for. Kept separate so a code issued to verify an
    email cannot be replayed against the password-reset flow, and vice versa."""

    verify_email = "verify_email"
    reset_password = "reset_password"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Stored normalised: lowercased and trimmed, so lookups are exact and two
    # accounts cannot differ only by case.
    email = Column(String(320), nullable=False, unique=True, index=True)
    # NULL for an account that only ever signed in with Google. Such an account
    # has no password to compare against, so password login refuses it — which
    # is why the column is nullable rather than holding an unguessable hash that
    # would only ever be a lie in the database.
    password_hash = Column(Text, nullable=True)
    # Google's stable account id (`sub`). Kept so a returning Google user is
    # matched by identity rather than by email, which can be renamed. NULL for
    # accounts that have never used Google sign-in.
    google_sub = Column(String(255), nullable=True)
    is_verified = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    verified_at = Column(DateTime, nullable=True)

    analyses = relationship("Analysis", back_populates="user")
    otp_codes = relationship("OtpCode", back_populates="user")

    # Unique index rather than a column-level unique: it is created explicitly
    # here so the model and the migration in app/migrations.py agree on the name,
    # and so a fresh database and an upgraded one end up identical. Postgres
    # treats NULLs as distinct, so many accounts may have no google_sub.
    __table_args__ = (Index("uq_users_google_sub", "google_sub", unique=True),)


class OtpCode(Base):
    __tablename__ = "otp_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_otp_codes_user_id_users"),
        nullable=False,
        index=True,
    )
    purpose = Column(Enum(OtpPurpose), nullable=False, default=OtpPurpose.verify_email)
    # Hashed with the password hasher. Single use, short lived, attempt capped —
    # a 6-digit code is only 10^6 wide, so an unsalted fast hash would not be
    # good enough if the database leaked.
    code_hash = Column(Text, nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    consumed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="otp_codes")


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
    # Nullable: rows written before accounts existed have no owner.
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_analyses_user_id_users"),
        nullable=True,
        index=True,
    )
    # A short label for the history list. Derived from the agreement's first
    # meaningful line; the user can rename it.
    title = Column(String(120), nullable=True)
    flagged_clauses = Column(JSONB, nullable=False, default=list)
    missing_protections = Column(JSONB, nullable=False, default=list)
    questions_to_ask = Column(JSONB, nullable=False, default=list)
    risk_score = Column(Integer, default=0)
    summary_text = Column(Text)
    # Deterministic, plain-language next step shown in the history list. Derived
    # from the counts — never generated by the model, so it cannot overstate.
    recommendation = Column(Text)
    # --- Phase 1 provenance / coverage (all nullable so older rows stay valid).
    # Which jurisdiction pack judged this run, and how complete the run was.
    # `coverage` is the fraction of the agreement's clauses that actually got a
    # verdict; a low number is why a run must never be shown as "low risk".
    jurisdiction = Column(String(16), nullable=True)
    coverage = Column(Float, nullable=True)
    degraded = Column(Boolean, nullable=False, default=False, server_default="false")
    # What produced the result, so a stored analysis can be explained later.
    pipeline_version = Column(String(20), nullable=True)
    prompt_version = Column(String(20), nullable=True)
    model_id = Column(String(120), nullable=True)
    clause_reference_version = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    agreement = relationship("Agreement", back_populates="analyses")
    user = relationship("User", back_populates="analyses")

    # The history page filters on user_id and sorts by created_at. A composite
    # index serves both in one pass (Postgres can walk it backwards for DESC).
    __table_args__ = (
        Index("ix_analyses_user_created", "user_id", "created_at"),
    )


class ClauseReference(Base):
    """
    Curated seed data: the known norms and red-flag patterns for common
    Nigerian tenancy clause types. This is what grounds the small AI model's
    judgments instead of asking it to reason about rental law cold.

    Provenance is explicit. Every seeded norm currently carries
    `legal_basis = "market_norm"`: it describes common Nigerian market practice,
    NOT a verified provision of law. The `source_*` fields and `reviewed_*`
    fields are the places a human legal reviewer fills in later; until then they
    are NULL and the UI must say "common practice", never "the law requires".
    """

    __tablename__ = "clause_reference"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clause_type = Column(String, nullable=False, index=True)
    # Which jurisdiction pack this norm belongs to. "NG" is the generic Nigerian
    # package; "NG-LA"/"NG-FC" would be state-specific overrides. A document in
    # NG-* is matched against its own jurisdiction plus the generic "NG" rows.
    jurisdiction = Column(String(16), nullable=True, default="NG", index=True)
    norm_description = Column(Text, nullable=False)
    red_flag_pattern = Column(Text, nullable=False)
    severity_default = Column(Enum(Severity), default=Severity.medium)
    keywords = Column(JSONB, nullable=False, default=list)  # for simple matching
    # "market_norm" or "statute" (see LEGAL_BASIS_* constants).
    legal_basis = Column(String(20), nullable=True, default="market_norm")
    # Cited source. Empty for market_norm rows until a reviewer supplies one.
    source_title = Column(Text, nullable=True)
    source_section = Column(Text, nullable=True)
    source_url = Column(Text, nullable=True)
    source_retrieved_at = Column(DateTime, nullable=True)
    source_quote = Column(Text, nullable=True)
    # Plain-language "what this means if you accept it", shown with a flag.
    consequence = Column(Text, nullable=True)
    # Which party the norm protects. Used to avoid judging one party's clause
    # against another party's protection.
    applies_to = Column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    # A fair alternative the tenant can propose, and a question to ask.
    counter_clause = Column(Text, nullable=True)
    tenant_question = Column(Text, nullable=True)
    # Bumped when the norm wording changes, so stored analyses can be tied to
    # the exact version that judged them.
    version = Column(String(20), nullable=False, default="1", server_default="1")
    reviewed_by = Column(String(120), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "clause_type",
            "jurisdiction",
            "version",
            name="uq_clause_reference_type_juris_version",
        ),
    )
