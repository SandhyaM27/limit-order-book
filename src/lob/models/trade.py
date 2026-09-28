from __future__ import annotations

from dataclasses import dataclass

from lob.models.order import Side


@dataclass(frozen=True, slots=True)
class Trade:
    """An executed match. Immutable: history must never change.

    `price` is always the RESTING order's price (the maker's price).
    `aggressor_side` is the side of the incoming (taker) order.
    """

    trade_id: int
    timestamp: int
    symbol: str
    price: int
    quantity: int
    buy_order_id: int
    sell_order_id: int
    aggressor_side: Side
