
from dataclasses import dataclass, field
from copy import deepcopy

from aegis.exchange import Exchange
from aegis.invariants import check_exchange


@dataclass
class MutationResult:
    name: str
    detected: bool
    violations: list[str] = field(default_factory=list)
    detection_methods: list[str] = field(default_factory=list)


@dataclass
class MutationReport:
    results: list[MutationResult]

    @property
    def total(self):
        return len(self.results)

    @property
    def detected(self):
        return sum(result.detected for result in self.results)

    @property
    def survived(self):
        return self.total - self.detected

    @property
    def score(self):
        return (
            self.detected / self.total * 100
            if self.total else 0.0
        )


def make_events():
    return [
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
            "client": "seller_b",
            "side": "SELL",
            "price": 100,
            "qty": 5,
        },
        {
            "type": "LIMIT",
            "id": 3,
            "client": "buyer_a",
            "side": "BUY",
            "price": 100,
            "qty": 7,
        },
    ]


def expected_trade_signature():
    """
    Expected FIFO executions.

    Order 1 arrived before order 2, so it executes first.
    The incoming buy order has quantity 7.
    """

    return [
        (1, 5, 3, 100),
        (2, 2, 3, 100),
    ]


def actual_trade_signature(exchange):
    return [
        (
            trade.sell_id,
            trade.qty,
            trade.buy_id,
            trade.price,
        )
        for trade in exchange.trades
    ]


def check_expected_behavior(exchange):
    violations = []

    expected = expected_trade_signature()
    actual = actual_trade_signature(exchange)

    if actual != expected:
        violations.append(
            "EXPECTED_TRADE_SEQUENCE_MISMATCH"
        )

    return violations


def run_correct_engine(events):
    exchange = Exchange()

    for event in events:
        exchange.process_event(deepcopy(event))

    return exchange


def run_priority_mutant(events):
    """Intentionally reverse FIFO priority."""

    exchange = Exchange()

    for event in events[:2]:
        exchange.process_event(deepcopy(event))

    # Corrupt the arrival sequence of the second resting order.
    exchange.orders[2].sequence = 0

    exchange.process_event(deepcopy(events[2]))

    return exchange


def run_wrong_price_mutant(events):
    """Intentionally corrupt an execution price."""

    exchange = run_correct_engine(events)

    if exchange.trades:
        exchange.trades[0].price += 1

    return exchange


def run_wrong_quantity_mutant(events):
    """Intentionally corrupt an execution quantity."""

    exchange = run_correct_engine(events)

    if exchange.trades:
        exchange.trades[0].qty += 1

    return exchange


def run_missing_history_mutant(events):
    """Intentionally remove an accepted order from history."""

    exchange = run_correct_engine(events)
    exchange.orders.pop(1, None)

    return exchange


def run_empty_order_mutant(events):
    """Intentionally leave an invalid empty order."""

    exchange = Exchange()

    for event in events[:2]:
        exchange.process_event(deepcopy(event))

    order = exchange.orders[1]
    order.remaining_qty = 0

    return exchange


MUTANTS = [
    ("reversed_fifo_priority", run_priority_mutant),
    ("wrong_execution_price", run_wrong_price_mutant),
    ("wrong_execution_quantity", run_wrong_quantity_mutant),
    ("missing_order_history", run_missing_history_mutant),
    ("empty_resting_order", run_empty_order_mutant),
]


def run_mutation_tests():
    results = []
    events = make_events()

    # Verify the unmodified engine first.
    correct = run_correct_engine(events)

    correct_report = check_exchange(correct)

    if correct_report.violations:
        raise RuntimeError(
            "Unmodified engine failed invariants: "
            + ", ".join(correct_report.violations)
        )

    behavior_violations = check_expected_behavior(correct)

    if behavior_violations:
        raise RuntimeError(
            "Unmodified engine failed expected behavior: "
            + ", ".join(behavior_violations)
        )

    for name, mutant in MUTANTS:
        violations = []
        detection_methods = []

        try:
            exchange = mutant(events)

            # Check exchange invariants.
            invariant_report = check_exchange(exchange)

            if invariant_report.violations:
                violations.extend(invariant_report.violations)
                detection_methods.append("INVARIANT_CHECKER")

            # Check explicit expected behaviour.
            behavior_errors = check_expected_behavior(exchange)

            if behavior_errors:
                violations.extend(behavior_errors)
                detection_methods.append("EXPECTED_OUTPUT_CHECK")

        except Exception as error:
            violations.append(
                f"MUTANT_EXECUTION_ERROR: {error}"
            )
            detection_methods.append("EXECUTION_ERROR")

        results.append(
            MutationResult(
                name=name,
                detected=bool(violations),
                violations=violations,
                detection_methods=detection_methods,
            )
        )

    return MutationReport(results)


def print_mutation_report(report):
    print("\n========== AEGIS MUTATION REPORT ==========")

    print(f"Total mutants:       {report.total}")
    print(f"Detected:            {report.detected}")
    print(f"Survived:            {report.survived}")
    print(f"Detection score:     {report.score:.1f}%")

    print("-------------------------------------------")

    for result in report.results:
        status = "DETECTED" if result.detected else "SURVIVED"

        print(f"{status:10} | {result.name}")

        if result.detection_methods:
            print(
                "             Detected by: "
                + ", ".join(result.detection_methods)
            )

        for violation in result.violations:
            print(f"             {violation}")

    print("===========================================\n")
