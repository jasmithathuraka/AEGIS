
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXECUTABLE = ROOT / "aegis_cpp_jsonl"


@pytest.fixture(scope="module")
def cpp_executable():
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
        str(EXECUTABLE),
    ]

    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, (
        "C++ compilation failed:\n" + result.stderr
    )

    return EXECUTABLE


def run_cpp(executable, input_text):
    result = subprocess.run(
        [str(executable)],
        input=input_text,
        text=True,
        capture_output=True,
        check=True,
    )

    return [
        json.loads(line)
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def test_two_limit_orders_match(cpp_executable):
    events = [
        {"type": "LIMIT", "id": 1, "client": "seller_a",
         "side": "SELL", "price": 100, "qty": 5},
        {"type": "LIMIT", "id": 2, "client": "buyer_a",
         "side": "BUY", "price": 100, "qty": 3},
    ]

    results = run_cpp(
        cpp_executable,
        "\n".join(json.dumps(e) for e in events) + "\n",
    )

    assert len(results) == 2
    assert results[0]["status"] == "ACCEPTED"
    assert results[1]["status"] == "ACCEPTED"
    assert len(results[1]["trades"]) == 1
    assert results[1]["trades"][0]["qty"] == 3
    assert results[1]["trades"][0]["price"] == 100


def test_blank_line_is_rejected(cpp_executable):
    results = run_cpp(cpp_executable, "\n")

    assert len(results) == 1
    assert results[0]["seq"] == 1
    assert results[0]["reject_code"] == "MALFORMED_EVENT"


def test_invalid_json_is_rejected(cpp_executable):
    results = run_cpp(cpp_executable, "not json\n")

    assert results[0]["reject_code"] == "MALFORMED_EVENT"


def test_zero_quantity_is_rejected(cpp_executable):
    event = {
        "type": "LIMIT", "id": 1, "client": "buyer_a",
        "side": "BUY", "price": 100, "qty": 0,
    }

    results = run_cpp(cpp_executable, json.dumps(event) + "\n")

    assert results[0]["status"] == "REJECTED"
    assert results[0]["reject_code"] == "INVALID_QUANTITY"


def test_extra_field_is_rejected(cpp_executable):
    event = {
        "type": "LIMIT", "id": 1, "client": "buyer_a",
        "side": "BUY", "price": 100, "qty": 5,
        "extra": "not_allowed",
    }

    results = run_cpp(cpp_executable, json.dumps(event) + "\n")

    assert results[0]["reject_code"] == "MALFORMED_EVENT"


def test_decimal_quantity_is_rejected(cpp_executable):
    event = (
        '{"type":"LIMIT","id":1,"client":"buyer_a",'
        '"side":"BUY","price":100,"qty":2.5}'
    )

    results = run_cpp(cpp_executable, event + "\n")

    assert results[0]["reject_code"] == "INVALID_QUANTITY"


def test_event_sequences_increase(cpp_executable):
    events = [
        '{"type":"UNKNOWN"}',
        '{"type":"LIMIT","id":1,"client":"seller_a",'
        '"side":"SELL","price":100,"qty":5}',
    ]

    results = run_cpp(cpp_executable, "\n".join(events) + "\n")

    assert results[0]["seq"] == 1
    assert results[1]["seq"] == 2


def test_duplicate_key_is_rejected(cpp_executable):
    event = (
        '{"type":"LIMIT","id":1,"client":"buyer_a",'
        '"side":"BUY","price":100,"qty":5,"qty":9}'
    )

    results = run_cpp(cpp_executable, event + "\n")

    assert results[0]["status"] == "REJECTED"
    assert results[0]["reject_code"] == "MALFORMED_EVENT"


def test_duplicate_key_does_not_block_next_event(cpp_executable):
    events = [
        '{"type":"LIMIT","id":1,"client":"buyer_a",'
        '"side":"BUY","price":100,"qty":5,"qty":9}',
        '{"type":"LIMIT","id":2,"client":"seller_a",'
        '"side":"SELL","price":100,"qty":3}',
    ]

    results = run_cpp(cpp_executable, "\n".join(events) + "\n")

    assert len(results) == 2
    assert results[0]["seq"] == 1
    assert results[0]["reject_code"] == "MALFORMED_EVENT"
    assert results[1]["seq"] == 2
    assert results[1]["status"] == "ACCEPTED"


def test_sequence_counts_malformed_lines(cpp_executable):
    events = [
        "not json",
        '{"type":"LIMIT","id":1,"client":"seller_a",'
        '"side":"SELL","price":100,"qty":5}',
    ]

    results = run_cpp(cpp_executable, "\n".join(events) + "\n")

    assert results[0]["seq"] == 1
    assert results[0]["reject_code"] == "MALFORMED_EVENT"
    assert results[1]["seq"] == 2
    assert results[1]["status"] == "ACCEPTED"


def test_trade_uses_physical_event_sequence(cpp_executable):
    events = [
        "not json",
        '{"type":"LIMIT","id":1,"client":"seller_a",'
        '"side":"SELL","price":100,"qty":5}',
        '{"type":"LIMIT","id":2,"client":"buyer_a",'
        '"side":"BUY","price":100,"qty":3}',
    ]

    results = run_cpp(cpp_executable, "\n".join(events) + "\n")

    assert results[2]["seq"] == 3
    assert len(results[2]["trades"]) == 1
    assert results[2]["trades"][0]["event_seq"] == 3
