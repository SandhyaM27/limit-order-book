# Learning Guide: read the code in this order

Run `pytest -v` first so you see everything green, then read each file with its
tests open next to it. After each stage, do the exercise *without* looking at
the solution code.

| Stage | Read | Concepts | Exercise |
|---|---|---|---|
| 1 | `models/order.py`, `tests/test_order.py` | dataclass, Enum, `__post_init__`, `slots`, why int prices | Add `TimeInForce` enum (GTC/IOC) with validation |
| 2 | `matching/order_book.py`, `tests/test_order_book.py` | deque, heapq, dict, lazy deletion, big-O | Add `volume_at(price)`; then make `depth()` O(n) for small n using `heapq.nsmallest` |
| 3 | `matching/engine.py`, `tests/test_matching_engine.py` | crossing, resting-price trades, partial fills | Implement IOC: leftover limit quantity is cancelled instead of resting |
| 4 | `simulation/simulator.py` | Poisson arrivals, lognormal sizes, seeded RNG | Add a "burst" regime: arrival rate x10 for 500 events |
| 5 | `analytics/metrics.py` | imbalance, VWAP, slippage, impact | Add TWAP and a "cost to buy X shares" curve |
| 6 | `simulation/runner.py`, `dashboard/app.py` | separation of concerns, session state | Add a table of the top-5 book levels |
| 7 | `benchmarks/benchmark.py` | fair benchmarking, percentiles | Compare `deque` vs `list` for level queues |

## Hand-trace (do this on paper, then check with code)
Book: asks 100@50.02 (A), 50@50.02 (B), 200@50.03 (C). Incoming: BUY LIMIT 180 @ 50.02.
Answer: trades 100 (A) and 50 (B) at 50.02; 30 remains and rests as a bid at 50.02;
C untouched. Spread afterwards = 1 tick (bid 50.02, ask 50.03).

## Math
- Poisson arrivals: inter-arrival ~ Exponential(rate), mean 1/rate.
- Lognormal: ln(Q) ~ Normal(mu, sigma); median = e^mu (here e^4 ~ 55), heavy right tail.
- Imbalance in [-1, 1]; VWAP = sum(pq)/sum(q); bps = 1/10,000.
