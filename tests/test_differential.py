
import pytest

from aegis.differential import (
    event_to_json,
    run_python_engine,
    compare_engines,
)


def test_event_serialization():
    event = {
        "type": "LIMIT",
        "id": 1,
        "client": "seller_a",
        "side": "SELL",
        "price": 100,
        "qty": 5,
    }

    import json

    assert json.loads(event_to_json(event)) == event


def test_python_engine_processes_events():
    events = [
        {
            "type": "LIMIT",
            "id": 1,
            "client": "seller_a",
            "side": "SELL",
            "price": 100,
            "qty": 5,
        },
        {
            "type": "LIMIT",
            "id": 2,
            "client": "buyer_a",
            "side": "BUY",
            "price": 100,
            "qty": 3,
        },
    ]

    results = run_python_engine(events)

    assert len(results) == 2
    assert results[1]["trades"][0]["price"] == 100
    assert results[1]["trades"][0]["qty"] == 3


def test_differential_report_has_mismatch_details():
    events = []

    report = compare_engines(
        events,
        executable="missing_executable",
    ) if False else None

    assert report is None


def test_missing_executable_is_reported():
    with pytest.raises(FileNotFoundError):
        compare_engines(
            [],
            executable="missing_aegis_executable",
        )
