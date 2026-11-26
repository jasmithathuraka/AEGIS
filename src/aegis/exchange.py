
from dataclasses import dataclass, field

from aegis.models import Order, Side, OrderType, OrderStatus


@dataclass
class Trade:
    trade_seq: int
    event_seq: int
    buy_id: int
    sell_id: int
    qty: int
    price: int


@dataclass
class EventResult:
    seq: int
    status: str
    reject_code: str | None = None
    trades: list[Trade] = field(default_factory=list)
    order_updates: list[dict] = field(default_factory=list)


@dataclass
class Exchange:
    orders: dict[int, Order] = field(default_factory=dict)
    used_order_ids: set[int] = field(default_factory=set)
    trades: list[Trade] = field(default_factory=list)

    next_event_seq: int = 1
    next_trade_seq: int = 1

    def get_order(self, order_id: int) -> Order | None:
        return self.orders.get(order_id)

    def get_bids(self) -> list[Order]:
        bids = [
            order for order in self.orders.values()
            if order.side == Side.BUY
            and order.remaining_qty > 0
            and order.status in (
                OrderStatus.ACTIVE, OrderStatus.PARTIAL
            )
        ]
        return sorted(
            bids,
            key=lambda order: (-order.price, order.sequence),
        )

    def get_asks(self) -> list[Order]:
        asks = [
            order for order in self.orders.values()
            if order.side == Side.SELL
            and order.remaining_qty > 0
            and order.status in (
                OrderStatus.ACTIVE, OrderStatus.PARTIAL
            )
        ]
        return sorted(
            asks,
            key=lambda order: (order.price, order.sequence),
        )

    def _match(self, incoming: Order, is_market: bool = False) -> list[Trade]:
        new_trades = []

        while incoming.remaining_qty > 0:
            opposite = (
                self.get_asks()
                if incoming.side == Side.BUY
                else self.get_bids()
            )

            if not opposite:
                break

            resting = opposite[0]

            if not is_market:
                crosses = (
                    resting.price <= incoming.price
                    if incoming.side == Side.BUY
                    else resting.price >= incoming.price
                )
                if not crosses:
                    break

            # Cancel-newest self-trade prevention.
            if resting.client_id == incoming.client_id:
                incoming.cancelled_qty += incoming.remaining_qty
                incoming.remaining_qty = 0
                incoming.status = OrderStatus.CANCELLED
                break

            quantity = min(
                incoming.remaining_qty,
                resting.remaining_qty,
            )

            trade = Trade(
                trade_seq=self.next_trade_seq,
                event_seq=incoming.sequence,
                buy_id=(
                    incoming.order_id
                    if incoming.side == Side.BUY
                    else resting.order_id
                ),
                sell_id=(
                    incoming.order_id
                    if incoming.side == Side.SELL
                    else resting.order_id
                ),
                qty=quantity,
                price=resting.price,
            )

            self.next_trade_seq += 1
            self.trades.append(trade)
            new_trades.append(trade)

            incoming.remaining_qty -= quantity
            incoming.executed_qty += quantity

            resting.remaining_qty -= quantity
            resting.executed_qty += quantity

            if resting.remaining_qty == 0:
                resting.status = OrderStatus.FILLED
            else:
                resting.status = OrderStatus.PARTIAL

        if incoming.remaining_qty > 0:
            incoming.status = (
                OrderStatus.PARTIAL
                if incoming.executed_qty > 0
                else OrderStatus.ACTIVE
            )
        elif incoming.executed_qty == incoming.original_qty:
            incoming.status = OrderStatus.FILLED

        return new_trades

    def match_limit_order(self, incoming: Order) -> list[Trade]:
        return self._match(incoming)

    def submit_limit_order(self, order: Order) -> list[Trade]:
        if order.order_id in self.used_order_ids:
            raise ValueError("DUPLICATE_ID")

        if order.order_type != OrderType.LIMIT:
            raise ValueError("INVALID_TYPE")

        if order.price is None:
            raise ValueError("INVALID_PRICE")

        trades = self._match(order)

        self.used_order_ids.add(order.order_id)
        self.orders[order.order_id] = order

        return trades

    def submit_market_order(self, order: Order) -> list[Trade]:
        if order.order_id in self.used_order_ids:
            raise ValueError("DUPLICATE_ID")

        if order.order_type != OrderType.MARKET:
            raise ValueError("INVALID_TYPE")

        trades = self._match(order, is_market=True)

        if order.remaining_qty > 0:
            order.cancelled_qty += order.remaining_qty
            order.remaining_qty = 0
            order.status = OrderStatus.CANCELLED

        self.used_order_ids.add(order.order_id)
        self.orders[order.order_id] = order

        return trades

    def cancel_order(self, order_id: int, client_id: str) -> str:
        order = self.orders.get(order_id)

        if order is None:
            return "UNKNOWN_ID"

        if order.client_id != client_id:
            return "WRONG_CLIENT"

        if order.remaining_qty == 0:
            return "NOT_ACTIVE"

        order.cancelled_qty += order.remaining_qty
        order.remaining_qty = 0
        order.status = OrderStatus.CANCELLED

        return "ACCEPTED"

    def process_event(self, event: dict) -> EventResult:
        seq = self.next_event_seq
        self.next_event_seq += 1

        event_type = event["type"]
        order_id = event["id"]

        if event_type == "CANCEL":
            result = self.cancel_order(order_id, event["client"])

            if result != "ACCEPTED":
                return EventResult(seq, "REJECTED", result)

            return EventResult(
                seq,
                "ACCEPTED",
                order_updates=[
                    self._order_update(self.orders[order_id])
                ],
            )

        if order_id in self.used_order_ids:
            return EventResult(seq, "REJECTED", "DUPLICATE_ID")

        order_type = OrderType(event_type)

        order = Order(
            order_id=order_id,
            client_id=event["client"],
            side=Side(event["side"]),
            order_type=order_type,
            price=event.get("price"),
            original_qty=event["qty"],
            sequence=seq,
        )

        if order_type == OrderType.LIMIT:
            trades = self.submit_limit_order(order)
        else:
            trades = self.submit_market_order(order)

        changed_ids = {
            order.order_id,
            *[trade.buy_id for trade in trades],
            *[trade.sell_id for trade in trades],
        }

        updates = [
            self._order_update(self.orders[oid])
            for oid in sorted(changed_ids)
            if oid in self.orders
        ]

        return EventResult(
            seq=seq,
            status="ACCEPTED",
            trades=trades,
            order_updates=updates,
        )

    @staticmethod
    def _order_update(order: Order) -> dict:
        return {
            "id": order.order_id,
            "status": order.status.value,
            "remaining_qty": order.remaining_qty,
            "executed_qty": order.executed_qty,
            "cancelled_qty": order.cancelled_qty,
        }
