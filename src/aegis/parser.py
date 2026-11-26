
import json
from dataclasses import dataclass
from typing import Any


class DuplicateKeyError(ValueError):
    pass


class InvalidJSONConstant(ValueError):
    pass


@dataclass
class ParseResult:
    valid: bool
    event: dict[str, Any] | None = None
    reject_code: str | None = None


def reject_duplicate_keys(pairs):
    result = {}

    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(key)
        result[key] = value

    return result


def reject_json_constant(value):
    raise InvalidJSONConstant(value)


def is_plain_integer(value):
    return type(value) is int


def parse_json_line(line: str) -> ParseResult:
    try:
        data = json.loads(
            line,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_json_constant,
        )
    except (json.JSONDecodeError, DuplicateKeyError, InvalidJSONConstant):
        return ParseResult(False, reject_code="MALFORMED_EVENT")

    if not isinstance(data, dict):
        return ParseResult(False, reject_code="MALFORMED_EVENT")

    if "type" not in data:
        return ParseResult(False, reject_code="MALFORMED_EVENT")

    event_type = data["type"]

    if event_type not in ("LIMIT", "MARKET", "CANCEL"):
        return ParseResult(False, reject_code="INVALID_TYPE")

    schemas = {
        "LIMIT": {"type", "id", "client", "side", "price", "qty"},
        "MARKET": {"type", "id", "client", "side", "qty"},
        "CANCEL": {"type", "id", "client"},
    }

    if set(data.keys()) != schemas[event_type]:
        return ParseResult(False, reject_code="MALFORMED_EVENT")

    client = data["client"]

    if (
        not isinstance(client, str)
        or not 1 <= len(client) <= 64
        or not client.isascii()
        or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-" for c in client)
    ):
        return ParseResult(False, reject_code="INVALID_CLIENT")

    order_id = data["id"]

    if not is_plain_integer(order_id) or not 1 <= order_id <= 4_294_967_295:
        return ParseResult(False, reject_code="INVALID_ID")

    if event_type != "CANCEL":
        if data["side"] not in ("BUY", "SELL"):
            return ParseResult(False, reject_code="INVALID_SIDE")

    if event_type == "LIMIT":
        price = data["price"]

        if not is_plain_integer(price) or not 1 <= price <= 2_147_483_647:
            return ParseResult(False, reject_code="INVALID_PRICE")

    if event_type != "CANCEL":
        qty = data["qty"]

        if not is_plain_integer(qty) or not 1 <= qty <= 2_147_483_647:
            return ParseResult(False, reject_code="INVALID_QUANTITY")

    return ParseResult(True, event=data)
