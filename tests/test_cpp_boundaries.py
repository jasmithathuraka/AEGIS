
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def cpp_executable(tmp_path_factory):
    executable = tmp_path_factory.mktemp("aegis_boundary") / "aegis_cpp"

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
        str(executable),
    ]

    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    return executable


def run_cpp(executable, lines):
    result = subprocess.run(
        [str(executable)],
        input="\n".join(lines) + "\n",
        capture_output=True,
        text=True,
        check=True,
    )

    return [json.loads(line) for line in result.stdout.splitlines()]


def test_maximum_order_id(cpp_executable):
    result = run_cpp(cpp_executable, [
        '{"type":"LIMIT","id":4294967295,"client":"buyer",'
        '"side":"BUY","price":100,"qty":1}'
    ])

    assert result[0]["status"] == "ACCEPTED"


def test_order_id_above_maximum(cpp_executable):
    result = run_cpp(cpp_executable, [
        '{"type":"LIMIT","id":4294967296,"client":"buyer",'
        '"side":"BUY","price":100,"qty":1}'
    ])

    assert result[0]["reject_code"] == "INVALID_ID"


def test_zero_order_id(cpp_executable):
    result = run_cpp(cpp_executable, [
        '{"type":"LIMIT","id":0,"client":"buyer",'
        '"side":"BUY","price":100,"qty":1}'
    ])

    assert result[0]["reject_code"] == "INVALID_ID"


def test_maximum_price(cpp_executable):
    result = run_cpp(cpp_executable, [
        '{"type":"LIMIT","id":1,"client":"buyer",'
        '"side":"BUY","price":2147483647,"qty":1}'
    ])

    assert result[0]["status"] == "ACCEPTED"


def test_price_above_maximum(cpp_executable):
    result = run_cpp(cpp_executable, [
        '{"type":"LIMIT","id":1,"client":"buyer",'
        '"side":"BUY","price":2147483648,"qty":1}'
    ])

    assert result[0]["reject_code"] == "INVALID_PRICE"


def test_maximum_quantity(cpp_executable):
    result = run_cpp(cpp_executable, [
        '{"type":"LIMIT","id":1,"client":"buyer",'
        '"side":"BUY","price":100,"qty":2147483647}'
    ])

    assert result[0]["status"] == "ACCEPTED"


def test_quantity_above_maximum(cpp_executable):
    result = run_cpp(cpp_executable, [
        '{"type":"LIMIT","id":1,"client":"buyer",'
        '"side":"BUY","price":100,"qty":2147483648}'
    ])

    assert result[0]["reject_code"] == "INVALID_QUANTITY"


def test_maximum_client_length(cpp_executable):
    client = "a" * 64
    event = {
        "type": "LIMIT",
        "id": 1,
        "client": client,
        "side": "BUY",
        "price": 100,
        "qty": 1,
    }

    result = run_cpp(cpp_executable, [json.dumps(event)])
    assert result[0]["status"] == "ACCEPTED"


def test_client_too_long(cpp_executable):
    client = "a" * 65
    event = {
        "type": "LIMIT",
        "id": 1,
        "client": client,
        "side": "BUY",
        "price": 100,
        "qty": 1,
    }

    result = run_cpp(cpp_executable, [json.dumps(event)])
    assert result[0]["reject_code"] == "INVALID_CLIENT"


def test_negative_quantity(cpp_executable):
    result = run_cpp(cpp_executable, [
        '{"type":"LIMIT","id":1,"client":"buyer",'
        '"side":"BUY","price":100,"qty":-1}'
    ])

    assert result[0]["reject_code"] == "INVALID_QUANTITY"


def test_boolean_quantity(cpp_executable):
    result = run_cpp(cpp_executable, [
        '{"type":"LIMIT","id":1,"client":"buyer",'
        '"side":"BUY","price":100,"qty":true}'
    ])

    assert result[0]["reject_code"] == "INVALID_QUANTITY"


def test_exponent_quantity(cpp_executable):
    result = run_cpp(cpp_executable, [
        '{"type":"LIMIT","id":1,"client":"buyer",'
        '"side":"BUY","price":100,"qty":1e2}'
    ])

    assert result[0]["reject_code"] == "INVALID_QUANTITY"


def test_numeric_string_quantity(cpp_executable):
    result = run_cpp(cpp_executable, [
        '{"type":"LIMIT","id":1,"client":"buyer",'
        '"side":"BUY","price":100,"qty":"5"}'
    ])

    assert result[0]["reject_code"] == "INVALID_QUANTITY"


def test_market_order_maximum_quantity(cpp_executable):
    result = run_cpp(cpp_executable, [
        '{"type":"MARKET","id":1,"client":"buyer",'
        '"side":"BUY","qty":2147483647}'
    ])

    assert result[0]["status"] == "ACCEPTED"
