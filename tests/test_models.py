from aegis.models import Order, Side, OrderType, OrderStatus


def test_create_limit_order():
    order = Order(
        order_id=101,
        client_id="ALICE",
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        price=100,
        original_qty=5,
        sequence=1,
    )

    assert order.order_id == 101
    assert order.price == 100
    assert order.remaining_qty == 5
    assert order.executed_qty == 0
    assert order.cancelled_qty == 0
    assert order.status == OrderStatus.ACTIVE


def test_create_market_order():
    order = Order(
        order_id=102,
        client_id="BOB",
        side=Side.SELL,
        order_type=OrderType.MARKET,
        price=None,
        original_qty=3,
        sequence=2,
    )

    assert order.price is None
    assert order.remaining_qty == 3


def test_buy_and_sell_sides():
    assert Side.BUY.value == "BUY"
    assert Side.SELL.value == "SELL"