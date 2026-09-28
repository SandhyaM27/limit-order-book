import pytest

from lob.models import Order, OrderStatus, OrderType, Side


def test_limit_order_creation():
    o = Order(1, 1, "AAPL", Side.BUY, OrderType.LIMIT, 100, 5002)
    assert o.remaining_quantity == 100
    assert o.filled_quantity == 0
    assert o.status is OrderStatus.NEW and o.is_active


def test_market_order_has_no_price():
    o = Order(2, 2, "AAPL", Side.SELL, OrderType.MARKET, 50)
    assert o.price is None


@pytest.mark.parametrize("qty", [0, -5])
def test_invalid_quantity(qty):
    with pytest.raises(ValueError):
        Order(3, 3, "AAPL", Side.BUY, OrderType.LIMIT, qty, 5000)


def test_float_quantity_rejected():
    with pytest.raises(ValueError):
        Order(3, 3, "AAPL", Side.BUY, OrderType.LIMIT, 1.5, 5000)  # type: ignore[arg-type]


def test_limit_order_requires_price():
    with pytest.raises(ValueError):
        Order(4, 4, "AAPL", Side.BUY, OrderType.LIMIT, 10)


@pytest.mark.parametrize("price", [0, -1])
def test_limit_order_rejects_non_positive_price(price):
    with pytest.raises(ValueError):
        Order(5, 5, "AAPL", Side.BUY, OrderType.LIMIT, 10, price)


def test_market_order_with_price_rejected():
    with pytest.raises(ValueError):
        Order(6, 6, "AAPL", Side.BUY, OrderType.MARKET, 10, 5000)


def test_empty_symbol_rejected():
    with pytest.raises(ValueError):
        Order(7, 7, "", Side.BUY, OrderType.MARKET, 10)


def test_side_opposite():
    assert Side.BUY.opposite is Side.SELL and Side.SELL.opposite is Side.BUY
