from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EventInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_id: str | None = None
    event_id: str | None = None
    type: str | None = None
    quantity: int | None = None
    target_event_id: str | None = None
    event_time: datetime | None = None

    def raw_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
