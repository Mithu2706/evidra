from __future__ import annotations

from fastapi import Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from ..auth import read_token
from ..db import get_db
from ..models import EvaluationRound, JudgeAssignment, Submission, User


def _token_from_request(request: Request, token_param: str | None) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    # <img src> and file downloads cannot set headers; allow a query token.
    return token_param


def current_user(
    request: Request,
    token: str | None = Query(default=None, include_in_schema=False),
    db: Session = Depends(get_db),
) -> User:
    raw = _token_from_request(request, token)
    user_id = read_token(raw) if raw else None
    user = db.get(User, user_id) if user_id else None
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    return user


def organizer(user: User = Depends(current_user)) -> User:
    if user.role != "organizer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Organizer access required")
    return user


def judge(user: User = Depends(current_user)) -> User:
    if user.role != "judge":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Judge access required")
    return user


def get_round_for(db: Session, round_id: int, user: User) -> EvaluationRound:
    rnd = db.get(EvaluationRound, round_id)
    if rnd is None or rnd.organization_id != user.organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Round not found")
    return rnd


def get_submission_for(db: Session, submission_id: int, user: User) -> Submission:
    sub = db.get(Submission, submission_id)
    if sub is None or sub.round.organization_id != user.organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")
    if user.role == "judge" and not any(a.judge_id == user.id for a in sub.assignments):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")
    return sub


def get_own_assignment(db: Session, assignment_id: int, user: User) -> JudgeAssignment:
    a = db.get(JudgeAssignment, assignment_id)
    if a is None or a.judge_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")
    return a
