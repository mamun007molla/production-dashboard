from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.modules.mqtt.service import (
    canonical_json,
    challenge_response,
    parse_expiry,
    payload_digest,
    process_challenge,
)


def test_canonical_json_ignores_dictionary_key_order():
    first = {"candidate_id": "11", "command": "PROCESS_EVENTS"}
    second = {"command": "PROCESS_EVENTS", "candidate_id": "11"}

    assert canonical_json(first) == canonical_json(second)


def test_payload_digest_ignores_dictionary_key_order():
    first = {"candidate_id": "11", "command": "PROCESS_EVENTS"}
    second = {"command": "PROCESS_EVENTS", "candidate_id": "11"}

    assert payload_digest(first) == payload_digest(second)


def test_payload_digest_changes_when_payload_changes():
    first = {"challenge_id": "CH-1", "command": "PROCESS_EVENTS"}
    second = {"challenge_id": "CH-1", "command": "OTHER_COMMAND"}

    assert payload_digest(first) != payload_digest(second)


def test_parse_expiry_accepts_utc_timestamp():
    expiry = parse_expiry("2027-01-01T10:00:00Z")

    assert expiry.tzinfo is not None
    assert expiry.utcoffset().total_seconds() == 0


def test_parse_expiry_rejects_timestamp_without_timezone():
    with pytest.raises(ValueError, match="timezone"):
        parse_expiry("2027-01-01T10:00:00")


def test_parse_expiry_rejects_invalid_timestamp():
    with pytest.raises(ValueError, match="valid ISO 8601"):
        parse_expiry("not-a-date")


def test_challenge_response_includes_six_summary_metrics():
    summary = {
        "net_total": 12,
        "processed_events": 5,
        "pending_ack": 3,
        "unresolved": 0,
        "duplicates": 1,
        "conflicts": 1,
    }

    response = challenge_response(
        "CH-1",
        "COMPLETED",
        results=[],
        summary=summary,
    )

    assert response["challenge_id"] == "CH-1"
    assert response["status"] == "COMPLETED"
    assert response["summary"] == summary
    assert len(response["summary"]) == 6


def test_challenge_response_includes_error_when_provided():
    response = challenge_response(
        "CH-1",
        "FAILED",
        error="CHALLENGE_CONFLICT",
    )

    assert response["error"] == "CHALLENGE_CONFLICT"


def test_same_challenge_replay_returns_stored_response():
    payload = {
        "challenge_id": "CH-REPLAY",
        "candidate_id": "11",
        "protocol_version": "1.0",
        "command": "PROCESS_EVENTS",
        "expires_at": "2027-01-01T10:00:00Z",
        "events": [{"source_id": "LINE-01", "event_id": "EV-1"}],
    }

    stored_response = {
        "challenge_id": "CH-REPLAY",
        "status": "COMPLETED",
        "results": [],
        "summary": {
            "net_total": 0,
            "processed_events": 0,
            "pending_ack": 0,
            "unresolved": 0,
            "duplicates": 0,
            "conflicts": 0,
        },
    }

    existing = MagicMock()
    existing.body_digest = payload_digest(payload)
    existing.response_payload = stored_response

    db = MagicMock()
    db.scalar.return_value = existing

    response = process_challenge(db, payload)

    assert response == stored_response
    db.commit.assert_not_called()


def test_same_challenge_id_with_different_payload_is_rejected():
    payload = {
        "challenge_id": "CH-CONFLICT",
        "candidate_id": "11",
        "protocol_version": "1.0",
        "command": "PROCESS_EVENTS",
        "expires_at": "2027-01-01T10:00:00Z",
        "events": [],
    }

    changed_payload = {
        **payload,
        "command": "OTHER_COMMAND",
    }

    existing = MagicMock()
    existing.body_digest = payload_digest(payload)
    existing.response_payload = {"status": "COMPLETED"}

    db = MagicMock()
    db.scalar.return_value = existing

    response = process_challenge(db, changed_payload)

    assert response["status"] == "FAILED"
    assert response["error"] == "CHALLENGE_CONFLICT"
    db.commit.assert_not_called()


def test_missing_challenge_id_is_rejected():
    db = MagicMock()

    response = process_challenge(db, {"command": "PROCESS_EVENTS"})

    assert response["status"] == "FAILED"
    assert response["challenge_id"] is None
    assert response["error"] == "challenge_id is required"
    db.scalar.assert_not_called()


def test_challenge_response_includes_rejected_submissions_metric():
    summary = {
        "net_total": 10,
        "processed_events": 2,
        "pending_ack": 1,
        "unresolved": 0,
        "duplicates": 1,
        "conflicts": 0,
        "rejected_submissions": 3,
    }

    response = challenge_response(
        "CH-REJECTED",
        "COMPLETED",
        summary=summary,
    )

    assert response["summary"]["rejected_submissions"] == 3
