"""Random order-flow generator.

Arrivals follow a Poisson process: inter-arrival times are exponential with
mean 1/arrival_rate seconds. Limit prices are placed around a slowly moving
reference price; quantities are log-normal (many small orders, few large).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np

from lob.models.order import Order, OrderType, Side


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    symbol: str = "SIM"
    n_events: int = 10_000
    seed: int = 42
    arrival_rate: float = 1_000.0  # events per simulated second (Poisson)
    p_limit: float = 0.65  # probability an event is a limit order
    p_market: float = 0.15  # ... a market order
    p_cancel: float = 0.20  # ... a cancellation
    initial_price: int = 10_000  # ticks (e.g. $100.00 in cents)
    price_sigma_ticks: float = 8.0  # spread of limit prices around reference
    aggressiveness_ticks: float = 1.0  # mean distance behind the reference price
    ref_drift_prob: float = 0.05  # chance the reference moves 1 tick per event
    qty_log_mean: float = 4.0  # lognormal params (median ~ e^4 = 55)
    qty_log_sigma: float = 0.6

    def __post_init__(self) -> None:
        total = self.p_limit + self.p_market + self.p_cancel
        if abs(total - 1.0) > 1e-9:
            raise ValueError("p_limit + p_market + p_cancel must equal 1")
        if self.arrival_rate <= 0 or self.n_events < 0:
            raise ValueError("arrival_rate must be > 0 and n_events >= 0")


@dataclass(frozen=True, slots=True)
class Event:
    timestamp: int  # microseconds of simulated time
    order: Order | None = None  # set for new orders
    cancel_id: int | None = None  # set for cancellations


class MarketSimulator:
    def __init__(self, config: SimulationConfig) -> None:
        self.config = config

    def events(self) -> Iterator[Event]:
        c = self.config
        rng = np.random.default_rng(c.seed)
        # Draw everything in vectorised batches: much faster than per-event calls.
        n = c.n_events
        gaps = rng.exponential(1.0 / c.arrival_rate, n)
        kinds = rng.choice(3, size=n, p=[c.p_limit, c.p_market, c.p_cancel])
        sides = rng.integers(0, 2, n)
        offsets = np.rint(rng.normal(c.aggressiveness_ticks, c.price_sigma_ticks, n)).astype(int)
        qtys = np.maximum(1, np.rint(rng.lognormal(c.qty_log_mean, c.qty_log_sigma, n))).astype(int)
        drift = rng.random(n) < c.ref_drift_prob
        drift_dir = rng.choice([-1, 1], n)
        cancel_pick = rng.random(n)

        ref = c.initial_price
        t_us = 0.0
        last_ts = 0
        next_id = 1
        live: list[int] = []  # ids that MAY still rest in the book

        for i in range(n):
            t_us += gaps[i] * 1e6
            ts = max(int(t_us), last_ts + 1)  # strictly increasing
            last_ts = ts
            if drift[i]:
                ref = max(100, ref + int(drift_dir[i]))  # keep prices positive
            kind = kinds[i]

            if kind == 2:  # cancel a random previously-issued limit order
                if not live:
                    kind = 0  # nothing to cancel -> emit a limit order instead
                else:
                    j = int(cancel_pick[i] * len(live))
                    live[j], live[-1] = live[-1], live[j]
                    yield Event(ts, cancel_id=live.pop())
                    continue

            side = Side.BUY if sides[i] == 0 else Side.SELL
            qty = int(qtys[i])
            if kind == 0:
                off = int(offsets[i])
                price = ref - off if side is Side.BUY else ref + off
                price = max(1, price)
                order = Order(next_id, ts, c.symbol, side, OrderType.LIMIT, qty, price)
                live.append(next_id)
            else:
                order = Order(next_id, ts, c.symbol, side, OrderType.MARKET, qty)
            next_id += 1
            yield Event(ts, order=order)
