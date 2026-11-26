
from aegis.runner import (
    run_events,
    run_generated_test,
    find_minimal_failure,
)


def test_empty_run():
    report = run_events([])

    assert report.valid
    assert report.event_count == 0


def test_generated_run():
    report = run_generated_test(seed=42, event_count=100)

    assert report.seed == 42
    assert report.event_count == 100
    assert len(report.results) == 100


def test_generated_run_is_reproducible():
    first = run_generated_test(seed=123, event_count=50)
    second = run_generated_test(seed=123, event_count=50)

    assert first.results == second.results
    assert first.violations == second.violations


def test_multiple_generated_seeds():
    for seed in range(10):
        report = run_generated_test(seed=seed, event_count=100)

        assert report.valid, (
            f"Seed {seed} produced violations: {report.violations}"
        )


def test_shrinker_reproduces_failure():
    events = [
        {"type": "LIMIT", "id": 1, "client": "ALICE",
         "side": "BUY", "price": 100, "qty": 5},
        {"type": "LIMIT", "id": 2, "client": "BOB",
         "side": "SELL", "price": 110, "qty": 5},
    ]

    def artificial_failure(candidate):
        return any(event["id"] == 1 for event in candidate)

    from aegis.shrinker import shrink_events

    reduced = shrink_events(events, artificial_failure)

    assert len(reduced) == 1
    assert reduced[0]["id"] == 1
