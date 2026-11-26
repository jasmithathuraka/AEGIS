
from dataclasses import dataclass, field


@dataclass
class ReferenceOrder:
    order_id: int
    client_id: str
    side: str
    order_type: str
    price: int | None
    original_qty: int
    sequence: int

    remaining_qty: int = 0
    executed_qty: int = 0
    cancelled_qty: int = 0
    status: str = "ACTIVE"

    def __post_init__(self):
        self.remaining_qty = self.original_qty


@dataclass
class ReferenceTrade:
    trade_seq: int
    event_seq: int
    buy_id: int
    sell_id: int
    qty: int
    price: int


@dataclass
class ReferenceExchange:
    orders: dict[int, ReferenceOrder] = field(default_factory=dict)
    used_order_ids: set[int] = field(default_factory=set)
    trades: list[ReferenceTrade] = field(default_factory=list)

    next_event_seq: int = 1
    next_trade_seq: int = 1

    def _best_resting_order(self, incoming):
        """
        Find the best eligible resting order using an independent
        list scan.

        LIMIT orders enforce their price boundary.
        MARKET orders have no price boundary.
        """

        candidates = []

        for order in self.orders.values():
            if order.side == incoming.side:
                continue

            if order.status not in ("ACTIVE", "PARTIAL"):
                continue

            if order.remaining_qty <= 0:
                continue

            if incoming.order_type == "LIMIT":
                if incoming.side == "BUY":
                    if order.price > incoming.price:
                        continue
                else:
                    if order.price < incoming.price:
                        continue

            if incoming.side == "BUY":
                priority = (order.price, order.sequence)
            else:
                priority = (-order.price, order.sequence)

            candidates.append((priority, order))

        if not candidates:
            return None

        return min(candidates, key=lambda item: item[0])[1]

    def _execute(self, incoming):
        event_trades = []

        while incoming.remaining_qty > 0:
            resting = self._best_resting_order(incoming)

            if resting is None:
                break

            if resting.client_id == incoming.client_id:
                incoming.cancelled_qty += incoming.remaining_qty
                incoming.remaining_qty = 0
                incoming.status = "CANCELLED"
                break

            executed = min(
                incoming.remaining_qty,
                resting.remaining_qty,
            )

            if incoming.side == "BUY":
                buy_id = incoming.order_id
                sell_id = resting.order_id
            else:
                buy_id = resting.order_id
                sell_id = incoming.order_id

            trade = ReferenceTrade(
                trade_seq=self.next_trade_seq,
                event_seq=incoming.sequence,
                buy_id=buy_id,
                sell_id=sell_id,
                qty=executed,
                price=resting.price,
            )

            self.next_trade_seq += 1

            self.trades.append(trade)
            event_trades.append(trade)

            incoming.remaining_qty -= executed
            incoming.executed_qty += executed

            resting.remaining_qty -= executed
            resting.executed_qty += executed

            if resting.remaining_qty == 0:
                resting.status = "FILLED"
            else:
                resting.status = "PARTIAL"

        if incoming.status != "CANCELLED":
            if incoming.remaining_qty == 0:
                incoming.status = "FILLED"
            elif incoming.executed_qty > 0:
                incoming.status = "PARTIAL"
            else:
                incoming.status = "ACTIVE"

        return event_trades

    def _cancel(self, order_id, client_id):
        order = self.orders.get(order_id)

        if order is None:
            return "UNKNOWN_ID", None

        if order.client_id != client_id:
            return "WRONG_CLIENT", None

        if order.remaining_qty == 0:
            return "NOT_ACTIVE", None

        order.cancelled_qty += order.remaining_qty
        order.remaining_qty = 0
        order.status = "CANCELLED"

        return "ACCEPTED", order

    @staticmethod
    def _trade_to_dict(trade):
        return {
            "trade_seq": trade.trade_seq,
            "event_seq": trade.event_seq,
            "buy_id": trade.buy_id,
            "sell_id": trade.sell_id,
            "qty": trade.qty,
            "price": trade.price,
        }

    @staticmethod
    def _order_update(order):
        return {
            "id": order.order_id,
            "remaining_qty": order.remaining_qty,
            "executed_qty": order.executed_qty,
            "cancelled_qty": order.cancelled_qty,
            "status": order.status,
        }

    def _result(
        self,
        seq,
        status,
        reject_code=None,
        trades=None,
        order_updates=None,
    ):
        return {
            "seq": seq,
            "status": status,
            "reject_code": reject_code,
            "trades": [
                self._trade_to_dict(trade)
                for trade in (trades or [])
            ],
            "order_updates": order_updates or [],
        }

    def process_event(self, event):
        seq = self.next_event_seq
        self.next_event_seq += 1

        event_type = event["type"]
        order_id = event["id"]

        if event_type == "CANCEL":
            result, order = self._cancel(
                order_id,
                event["client"],
            )

            if result != "ACCEPTED":
                return self._result(
                    seq,
                    "REJECTED",
                    reject_code=result,
                )

            return self._result(
                seq,
                "ACCEPTED",
                order_updates=[self._order_update(order)],
            )

        if order_id in self.used_order_ids:
            return self._result(
                seq,
                "REJECTED",
                reject_code="DUPLICATE_ID",
            )

        if event_type not in ("LIMIT", "MARKET"):
            raise ValueError("INVALID_TYPE")

        order = ReferenceOrder(
            order_id=order_id,
            client_id=event["client"],
            side=event["side"],
            order_type=event_type,
            price=event.get("price"),
            original_qty=event["qty"],
            sequence=seq,
        )

        event_trades = self._execute(order)

        if event_type == "MARKET" and order.remaining_qty > 0:
            order.cancelled_qty += order.remaining_qty
            order.remaining_qty = 0
            order.status = "CANCELLED"

        self.orders[order_id] = order
        self.used_order_ids.add(order_id)

        changed_ids = {order_id}

        for trade in event_trades:
            changed_ids.add(trade.buy_id)
            changed_ids.add(trade.sell_id)

        updates = [
            self._order_update(self.orders[changed_id])
            for changed_id in sorted(changed_ids)
        ]

        return self._result(
            seq,
            "ACCEPTED",
            trades=event_trades,
            order_updates=updates,
        )


def reference_result(event, exchange):
    return exchange.process_event(event)


def run_reference_engine(events):
    exchange = ReferenceExchange()

    return [
        reference_result(event, exchange)
        for event in events
    ]
