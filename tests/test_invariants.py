
from aegis.exchange import Exchange
from aegis.models import Order, Side, OrderType
from aegis.invariants import check_exchange


def make_order(order_id, client, side, price, qty, sequence):
    return Order(
        order_id=order_id,
        client_id=client,
        side=side,
        order_type=OrderType.LIMIT,
        price=price,
        original_qty=qty,
        sequence=sequence,
    )


def test_empty_exchange_is_valid():
    exchange = Exchange()

    report = check_exchange(exchange)

    assert report.valid
    assert report.violations == []


def test_valid_resting_order_is_valid():
    exchange = Exchange()

    order = make_order(1, "ALICE", Side.BUY, 100, 5, 1)
    exchange.submit_limit_order(order)

    report = check_exchange(exchange)

    assert report.valid


def test_valid_full_trade_is_valid():
    exchange = Exchange()

    resting = make_order(1, "ALICE", Side.SELL, 100, 5, 1)
    incoming = make_order(2, "BOB", Side.BUY, 100, 5, 2)

    exchange.submit_limit_order(resting)
    exchange.submit_limit_order(incoming)

    report = check_exchange(exchange)

    assert report.valid, report.violations


def test_valid_partial_trade_is_valid():
    exchange = Exchange()

    resting = make_order(1, "ALICE", Side.SELL, 100, 5, 1)
    incoming = make_order(2, "BOB", Side.BUY, 100, 2, 2)

    exchange.submit_limit_order(resting)
    exchange.submit_limit_order(incoming)

    report = check_exchange(exchange)

    assert report.valid, report.violations


def test_detects_quantity_conservation_violation():
    exchange = Exchange()

    order = make_order(1, "ALICE", Side.BUY, 100, 5, 1)
    exchange.submit_limit_order(order)

    order.remaining_qty = 3

    report = check_exchange(exchange)

    assert not report.valid
    assert any(
        "QUANTITY_CONSERVATION" in item
        for item in report.violations
    )


def test_detects_crossed_order_book():
    exchange = Exchange()

    buy = make_order(1, "ALICE", Side.BUY, 110, 5, 1)
    sell = make_order(2, "BOB", Side.SELL, 100, 5, 2)

    exchange.orders[1] = buy
    exchange.orders[2] = sell
    exchange.used_order_ids.update({1, 2})

    report = check_exchange(exchange)

    assert not report.valid
    assert "CROSSED_ORDER_BOOK" in report.violations


def test_detects_negative_remaining_quantity():
    exchange = Exchange()

    order = make_order(1, "ALICE", Side.BUY, 100, 5, 1)
    exchange.submit_limit_order(order)

    order.remaining_qty = -1

    report = check_exchange(exchange)

    assert not report.valid
    assert any(
        "NEGATIVE_QUANTITY" in item
        for item in report.violations
    )


def test_detects_wrong_trade_price():
    exchange = Exchange()

    resting = make_order(1, "ALICE", Side.SELL, 100, 5, 1)
    incoming = make_order(2, "BOB", Side.BUY, 110, 5, 2)

    exchange.submit_limit_order(resting)
    exchange.submit_limit_order(incoming)

    exchange.trades[0].price = 105

    report = check_exchange(exchange)

    assert not report.valid
    assert "RESTING_PRICE_MISMATCH: 1" in report.violations
