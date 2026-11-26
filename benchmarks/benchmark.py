
import json
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

from aegis.generator import generate_events
from aegis.exchange import Exchange

ROOT = Path(__file__).resolve().parents[1]

CPP_SOURCE = ROOT / "cpp" / "src" / "benchmark.cpp"
CPP_ENGINE = ROOT / "cpp" / "src" / "exchange.cpp"
CPP_EXECUTABLE = ROOT / "aegis_cpp_benchmark"

WORKLOADS = [1000, 5000, 10000]
REPEATS = 5


def build_cpp():
    subprocess.run(
        [
            "clang++",
            "-std=c++20",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Icpp/include",
            "-I/opt/homebrew/include",
            str(CPP_SOURCE),
            str(CPP_ENGINE),
            "-o",
            str(CPP_EXECUTABLE),
        ],
        cwd=ROOT,
        check=True,
    )


def write_jsonl(events, path):
    with open(path, "w", encoding="utf-8") as file:
        for event in events:
            file.write(json.dumps(event) + "\n")


def python_state(exchange):
    orders = []

    for order_id in sorted(exchange.orders):
        order = exchange.orders[order_id]

        orders.append({
            "id": order.order_id,
            "client": order.client_id,
            "side": order.side.value.upper(),
            "type": order.order_type.value.upper(),
            "price": order.price,
            "original_qty": order.original_qty,
            "remaining_qty": order.remaining_qty,
            "executed_qty": order.executed_qty,
            "cancelled_qty": order.cancelled_qty,
            "sequence": order.sequence,
            "status": order.status.value.upper(),
        })

    trades = [
        {
            "trade_seq": trade.trade_seq,
            "event_seq": trade.event_seq,
            "buy_id": trade.buy_id,
            "sell_id": trade.sell_id,
            "qty": trade.qty,
            "price": trade.price,
        }
        for trade in exchange.trades
    ]

    return {"orders": orders, "trades": trades}


def run_python(events):
    exchange = Exchange()

    start = time.perf_counter()

    for event in events:
        exchange.process_event(event)

    elapsed = time.perf_counter() - start

    return elapsed, python_state(exchange)


def run_cpp(event_path):
    result = subprocess.run(
        [str(CPP_EXECUTABLE), str(event_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    output = json.loads(result.stdout)

    elapsed = output.pop("elapsed_seconds")

    return elapsed, output


def main():
    build_cpp()

    print("\nAEGIS FAIR ENGINE BENCHMARK")
    print("=" * 78)
    print(f"Workload repetitions: {REPEATS}")
    print("Timing excludes event generation, JSON parsing and process startup.")
    print("Full final order state and trade history are compared.")
    print("-" * 78)

    print(
        f"{'Events':>10} "
        f"{'Python median':>16} "
        f"{'C++ median':>16} "
        f"{'C++ speedup':>14}"
    )

    print("-" * 78)

    for count in WORKLOADS:
        events = generate_events(seed=42, event_count=count)

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".jsonl",
            delete=False,
        ) as file:
            event_path = Path(file.name)

        try:
            write_jsonl(events, event_path)

            python_times = []
            cpp_times = []

            for _ in range(REPEATS):
                py_time, py_state = run_python(events)
                cpp_time, cpp_state = run_cpp(event_path)

                if py_state != cpp_state:
                    raise RuntimeError(
                        f"Full state mismatch for {count} events"
                    )

                python_times.append(py_time)
                cpp_times.append(cpp_time)

            py_median = statistics.median(python_times)
            cpp_median = statistics.median(cpp_times)

            speedup = (
                py_median / cpp_median
                if cpp_median > 0
                else 0
            )

            print(
                f"{count:>10} "
                f"{py_median:>16.6f} "
                f"{cpp_median:>16.6f} "
                f"{speedup:>13.2f}x"
            )

        finally:
            event_path.unlink(missing_ok=True)

    print("-" * 78)
    print("All workloads completed with matching final exchange states.")


if __name__ == "__main__":
    main()
