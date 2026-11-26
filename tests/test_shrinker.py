
import pytest

from aegis.shrinker import (
    shrink_events,
    create_shrink_report,
)


def test_shrinker_rejects_non_failing_input():
    events = [{"type": "LIMIT", "id": 1, "qty": 5}]

    with pytest.raises(ValueError):
        shrink_events(events, lambda candidate: False)


def test_shrinker_removes_irrelevant_events():
    events = [
        {"id": 1, "qty": 5},
        {"id": 2, "qty": 8},
        {"id": 3, "qty": 3},
    ]

    def still_fails(candidate):
        return any(
            event["id"] == 2 and event["qty"] == 8
            for event in candidate
        )

    result = shrink_events(events, still_fails)

    assert result == [{"id": 2, "qty": 8}]


def test_shrinker_reduces_quantity():
    events = [{"id": 1, "qty": 100}]

    def still_fails(candidate):
        return candidate[0]["qty"] >= 10

    result = shrink_events(events, still_fails)

    assert result[0]["qty"] == 10


def test_shrinker_reduces_price():
    events = [{"id": 1, "price": 100}]

    def still_fails(candidate):
        return candidate[0]["price"] >= 7

    result = shrink_events(events, still_fails)

    assert result[0]["price"] == 7


def test_shrinker_preserves_failure():
    events = [
        {"id": 1, "qty": 10},
        {"id": 2, "qty": 20},
    ]

    def still_fails(candidate):
        return any(event["id"] == 2 for event in candidate)

    result = shrink_events(events, still_fails)

    assert still_fails(result)


def test_shrinker_does_not_modify_original_events():
    events = [{"id": 1, "qty": 100}]
    original = [event.copy() for event in events]

    shrink_events(
        events,
        lambda candidate: candidate[0]["qty"] >= 10
    )

    assert events == original


def test_shrink_report_calculates_reduction():
    report = create_shrink_report(
        original_events=[1, 2, 3, 4, 5],
        reduced_events=[2, 4],
        original_failure="TEST_FAILURE",
        reduced_failure="TEST_FAILURE",
    )

    assert report.original_count == 5
    assert report.reduced_count == 2
    assert report.reduction == 60.0


def test_shrink_report_handles_empty_input():
    report = create_shrink_report([], [])

    assert report.reduction == 0.0
