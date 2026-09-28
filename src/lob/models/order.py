"""Order model.

Prices are integers ("ticks", e.g. cents): floats cannot represent most
decimal prices exactly, and matching needs exact equality between prices.
Timestamps are integers (microseconds of simulated time or a sequence number)
so runs are deterministic and testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"

    @property
    def opposite(self) -> Side:
        return Side.SELL if self is Side.BUY else Side.BUY


class OrderType(Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"


class OrderStatus(Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


@dataclass(slots=True)
class Order:
    """A single order. `slots=True` cuts per-object memory (no __dict__),
    which matters when a benchmark creates a million of them."""

    order_id: int
    timestamp: int
    symbol: str
    side: Side
    order_type: OrderType
    quantity: int
    price: int | None = None  # ticks; must be None for MARKET orders
    remaining_quantity: int = field(init=False)
    status: OrderStatus = field(default=OrderStatus.NEW, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.quantity, int) or self.quantity <= 0:
            raise ValueError("quantity must be a positive integer")
        if not self.symbol:
            raise ValueError("symbol must be non-empty")
        if self.order_type is OrderType.LIMIT:
            if self.price is None or self.price <= 0:
                raise ValueError("limit order needs a positive integer price")
        elif self.price is not None:
            raise ValueError("market order must not have a price")
        self.remaining_quantity = self.quantity

    @property
    def filled_quantity(self) -> int:
        return self.quantity - self.remaining_quantity

    @property
    def is_active(self) -> bool:
        return self.status in (OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED)
