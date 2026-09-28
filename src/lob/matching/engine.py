"""Matching engine: price-time priority, continuous trading.

Algorithm for an incoming order:
  1. Look at the best price on the OPPOSITE side.
  2. Does it cross? (BUY crosses if best_ask <= limit; SELL if best_bid >= limit;
     MARKET always crosses while liquidity exists.)
  3. Fill against the oldest order at that level; trade price = RESTING price.
  4. Repeat until the order is filled, or stops crossing, or the book is empty.
  5. Leftover LIMIT quantity rests in the book. Leftover MARKET quantity is
     discarded (it never rests).
"""

from __future__ import annotations

from lob.matching.order_book import OrderBook
from lob.models.order import Order, OrderStatus, OrderType, Side
from lob.models.trade import Trade


class MatchingEngine:
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self.book = OrderBook(symbol)
        self._next_trade_id = 1

    def submit(self, order: Order) -> list[Trade]:
        """Process one order. Returns the trades it generated (maybe empty)."""
        if order.symbol != self.symbol:
            raise ValueError(f"engine trades {self.symbol}, got {order.symbol}")
        if not order.is_active or order.remaining_quantity != order.quantity:
            raise ValueError("order must be fresh (NEW, unfilled)")
        if order.order_id in self.book._orders:
            raise ValueError(f"duplicate order id {order.order_id}")

        trades = self._match(order)

        if order.remaining_quantity == 0:
            order.status = OrderStatus.FILLED
        elif order.order_type is OrderType.LIMIT:
            order.status = OrderStatus.PARTIALLY_FILLED if trades else OrderStatus.NEW
            self.book.add_order(order)
        else:  # MARKET with leftover: liquidity ran out, remainder discarded
            order.status = OrderStatus.PARTIALLY_FILLED if trades else OrderStatus.CANCELLED
        return trades

    def cancel(self, order_id: int) -> bool:
        return self.book.cancel_order(order_id)

    def _match(self, incoming: Order) -> list[Trade]:
        trades: list[Trade] = []
        book = self.book
        opp = incoming.side.opposite
        is_buy = incoming.side is Side.BUY

        while incoming.remaining_quantity > 0:
            level = book.best_level(opp)
            if level is None:
                break
            if incoming.order_type is OrderType.LIMIT:
                limit = incoming.price
                assert limit is not None
                if (is_buy and level.price > limit) or (not is_buy and level.price < limit):
                    break

            resting = level.head()
            if resting is None:  # impossible if level totals are consistent
                raise RuntimeError("corrupt book: non-empty level has no active order")

            qty = min(incoming.remaining_quantity, resting.remaining_quantity)
            incoming.remaining_quantity -= qty
            resting.remaining_quantity -= qty
            book.reduce_level(level, opp, qty)

            if resting.remaining_quantity == 0:
                resting.status = OrderStatus.FILLED
                level.orders.popleft()
                book.remove_filled(resting)
            else:
                resting.status = OrderStatus.PARTIALLY_FILLED

            buy_id, sell_id = (
                (incoming.order_id, resting.order_id) if is_buy else (resting.order_id, incoming.order_id)
            )
            trades.append(
                Trade(
                    trade_id=self._next_trade_id,
                    timestamp=incoming.timestamp,
                    symbol=self.symbol,
                    price=level.price,
                    quantity=qty,
                    buy_order_id=buy_id,
                    sell_order_id=sell_id,
                    aggressor_side=incoming.side,
                )
            )
            self._next_trade_id += 1
        return trades
