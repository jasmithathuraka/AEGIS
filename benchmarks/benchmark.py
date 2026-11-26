
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import statistics
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aegis.generator import generate_events
from aegis.exchange import Exchange


ROOT = Path(__file__).resolve().parents[1]

CPP_SOURCE = ROOT / "cpp" / "src" / "benchmark.cpp"
CPP_ENGINE = ROOT / "cpp" / "src" / "exchange.cpp"
CPP_EXECUTABLE = ROOT / "aegis_cpp_benchmark"

WORKLOADS = [1000, 5000, 10000]
WARMUP_RUNS = 2
REPEATS = 7


def find_compiler() -> str:
    """Find an available C++ compiler without assuming a specific OS."""

    configured = os.environ.get("CXX")

    candidates = (
        [configured] if configured
        else ["clang++", "g++", "c++"]
    )

    for candidate in candidates:
        if candidate and shutil.which(candidate):
            return candidate

    raise RuntimeError(
        "No C++ compiler found. Install clang++ or g++, "
        "or set the CXX environment variable."
    )


def compiler_information(compiler: str) -> dict[str, str]:
    """Capture the compiler identity used for this benchmark."""

    result = subprocess.run(
        [compiler, "--version"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    first_line = (
        result.stdout.strip().splitlines()
        or result.stderr.strip().splitlines()
        or ["Unknown compiler"]
    )[0]

    return {
        "command": compiler,
        "version": first_line,
    }


def build_cpp(compiler: str) -> None:
    """Build the benchmark executable outside measured engine timings."""

    command = [
        compiler,
        "-std=c++20",
        "-O2",
        "-Wall",
        "-Wextra",
        "-Wpedantic",
        "-Icpp/include",
    ]

    # Homebrew's default include directory, when present.
    homebrew_include = Path("/opt/homebrew/include")

    if homebrew_include.is_dir():
        command.append(f"-I{homebrew_include}")

    command.extend([
        str(CPP_SOURCE),
        str(CPP_ENGINE),
        "-o",
        str(CPP_EXECUTABLE),
    ])

    subprocess.run(
        command,
        cwd=ROOT,
        check=True,
    )


def write_jsonl(events: list[dict[str, Any]], path: Path) -> None:
    """Write generated events before either engine is timed."""

    with path.open("w", encoding="utf-8") as file:
        for event in events:
            file.write(json.dumps(event) + "\n")


def python_state(exchange: Exchange) -> dict[str, Any]:
    """Serialize Python's final orders and trades for comparison."""

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

    return {
        "orders": orders,
        "trades": trades,
    }


def run_python(
    events: list[dict[str, Any]],
) -> tuple[float, dict[str, Any]]:
    """Measure Python event processing, excluding generation and setup."""

    exchange = Exchange()

    start = time.perf_counter()

    for event in events:
        exchange.process_event(event)

    elapsed = time.perf_counter() - start

    return elapsed, python_state(exchange)


def run_cpp(
    event_path: Path,
) -> tuple[float, dict[str, Any]]:
    """Run the C++ benchmark and read its engine-only timing."""

    result = subprocess.run(
        [str(CPP_EXECUTABLE), str(event_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    output = json.loads(result.stdout)
    elapsed = float(output.pop("elapsed_seconds"))

    return elapsed, output


def verify_states(
    python_result: dict[str, Any],
    cpp_result: dict[str, Any],
    count: int,
) -> None:
    """Reject a benchmark result if the engines disagree."""

    if python_result != cpp_result:
        raise RuntimeError(
            f"Final exchange state mismatch for {count} events"
        )


def benchmark_workload(count: int) -> dict[str, Any]:
    """Measure one workload and verify every measured execution."""

    events = generate_events(
        seed=42,
        event_count=count,
    )

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".jsonl",
        delete=False,
        encoding="utf-8",
    ) as file:
        event_path = Path(file.name)

    try:
        write_jsonl(events, event_path)

        # Warm-ups are deliberately excluded from measured samples.
        for _ in range(WARMUP_RUNS):
            py_time, py_state = run_python(events)
            cpp_time, cpp_state = run_cpp(event_path)

            verify_states(py_state, cpp_state, count)

        python_times = []
        cpp_times = []

        # Alternate execution order to reduce systematic ordering bias.
        for repetition in range(REPEATS):
            if repetition % 2 == 0:
                py_time, py_state = run_python(events)
                cpp_time, cpp_state = run_cpp(event_path)
            else:
                cpp_time, cpp_state = run_cpp(event_path)
                py_time, py_state = run_python(events)

            verify_states(py_state, cpp_state, count)

            python_times.append(py_time)
            cpp_times.append(cpp_time)

        py_median = statistics.median(python_times)
        cpp_median = statistics.median(cpp_times)

        speedup = (
            py_median / cpp_median
            if cpp_median > 0
            else None
        )

        return {
            "event_count": count,
            "python": {
                "median_seconds": py_median,
                "events_per_second": (
                    count / py_median if py_median > 0 else None
                ),
                "samples_seconds": python_times,
            },
            "cpp": {
                "median_seconds": cpp_median,
                "events_per_second": (
                    count / cpp_median if cpp_median > 0 else None
                ),
                "samples_seconds": cpp_times,
            },
            "cpp_speedup": speedup,
            "correctness": {
                "final_state_match": True,
                "comparisons": WARMUP_RUNS + REPEATS,
            },
        }

    finally:
        event_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark the AEGIS Python and C++ engines."
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "benchmarks" / "report.json",
        help="Where to save the structured benchmark report.",
    )

    args = parser.parse_args()

    compiler = find_compiler()
    compiler_info = compiler_information(compiler)

    print("\nAEGIS ENGINE BENCHMARK")
    print("=" * 82)
    print(f"Compiler: {compiler_info['version']}")
    print(f"Warm-up runs per implementation: {WARMUP_RUNS}")
    print(f"Measured repetitions: {REPEATS}")
    print("Event generation and input parsing are excluded from timing.")
    print("Final order state and complete trade history are compared.")
    print("Execution order alternates between implementations.")
    print("-" * 82)

    build_cpp(compiler)

    results = []

    print(
        f"{'Events':>10} "
        f"{'Python median':>16} "
        f"{'C++ median':>16} "
        f"{'C++ speedup':>14}"
    )
    print("-" * 82)

    for count in WORKLOADS:
        result = benchmark_workload(count)
        results.append(result)

        py_median = result["python"]["median_seconds"]
        cpp_median = result["cpp"]["median_seconds"]
        speedup = result["cpp_speedup"]

        speedup_text = (
            f"{speedup:.2f}x"
            if speedup is not None
            else "N/A"
        )

        print(
            f"{count:>10} "
            f"{py_median:>16.6f} "
            f"{cpp_median:>16.6f} "
            f"{speedup_text:>14}"
        )

    report = {
        "project": "AEGIS",
        "report_type": "recorded_engine_benchmark",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "operating_system": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor() or "Not reported",
            "python_version": platform.python_version(),
            "compiler": compiler_info,
            "cpp_standard": "C++20",
            "optimization": "-O2",
        },
        "configuration": {
            "workloads": WORKLOADS,
            "warmup_runs": WARMUP_RUNS,
            "measured_repetitions": REPEATS,
            "random_seed": 42,
            "timing_scope": (
                "Engine event-processing loop only. "
                "Generation, input parsing, process startup, "
                "and result serialization are excluded."
            ),
        },
        "results": results,
        "all_final_states_match": all(
            item["correctness"]["final_state_match"]
            for item in results
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)

    args.output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    print("-" * 82)
    print("PASS: all workloads produced matching final exchange states.")
    print(f"Structured report saved to: {args.output}")
    print(
        "Speedup values describe these implementations, "
        "workloads and this machine only."
    )


if __name__ == "__main__":
    main()
