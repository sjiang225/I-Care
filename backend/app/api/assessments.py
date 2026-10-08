"""Explicitly submitted questionnaires. No chat, model, or legacy score access."""
from __future__ import annotations

import time
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from ..assessments.instruments import INSTRUMENTS, score_assessment, with_pss_reference
from ..db import User, get_db

router = APIRouter(prefix="/api/assessments", tags=["assessments"])


def assessment_user(authorization: str | None = Header(default=None)) -> User | None:
    # An expired/malformed token must not silently turn a save into a guest result.
    if authorization is None:
        return None
    if authorization.lower().startswith("bearer "):
        user = get_db().user_for_token(authorization[7:].strip())
        if user is not None:
            return user
    raise HTTPException(401, "Your sign-in has expired. Please sign in again before saving.")


def private_response(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


class AssessmentSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instrument_id: Literal["phq9", "gad7", "pss10"]
    instrument_version: str = Field(min_length=1, max_length=80)
    answers: list[StrictInt] = Field(min_length=7, max_length=10)
    difficulty: StrictInt | None = Field(default=None, ge=0, le=3)
    submission_id: UUID
    save: StrictBool


@router.get("/instruments")
def instruments() -> dict:
    return {"instruments": list(INSTRUMENTS.values())}


@router.post("", dependencies=[Depends(private_response)])
def submit(req: AssessmentSubmission, user: User | None = Depends(assessment_user)) -> dict:
    instrument = INSTRUMENTS[req.instrument_id]
    if req.instrument_version != instrument["version"]:
        raise HTTPException(409, "This questionnaire has changed. Refresh this page to load the latest version and start again.")
    if req.save and user is None:
        raise HTTPException(401, "Please sign in before saving your result.")
    try:
        result = score_assessment(req.instrument_id, req.answers, req.difficulty)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    if req.save and user is not None:
        try:
            return get_db().save_assessment(
                user.id, str(req.submission_id), req.answers, req.difficulty, result,
            )
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
    # Guest answers are scored in memory and never persisted.
    return {**result, "id": None, "created_at": time.time(), "saved": False}


@router.get("/history", dependencies=[Depends(private_response)])
def history(
    user: User | None = Depends(assessment_user),
    limit: int = Query(default=20, ge=1, le=50),
) -> dict:
    if user is None:
        raise HTTPException(401, "Please sign in to view your saved results.")
    return {"results": [with_pss_reference(result) for result in get_db().assessment_history(user.id, limit)]}
