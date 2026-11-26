
import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def cpp_executable(tmp_path_factory):
    output = tmp_path_factory.mktemp("aegis") / "aegis_cpp"

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

    subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    return output


def run_events(executable, events):
    input_text = "\n".join(
        event if isinstance(event, str) else json.dumps(event)
        for event in events
    ) + "\n"

    result = subprocess.run(
        [str(executable)],
        input=input_text,
        capture_output=True,
        text=True,
        check=True,
    )

    return [json.loads(line) for line in result.stdout.splitlines()]


def limit(order_id, client, side, price, qty):
    return {
        "type": "LIMIT",
        "id": order_id,
        "client": client,
        "side": side,
        "price": price,
        "qty": qty,
    }


def market(order_id, client, side, qty):
    return {
        "type": "MARKET",
        "id": order_id,
        "client": client,
        "side": side,
        "qty": qty,
    }


def cancel(order_id, client):
    return {
        "type": "CANCEL",
        "id": order_id,
        "client": client,
    }


def test_repeated_cancel(cpp_executable):
    results = run_events(cpp_executable, [
        limit(1, "seller", "SELL", 100, 5),
        cancel(1, "seller"),
        cancel(1, "seller"),
    ])

    assert results[0]["status"] == "ACCEPTED"
    assert results[1]["status"] == "ACCEPTED"
    assert results[2]["reject_code"] == "NOT_ACTIVE"


def test_duplicate_order_id(cpp_executable):
    results = run_events(cpp_executable, [
        limit(1, "seller", "SELL", 100, 5),
        limit(1, "buyer", "BUY", 100, 5),
    ])

    assert results[0]["status"] == "ACCEPTED"
    assert results[1]["reject_code"] == "DUPLICATE_ID"


def test_self_trade_prevention(cpp_executable):
    results = run_events(cpp_executable, [
        limit(1, "same_client", "SELL", 100, 5),
        limit(2, "same_client", "BUY", 100, 5),
    ])

    assert results[0]["status"] == "ACCEPTED"
    assert results[1]["status"] == "ACCEPTED"
    assert results[1]["trades"] == []
    assert results[1]["order_updates"][0]["status"] == "CANCELLED"


def test_partial_fill(cpp_executable):
    results = run_events(cpp_executable, [
        limit(1, "seller", "SELL", 100, 5),
        limit(2, "buyer", "BUY", 100, 3),
    ])

    assert len(results[1]["trades"]) == 1
    assert results[1]["trades"][0]["qty"] == 3
    assert results[1]["trades"][0]["price"] == 100


def test_market_order_empty_book(cpp_executable):
    results = run_events(cpp_executable, [
        market(1, "buyer", "BUY", 10),
    ])

    assert results[0]["status"] == "ACCEPTED"
    assert results[0]["trades"] == []
    assert results[0]["order_updates"][0]["status"] == "CANCELLED"


def test_malformed_json(cpp_executable):
    results = run_events(cpp_executable, [
        "{not valid json",
        limit(1, "seller", "SELL", 100, 5),
    ])

    assert results[0]["reject_code"] == "MALFORMED_EVENT"
    assert results[1]["status"] == "ACCEPTED"
    assert results[0]["seq"] == 1
    assert results[1]["seq"] == 2


def test_decimal_quantity_rejected(cpp_executable):
    results = run_events(cpp_executable, [
        '{"type":"LIMIT","id":1,"client":"seller",'
        '"side":"SELL","price":100,"qty":2.5}'
    ])

    assert results[0]["reject_code"] == "INVALID_QUANTITY"


def test_zero_quantity_rejected(cpp_executable):
    results = run_events(cpp_executable, [
        limit(1, "seller", "SELL", 100, 0),
    ])

    assert results[0]["reject_code"] == "INVALID_QUANTITY"


def test_wrong_client_cannot_cancel(cpp_executable):
    results = run_events(cpp_executable, [
        limit(1, "seller", "SELL", 100, 5),
        cancel(1, "someone_else"),
    ])

    assert results[1]["reject_code"] == "WRONG_CLIENT"


def test_trade_sequence_increases(cpp_executable):
    results = run_events(cpp_executable, [
        limit(1, "seller_a", "SELL", 100, 2),
        limit(2, "seller_b", "SELL", 100, 2),
        limit(3, "buyer", "BUY", 100, 4),
    ])

    trades = results[2]["trades"]

    assert len(trades) == 2
    assert trades[0]["trade_seq"] < trades[1]["trade_seq"]
    assert [trade["qty"] for trade in trades] == [2, 2]

