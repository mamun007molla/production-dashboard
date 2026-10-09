
from types import SimpleNamespace

from app.modules.state.router import calculate_net_total


def make_event(
    event_id,
    event_type,
    quantity=None,
    target_event_id=None,
    status="ACCEPTED",
    source_id="LINE-01",
):
    """Create a lightweight event object for unit testing."""
    return SimpleNamespace(
        source_id=source_id,
        event_id=event_id,
        type=event_type,
        quantity=quantity,
        target_event_id=target_event_id,
        status=status,
    )


def test_count_quantities_are_added():
    events = [
        make_event("C-1", "COUNT", quantity=10),
        make_event("C-2", "COUNT", quantity=5),
    ]

    assert calculate_net_total(events) == 15


def test_accepted_void_reverses_target_count():
    events = [
        make_event("C-1", "COUNT", quantity=10),
        make_event(
            "V-1",
            "VOID",
            target_event_id="C-1",
        ),
    ]

    assert calculate_net_total(events) == 0


def test_pending_void_does_not_reverse_count():
    events = [
        make_event("C-1", "COUNT", quantity=10),
        make_event(
            "V-1",
            "VOID",
            target_event_id="C-1",
            status="PENDING_REFERENCE",
        ),
    ]

    assert calculate_net_total(events) == 10


def test_reversed_count_does_not_affect_other_counts():
    events = [
        make_event("C-1", "COUNT", quantity=10),
        make_event(
            "V-1",
            "VOID",
            target_event_id="C-1",
        ),
        make_event("C-2", "COUNT", quantity=7),
    ]

    assert calculate_net_total(events) == 7


def test_rejected_count_is_not_added():
    events = [
        make_event(
            "C-1",
            "COUNT",
            quantity=10,
            status="REJECTED",
        ),
    ]

    assert calculate_net_total(events) == 0


def test_void_only_reverses_count_from_same_source():
    events = [
        make_event(
            "COUNT-1",
            "COUNT",
            quantity=10,
            source_id="LINE-01",
        ),
        make_event(
            "COUNT-1",
            "COUNT",
            quantity=7,
            source_id="LINE-02",
        ),
        make_event(
            "VOID-1",
            "VOID",
            target_event_id="COUNT-1",
            source_id="LINE-01",
        ),
    ]

    assert calculate_net_total(events) == 7


def test_rejected_void_does_not_reverse_count():
    events = [
        make_event("C-1", "COUNT", quantity=10),
        make_event(
            "V-1",
            "VOID",
            target_event_id="C-1",
            status="REJECTED",
        ),
    ]

    assert calculate_net_total(events) == 10


def test_empty_events_return_zero():
    assert calculate_net_total([]) == 0
