import pytest

from lob.analytics import (
    estimate_market_order,
    market_depth,
    market_impact_bps,
    order_book_imbalance,
    slippage_bps,
    spread,
    trade_volume,
    vwap,
)
from lob.matching import OrderBook
from lob.models import Side, Trade


def _trade(price, qty):
    return Trade(1, 1, "TEST", price, qty, 1, 2, Side.BUY)


def _book(make, bids, asks):
    b = OrderBook("TEST")
    for p, q in bids:
        b.add_order(make(Side.BUY, q, p))
    for p, q in asks:
        b.add_order(make(Side.SELL, q, p))
    return b


def test_spread_and_empty(make):
    assert spread(OrderBook("TEST")) is None
    assert spread(_book(make, [(99, 1)], [(102, 1)])) == 3


def test_imbalance_values(make):
    assert order_book_imbalance(OrderBook("TEST")) is None
    assert order_book_imbalance(_book(make, [(99, 30)], [(101, 10)])) == pytest.approx(0.5)
    assert order_book_imbalance(_book(make, [(99, 10)], [(101, 30)])) == pytest.approx(-0.5)
    assert order_book_imbalance(_book(make, [(99, 10)], [(101, 10)])) == 0.0
    assert order_book_imbalance(_book(make, [(99, 10)], [])) == 1.0


def test_market_depth_respects_levels(make):
    b = _book(make, [(99, 10), (98, 20), (97, 30)], [(101, 5)])
    assert market_depth(b, 2) == {"bid": 30, "ask": 5}


def test_volume_and_vwap():
    ts = [_trade(100, 10), _trade(110, 30)]
    assert trade_volume(ts) == 40
    assert vwap(ts) == pytest.approx((1000 + 3300) / 40)
    assert vwap([]) is None and trade_volume([]) == 0


def test_slippage_sign_convention():
    assert slippage_bps(100.10, 100.00, Side.BUY) == pytest.approx(10.0)
    assert slippage_bps(99.90, 100.00, Side.SELL) == pytest.approx(10.0)
    assert slippage_bps(99.90, 100.00, Side.BUY) < 0  # price improvement


def test_market_impact_sign_convention():
    assert market_impact_bps(100.0, 100.5, Side.BUY) == pytest.approx(50.0)
    assert market_impact_bps(100.0, 99.5, Side.SELL) == pytest.approx(50.0)


def test_estimate_market_order_does_not_mutate_book(make):
    b = _book(make, [(99, 10)], [(101, 100), (102, 200)])
    est = estimate_market_order(b, Side.BUY, 150)
    assert est.filled == 150 and est.unfilled == 0
    assert est.avg_price == pytest.approx((100 * 101 + 50 * 102) / 150)
    assert b.depth(Side.SELL) == [(101, 100), (102, 200)]


def test_estimate_exceeding_liquidity(make):
    b = _book(make, [], [(101, 10)])
    est = estimate_market_order(b, Side.BUY, 25)
    assert (est.filled, est.unfilled) == (10, 15)
    assert estimate_market_order(OrderBook("TEST"), Side.BUY, 5).avg_price is None
