import itertools

import pytest

from lob.matching import MatchingEngine
from lob.models import Order, OrderType


@pytest.fixture
def engine() -> MatchingEngine:
    return MatchingEngine("TEST")


@pytest.fixture
def make():
    """Order factory with auto ids/timestamps: make(Side.BUY, 100, price=5000)."""
    ids = itertools.count(1)

    def _make(side, qty, price=None, otype=None):
        i = next(ids)
        otype = otype or (OrderType.LIMIT if price is not None else OrderType.MARKET)
        return Order(i, i, "TEST", side, otype, qty, price)

    return _make
