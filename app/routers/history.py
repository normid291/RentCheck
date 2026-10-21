"""A signed-in user's own analyses: list, open, rename, delete.

Every route requires a session and every query is filtered by the owner inside
app/services/analysis_store.py, so one account can never read or touch another's
records. An id that is not yours returns 404, the same as one that does not
exist at all — being told "that exists but is not yours" would leak the fact that
somebody else holds that analysis.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db import User
from app.services import analysis_store
from app.services.auth import require_user

router = APIRouter()

_NOT_FOUND = "We could not find that analysis."


class RenameIn(BaseModel):
    title: str = Field(max_length=120)


@router.get("/analyses")
def list_analyses(
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """The user's saved analyses, newest first."""
    analyses = analysis_store.list_for_user(db, user, limit=limit)
    return {"status": "ok", "count": len(analyses), "analyses": analyses}


@router.get("/analyses/{analysis_id}")
def get_analysis(
    analysis_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    analysis = analysis_store.get_owned(db, user, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    return {"status": "ok", "analysis": analysis_store.detail_of(analysis)}


@router.patch("/analyses/{analysis_id}")
def rename_analysis(
    analysis_id: str,
    payload: RenameIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    analysis = analysis_store.rename(db, user, analysis_id, payload.title)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    return {"status": "ok", "analysis": analysis_store.summary_of(analysis)}


@router.delete("/analyses/{analysis_id}")
def delete_analysis(
    analysis_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Remove the analysis and its agreement text, permanently."""
    if not analysis_store.delete(db, user, analysis_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    return {"status": "ok", "deleted": analysis_id}
