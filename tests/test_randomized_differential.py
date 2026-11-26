
import subprocess
from pathlib import Path

import pytest

from aegis.differential import compare_engines
from aegis.generator import generate_events
from aegis.reference import run_reference_engine


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def cpp_executable(tmp_path_factory):
    output = tmp_path_factory.mktemp("aegis_randomized") / "aegis_cpp"

    command = [
        "clang++",
        "-std=c++20",
        "-Wall",
        "-Wextra",
        "-Wpedantic",
        "-O2",
        "-Icpp/include",
        "-I/opt/homebrew/include",
        "cpp/src/exchange.cpp",
        "cpp/src/main.cpp",
        "-o",
        str(output),
    ]

    subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    return str(output)


@pytest.mark.parametrize(
    "seed",
    [1, 7, 21, 42, 99, 123, 256, 512, 999, 2026],
)
def test_randomized_three_engine_agreement(seed, cpp_executable):
    events = generate_events(seed, event_count=500)

    report = compare_engines(
        events,
        executable=cpp_executable,
    )

    assert report["matched"], (
        f"Three-engine disagreement for seed {seed}.\n"
        f"Report: {report}"
    )

    assert report["event_count"] == 500
    assert report["engines"] == [
        "Python",
        "Reference",
        "C++",
    ]


def test_generator_is_deterministic():
    first = generate_events(seed=42, event_count=500)
    second = generate_events(seed=42, event_count=500)

    assert first == second


def test_reference_engine_is_deterministic():
    events = generate_events(seed=2026, event_count=500)

    first = run_reference_engine(events)
    second = run_reference_engine(events)

    assert first == second
