import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    Acknowledgement,
    MqttChallenge,
    ProductionEvent,
    SubmissionAttempt,
)
from app.database.session import settings
from app.modules.events.schemas import EventInput
from app.modules.events.service import process_event
from app.modules.state.router import calculate_net_total

logger = logging.getLogger(__name__)


def canonical_json(payload: dict[str, Any]) -> str:
    """Serialize JSON consistently so key order does not affect the digest."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def payload_digest(payload: dict[str, Any]) -> str:
    """Return a SHA-256 digest of a canonical JSON payload."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def parse_expiry(value: Any) -> datetime:
    """Parse a timezone-aware ISO 8601 expiry timestamp."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("expires_at must be an ISO 8601 timestamp")

    try:
        expiry = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("expires_at is not a valid ISO 8601 timestamp") from exc

    if expiry.tzinfo is None or expiry.utcoffset() is None:
        raise ValueError("expires_at must include a timezone")

    return expiry.astimezone(timezone.utc)


def get_summary(db: Session) -> dict[str, int]:
    """Calculate the six dashboard metrics from persisted data."""
    events = list(db.scalars(select(ProductionEvent)).all())

    attempts = list(db.scalars(select(SubmissionAttempt)).all())

    acknowledged_ids = set(db.scalars(select(Acknowledgement.event_pk)).all())

    accepted_events = [event for event in events if event.status == "ACCEPTED"]

    pending_ack = [
        event for event in accepted_events if event.id not in acknowledged_ids
    ]

    unresolved_events = [
        event for event in events if event.status == "PENDING_REFERENCE"
    ]

    duplicates = [
        attempt for attempt in attempts if attempt.classification == "DUPLICATE"
    ]

    conflicts = [
        attempt for attempt in attempts if attempt.classification == "CONFLICT"
    ]

    return {
        "net_total": calculate_net_total(events),
        "processed_events": len(accepted_events),
        "pending_ack": len(pending_ack),
        "unresolved": len(unresolved_events),
        "duplicates": len(duplicates),
        "conflicts": len(conflicts),
    }


def challenge_response(
    challenge_id: str | None,
    status: str,
    results: list[dict[str, Any]] | None = None,
    error: str | None = None,
    summary: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Build a consistent MQTT challenge response."""
    response: dict[str, Any] = {
        "challenge_id": challenge_id,
        "status": status,
        "results": results if results is not None else [],
    }

    if summary is not None:
        response["summary"] = summary

    if error:
        response["error"] = error

    return response


def process_challenge(
    db: Session,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Validate, process, persist, and respond to an MQTT challenge."""

    challenge_id = payload.get("challenge_id")

    if not isinstance(challenge_id, str) or not challenge_id.strip():
        return challenge_response(
            None,
            "FAILED",
            error="challenge_id is required",
        )

    digest = payload_digest(payload)

    # Check an existing challenge before processing its events.
    existing = db.scalar(
        select(MqttChallenge).where(MqttChallenge.challenge_id == challenge_id)
    )

    if existing is not None:
        if existing.body_digest != digest:
            return challenge_response(
                challenge_id,
                "FAILED",
                error="CHALLENGE_CONFLICT",
            )

        if existing.response_payload is not None:
            return existing.response_payload

        return challenge_response(
            challenge_id,
            "FAILED",
            error="Challenge has no stored response; manual recovery is required",
        )

    candidate_id = payload.get("candidate_id")
    protocol_version = payload.get("protocol_version")
    command = payload.get("command")

    if candidate_id != settings.mqtt_candidate_id:
        return challenge_response(
            challenge_id,
            "FAILED",
            error="Invalid candidate_id",
        )

    if not isinstance(protocol_version, str) or not protocol_version.strip():
        return challenge_response(
            challenge_id,
            "FAILED",
            error="protocol_version is required",
        )

    if command != "PROCESS_EVENTS":
        return challenge_response(
            challenge_id,
            "FAILED",
            error="Unsupported command",
        )

    try:
        expiry = parse_expiry(payload.get("expires_at"))
    except ValueError as exc:
        return challenge_response(
            challenge_id,
            "FAILED",
            error=str(exc),
        )

    if expiry <= datetime.now(timezone.utc):
        return challenge_response(
            challenge_id,
            "FAILED",
            error="Challenge has expired",
        )

    events = payload.get("events")

    if not isinstance(events, list) or not events:
        return challenge_response(
            challenge_id,
            "FAILED",
            error="events must be a non-empty list",
        )

    if any(not isinstance(item, dict) for item in events):
        return challenge_response(
            challenge_id,
            "FAILED",
            error="Every event must be a JSON object",
        )

    challenge = MqttChallenge(
        challenge_id=challenge_id,
        candidate_id=candidate_id,
        body_digest=digest,
        request_payload=payload,
        status="PROCESSING",
        expires_at=expiry,
    )

    db.add(challenge)

    try:
        db.commit()
    except Exception:
        db.rollback()

        # A concurrent request may have inserted the challenge first.
        existing = db.scalar(
            select(MqttChallenge).where(MqttChallenge.challenge_id == challenge_id)
        )

        if existing is not None:
            if existing.body_digest != digest:
                return challenge_response(
                    challenge_id,
                    "FAILED",
                    error="CHALLENGE_CONFLICT",
                )

            if existing.response_payload is not None:
                return existing.response_payload

            return challenge_response(
                challenge_id,
                "FAILED",
                error="Challenge is already being processed",
            )

        raise

    results: list[dict[str, Any]] = []

    for item in events:
        try:
            event = EventInput.model_validate(item)
            result = process_event(db, event)
            results.append(result)

        except Exception:
            db.rollback()

            logger.exception(
                "Failed to process an event in challenge %s",
                challenge_id,
            )

            results.append(
                {
                    "source_id": item.get("source_id"),
                    "event_id": item.get("event_id"),
                    "status": "REJECTED",
                    "reason": "Event could not be processed",
                }
            )

    try:
        summary = get_summary(db)

        response = challenge_response(
            challenge_id,
            "COMPLETED",
            results=results,
            summary=summary,
        )

        stored_challenge = db.scalar(
            select(MqttChallenge).where(MqttChallenge.challenge_id == challenge_id)
        )

        if stored_challenge is None:
            raise RuntimeError("Challenge record disappeared during processing")

        stored_challenge.response_payload = response
        stored_challenge.status = "COMPLETED"
        stored_challenge.processed_at = datetime.now(timezone.utc)

        db.commit()

        return response

    except Exception:
        db.rollback()

        logger.exception(
            "Failed to store the response for challenge %s",
            challenge_id,
        )

        return challenge_response(
            challenge_id,
            "FAILED",
            results=results,
            error="Failed to store challenge response",
        )
