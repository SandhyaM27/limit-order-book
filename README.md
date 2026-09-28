# Event-Driven Limit Order Book & Matching Engine

A pure-Python simulation of a limit order book (LOB) with a price-time-priority
matching engine, a random order-flow simulator, market-microstructure analytics,
a Streamlit dashboard, tests and benchmarks.

> **This is an educational simulator, not an exchange.** It has no networking,
> persistence, risk checks, auth, or fault tolerance, and it is single-symbol and
> single-threaded. It is **not production-ready** and must not be used for trading.

## Motivation
Every electronic market is built around a limit order book. Building one from
scratch forces you to reason about data-structure trade-offs, correctness under
edge cases (partial fills, cancels), and how microstructure metrics (spread,
depth, impact) emerge from order flow.

## Architecture
```
Simulator (numpy RNG) --Event--> Runner --Order--> MatchingEngine --> OrderBook
                                    |                    |
                                    |                    +--> Trade[]
                                    +--> Analytics (read-only) --> Dashboard / Notebook
```
| Package | Responsibility |
|---|---|
| `lob.models` | `Order`, `Trade`, enums. Validation lives in `Order.__post_init__`. |
| `lob.matching` | `OrderBook` (state + queries), `MatchingEngine` (algorithm). |
| `lob.simulation` | `MarketSimulator` (event stream), `SimulationRun` (glue + recording). |
| `lob.analytics` | Pure functions: spread, mid, depth, imbalance, VWAP, slippage, impact. |
| `lob.visualization` | Plotly figure builders. |
| `lob.benchmarks` | Reproducible benchmark script. |
| `dashboard/app.py` | Streamlit UI. |

Design rules: the engine never imports analytics/visualization; analytics never
mutate the book; the engine returns trades instead of storing them (caller decides).
"Event-driven" here means the system is driven by a stream of timestamped
`Event`s (new order / cancel) processed one at a time, in order.

## How a limit order book works
- **Bids** = resting buy orders; **asks** = resting sell orders.
- **Best bid** = highest bid; **best ask** = lowest ask. The book is never
  *crossed* (best bid < best ask) because crossing orders trade immediately.
- **Spread** = ask - bid; **mid** = (bid + ask) / 2.
- **Limit order**: buy/sell at a price or better; rests if it can't fully trade.
- **Market order**: trade now at the best available prices; never rests.
- **Price-time priority**: better price first; equal price -> earlier arrival first (FIFO).

Example: asks `100 @ 50.02`, `200 @ 50.03`. A market buy of 250 produces two
trades (100 @ 50.02, 150 @ 50.03) and leaves 50 @ 50.03 resting.

## Matching algorithm
For each incoming order: (1) peek best opposite level; (2) stop if a limit order
no longer crosses (`buy: ask <= limit`, `sell: bid >= limit`); (3) fill against the
oldest order at that level for `min(incoming_remaining, resting_remaining)`;
(4) emit a `Trade` at the **resting** order's price; (5) repeat. Leftover limit
quantity rests; leftover market quantity is discarded.

## Data structures
| Structure | Used for | Why |
|---|---|---|
| `dict[price, PriceLevel]` | Levels per side | O(1) access by price |
| `collections.deque` | FIFO queue per level | O(1) append and pop-left (a `list.pop(0)` is O(n)) |
| `heapq` min-heap (bids negated) | Best price | O(1) peek, O(log P) insert |
| `dict[order_id, Order]` | Cancel lookup | O(1) |
| Lazy deletion | Cancels and empty levels | Avoids O(n) removal from the middle of a deque/heap |

Prices are **integer ticks** (no float equality bugs). Timestamps are integers.

## Time complexity (N orders, P price levels, k fills)
| Operation | Cost |
|---|---|
| Add limit order (level exists / new level) | O(1) / O(log P) |
| Cancel | O(1) |
| Best bid / ask | O(1) amortised (stale heap entries popped lazily) |
| Match one order | O(k + L log P), L = levels emptied |
| Spread / mid | O(1) amortised |
| `depth(n)` / imbalance / what-if estimate | O(P log P) (sorts levels; could be O(n log P) with a sorted structure) |

## Market microstructure metrics
- **Depth**: resting quantity in the top N levels per side.
- **Imbalance** = (bidVol - askVol) / (bidVol + askVol) in [-1, 1].
- **VWAP** = sum(p_i q_i) / sum(q_i).
- **Slippage (bps)** = side * (avg_fill - arrival_mid) / arrival_mid * 10^4.
- **Market impact (bps)** = side * (mid_after - mid_before) / mid_before * 10^4.
  Here it is a *temporary, immediate* impact measured on the next book state; it
  ignores later price reversion or permanent impact.

## Quick start (developers)
```bash
make install   # deps + editable install
make check     # ruff + mypy + pytest
make run       # dashboard at http://localhost:8501
make docker && make docker-run
```

## Installation
```bash
python3.12 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"      # or: pip install -r requirements.txt && pip install -e .
```

## Usage
```python
from lob.matching import MatchingEngine
from lob.models import Order, OrderType, Side

eng = MatchingEngine("AAPL")
eng.submit(Order(1, 1, "AAPL", Side.SELL, OrderType.LIMIT, 100, 5002))
trades = eng.submit(Order(2, 2, "AAPL", Side.BUY, OrderType.MARKET, 40))
print(trades[0].price, trades[0].quantity)  # 5002 40
```
```bash
streamlit run dashboard/app.py     # dashboard
python -m lob.benchmarks.benchmark # benchmark
```

## Deployment
The dashboard deploys to Streamlit Community Cloud, Docker/any VPS, or Render;
CI (GitHub Actions) runs lint, type-check, tests and a container health check.
See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md). Only the demo dashboard is
deployed; the engine is a library, not a networked service.

## Testing
```bash
pytest -v
```
59 tests (plus ruff and mypy in CI) cover order validation, insertion, market/limit orders, price-time
priority, partial/complete fills, multi-level matching, cancellation, empty
books, spread, imbalance, analytics sign conventions, simulator reproducibility,
whole-simulation invariants (book never crossed, fill accounting balances) and a
dashboard smoke test.

## Benchmarking
`python -m lob.benchmarks.benchmark` generates events first (not timed), then
times matching only. Latency percentiles come from a separate per-event-timed
pass (adds timer overhead); memory from a separate `tracemalloc` pass.

Sample run (Python 3.12.3, 1 vCPU Linux sandbox, default simulator config,
seed 1; **your numbers will differ**, run it yourself):

| Events | Seconds | Events/s | Avg latency | p50 / p99 (timed pass) |
|---|---|---|---|---|
| 1,000 | 0.004 | ~274k | 3.65 us | 2.3 / 17.1 us |
| 10,000 | 0.062 | ~161k | 6.23 us | 2.3 / 32.5 us |
| 100,000 | 0.347 | ~289k | 3.47 us | 2.0 / 16.9 us |
| 1,000,000 | 3.53 | ~283k | 3.53 us | 2.1 / 17.4 us |

Memory considerations: `tracemalloc` showed only ~1.6 MB of growth (3 MB peak)
at 1M events, because the simulated book stays small (about 12k resting orders at
the end) and trades are not retained by the engine. The pre-generated event list
(not counted) is far larger. `Order` uses `slots=True` to reduce per-object size.
The 1k/10k rows are noisy (warm-up, tiny runs). Throughput with deeper books or
different order mixes will differ.

## Limitations
- Simulation only; single symbol, single thread, in-memory, no persistence/replay log.
- No time-in-force (IOC/FOK/GTC), stop or iceberg orders; no order modification.
- No self-trade prevention, fees, tick/lot-size rules, circuit breakers, auctions.
- Synthetic order flow (i.i.d. draws) lacks real-market features: clustering,
  autocorrelated order flow, informed traders, realistic cancel behaviour.
- `depth()` sorts levels each call; heaps can hold stale entries until popped.
- Python is far slower than production engines (C++/Rust, ~microseconds or less
  with lock-free structures); these numbers are not comparable to real venues.

## Future improvements
Order modification and IOC/FOK; sorted-container or array-of-levels book; multiple
symbols; event log + deterministic replay; Hawkes-process order flow; agent-based
market makers; Cython/Rust core; property-based tests (Hypothesis); type-checking in CI.

## Project layout
```
src/lob/{models,matching,simulation,analytics,visualization,benchmarks}
tests/  notebooks/  dashboard/  docs/
```
Also: `Dockerfile`, `docker-compose.yml`, `render.yaml`, `Makefile`, `.github/workflows/`, `.streamlit/config.toml`.
See `docs/LEARNING_GUIDE.md`, `docs/GIT_GUIDE.md`, `docs/INTERVIEW_PREP.md`, `docs/DEPLOYMENT.md`.
