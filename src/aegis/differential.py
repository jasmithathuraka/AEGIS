
import json
import subprocess
from pathlib import Path

from aegis.exchange import Exchange
from aegis.generator import generate_events
from aegis.reference import run_reference_engine


class DifferentialError(RuntimeError):
    pass


def event_to_json(event):
    return json.dumps(event, separators=(",", ":"))


def python_result(event, exchange):
    result = exchange.process_event(event)

    return {
        "seq": result.seq,
        "status": result.status,
        "reject_code": result.reject_code,
        "trades": [
            {
                "trade_seq": trade.trade_seq,
                "event_seq": trade.event_seq,
                "buy_id": trade.buy_id,
                "sell_id": trade.sell_id,
                "qty": trade.qty,
                "price": trade.price,
            }
            for trade in result.trades
        ],
        "order_updates": [
            {
                "id": update["id"],
                "remaining_qty": update["remaining_qty"],
                "executed_qty": update["executed_qty"],
                "cancelled_qty": update["cancelled_qty"],
                "status": update["status"],
            }
            for update in result.order_updates
        ],
    }


def run_python_engine(events):
    exchange = Exchange()

    return [
        python_result(event, exchange)
        for event in events
    ]


def run_cpp_engine(events, executable="aegis_cpp_jsonl"):
    executable_path = Path(executable)

    if not executable_path.is_file():
        raise FileNotFoundError(
            f"C++ executable not found: {executable_path.resolve()}"
        )

    input_text = "\n".join(
        event_to_json(event)
        for event in events
    ) + "\n"

    completed = subprocess.run(
        [str(executable_path.resolve())],
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )

    if completed.returncode != 0:
        raise DifferentialError(
            completed.stderr or completed.stdout
        )

    try:
        return [
            json.loads(line)
            for line in completed.stdout.splitlines()
            if line.strip()
        ]
    except json.JSONDecodeError as error:
        raise DifferentialError(
            f"C++ returned invalid JSON: {error}"
        ) from error


def compare_engines(events, executable="aegis_cpp_jsonl"):
    results = {
        "Python": run_python_engine(events),
        "Reference": run_reference_engine(events),
        "C++": run_cpp_engine(events, executable),
    }

    python_results = results["Python"]

    for engine_name, engine_results in results.items():
        if len(python_results) != len(engine_results):
            return {
                "matched": False,
                "reason": "RESULT_COUNT_MISMATCH",
                "engine": engine_name,
                "python_count": len(python_results),
                "engine_count": len(engine_results),
                "first_mismatch": None,
            }

    for index in range(len(events)):
        expected = python_results[index]

        for engine_name in ("Reference", "C++"):
            actual = results[engine_name][index]

            if expected != actual:
                return {
                    "matched": False,
                    "reason": "EVENT_RESULT_MISMATCH",
                    "engine": engine_name,
                    "event_index": index,
                    "event": events[index],
                    "python_result": expected,
                    "engine_result": actual,
                    "first_mismatch": index,
                }

    return {
        "matched": True,
        "reason": None,
        "event_count": len(events),
        "engines": ["Python", "Reference", "C++"],
        "first_mismatch": None,
    }


def run_differential_test(
    seed=42,
    event_count=100,
    executable="aegis_cpp_jsonl",
):
    events = generate_events(seed, event_count)

    report = compare_engines(events, executable)

    report["seed"] = seed
    report["event_count"] = event_count

    return report
