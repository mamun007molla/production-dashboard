from datetime import timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    ProductionEvent,
    ProductionSource,
    SubmissionAttempt,
)
from app.modules.events.schemas import EventInput


def normalize_payload(event: EventInput) -> dict[str, Any]:
    data = event.raw_payload()
    event_time = event.event_time

    if event_time is not None:
        data["event_time"] = (
            event_time.astimezone(timezone.utc).isoformat()
            if event_time.tzinfo is not None
            else event_time.isoformat()
        )

    return data


def record_attempt(
    db: Session,
    event: EventInput,
    classification: str,
    reason: str | None = None,
    normalized: dict[str, Any] | None = None,
) -> None:
    db.add(
        SubmissionAttempt(
            source_id=event.source_id,
            event_id=event.event_id,
            raw_payload=event.raw_payload(),
            normalized_payload=normalized,
            classification=classification,
            failure_reason=reason,
        )
    )


def result(
    event: EventInput,
    status: str,
    reason: str | None = None,
) -> dict[str, Any]:
    return {
        "source_id": event.source_id,
        "event_id": event.event_id,
        "status": status,
        "reason": reason,
    }


def validate_event(event: EventInput) -> None:
    if not event.source_id or not event.source_id.strip():
        raise ValueError("source_id is required")

    if not event.event_id or not event.event_id.strip():
        raise ValueError("event_id is required")

    if event.type not in {"COUNT", "VOID"}:
        raise ValueError("type must be COUNT or VOID")

    if event.event_time is None:
        raise ValueError("event_time is required")

    if event.event_time.tzinfo is None or event.event_time.utcoffset() is None:
        raise ValueError("event_time must include a timezone")

    if event.type == "COUNT":
        if (
            isinstance(event.quantity, bool)
            or not isinstance(event.quantity, int)
            or event.quantity <= 0
        ):
            raise ValueError("COUNT quantity must be a positive integer")

        if event.target_event_id is not None:
            raise ValueError("COUNT target_event_id must be null or omitted")

    if event.type == "VOID":
        if event.quantity is not None:
            raise ValueError("VOID quantity must be null")

        if not event.target_event_id or not event.target_event_id.strip():
            raise ValueError("VOID target_event_id is required")


def find_existing_event(
    db: Session,
    source_id: str,
    event_id: str,
) -> ProductionEvent | None:
    return db.scalar(
        select(ProductionEvent).where(
            ProductionEvent.source_id == source_id,
            ProductionEvent.event_id == event_id,
        )
    )


def payload_from_existing(
    existing: ProductionEvent,
) -> dict[str, Any]:
    event_time = existing.event_time

    return {
        "source_id": existing.source_id,
        "event_id": existing.event_id,
        "type": existing.type,
        "quantity": existing.quantity,
        "target_event_id": existing.target_event_id,
        "event_time": (
            event_time.astimezone(timezone.utc).isoformat()
            if event_time.tzinfo is not None
            else event_time.isoformat()
        ),
    }


def ensure_source(db: Session, source_id: str) -> None:
    source = db.scalar(
        select(ProductionSource).where(ProductionSource.source_id == source_id)
    )

    if source is None:
        db.add(
            ProductionSource(
                source_id=source_id,
                display_name=source_id,
            )
        )
        db.flush()


def record_rejection(
    db: Session,
    event: EventInput,
    normalized: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    record_attempt(
        db,
        event,
        "REJECTED",
        reason=reason,
        normalized=normalized,
    )
    db.commit()
    return result(event, "REJECTED", reason)


def process_event(
    db: Session,
    event: EventInput,
) -> dict[str, Any]:
    normalized = normalize_payload(event)

    try:
        validate_event(event)

        # The pair (source_id, event_id) identifies one logical event.
        existing = find_existing_event(db, event.source_id, event.event_id)

        if existing is not None:
            if payload_from_existing(existing) == normalized:
                status = "DUPLICATE"
                reason = None
            else:
                status = "CONFLICT"
                reason = "Event ID already exists with different data"

            record_attempt(
                db,
                event,
                status,
                reason=reason,
                normalized=normalized,
            )
            db.commit()
            return result(event, status, reason)

        ensure_source(db, event.source_id)

        if event.type == "COUNT":
            production_event = ProductionEvent(
                source_id=event.source_id,
                event_id=event.event_id,
                type="COUNT",
                quantity=event.quantity,
                target_event_id=None,
                event_time=event.event_time,
                status="ACCEPTED",
            )
            db.add(production_event)
            db.flush()

            record_attempt(
                db,
                event,
                "ACCEPTED",
                normalized=normalized,
            )

            # Resolve pending VOID events in insertion order.
            pending_voids = list(
                db.scalars(
                    select(ProductionEvent)
                    .where(
                        ProductionEvent.source_id == event.source_id,
                        ProductionEvent.target_event_id == event.event_id,
                        ProductionEvent.type == "VOID",
                        ProductionEvent.status == "PENDING_REFERENCE",
                    )
                    .order_by(
                        ProductionEvent.received_at,
                        ProductionEvent.id,
                    )
                ).all()
            )

            for index, pending_void in enumerate(pending_voids):
                if index == 0:
                    pending_void.status = "ACCEPTED"

                    db.add(
                        SubmissionAttempt(
                            source_id=pending_void.source_id,
                            event_id=pending_void.event_id,
                            raw_payload={
                                "source_id": pending_void.source_id,
                                "event_id": pending_void.event_id,
                                "type": "VOID",
                                "quantity": None,
                                "target_event_id": pending_void.target_event_id,
                                "event_time": pending_void.event_time.isoformat(),
                            },
                            normalized_payload=None,
                            classification="RESOLVED",
                            failure_reason=None,
                        )
                    )
                else:
                    pending_void.status = "REJECTED"

                    db.add(
                        SubmissionAttempt(
                            source_id=pending_void.source_id,
                            event_id=pending_void.event_id,
                            raw_payload={
                                "source_id": pending_void.source_id,
                                "event_id": pending_void.event_id,
                                "type": "VOID",
                                "quantity": None,
                                "target_event_id": pending_void.target_event_id,
                                "event_time": pending_void.event_time.isoformat(),
                            },
                            normalized_payload=None,
                            classification="REJECTED",
                            failure_reason=("Another VOID already reversed this COUNT"),
                        )
                    )

            db.commit()
            return result(event, "ACCEPTED")

        # VOID: its target must be a COUNT from the same source.
        target = find_existing_event(
            db,
            event.source_id,
            event.target_event_id,
        )

        if target is not None and target.type != "COUNT":
            return record_rejection(
                db,
                event,
                normalized,
                "VOID target must be a COUNT event",
            )

        # The first stored valid VOID targeting a COUNT wins.
        existing_void = db.scalar(
            select(ProductionEvent)
            .where(
                ProductionEvent.source_id == event.source_id,
                ProductionEvent.target_event_id == event.target_event_id,
                ProductionEvent.type == "VOID",
                ProductionEvent.status.in_(["ACCEPTED", "PENDING_REFERENCE"]),
            )
            .order_by(
                ProductionEvent.received_at,
                ProductionEvent.id,
            )
        )

        if existing_void is not None:
            return record_rejection(
                db,
                event,
                normalized,
                "Another VOID already targets this COUNT",
            )

        if target is not None and target.status != "ACCEPTED":
            return record_rejection(
                db,
                event,
                normalized,
                "Target COUNT is not eligible for reversal",
            )

        void_status = "ACCEPTED" if target is not None else "PENDING_REFERENCE"

        db.add(
            ProductionEvent(
                source_id=event.source_id,
                event_id=event.event_id,
                type="VOID",
                quantity=None,
                target_event_id=event.target_event_id,
                event_time=event.event_time,
                status=void_status,
            )
        )

        record_attempt(
            db,
            event,
            void_status,
            normalized=normalized,
        )
        db.commit()

        return result(event, void_status)

    except ValueError as exc:
        db.rollback()
        return record_rejection(db, event, normalized, str(exc))

    except Exception:
        db.rollback()
        raise
