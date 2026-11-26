
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path

from aegis.generator import generate_events
from aegis.runner import run_events
from aegis.mutation import run_mutation_tests
from aegis.shrinker import (
    shrink_events,
    create_shrink_report,
)


def json_safe(value):
    """Convert dataclasses and enums into JSON-compatible values."""

    if is_dataclass(value):
        return json_safe(asdict(value))

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, dict):
        return {
            str(key): json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]

    return value


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(
            json_safe(data),
            file,
            indent=4,
            sort_keys=True,
        )


def save_jsonl(path, events):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        for event in events:
            file.write(json.dumps(event, sort_keys=True) + "\n")


def failure_signature(report):
    """Return the exact ordered violation list."""
    return tuple(report.violations)


def run_pipeline(seed, event_count=100, output_dir="testdata/reports"):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print("\n========== AEGIS PIPELINE ==========")

    # Stage 1: Generate deterministic events.
    print("[1/6] Generating events...")

    events = generate_events(seed, event_count)

    save_jsonl(
        output_path / "original_events.jsonl",
        events,
    )

    # Stage 2: Execute the exchange.
    print("[2/6] Running exchange engine...")

    exchange_report = run_events(events)

    # Stage 3: Check exchange invariants.
    print("[3/6] Checking invariants...")

    exchange_valid = exchange_report.valid

    print(
        "Exchange status:",
        "VALID" if exchange_valid else "FAILED",
    )

    # Stage 4: Run mutation tests.
    print("[4/6] Running mutation tests...")

    mutation_report = run_mutation_tests()

    print(
        f"Mutation detection: "
        f"{mutation_report.detected}/{mutation_report.total}"
    )

    # Stage 5: Shrink failures when possible.
    print("[5/6] Checking for reproducible failures...")

    shrink_report = None
    reduced_events = None

    if not exchange_valid:
        original_signature = failure_signature(exchange_report)

        def still_has_same_failure(candidate):
            candidate_report = run_events(candidate)

            return (
                failure_signature(candidate_report)
                == original_signature
            )

        reduced_events = shrink_events(
            events,
            still_has_same_failure,
        )

        reduced_result = run_events(reduced_events)

        shrink_report = create_shrink_report(
            original_events=events,
            reduced_events=reduced_events,
            original_failure=str(original_signature),
            reduced_failure=str(
                failure_signature(reduced_result)
            ),
        )

        save_jsonl(
            output_path / "reduced_reproduction.jsonl",
            reduced_events,
        )

        save_json(
            output_path / "shrink_report.json",
            shrink_report,
        )

    # Stage 6: Save complete report.
    print("[6/6] Saving results...")

    final_report = {
        "project": "AEGIS",
        "seed": seed,
        "requested_event_count": event_count,
        "generated_event_count": len(events),
        "exchange_valid": exchange_valid,
        "exchange_violations": exchange_report.violations,
        "exchange_results": exchange_report.results,
        "mutation_total": mutation_report.total,
        "mutation_detected": mutation_report.detected,
        "mutation_survived": mutation_report.survived,
        "mutation_score": mutation_report.score,
        "mutation_results": mutation_report.results,
        "shrink_performed": shrink_report is not None,
        "shrink_report": shrink_report,
    }

    save_json(
        output_path / "pipeline_report.json",
        final_report,
    )

    print("\n========== PIPELINE SUMMARY ==========")
    print(f"Seed:              {seed}")
    print(f"Events:            {len(events)}")
    print(f"Exchange valid:    {exchange_valid}")
    print(
        f"Mutation score:    {mutation_report.score:.1f}%"
    )
    print(
        f"Failure shrunk:    {shrink_report is not None}"
    )
    print(f"Reports saved to:  {output_path}")
    print("======================================\n")

    return final_report
