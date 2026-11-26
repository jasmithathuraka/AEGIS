
import json
import subprocess
from pathlib import Path

from aegis.exchange import Exchange
from aegis.generator import generate_events


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
    python_results = run_python_engine(events)
    cpp_results = run_cpp_engine(events, executable)

    if len(python_results) != len(cpp_results):
        return {
            "matched": False,
            "reason": "RESULT_COUNT_MISMATCH",
            "python_count": len(python_results),
            "cpp_count": len(cpp_results),
            "first_mismatch": None,
        }

    for index, (python_result_item, cpp_result_item) in enumerate(
        zip(python_results, cpp_results)
    ):
        if python_result_item != cpp_result_item:
            return {
                "matched": False,
                "reason": "EVENT_RESULT_MISMATCH",
                "event_index": index,
                "event": events[index],
                "python_result": python_result_item,
                "cpp_result": cpp_result_item,
                "first_mismatch": index,
            }

    return {
        "matched": True,
        "reason": None,
        "event_count": len(events),
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
