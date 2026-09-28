import pytest

from lob.matching import OrderBook
from lob.models import Side


def test_empty_book():
    b = OrderBook("TEST")
    assert b.best_bid() is None and b.best_ask() is None
    assert b.spread() is None and b.mid_price() is None
    assert b.depth(Side.BUY) == [] and len(b) == 0


def test_best_prices_and_spread(make):
    b = OrderBook("TEST")
    for o in (
        make(Side.BUY, 10, 4990),
        make(Side.BUY, 10, 4995),
        make(Side.SELL, 10, 5005),
        make(Side.SELL, 10, 5010),
    ):
        b.add_order(o)
    assert b.best_bid() == 4995 and b.best_ask() == 5005
    assert b.spread() == 10
    assert b.mid_price() == 5000.0


def test_one_sided_book_has_no_spread(make):
    b = OrderBook("TEST")
    b.add_order(make(Side.BUY, 10, 4990))
    assert b.best_bid() == 4990 and b.best_ask() is None
    assert b.spread() is None and b.mid_price() is None


def test_depth_aggregates_levels_best_first(make):
    b = OrderBook("TEST")
    for o in (
        make(Side.BUY, 10, 100),
        make(Side.BUY, 5, 100),
        make(Side.BUY, 7, 99),
        make(Side.SELL, 3, 101),
    ):
        b.add_order(o)
    assert b.depth(Side.BUY) == [(100, 15), (99, 7)]
    assert b.depth(Side.BUY, levels=1) == [(100, 15)]
    assert b.depth(Side.SELL) == [(101, 3)]


def test_duplicate_id_rejected(make):
    b = OrderBook("TEST")
    o = make(Side.BUY, 10, 100)
    b.add_order(o)
    with pytest.raises(ValueError):
        b.add_order(o)


def test_cancel_removes_from_depth_and_best(make):
    b = OrderBook("TEST")
    o1, o2 = make(Side.BUY, 10, 100), make(Side.BUY, 5, 99)
    b.add_order(o1)
    b.add_order(o2)
    assert b.cancel_order(o1.order_id) is True
    assert b.best_bid() == 99
    assert b.depth(Side.BUY) == [(99, 5)]


def test_cancel_unknown_or_twice(make):
    b = OrderBook("TEST")
    o = make(Side.BUY, 10, 100)
    b.add_order(o)
    assert b.cancel_order(999) is False
    assert b.cancel_order(o.order_id) is True
    assert b.cancel_order(o.order_id) is False


def test_readd_price_after_level_emptied(make):
    """Stale heap entries must not confuse best-price lookup."""
    b = OrderBook("TEST")
    o1 = make(Side.BUY, 10, 100)
    b.add_order(o1)
    b.cancel_order(o1.order_id)
    assert b.best_bid() is None
    b.add_order(make(Side.BUY, 4, 100))
    assert b.best_bid() == 100 and b.depth(Side.BUY) == [(100, 4)]
