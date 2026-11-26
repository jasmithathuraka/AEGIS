
import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CPP_SOURCE = ROOT / "cpp" / "src" / "exchange.cpp"
CPP_MAIN = ROOT / "cpp" / "src" / "main.cpp"

MUTATIONS = [
    {
        "name": "reversed_fifo_priority",
        "old": "level_it->second.begin()->second",
        "new": "level_it->second.rbegin()->second",
        "count": 2,
        "events": [
            {"type": "LIMIT", "id": 1, "client": "seller_a",
             "side": "SELL", "price": 100, "qty": 5},
            {"type": "LIMIT", "id": 2, "client": "seller_b",
             "side": "SELL", "price": 100, "qty": 5},
            {"type": "LIMIT", "id": 3, "client": "buyer_a",
             "side": "BUY", "price": 100, "qty": 7},
        ],
    },
    {
        "name": "wrong_execution_price",
        "old": "            quantity,\n            resting_price\n        };",
        "new": "            quantity,\n            *incoming.price\n        };",
        "count": 1,
        "events": [
            {"type": "LIMIT", "id": 1, "client": "seller_a",
             "side": "SELL", "price": 100, "qty": 5},
            {"type": "LIMIT", "id": 2, "client": "buyer_a",
             "side": "BUY", "price": 105, "qty": 5},
        ],
    },
    {
        "name": "wrong_execution_quantity",
        "old": "std::min(",
        "new": "std::max(",
        "count": 1,
        "events": [
            {"type": "LIMIT", "id": 1, "client": "seller_a",
             "side": "SELL", "price": 100, "qty": 5},
            {"type": "LIMIT", "id": 2, "client": "buyer_a",
             "side": "BUY", "price": 100, "qty": 7},
        ],
    },
    {
        "name": "cancel_leaves_stale_book_entry",
        "old": (
            "        remove_from_book(it->second);\n\n"
            "        it->second.cancelled_qty = checked_add("
        ),
        "new": (
            "        // MUTANT: deliberately leave the order in the book.\n"
            "        it->second.cancelled_qty = checked_add("
        ),
        "count": 1,
        "events": [
            {"type": "LIMIT", "id": 1, "client": "seller_a",
             "side": "SELL", "price": 100, "qty": 5},
            {"type": "CANCEL", "id": 1, "client": "seller_a"},
            {"type": "LIMIT", "id": 2, "client": "buyer_a",
             "side": "BUY", "price": 100, "qty": 5},
        ],
    },
    {
        "name": "self_trade_prevention_disabled",
        "old": "if (resting.client == incoming.client)",
        "new": "if (false)",
        "count": 1,
        "events": [
            {"type": "LIMIT", "id": 1, "client": "alice",
             "side": "SELL", "price": 100, "qty": 5},
            {"type": "LIMIT", "id": 2, "client": "alice",
             "side": "BUY", "price": 100, "qty": 5},
        ],
    },
]


def compile_engine(source_path, executable):
    command = [
        "clang++",
        "-std=c++20",
        "-O2",
        "-Wall",
        "-Wextra",
        "-Wpedantic",
        "-Icpp/include",
        "-I/opt/homebrew/include",
        str(source_path),
        str(CPP_MAIN),
        "-o",
        str(executable),
    ]

    subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def make_jsonl(events):
    return "".join(
        json.dumps(event, separators=(",", ":")) + "\n"
        for event in events
    )


def run_engine(executable, events):
    result = subprocess.run(
        [str(executable)],
        input=make_jsonl(events),
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    return result


def main():
    original_source = CPP_SOURCE.read_text(encoding="utf-8")

    results = []

    with tempfile.TemporaryDirectory(
        prefix="aegis_cpp_mutation_"
    ) as temp:
        temp_dir = Path(temp)

        # Compile the unmodified engine once.
        correct_source = temp_dir / "exchange_correct.cpp"
        correct_executable = temp_dir / "aegis_correct"

        correct_source.write_text(
            original_source,
            encoding="utf-8",
        )

        print("Building original C++ engine...")

        compile_engine(correct_source, correct_executable)

        for mutation in MUTATIONS:
            name = mutation["name"]

            print(f"\nTesting mutant: {name}")

            old = mutation["old"]
            new = mutation["new"]
            expected_count = mutation["count"]

            actual_count = original_source.count(old)

            if actual_count != expected_count:
                raise RuntimeError(
                    f"{name}: expected {expected_count} "
                    f"replacement locations, found {actual_count}"
                )

            mutated_source_text = original_source.replace(old, new)

            mutated_source = temp_dir / f"{name}.cpp"
            mutated_executable = temp_dir / name

            mutated_source.write_text(
                mutated_source_text,
                encoding="utf-8",
            )

            try:
                compile_engine(
                    mutated_source,
                    mutated_executable,
                )
            except subprocess.CalledProcessError as error:
                print("MUTANT COMPILE FAILED")
                print(error.stderr)
                results.append((name, False, "COMPILE_ERROR"))
                continue

            events = mutation["events"]

            correct_result = run_engine(
                correct_executable,
                events,
            )

            if correct_result.returncode != 0:
                raise RuntimeError(
                    f"Original engine failed for {name}:\n"
                    + correct_result.stderr
                )

            mutated_result = run_engine(
                mutated_executable,
                events,
            )

            detected = (
                mutated_result.returncode != 0
                or mutated_result.stdout != correct_result.stdout
            )

            if detected:
                reason = (
                    "RUNTIME_FAILURE"
                    if mutated_result.returncode != 0
                    else "OUTPUT_MISMATCH"
                )
                print(f"DETECTED ({reason})")
            else:
                reason = "SURVIVED"
                print("SURVIVED")

            results.append((name, detected, reason))

    detected_count = sum(
        1 for _, detected, _ in results if detected
    )

    total = len(results)
    survived = total - detected_count

    score = (
        detected_count / total * 100
        if total else 0.0
    )

    print("\n========== AEGIS C++ MUTATION REPORT ==========")
    print(f"Total mutants:    {total}")
    print(f"Detected:         {detected_count}")
    print(f"Survived:         {survived}")
    print(f"Detection score:  {score:.1f}%")
    print("-----------------------------------------------")

    for name, detected, reason in results:
        status = "DETECTED" if detected else "SURVIVED"
        print(f"{status:10} | {name} | {reason}")

    print("================================================")


if __name__ == "__main__":
    main()
