
from dataclasses import dataclass
from enum import Enum


class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"


class OrderStatus(Enum):
    ACTIVE = "ACTIVE"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


@dataclass
class Order:
    order_id: int
    client_id: str
    side: Side
    order_type: OrderType
    price: int | None
    original_qty: int
    sequence: int

    remaining_qty: int = 0
    executed_qty: int = 0
    cancelled_qty: int = 0
    status: OrderStatus = OrderStatus.ACTIVE

    def __post_init__(self):
        self.remaining_qty = self.original_qty

    def check_quantity_conservation(self) -> bool:
        return self.original_qty == (
            self.executed_qty
            + self.cancelled_qty
            + self.remaining_qty
        )
