
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.dependencies import get_db
from app.database.models import (
    Acknowledgement,
    ProductionEvent,
)

router = APIRouter(
    prefix="/api/ack",
    tags=["Acknowledgements"],
)


class AckRequest(BaseModel):
    event_ids: list[str]


@router.post("")
def acknowledge_events(
    payload: AckRequest,
    source_id: str,
    db: Session = Depends(get_db),
):
    results = []

    for event_id in payload.event_ids:
        event = db.scalar(
            select(ProductionEvent)
            .where(
                ProductionEvent.source_id == source_id,
                ProductionEvent.event_id == event_id,
            )
            .with_for_update()
        )

        if event is None:
            results.append({
                "event_id": event_id,
                "status": "NOT_FOUND",
            })
            continue

        existing_ack = db.scalar(
            select(Acknowledgement).where(
                Acknowledgement.event_pk == event.id
            )
        )

        if existing_ack is not None:
            results.append({
                "event_id": event_id,
                "status": "ALREADY_ACKED",
            })
            continue

        if event.status != "ACCEPTED":
            results.append({
                "event_id": event_id,
                "status": "NOT_READY",
            })
            continue

        acknowledgement = Acknowledgement(
            event_pk=event.id,
            acknowledged_at=datetime.now(timezone.utc),
        )
        db.add(acknowledgement)

        results.append({
            "event_id": event_id,
            "status": "ACKED",
        })

    db.commit()

    return {
        "source_id": source_id,
        "results": results,
    }
