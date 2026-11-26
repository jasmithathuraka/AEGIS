
from dataclasses import dataclass, field
from collections.abc import Mapping
from typing import Any


@dataclass
class InvariantReport:
    valid: bool
    violations: list[str] = field(default_factory=list)


def _get(obj: Any, *names: str, default=None):
    for name in names:
        if isinstance(obj, Mapping):
            if name in obj:
                return obj[name]
        elif hasattr(obj, name):
            return getattr(obj, name)
    return default


def _value(value):
    return getattr(value, "value", value)


def _side(order):
    return str(_value(_get(order, "side", default=""))).upper()


def _status(order):
    return str(_value(_get(order, "status", default=""))).upper()


def check_exchange(exchange: Any) -> InvariantReport:
    violations = []

    orders = _get(exchange, "orders", default={})
    trades = _get(exchange, "trades", default=[])

    if not isinstance(orders, Mapping):
        return InvariantReport(False, ["INVALID_ORDER_COLLECTION"])

    if not isinstance(trades, (list, tuple)):
        return InvariantReport(False, ["INVALID_TRADE_COLLECTION"])

    # Check every order independently.
    for key, order in orders.items():
        order_id = _get(order, "order_id", "id", default=key)

        original = _get(order, "original_qty")
        remaining = _get(order, "remaining_qty")
        executed = _get(order, "executed_qty", default=0)
        cancelled = _get(order, "cancelled_qty", default=0)

        quantities = {
            "original_qty": original,
            "remaining_qty": remaining,
            "executed_qty": executed,
            "cancelled_qty": cancelled,
        }

        invalid_quantity = False

        for name, quantity in quantities.items():
            if type(quantity) is not int:
                violations.append(
                    f"INVALID_QUANTITY: {order_id} {name}"
                )
                invalid_quantity = True
            elif quantity < 0:
                violations.append(
                    f"NEGATIVE_QUANTITY: {order_id} {name}"
                )
                invalid_quantity = True

        if invalid_quantity:
            continue

        if original <= 0:
            violations.append(f"INVALID_ORIGINAL_QUANTITY: {order_id}")

        if original > 2_147_483_647:
            violations.append(f"QUANTITY_LIMIT_EXCEEDED: {order_id}")

        if original != executed + cancelled + remaining:
            violations.append(f"QUANTITY_CONSERVATION: {order_id}")

        if executed > original or cancelled > original:
            violations.append(f"QUANTITY_EXCEEDED: {order_id}")

        side = _side(order)
        if side not in {"BUY", "SELL"}:
            violations.append(f"INVALID_SIDE: {order_id}")

        client = _get(order, "client_id", "client")
        if not isinstance(client, str) or not 1 <= len(client) <= 64:
            violations.append(f"INVALID_CLIENT: {order_id}")

        price = _get(order, "price")

        if price is not None:
            if (
                type(price) is not int
                or not 1 <= price <= 2_147_483_647
            ):
                violations.append(f"INVALID_PRICE: {order_id}")

        status = _status(order)

        if status not in {"ACTIVE", "PARTIAL", "FILLED", "CANCELLED"}:
            violations.append(f"INVALID_STATUS: {order_id}")

        if status == "ACTIVE" and (
            executed != 0 or cancelled != 0 or remaining <= 0
        ):
            violations.append(f"INVALID_ACTIVE_ORDER: {order_id}")

        if status == "PARTIAL" and (
            executed <= 0 or remaining <= 0 or cancelled != 0
        ):
            violations.append(f"INVALID_PARTIAL_ORDER: {order_id}")

        if status == "FILLED" and (
            remaining != 0 or executed != original or cancelled != 0
        ):
            violations.append(f"INVALID_FILLED_ORDER: {order_id}")

        if status == "CANCELLED" and remaining != 0:
            violations.append(f"INVALID_CANCELLED_ORDER: {order_id}")

    # A valid resting book must never have crossed prices.
    active_bids = [
        order for order in orders.values()
        if _side(order) == "BUY"
        and _status(order) in {"ACTIVE", "PARTIAL"}
        and type(_get(order, "price")) is int
        and type(_get(order, "remaining_qty")) is int
        and _get(order, "remaining_qty") > 0
    ]

    active_asks = [
        order for order in orders.values()
        if _side(order) == "SELL"
        and _status(order) in {"ACTIVE", "PARTIAL"}
        and type(_get(order, "price")) is int
        and type(_get(order, "remaining_qty")) is int
        and _get(order, "remaining_qty") > 0
    ]

    if active_bids and active_asks:
        best_bid = max(_get(order, "price") for order in active_bids)
        best_ask = min(_get(order, "price") for order in active_asks)

        if best_bid >= best_ask:
            violations.append("CROSSED_ORDER_BOOK")

    # Check trades against their participating orders.
    executed_from_trades = {}

    for index, trade in enumerate(trades):
        buy_id = _get(
            trade, "buy_order_id", "buy_id", "buyer_order_id"
        )
        sell_id = _get(
            trade, "sell_order_id", "sell_id", "seller_order_id"
        )
        quantity = _get(trade, "quantity", "qty")
        trade_price = _get(trade, "price")

        if type(quantity) is not int or quantity <= 0:
            violations.append(f"INVALID_TRADE_QUANTITY: {index}")
            continue

        if (
            type(trade_price) is not int
            or not 1 <= trade_price <= 2_147_483_647
        ):
            violations.append(f"INVALID_TRADE_PRICE: {index}")
            continue

        if buy_id == sell_id:
            violations.append(f"SELF_TRADE: {index}")

        if buy_id not in orders:
            violations.append(f"UNKNOWN_BUY_ORDER: {buy_id}")
            continue

        if sell_id not in orders:
            violations.append(f"UNKNOWN_SELL_ORDER: {sell_id}")
            continue

        buy_order = orders[buy_id]
        sell_order = orders[sell_id]

        if _side(buy_order) != "BUY":
            violations.append(f"INVALID_BUY_SIDE: {buy_id}")

        if _side(sell_order) != "SELL":
            violations.append(f"INVALID_SELL_SIDE: {sell_id}")

        executed_from_trades[buy_id] = (
            executed_from_trades.get(buy_id, 0) + quantity
        )
        executed_from_trades[sell_id] = (
            executed_from_trades.get(sell_id, 0) + quantity
        )

        # The older order is the resting order.
        buy_sequence = _get(buy_order, "sequence")
        sell_sequence = _get(sell_order, "sequence")

        if (
            type(buy_sequence) is int
            and type(sell_sequence) is int
        ):
            resting_order = (
                buy_order if buy_sequence < sell_sequence else sell_order
            )

            resting_id = _get(
                resting_order, "order_id", "id",
                default=buy_id if resting_order is buy_order else sell_id
            )

            resting_price = _get(resting_order, "price")

            if (
                type(resting_price) is int
                and trade_price != resting_price
            ):
                violations.append(
                    f"RESTING_PRICE_MISMATCH: {resting_id}"
                )

    # Trade history must agree with each order's executed quantity.
    for order_id, order in orders.items():
        recorded_executed = _get(order, "executed_qty", default=0)
        actual_executed = executed_from_trades.get(order_id, 0)

        if (
            type(recorded_executed) is int
            and recorded_executed != actual_executed
        ):
            violations.append(
                f"TRADE_QUANTITY_MISMATCH: {order_id}"
            )

    return InvariantReport(
        valid=len(violations) == 0,
        violations=violations,
    )


def check_invariants(exchange: Any) -> list[str]:
    return check_exchange(exchange).violations


def assert_invariants(exchange: Any) -> None:
    report = check_exchange(exchange)

    if not report.valid:
        raise AssertionError(
            "Invariant violations:\n- "
            + "\n- ".join(report.violations)
        )


def validate_exchange(exchange: Any) -> bool:
    return check_exchange(exchange).valid
