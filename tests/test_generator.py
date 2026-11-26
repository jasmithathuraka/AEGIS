
import json

from aegis.generator import (
    generate_events,
    generate_jsonl,
)


def test_same_seed_generates_same_events():
    first = generate_events(seed=42, event_count=100)
    second = generate_events(seed=42, event_count=100)

    assert first == second


def test_different_seeds_generate_different_events():
    first = generate_events(seed=42, event_count=100)
    second = generate_events(seed=99, event_count=100)

    assert first != second


def test_event_count_is_respected():
    events = generate_events(seed=42, event_count=50)

    assert len(events) == 50


def test_generated_order_ids_are_unique():
    events = generate_events(seed=42, event_count=100)

    order_ids = [
        event["id"]
        for event in events
        if event["type"] in ("LIMIT", "MARKET")
    ]

    assert len(order_ids) == len(set(order_ids))


def test_generated_events_have_valid_types():
    events = generate_events(seed=42, event_count=100)

    for event in events:
        assert event["type"] in ("LIMIT", "MARKET", "CANCEL")


def test_generated_jsonl_can_be_parsed():
    content = generate_jsonl(seed=42, event_count=30)

    lines = content.splitlines()

    assert len(lines) == 30

    for line in lines:
        event = json.loads(line)
        assert isinstance(event, dict)


def test_negative_event_count_is_rejected():
    try:
        generate_events(seed=42, event_count=-1)
    except ValueError:
        pass
    else:
        assert False, "Expected ValueError"
