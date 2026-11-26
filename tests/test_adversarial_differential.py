
import subprocess
from pathlib import Path

import pytest

from aegis.differential import compare_engines


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def cpp_executable(tmp_path_factory):
    output = tmp_path_factory.mktemp("aegis_adversarial") / "aegis_cpp"

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


def check_both_engines(events, cpp_executable):
    report = compare_engines(
        events,
        executable=cpp_executable,
    )

    assert report["matched"], (
        f"Python and C++ engines disagree.\n"
        f"Events: {events}\n"
        f"Report: {report}"
    )


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


def test_partial_fill_and_remaining_order(cpp_executable):
    events = [
        limit(1, "seller", "SELL", 100, 10),
        limit(2, "buyer", "BUY", 100, 4),
    ]
    check_both_engines(events, cpp_executable)


def test_price_priority(cpp_executable):
    events = [
        limit(1, "seller_a", "SELL", 105, 5),
        limit(2, "seller_b", "SELL", 100, 5),
        limit(3, "buyer", "BUY", 110, 7),
    ]
    check_both_engines(events, cpp_executable)


def test_fifo_priority(cpp_executable):
    events = [
        limit(1, "seller_a", "SELL", 100, 3),
        limit(2, "seller_b", "SELL", 100, 4),
        limit(3, "buyer", "BUY", 100, 5),
    ]
    check_both_engines(events, cpp_executable)


def test_market_order_sweeps_multiple_levels(cpp_executable):
    events = [
        limit(1, "seller_a", "SELL", 100, 3),
        limit(2, "seller_b", "SELL", 101, 4),
        market(3, "buyer", "BUY", 10),
    ]
    check_both_engines(events, cpp_executable)


def test_cancel_then_submit(cpp_executable):
    events = [
        limit(1, "seller", "SELL", 100, 5),
        cancel(1, "seller"),
        limit(2, "buyer", "BUY", 100, 5),
    ]
    check_both_engines(events, cpp_executable)


def test_self_trade_stops_matching(cpp_executable):
    events = [
        limit(1, "same_client", "SELL", 100, 3),
        limit(2, "other_client", "SELL", 100, 3),
        limit(3, "same_client", "BUY", 100, 5),
    ]
    check_both_engines(events, cpp_executable)


def test_market_order_with_self_trade(cpp_executable):
    events = [
        limit(1, "same_client", "SELL", 100, 3),
        limit(2, "other_client", "SELL", 101, 3),
        market(3, "same_client", "BUY", 5),
    ]
    check_both_engines(events, cpp_executable)


def test_multiple_partial_fills(cpp_executable):
    events = [
        limit(1, "seller_a", "SELL", 100, 2),
        limit(2, "seller_b", "SELL", 100, 3),
        limit(3, "buyer", "BUY", 100, 4),
    ]
    check_both_engines(events, cpp_executable)


def test_multiple_cancellations(cpp_executable):
    events = [
        limit(1, "seller_a", "SELL", 100, 5),
        limit(2, "seller_b", "SELL", 101, 5),
        cancel(1, "seller_a"),
        cancel(2, "seller_b"),
    ]
    check_both_engines(events, cpp_executable)


def test_rejected_duplicate_does_not_change_book(cpp_executable):
    events = [
        limit(1, "seller", "SELL", 100, 5),
        limit(1, "buyer", "BUY", 100, 5),
        limit(2, "buyer", "BUY", 100, 3),
    ]
    check_both_engines(events, cpp_executable)
