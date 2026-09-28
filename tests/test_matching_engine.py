import pytest

from lob.models import Order, OrderStatus, OrderType, Side


def test_limit_order_rests_when_no_cross(engine, make):
    o = make(Side.BUY, 100, 5000)
    assert engine.submit(o) == []
    assert o.status is OrderStatus.NEW
    assert engine.book.best_bid() == 5000


def test_non_crossing_orders_do_not_trade(engine, make):
    engine.submit(make(Side.SELL, 100, 5010))
    assert engine.submit(make(Side.BUY, 100, 5000)) == []
    assert engine.book.spread() == 10


def test_limit_order_crosses_at_resting_price(engine, make):
    sell = make(Side.SELL, 100, 5000)
    engine.submit(sell)
    buy = make(Side.BUY, 100, 5010)  # willing to pay more
    (t,) = engine.submit(buy)
    assert t.price == 5000  # trade at RESTING price
    assert t.quantity == 100 and t.aggressor_side is Side.BUY
    assert (t.buy_order_id, t.sell_order_id) == (buy.order_id, sell.order_id)
    assert buy.status is sell.status is OrderStatus.FILLED
    assert len(engine.book) == 0


def test_complete_fill_exact_match_leaves_empty_book(engine, make):
    engine.submit(make(Side.BUY, 50, 5000))
    engine.submit(make(Side.SELL, 50, 5000))
    assert engine.book.best_bid() is None and engine.book.best_ask() is None


def test_partial_fill_incoming_rests_remainder(engine, make):
    engine.submit(make(Side.SELL, 30, 5000))
    buy = make(Side.BUY, 100, 5000)
    (t,) = engine.submit(buy)
    assert t.quantity == 30
    assert buy.remaining_quantity == 70 and buy.status is OrderStatus.PARTIALLY_FILLED
    assert engine.book.depth(Side.BUY) == [(5000, 70)]
    assert engine.book.best_ask() is None


def test_partial_fill_resting_keeps_remainder(engine, make):
    sell = make(Side.SELL, 100, 5000)
    engine.submit(sell)
    engine.submit(make(Side.BUY, 40, 5000))
    assert sell.remaining_quantity == 60 and sell.status is OrderStatus.PARTIALLY_FILLED
    assert engine.book.depth(Side.SELL) == [(5000, 60)]


def test_multiple_matches_across_levels(engine, make):
    engine.submit(make(Side.SELL, 100, 5002))
    engine.submit(make(Side.SELL, 200, 5003))
    trades = engine.submit(make(Side.BUY, 250, None))  # market buy
    assert [(t.price, t.quantity) for t in trades] == [(5002, 100), (5003, 150)]
    assert engine.book.depth(Side.SELL) == [(5003, 50)]


def test_limit_stops_at_limit_price(engine, make):
    engine.submit(make(Side.SELL, 100, 5000))
    engine.submit(make(Side.SELL, 100, 5005))
    buy = make(Side.BUY, 300, 5002)
    trades = engine.submit(buy)
    assert [(t.price, t.quantity) for t in trades] == [(5000, 100)]
    assert engine.book.best_bid() == 5002 and engine.book.best_ask() == 5005


def test_price_priority_best_price_first(engine, make):
    engine.submit(make(Side.SELL, 10, 5005))
    engine.submit(make(Side.SELL, 10, 5001))
    engine.submit(make(Side.SELL, 10, 5003))
    trades = engine.submit(make(Side.BUY, 20, None))
    assert [t.price for t in trades] == [5001, 5003]


def test_time_priority_fifo_within_level(engine, make):
    first, second = make(Side.SELL, 10, 5000), make(Side.SELL, 10, 5000)
    engine.submit(first)
    engine.submit(second)
    (t,) = engine.submit(make(Side.BUY, 10, None))
    assert t.sell_order_id == first.order_id
    assert first.status is OrderStatus.FILLED and second.status is OrderStatus.NEW


def test_partially_filled_order_keeps_queue_position(engine, make):
    first, second = make(Side.SELL, 10, 5000), make(Side.SELL, 10, 5000)
    engine.submit(first)
    engine.submit(second)
    engine.submit(make(Side.BUY, 4, None))
    (t,) = engine.submit(make(Side.BUY, 4, None))
    assert t.sell_order_id == first.order_id  # still ahead of `second`


def test_market_order_on_empty_book(engine, make):
    m = make(Side.BUY, 10)
    assert engine.submit(m) == []
    assert m.status is OrderStatus.CANCELLED and len(engine.book) == 0


def test_market_order_exceeding_liquidity_discards_remainder(engine, make):
    engine.submit(make(Side.SELL, 10, 5000))
    m = make(Side.BUY, 25)
    (t,) = engine.submit(m)
    assert t.quantity == 10
    assert m.status is OrderStatus.PARTIALLY_FILLED and m.remaining_quantity == 15
    assert len(engine.book) == 0  # market orders never rest


def test_sell_side_symmetry(engine, make):
    engine.submit(make(Side.BUY, 10, 5000))
    engine.submit(make(Side.BUY, 10, 4990))
    trades = engine.submit(make(Side.SELL, 15, 4990))
    assert [(t.price, t.quantity) for t in trades] == [(5000, 10), (4990, 5)]
    assert all(t.aggressor_side is Side.SELL for t in trades)


def test_cancel_resting_order(engine, make):
    o = make(Side.BUY, 10, 5000)
    engine.submit(o)
    assert engine.cancel(o.order_id) is True
    assert o.status is OrderStatus.CANCELLED and engine.book.best_bid() is None


def test_cancelled_order_never_matches(engine, make):
    a, b = make(Side.SELL, 10, 5000), make(Side.SELL, 10, 5000)
    engine.submit(a)
    engine.submit(b)
    engine.cancel(a.order_id)
    (t,) = engine.submit(make(Side.BUY, 10, None))
    assert t.sell_order_id == b.order_id


def test_cancel_filled_order_fails(engine, make):
    s = make(Side.SELL, 10, 5000)
    engine.submit(s)
    engine.submit(make(Side.BUY, 10, None))
    assert engine.cancel(s.order_id) is False


def test_cancel_partially_filled_removes_only_remainder(engine, make):
    s = make(Side.SELL, 100, 5000)
    engine.submit(s)
    engine.submit(make(Side.BUY, 30, None))
    assert engine.cancel(s.order_id) is True
    assert engine.book.best_ask() is None


def test_wrong_symbol_rejected(engine):
    with pytest.raises(ValueError):
        engine.submit(Order(1, 1, "OTHER", Side.BUY, OrderType.MARKET, 1))


def test_duplicate_order_id_rejected(engine, make):
    o = make(Side.BUY, 10, 5000)
    engine.submit(o)
    dup = Order(o.order_id, 99, "TEST", Side.BUY, OrderType.LIMIT, 5, 4000)
    with pytest.raises(ValueError):
        engine.submit(dup)


def test_resubmitting_used_order_rejected(engine, make):
    o = make(Side.BUY, 10, 5000)
    engine.submit(o)
    engine.cancel(o.order_id)
    with pytest.raises(ValueError):
        engine.submit(o)


def test_trade_ids_increment(engine, make):
    engine.submit(make(Side.SELL, 5, 5000))
    engine.submit(make(Side.SELL, 5, 5001))
    trades = engine.submit(make(Side.BUY, 10, None))
    assert [t.trade_id for t in trades] == [1, 2]
