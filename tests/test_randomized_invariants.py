
import pytest

from aegis.exchange import Exchange
from aegis.generator import generate_events
from aegis.invariants import check_exchange
from aegis.reference import ReferenceExchange


@pytest.mark.parametrize(
    "seed",
    [1, 7, 21, 42, 99, 123, 256, 512, 999, 2026],
)
def test_python_invariants_after_every_event(seed):
    events = generate_events(seed, event_count=500)
    exchange = Exchange()

    for index, event in enumerate(events):
        exchange.process_event(event)

        report = check_exchange(exchange)

        assert report.valid, (
            f"Python invariant violation.\n"
            f"Seed: {seed}\n"
            f"Event index: {index}\n"
            f"Event: {event}\n"
            f"Violations: {report.violations}"
        )


@pytest.mark.parametrize(
    "seed",
    [1, 7, 21, 42, 99, 123, 256, 512, 999, 2026],
)
def test_reference_invariants_after_every_event(seed):
    events = generate_events(seed, event_count=500)
    exchange = ReferenceExchange()

    for index, event in enumerate(events):
        exchange.process_event(event)

        report = check_exchange(exchange)

        assert report.valid, (
            f"Reference invariant violation.\n"
            f"Seed: {seed}\n"
            f"Event index: {index}\n"
            f"Event: {event}\n"
            f"Violations: {report.violations}"
        )


def test_python_and_reference_final_invariants():
    events = generate_events(seed=2026, event_count=1000)

    python_exchange = Exchange()
    reference_exchange = ReferenceExchange()

    for event in events:
        python_exchange.process_event(event)
        reference_exchange.process_event(event)

    python_report = check_exchange(python_exchange)
    reference_report = check_exchange(reference_exchange)

    assert python_report.valid, python_report.violations
    assert reference_report.valid, reference_report.violations
