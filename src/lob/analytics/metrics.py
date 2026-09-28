"""Market microstructure analytics. Pure functions: they READ the book/trades,
never modify them."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from lob.matching.order_book import OrderBook
from lob.models.order import Side
from lob.models.trade import Trade

BPS = 10_000


def spread(book: OrderBook) -> int | None:
    """Best ask - best bid, in ticks."""
    return book.spread()


def mid_price(book: OrderBook) -> float | None:
    """(best bid + best ask) / 2."""
    return book.mid_price()


def market_depth(book: OrderBook, levels: int = 5) -> dict[str, int]:
    """Total resting quantity in the top N levels of each side."""
    return {
        "bid": sum(q for _, q in book.depth(Side.BUY, levels)),
        "ask": sum(q for _, q in book.depth(Side.SELL, levels)),
    }


def order_book_imbalance(book: OrderBook, levels: int = 5) -> float | None:
    """(bid_vol - ask_vol) / (bid_vol + ask_vol) in [-1, 1].

    > 0 means more resting buy interest (upward pressure), < 0 the opposite.
    None if the book is completely empty.
    """
    d = market_depth(book, levels)
    total = d["bid"] + d["ask"]
    return None if total == 0 else (d["bid"] - d["ask"]) / total


def trade_volume(trades: Iterable[Trade]) -> int:
    return sum(t.quantity for t in trades)


def vwap(trades: Iterable[Trade]) -> float | None:
    """Volume-weighted average price = sum(p_i * q_i) / sum(q_i)."""
    notional = volume = 0
    for t in trades:
        notional += t.price * t.quantity
        volume += t.quantity
    return None if volume == 0 else notional / volume


def slippage_bps(avg_fill_price: float, arrival_mid: float, side: Side) -> float:
    """Execution cost vs. the mid price at arrival, in basis points.

    BUY:  (avg_fill - mid) / mid * 10_000  (paying more than mid = positive cost)
    SELL: (mid - avg_fill) / mid * 10_000
    """
    sign = 1 if side is Side.BUY else -1
    return sign * (avg_fill_price - arrival_mid) / arrival_mid * BPS


def market_impact_bps(mid_before: float, mid_after: float, side: Side) -> float:
    """Price move caused by the order: how far the mid shifted in the order's
    direction, in bps of the pre-trade mid. Positive = the order moved the
    price against itself (buys push price up, sells push it down)."""
    sign = 1 if side is Side.BUY else -1
    return sign * (mid_after - mid_before) / mid_before * BPS


@dataclass(frozen=True, slots=True)
class ExecutionEstimate:
    filled: int
    avg_price: float | None
    unfilled: int


def estimate_market_order(book: OrderBook, side: Side, quantity: int) -> ExecutionEstimate:
    """What WOULD a market order of `quantity` pay? Walks the book WITHOUT
    changing it. O(P log P) because depth() sorts price levels."""
    opp = side.opposite
    remaining, notional = quantity, 0
    for price, qty in book.depth(opp, levels=10**9):
        take = min(remaining, qty)
        notional += take * price
        remaining -= take
        if remaining == 0:
            break
    filled = quantity - remaining
    return ExecutionEstimate(filled, notional / filled if filled else None, remaining)
