"""Limit order book.

Data structures (and why):
  * price -> PriceLevel dict ........ O(1) access to any price level
  * PriceLevel = deque of orders .... O(1) FIFO append / pop-front (time priority)
  * heap of prices per side ......... O(log P) insert, O(1) peek of best price
  * order_id -> Order dict .......... O(1) cancel lookup

Cancellation is *lazy*: a cancelled order is marked CANCELLED and its quantity
is subtracted from the level's total immediately, but it stays in the deque
until it reaches the front (then it is skipped). This makes cancel O(1)
instead of O(n) for removing from the middle of a deque.
Empty price levels are removed from the dict; stale heap entries are discarded
lazily when they reach the top of the heap.
"""

from __future__ import annotations

import heapq
from collections import deque

from lob.models.order import Order, OrderStatus, Side


class PriceLevel:
    """All resting orders at one price, oldest first."""

    __slots__ = ("price", "orders", "total_quantity")

    def __init__(self, price: int) -> None:
        self.price = price
        self.orders: deque[Order] = deque()
        self.total_quantity = 0  # sum of remaining qty of ACTIVE orders

    def add(self, order: Order) -> None:
        self.orders.append(order)
        self.total_quantity += order.remaining_quantity

    def head(self) -> Order | None:
        """Oldest active order (drops cancelled ones lazily)."""
        while self.orders:
            if self.orders[0].is_active:
                return self.orders[0]
            self.orders.popleft()
        return None

    @property
    def is_empty(self) -> bool:
        return self.total_quantity == 0


class OrderBook:
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self._levels: dict[Side, dict[int, PriceLevel]] = {Side.BUY: {}, Side.SELL: {}}
        # Min-heaps. Bids store NEGATED prices so the highest bid pops first.
        self._heaps: dict[Side, list[int]] = {Side.BUY: [], Side.SELL: []}
        self._orders: dict[int, Order] = {}

    # ---- mutation -------------------------------------------------------
    def add_order(self, order: Order) -> None:
        """Rest a LIMIT order in the book. O(1) if the level exists, else O(log P)."""
        if order.order_id in self._orders:
            raise ValueError(f"duplicate order id {order.order_id}")
        assert order.price is not None
        levels = self._levels[order.side]
        level = levels.get(order.price)
        if level is None:
            level = levels[order.price] = PriceLevel(order.price)
            key = -order.price if order.side is Side.BUY else order.price
            heapq.heappush(self._heaps[order.side], key)
        level.add(order)
        self._orders[order.order_id] = order

    def cancel_order(self, order_id: int) -> bool:
        """Cancel a resting order. O(1) amortised. False if unknown/already done."""
        order = self._orders.get(order_id)
        if order is None or not order.is_active:
            return False
        level = self._levels[order.side][order.price]  # type: ignore[index]
        level.total_quantity -= order.remaining_quantity
        order.status = OrderStatus.CANCELLED
        del self._orders[order_id]
        if level.is_empty:
            del self._levels[order.side][order.price]  # type: ignore[arg-type]
        return True

    def reduce_level(self, level: PriceLevel, side: Side, qty: int) -> None:
        """Called by the engine after a fill to keep level totals correct."""
        level.total_quantity -= qty
        if level.is_empty:
            del self._levels[side][level.price]

    def remove_filled(self, order: Order) -> None:
        self._orders.pop(order.order_id, None)

    # ---- queries --------------------------------------------------------
    def _best_price(self, side: Side) -> int | None:
        heap, levels = self._heaps[side], self._levels[side]
        while heap:
            price = -heap[0] if side is Side.BUY else heap[0]
            if price in levels:
                return price
            heapq.heappop(heap)  # stale entry
        return None

    def best_bid(self) -> int | None:
        return self._best_price(Side.BUY)

    def best_ask(self) -> int | None:
        return self._best_price(Side.SELL)

    def best_level(self, side: Side) -> PriceLevel | None:
        price = self._best_price(side)
        return None if price is None else self._levels[side][price]

    def spread(self) -> int | None:
        bid, ask = self.best_bid(), self.best_ask()
        return None if bid is None or ask is None else ask - bid

    def mid_price(self) -> float | None:
        bid, ask = self.best_bid(), self.best_ask()
        return None if bid is None or ask is None else (bid + ask) / 2

    def depth(self, side: Side, levels: int = 10) -> list[tuple[int, int]]:
        """Top `levels` (price, total_quantity), best first. O(P log P)."""
        prices = sorted(self._levels[side], reverse=(side is Side.BUY))
        return [(p, self._levels[side][p].total_quantity) for p in prices[:levels]]

    def get_order(self, order_id: int) -> Order | None:
        return self._orders.get(order_id)

    def __len__(self) -> int:
        return len(self._orders)
