# Interview Prep

Format: **Q**, *what they test*, **strong answer**, **common mistakes**.
Answer with reference to YOUR code (file names help) and be upfront that it is a simulator.

## Python & OOP
**1. Why `@dataclass(slots=True)` for `Order`?**
*Tests:* Python internals, memory awareness.
**Answer:** Dataclass generates `__init__/__repr__/__eq__`. `slots=True` removes the per-instance `__dict__`, cutting memory and speeding attribute access, useful when creating ~10^6 orders. Trade-off: no dynamic attributes. `field(init=False)` + `__post_init__` computes `remaining_quantity` and validates.
**Mistakes:** Saying slots makes it "immutable"; not knowing `__post_init__`.

**2. Why is `Trade` frozen but `Order` mutable?**
*Tests:* modelling/immutability.
**Answer:** A trade is a historical fact and must never change (safe to share, hashable). An order's `remaining_quantity` and `status` legitimately change during matching.
**Mistakes:** "No reason"; making everything mutable.

**3. Why Enums for Side/OrderType/Status?**
**Answer:** Closed set of values, typo-proof (`Side.BUYY` errors immediately), self-documenting, comparable with `is`. Strings would fail silently.
**Mistakes:** Comparing enums with `==` on strings; using bare strings.

**4. Where does validation belong and why?**
**Answer:** In the constructor (`__post_init__`) so an invalid `Order` can never exist; the engine can then assume valid input. Engine-level checks cover cross-object rules (wrong symbol, duplicate id, re-submission).
**Mistakes:** Scattering `if` checks through the engine.

**5. Why `int` prices instead of `float`?**
*Tests:* numerical awareness.
**Answer:** `0.1 + 0.2 != 0.3` in binary floating point. Matching needs exact price equality to group levels and compare crosses. Exchanges use integer ticks; convert to decimals only for display. `decimal.Decimal` is exact but much slower.
**Mistakes:** "Floats are less precise" without an example; rounding floats at compare time.

## Data structures & algorithms
**6. Walk me through your order book data structures.**
*Tests:* can you justify choices.
**Answer:** Per side: `dict[price -> PriceLevel]` (O(1) level access), a `deque` per level (O(1) FIFO), a heap of prices for best price (bids negated because `heapq` is a min-heap), plus `dict[order_id -> Order]` for O(1) cancel lookup.
**Mistakes:** Saying "a list sorted on every insert" (O(n log n) or O(n) per insert).

**7. How does cancel work in O(1)?**
**Answer:** Lazy deletion: mark the order CANCELLED, subtract its remaining quantity from the level total, drop it from the id map; the deque entry is skipped when it reaches the front. Empty levels are deleted from the dict; stale heap prices are popped when they surface at the top. Cost: temporary garbage, so heap/deque can hold dead entries.
**Mistakes:** `deque.remove()` is O(n); forgetting to update level totals (corrupts depth).

**8. Complexity of your main operations?**
**Answer:** Add O(1) or O(log P) for a new level; cancel O(1); best price O(1) amortised; matching O(k + L log P); `depth()` O(P log P) because I sort levels. Say what you would improve (sorted container / maintain top-N).
**Mistakes:** Claiming everything is O(1); forgetting P (levels) vs N (orders).

**9. Why heap and not a balanced BST / SortedDict?**
**Answer:** Only the *best* price is needed on the hot path, so a heap gives O(1) peek and simple code. A BST/sorted structure gives ordered iteration (cheap depth queries, O(log P) removal of arbitrary levels) at more complexity. Real engines often use arrays indexed by tick, because prices are bounded and discrete: O(1) everything.
**Mistakes:** Not knowing heap removal of arbitrary items is O(n).

**10. What is amortised complexity? Where do you use it?**
**Answer:** Average cost over a sequence of operations. Each stale heap entry is pushed once and popped once, so lazy cleanup costs O(log P) per entry, spread over operations, even though one `best_bid()` call may pop several.

## Order books & matching
**11. Explain price-time priority and where your code enforces it.**
**Answer:** Best price first; ties broken by arrival. Price: heap gives best level. Time: deque FIFO per level; partially filled orders keep their position (I have a test for this). Timestamps are informational; queue position *is* the priority.
**Mistakes:** Sorting by timestamp; letting a partially filled order go to the back.

**12. At what price does a trade execute?**
**Answer:** The resting (maker) order's price. An aggressive buy at 50.10 against an ask at 50.02 trades at 50.02: price improvement for the taker.
**Mistakes:** Using the incoming limit price or the midpoint.

**13. Market order vs limit order; what if a market order finds no liquidity?**
**Answer:** Market: immediate execution at best available prices, never rests, no price protection (risk of large slippage). If liquidity runs out, my engine discards the remainder (status PARTIALLY_FILLED or CANCELLED). Real venues add price bands / protections.
**Mistakes:** Resting a market order.

**14. What invariants must the book maintain?**
**Answer:** Best bid < best ask (never crossed); level total == sum of active remaining quantities; every resting order has remaining > 0; total bought == total sold. My simulation tests assert these after every event.
**Mistakes:** Only testing happy paths.

**15. How would you add IOC / FOK / order modification?**
**Answer:** IOC: match then cancel the remainder instead of resting. FOK: pre-check total crossing liquidity (like `estimate_market_order`) and reject if insufficient; do not mutate. Modify: quantity decrease keeps priority; price change or quantity increase = cancel + new order (loses time priority).

## Market microstructure
**16. Define spread, mid, depth, imbalance. What does imbalance tell you?**
**Answer:** Spread = ask - bid (cost of immediacy); mid = average; depth = quantity near the touch; imbalance = (B - A)/(B + A). Positive imbalance correlates with short-term upward pressure but is noisy and easily spoofed.
**Mistakes:** Presenting imbalance as a guaranteed predictor.

**17. Slippage vs market impact?**
**Answer:** Slippage = your execution cost relative to a benchmark (here arrival mid), includes half-spread. Impact = how much your trade moved the price (mid after vs before). Both grow with order size relative to depth; empirically impact is roughly concave (square-root law) in size, which my simulator does not calibrate.
**Mistakes:** Treating them as identical; ignoring the spread component.

**18. What is VWAP and how is it used?**
**Answer:** sum(p q)/sum(q). A benchmark for execution quality (did I beat market VWAP?) and a target for execution algorithms. Weakness: it is backward-looking and can be gamed.

**19. Is your simulated flow realistic?**
**Answer:** No. Independent Poisson arrivals with random prices lack clustering, autocorrelation, informed flow and market-maker behaviour. Useful to test mechanics and analytics, not to draw market conclusions. Next steps: Hawkes processes, agent-based models.
**Mistakes:** Over-claiming realism.

## Trading systems & system design
**20. Your engine does ~280k events/s in Python. Is that good?**
**Answer:** Fine for a simulator, the number is machine-specific (my sandbox, 1 vCPU) and measured with a shallow book. Real engines reach millions of events per second with microsecond or sub-microsecond latency using C++/Rust, preallocated memory, cache-friendly arrays, lock-free queues, kernel bypass. Python's overhead here is interpreter dispatch, object allocation and GC.
**Mistakes:** Comparing to real exchanges; quoting numbers you did not measure.

**21. How would you scale or make this production-grade?**
**Answer:** One matching engine per symbol, single-threaded and deterministic (sequencer assigns global order); an append-only event log for replay and recovery; separate gateway (validation, risk), market-data publisher, and persistence; hot standby replaying the same log; idempotency and sequence numbers; monitoring of latency percentiles; fuzz and property-based tests.
**Mistakes:** Multi-threading one book with locks (kills determinism and latency).

**22. How did you benchmark fairly?**
**Answer:** Pre-generated events (excluded), one timer around the loop for throughput, a separate per-event timing pass for percentiles (timer overhead), a separate tracemalloc pass for memory, fixed seed, reported hardware and version, noted warm-up noise on small sizes.
**Mistakes:** Timing event generation too; reporting only averages (tail latency matters).

**23. How do you test a matching engine?**
**Answer:** Unit tests per behaviour (priority, partial fills, cancels, empty book), plus invariant checks over a long random simulation (never crossed, fill accounting balances, reproducible by seed). Next: property-based tests with Hypothesis and differential testing against a slow, obviously correct reference implementation.
