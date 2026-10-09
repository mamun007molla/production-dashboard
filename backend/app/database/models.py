from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ProductionSource(Base):
    __tablename__ = "production_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(100), unique=True, index=True
    )
    display_name: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class ProductionEvent(Base):
    __tablename__ = "production_events"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "event_id",
            name="uq_production_event_source_event",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("production_sources.source_id"), index=True
    )
    event_id: Mapped[str] = mapped_column(String(150))
    type: Mapped[str] = mapped_column(String(10))
    quantity: Mapped[int | None] = mapped_column(Integer)
    target_event_id: Mapped[str | None] = mapped_column(String(150))
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    status: Mapped[str] = mapped_column(
        String(30), default="RECEIVED", index=True
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


class SubmissionAttempt(Base):
    __tablename__ = "submission_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str | None] = mapped_column(
        String(100), index=True
    )
    event_id: Mapped[str | None] = mapped_column(
        String(150), index=True
    )
    raw_payload: Mapped[dict] = mapped_column(JSON)
    normalized_payload: Mapped[dict | None] = mapped_column(JSON)
    classification: Mapped[str] = mapped_column(
        String(30), index=True
    )
    failure_reason: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class Acknowledgement(Base):
    __tablename__ = "acknowledgements"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_pk: Mapped[int] = mapped_column(
        ForeignKey("production_events.id"), index=True
    )
    acknowledged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    acknowledged_by: Mapped[str | None] = mapped_column(String(100))


class MqttChallenge(Base):
    __tablename__ = "mqtt_challenges"

    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[str] = mapped_column(
        String(200), unique=True, index=True
    )
    candidate_id: Mapped[str] = mapped_column(String(100))
    body_digest: Mapped[str] = mapped_column(String(64))
    request_payload: Mapped[dict] = mapped_column(JSON)
    response_payload: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(
        String(30), default="RECEIVED"
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_error: Mapped[str | None] = mapped_column(Text)
