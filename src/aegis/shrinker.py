
from copy import deepcopy
from dataclasses import dataclass, field


@dataclass
class ShrinkReport:
    original_events: list
    reduced_events: list
    original_count: int
    reduced_count: int
    original_failure: str | None = None
    reduced_failure: str | None = None

    @property
    def reduction(self):
        if self.original_count == 0:
            return 0.0

        return (
            (self.original_count - self.reduced_count)
            / self.original_count
        ) * 100


def _fails(events, still_fails):
    try:
        return bool(still_fails(deepcopy(events)))
    except Exception:
        return False


def _reduce_event_count(events, still_fails):
    current = deepcopy(events)
    granularity = 2

    while len(current) >= 2:
        chunk_size = (
            len(current) + granularity - 1
        ) // granularity

        reduced = False

        for start in range(0, len(current), chunk_size):
            candidate = (
                current[:start]
                + current[start + chunk_size:]
            )

            if _fails(candidate, still_fails):
                current = candidate
                granularity = max(2, granularity - 1)
                reduced = True
                break

        if reduced:
            continue

        if granularity >= len(current):
            break

        granularity = min(
            len(current),
            granularity * 2
        )

    return current


def _numeric_candidates(value):
    if type(value) is not int or value <= 1:
        return []

    candidates = [1, value // 2, value - 1]

    result = []
    seen = set()

    for candidate in candidates:
        if 1 <= candidate < value and candidate not in seen:
            result.append(candidate)
            seen.add(candidate)

    return result


def _reduce_numeric_values(events, still_fails):
    current = deepcopy(events)

    # Only reduce fields whose values affect matching behaviour.
    fields = ("price", "qty")

    changed = True

    while changed:
        changed = False

        for event_index in range(len(current)):
            for field_name in fields:
                event = current[event_index]

                if field_name not in event:
                    continue

                original_value = event[field_name]

                for candidate_value in _numeric_candidates(
                    original_value
                ):
                    candidate = deepcopy(current)
                    candidate[event_index][field_name] = (
                        candidate_value
                    )

                    if _fails(candidate, still_fails):
                        current = candidate
                        changed = True
                        break

                if changed:
                    break

            if changed:
                break

    return current


def shrink_events(events, still_fails):
    """
    Minimise a failing event sequence.

    The supplied predicate must return True only when the
    original failure is still reproduced.
    """
    original = deepcopy(list(events))

    if not _fails(original, still_fails):
        raise ValueError(
            "The original event sequence does not reproduce a failure."
        )

    reduced = _reduce_event_count(
        original,
        still_fails
    )

    reduced = _reduce_numeric_values(
        reduced,
        still_fails
    )

    return reduced


def create_shrink_report(
    original_events,
    reduced_events,
    original_failure=None,
    reduced_failure=None,
):
    original = deepcopy(list(original_events))
    reduced = deepcopy(list(reduced_events))

    return ShrinkReport(
        original_events=original,
        reduced_events=reduced,
        original_count=len(original),
        reduced_count=len(reduced),
        original_failure=original_failure,
        reduced_failure=reduced_failure,
    )


def print_shrink_report(report):
    print("\n========== AEGIS FAILURE SHRINKER ==========")
    print(f"Original events: {report.original_count}")
    print(f"Reduced events:  {report.reduced_count}")
    print(f"Reduction:       {report.reduction:.1f}%")

    if report.original_failure:
        print(f"Original failure: {report.original_failure}")

    if report.reduced_failure:
        print(f"Reduced failure:  {report.reduced_failure}")

    print("--------------------------------------------")
    print("MINIMAL REPRODUCTION")

    for index, event in enumerate(report.reduced_events, start=1):
        print(f"{index}. {event}")

    print("============================================\n")
