from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.dependencies import get_db
from app.modules.events.schemas import EventInput
from app.modules.events.service import process_event

router = APIRouter(prefix="/api/events", tags=["Events"])


@router.post("")
def submit_events(
    payload: Any = Body(...),
    db: Session = Depends(get_db),
):
    is_batch = isinstance(payload, list)
    items = payload if is_batch else [payload]

    if not items:
        raise HTTPException(
            status_code=400,
            detail="Event list cannot be empty",
        )

    if not all(isinstance(item, dict) for item in items):
        raise HTTPException(
            status_code=400,
            detail="Each event must be a JSON object",
        )

    results = []

    for item in items:
        event = EventInput.model_validate(item)
        results.append(process_event(db, event))

    return {"results": results}
