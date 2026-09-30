"""Append-only audit trail helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .models import AuditEvent, User


def record(
    db: Session,
    action: str,
    *,
    actor: User | None = None,
    organization_id: int | None = None,
    round_id: int | None = None,
    submission_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    """Add an audit event to the session. The caller owns the commit."""
    event = AuditEvent(
        organization_id=organization_id if organization_id is not None else (
            actor.organization_id if actor else None
        ),
        round_id=round_id,
        submission_id=submission_id,
        actor_id=actor.id if actor else None,
        actor_label=f"{actor.name} ({actor.role})" if actor else "system",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details or {},
    )
    db.add(event)
    return event
