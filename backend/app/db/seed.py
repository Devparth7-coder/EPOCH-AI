"""Idempotent seeding: a single local analyst account (no auth in v1)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User

DEFAULT_EMAIL = "analyst@epoch.local"


def ensure_default_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == DEFAULT_EMAIL))
    if user is None:
        user = User(email=DEFAULT_EMAIL, display_name="Local Analyst", role="owner")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
