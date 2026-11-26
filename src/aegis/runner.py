
from dataclasses import dataclass, field

from aegis.exchange import Exchange, EventResult
from aegis.generator import generate_events
from aegis.invariants import check_exchange
from aegis.shrinker import shrink_events


@dataclass
class RunReport:
    seed: int
    event_count: int
    results: list[EventResult] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return len(self.violations) == 0


def run_events(events: list[dict]) -> RunReport:
    """Run events through a fresh exchange and inspect its final state."""

    exchange = Exchange()
    results = []

    for event in events:
        try:
            result = exchange.process_event(event)
            results.append(result)
        except (KeyError, ValueError, TypeError) as error:
            return RunReport(
                seed=0,
                event_count=len(events),
                results=results,
                violations=[f"EVENT_PROCESSING_ERROR: {error}"],
            )

    report = check_exchange(exchange)

    return RunReport(
        seed=0,
        event_count=len(events),
        results=results,
        violations=report.violations,
    )


def run_generated_test(seed: int, event_count: int = 100) -> RunReport:
    """Generate reproducible events and run the exchange."""

    events = generate_events(seed, event_count)

    report = run_events(events)
    report.seed = seed

    return report


def find_minimal_failure(events: list[dict]) -> list[dict]:
    """Attempt to reduce an event sequence that causes a failure."""

    def still_fails(candidate):
        report = run_events(candidate)
        return not report.valid

    return shrink_events(events, still_fails)
