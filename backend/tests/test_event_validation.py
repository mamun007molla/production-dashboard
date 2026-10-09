from datetime import datetime, timezone

import pytest

from app.modules.events.schemas import EventInput
from app.modules.events.service import validate_event


def make_count_event(quantity):
    return EventInput(
        source_id="TEST-LINE",
        event_id="COUNT-001",
        type="COUNT",
        quantity=quantity,
        event_time=datetime.now(timezone.utc),
    )


@pytest.mark.parametrize("quantity", [1, 500])
def test_count_quantity_boundary_values_are_valid(quantity):
    validate_event(make_count_event(quantity))


@pytest.mark.parametrize("quantity", [0, 501, -1])
def test_count_quantity_outside_allowed_range_is_invalid(quantity):
    with pytest.raises(
        ValueError,
        match="COUNT quantity must be an integer between 1 and 500",
    ):
        validate_event(make_count_event(quantity))


def test_count_quantity_boolean_is_invalid():
    event = make_count_event(1)
    event.quantity = True

    with pytest.raises(
        ValueError,
        match="COUNT quantity must be an integer between 1 and 500",
    ):
        validate_event(event)
