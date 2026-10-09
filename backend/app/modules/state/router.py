from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.dependencies import get_db
from app.database.models import (
    Acknowledgement,
    ProductionEvent,
    SubmissionAttempt,
)

router = APIRouter(prefix="/api/state", tags=["State"])


def calculate_net_total(events: list[ProductionEvent]) -> int:
    """Calculate net production after accepted VOID events.

    A VOID reverses a COUNT only when both source_id and event_id match.
    """
    reversed_targets = {
        (event.source_id, event.target_event_id)
        for event in events
        if (
            event.type == "VOID"
            and event.status == "ACCEPTED"
            and event.target_event_id is not None
        )
    }

    return sum(
        event.quantity or 0
        for event in events
        if (
            event.type == "COUNT"
            and event.status == "ACCEPTED"
            and (event.source_id, event.event_id) not in reversed_targets
        )
    )


def serialize_event(event: ProductionEvent) -> dict:
    """Convert a production event into a JSON-compatible dictionary."""
    return {
        "source_id": event.source_id,
        "event_id": event.event_id,
        "type": event.type,
        "quantity": event.quantity,
        "target_event_id": event.target_event_id,
        "status": event.status,
        "event_time": (event.event_time.isoformat() if event.event_time else None),
        "received_at": (event.received_at.isoformat() if event.received_at else None),
    }


@router.get("")
def get_state(
    view: Literal["summary", "pending", "exceptions"] = Query(default="summary"),
    source_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Return production summary, pending acknowledgements, or exceptions."""

    event_query = select(ProductionEvent).order_by(
        ProductionEvent.received_at,
        ProductionEvent.id,
    )

    attempt_query = select(SubmissionAttempt).order_by(
        SubmissionAttempt.received_at,
        SubmissionAttempt.id,
    )

    if source_id:
        event_query = event_query.where(ProductionEvent.source_id == source_id)

        attempt_query = attempt_query.where(SubmissionAttempt.source_id == source_id)

    events = list(db.scalars(event_query).all())
    attempts = list(db.scalars(attempt_query).all())

    acknowledged_ids = set(db.scalars(select(Acknowledgement.event_pk)).all())

    # Calculate the net production using source-aware event identities.
    net_total = calculate_net_total(events)

    accepted_events = [event for event in events if event.status == "ACCEPTED"]

    pending_events = [
        event for event in accepted_events if event.id not in acknowledged_ids
    ]

    unresolved_events = [
        event for event in events if event.status == "PENDING_REFERENCE"
    ]

    duplicate_attempts = [
        attempt for attempt in attempts if attempt.classification == "DUPLICATE"
    ]

    conflict_attempts = [
        attempt for attempt in attempts if attempt.classification == "CONFLICT"
    ]

    summary = {
        "net_total": net_total,
        "processed_events": len(accepted_events),
        "pending_ack": len(pending_events),
        "unresolved": len(unresolved_events),
        "duplicates": len(duplicate_attempts),
        "conflicts": len(conflict_attempts),
    }

    if view == "pending":
        return {
            "summary": summary,
            "items": [serialize_event(event) for event in pending_events],
        }

    if view == "exceptions":
        return {
            "summary": summary,
            "unresolved": [serialize_event(event) for event in unresolved_events],
            "duplicates": [
                {
                    "source_id": attempt.source_id,
                    "event_id": attempt.event_id,
                    "reason": attempt.failure_reason,
                }
                for attempt in duplicate_attempts
            ],
            "conflicts": [
                {
                    "source_id": attempt.source_id,
                    "event_id": attempt.event_id,
                    "reason": attempt.failure_reason,
                }
                for attempt in conflict_attempts
            ],
        }

    return summary
