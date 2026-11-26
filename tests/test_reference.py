
from aegis.reference import ReferenceExchange, run_reference_engine


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


def test_price_priority():
    events = [
        limit(1, "seller_a", "SELL", 105, 5),
        limit(2, "seller_b", "SELL", 100, 5),
        limit(3, "buyer", "BUY", 110, 5),
    ]

    results = run_reference_engine(events)

    assert results[2]["trades"][0]["sell_id"] == 2
    assert results[2]["trades"][0]["price"] == 100


def test_fifo_priority():
    events = [
        limit(1, "seller_a", "SELL", 100, 3),
        limit(2, "seller_b", "SELL", 100, 4),
        limit(3, "buyer", "BUY", 100, 5),
    ]

    results = run_reference_engine(events)

    trades = results[2]["trades"]

    assert [trade["sell_id"] for trade in trades] == [1, 2]
    assert [trade["qty"] for trade in trades] == [3, 2]


def test_partial_fill_preserves_remaining_quantity():
    exchange = ReferenceExchange()

    exchange.process_event(limit(1, "seller", "SELL", 100, 10))
    result = exchange.process_event(limit(2, "buyer", "BUY", 100, 4))

    assert result["trades"][0]["qty"] == 4

    seller = exchange.orders[1]

    assert seller.remaining_qty == 6
    assert seller.executed_qty == 4
    assert seller.status == "PARTIAL"


def test_market_order_sweeps_multiple_price_levels():
    events = [
        limit(1, "seller_a", "SELL", 100, 3),
        limit(2, "seller_b", "SELL", 101, 4),
        market(3, "buyer", "BUY", 5),
    ]

    results = run_reference_engine(events)

    trades = results[2]["trades"]

    assert [trade["sell_id"] for trade in trades] == [1, 2]
    assert [trade["qty"] for trade in trades] == [3, 2]
    assert [trade["price"] for trade in trades] == [100, 101]


def test_unfilled_market_quantity_is_cancelled():
    exchange = ReferenceExchange()

    result = exchange.process_event(
        market(1, "buyer", "BUY", 10)
    )

    order = exchange.orders[1]

    assert result["status"] == "ACCEPTED"
    assert order.remaining_qty == 0
    assert order.cancelled_qty == 10
    assert order.status == "CANCELLED"


def test_self_trade_prevention_does_not_skip_order():
    events = [
        limit(1, "same_client", "SELL", 100, 3),
        limit(2, "other_client", "SELL", 100, 3),
        limit(3, "same_client", "BUY", 100, 5),
    ]

    results = run_reference_engine(events)

    incoming = results[2]

    assert incoming["trades"] == []
    assert incoming["order_updates"][0]["status"] == "CANCELLED"

    exchange = ReferenceExchange()
    for event in events:
        exchange.process_event(event)

    assert exchange.orders[2].remaining_qty == 3


def test_wrong_client_cannot_cancel_order():
    events = [
        limit(1, "seller", "SELL", 100, 5),
        cancel(1, "another_client"),
    ]

    results = run_reference_engine(events)

    assert results[1]["status"] == "REJECTED"
    assert results[1]["reject_code"] == "WRONG_CLIENT"


def test_successful_cancel_removes_remaining_quantity():
    exchange = ReferenceExchange()

    exchange.process_event(
        limit(1, "seller", "SELL", 100, 5)
    )

    result = exchange.process_event(
        cancel(1, "seller")
    )

    order = exchange.orders[1]

    assert result["status"] == "ACCEPTED"
    assert order.remaining_qty == 0
    assert order.cancelled_qty == 5
    assert order.status == "CANCELLED"


def test_duplicate_order_id_is_rejected():
    events = [
        limit(1, "seller", "SELL", 100, 5),
        limit(1, "buyer", "BUY", 100, 5),
    ]

    results = run_reference_engine(events)

    assert results[1]["status"] == "REJECTED"
    assert results[1]["reject_code"] == "DUPLICATE_ID"


def test_quantity_conservation_for_all_orders():
    events = [
        limit(1, "seller_a", "SELL", 100, 10),
        limit(2, "seller_b", "SELL", 101, 5),
        limit(3, "buyer", "BUY", 100, 4),
        cancel(1, "seller_a"),
        market(4, "market_buyer", "BUY", 10),
    ]

    exchange = ReferenceExchange()

    for event in events:
        exchange.process_event(event)

    for order in exchange.orders.values():
        assert order.original_qty == (
            order.executed_qty
            + order.cancelled_qty
            + order.remaining_qty
        )
