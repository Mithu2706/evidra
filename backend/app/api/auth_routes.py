from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..auth import issue_token, verify_password
from ..config import get_settings
from ..db import get_db
from ..models import User
from .deps import current_user
from .serializers import user_out

router = APIRouter(prefix="/api/auth", tags=["auth"])

DEMO_PASSWORD = "evidra-demo"

# Seeded accounts a guest can enter as when EVIDRA_DEMO_MODE is on.
DEMO_GUEST_ACCOUNTS = {
    "judge": "marcus@demo.evidra.app",
    "organizer": "dana@demo.evidra.app",
}


class LoginIn(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.strip().lower()))
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    audit.record(db, "auth.login", actor=user, entity_type="user", entity_id=user.id)
    db.commit()
    return {"token": issue_token(user.id), "user": user_out(user)}


class DemoLoginIn(BaseModel):
    role: Literal["judge", "organizer"] = "judge"


@router.post("/demo")
def demo_login(body: DemoLoginIn | None = None, db: Session = Depends(get_db)):
    """Password-less guest sign-in for the public demo (only when EVIDRA_DEMO_MODE=true).

    Returns the same {token, user} payload as /login.
    """
    if not get_settings().demo_mode:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    role = body.role if body else "judge"
    user = db.scalar(select(User).where(User.email == DEMO_GUEST_ACCOUNTS[role]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Demo data is not ready yet. Try again in a moment.")
    audit.record(db, "auth.login", actor=user, entity_type="user", entity_id=user.id, details={"method": "guest_demo"})
    db.commit()
    return {"token": issue_token(user.id), "user": user_out(user)}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_out(user)


@router.get("/demo-accounts")
def demo_accounts(db: Session = Depends(get_db)):
    """Seeded demo accounts for the sign-in screen (disabled in production)."""
    if get_settings().environment == "production":
        return {"accounts": [], "password": None}
    users = db.scalars(select(User).where(User.email.like("%@demo.evidra.app")).order_by(User.role.desc(), User.id)).all()
    return {"accounts": [user_out(u) for u in users], "password": DEMO_PASSWORD}
