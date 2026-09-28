import pytest

from lob.matching import MatchingEngine
from lob.models import OrderStatus
from lob.simulation import MarketSimulator, SimulationConfig, run_simulation


def test_config_probabilities_must_sum_to_one():
    with pytest.raises(ValueError):
        SimulationConfig(p_limit=0.5, p_market=0.5, p_cancel=0.5)


def test_same_seed_is_reproducible():
    cfg = SimulationConfig(n_events=500, seed=7)
    a = [
        (e.timestamp, e.cancel_id, e.order and (e.order.side, e.order.price, e.order.quantity))
        for e in MarketSimulator(cfg).events()
    ]
    b = [
        (e.timestamp, e.cancel_id, e.order and (e.order.side, e.order.price, e.order.quantity))
        for e in MarketSimulator(cfg).events()
    ]
    assert a == b and len(a) == 500


def test_timestamps_strictly_increasing():
    ts = [e.timestamp for e in MarketSimulator(SimulationConfig(n_events=2000)).events()]
    assert all(b > a for a, b in zip(ts, ts[1:]))


def test_higher_arrival_rate_compresses_time():
    slow = list(MarketSimulator(SimulationConfig(n_events=1000, arrival_rate=100)).events())[-1].timestamp
    fast = list(MarketSimulator(SimulationConfig(n_events=1000, arrival_rate=10_000)).events())[-1].timestamp
    assert fast < slow


def test_event_mix_roughly_matches_config():
    evs = list(
        MarketSimulator(SimulationConfig(n_events=20_000, p_limit=0.5, p_market=0.3, p_cancel=0.2)).events()
    )
    cancels = sum(e.cancel_id is not None for e in evs) / len(evs)
    assert 0.15 < cancels < 0.25


def test_invariants_hold_throughout_simulation():
    """Book never crossed; per-trade buys == sells; status/qty consistent."""
    cfg = SimulationConfig(n_events=5000, seed=3, price_sigma_ticks=4)
    eng = MatchingEngine(cfg.symbol)
    orders = {}
    for ev in MarketSimulator(cfg).events():
        if ev.cancel_id is not None:
            eng.cancel(ev.cancel_id)
        else:
            orders[ev.order.order_id] = ev.order
            for t in eng.submit(ev.order):
                assert t.quantity > 0
        bid, ask = eng.book.best_bid(), eng.book.best_ask()
        assert bid is None or ask is None or bid < ask, "book is crossed!"
    for o in orders.values():
        assert 0 <= o.remaining_quantity <= o.quantity
        if o.status is OrderStatus.FILLED:
            assert o.remaining_quantity == 0


def test_fill_accounting_matches_trades():
    """For every order, quantity in trades == quantity it reports as filled,
    and total bought == total sold (each trade has exactly one buyer and seller)."""
    from collections import defaultdict

    cfg = SimulationConfig(n_events=5000, seed=11)
    eng = MatchingEngine(cfg.symbol)
    orders, per_order, trades = {}, defaultdict(int), []
    for ev in MarketSimulator(cfg).events():
        if ev.cancel_id is not None:
            eng.cancel(ev.cancel_id)
            continue
        orders[ev.order.order_id] = ev.order
        trades += eng.submit(ev.order)
    for t in trades:
        per_order[t.buy_order_id] += t.quantity
        per_order[t.sell_order_id] += t.quantity
    assert trades
    for oid, o in orders.items():
        assert per_order[oid] == o.filled_quantity
    assert sum(o.filled_quantity for o in orders.values()) == 2 * sum(t.quantity for t in trades)


def test_runner_records_analytics():
    run = run_simulation(SimulationConfig(n_events=3000), snapshot_every=100)
    assert len(run.snapshots_df()) == 30
    ex = run.executions_df()
    assert {"slippage_bps", "impact_bps"} <= set(ex.columns)
