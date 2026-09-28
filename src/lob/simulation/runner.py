"""Glue: feed simulator events into the engine and record analytics."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

import pandas as pd

from lob.analytics import metrics
from lob.matching.engine import MatchingEngine
from lob.models.order import OrderType
from lob.models.trade import Trade
from lob.simulation.simulator import Event, MarketSimulator, SimulationConfig


@dataclass
class SimulationRun:
    """Stateful, steppable run (used by the dashboard's live mode too)."""

    config: SimulationConfig
    engine: MatchingEngine = field(init=False)
    trades: list[Trade] = field(default_factory=list)
    snapshots: list[dict] = field(default_factory=list)  # book state over time
    executions: list[dict] = field(default_factory=list)  # per market order
    events_processed: int = 0
    snapshot_every: int = 50
    _stream: Iterator[Event] = field(init=False, repr=False)
    _cum_notional: int = 0
    _cum_volume: int = 0

    def __post_init__(self) -> None:
        self.engine = MatchingEngine(self.config.symbol)
        self._stream = MarketSimulator(self.config).events()

    @property
    def finished(self) -> bool:
        return self.events_processed >= self.config.n_events

    def step(self, n: int = 1) -> int:
        """Process up to n events; returns how many were processed."""
        done = 0
        for ev in self._stream:
            self._process(ev)
            done += 1
            if done >= n:
                break
        return done

    def _process(self, ev: Event) -> None:
        eng = self.engine
        if ev.cancel_id is not None:
            eng.cancel(ev.cancel_id)
        else:
            order = ev.order
            assert order is not None
            mid_before = eng.book.mid_price()
            trades = eng.submit(order)
            self.trades.extend(trades)
            for t in trades:
                self._cum_notional += t.price * t.quantity
                self._cum_volume += t.quantity
            if order.order_type is OrderType.MARKET and trades and mid_before:
                filled = sum(t.quantity for t in trades)
                avg = sum(t.price * t.quantity for t in trades) / filled
                mid_after = eng.book.mid_price()
                self.executions.append(
                    {
                        "timestamp": ev.timestamp,
                        "side": order.side.value,
                        "quantity": order.quantity,
                        "filled": filled,
                        "avg_price": avg,
                        "slippage_bps": metrics.slippage_bps(avg, mid_before, order.side),
                        "impact_bps": (
                            metrics.market_impact_bps(mid_before, mid_after, order.side)
                            if mid_after
                            else None
                        ),
                    }
                )
        self.events_processed += 1
        if self.events_processed % self.snapshot_every == 0:
            self._snapshot(ev.timestamp)

    def _snapshot(self, ts: int) -> None:
        b = self.engine.book
        self.snapshots.append(
            {
                "events": self.events_processed,
                "timestamp": ts,
                "best_bid": b.best_bid(),
                "best_ask": b.best_ask(),
                "mid": b.mid_price(),
                "spread": b.spread(),
                "imbalance": metrics.order_book_imbalance(b, 5),
                "cum_volume": self._cum_volume,
                "vwap": self._cum_notional / self._cum_volume if self._cum_volume else None,
            }
        )

    def snapshots_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.snapshots)

    def executions_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.executions)

    def trades_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "trade_id": t.trade_id,
                    "timestamp": t.timestamp,
                    "price": t.price,
                    "quantity": t.quantity,
                    "aggressor": t.aggressor_side.value,
                }
                for t in self.trades
            ]
        )


def run_simulation(config: SimulationConfig, snapshot_every: int = 50) -> SimulationRun:
    run = SimulationRun(config, snapshot_every=snapshot_every)
    run.step(config.n_events)
    return run
