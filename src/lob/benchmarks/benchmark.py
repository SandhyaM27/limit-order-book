"""Matching-engine benchmark.

Method (so the numbers are honest):
  * Events are generated FIRST and excluded from timing.
  * Timing pass: one perf_counter around the whole loop (no per-event overhead).
  * Latency pass: a separate run timing each event with perf_counter_ns
    (this adds timer overhead, so it is reported separately).
  * Memory pass: separate run under tracemalloc (slow; timing not reported).
Results depend on your CPU, Python build and OS. Compare runs on YOUR machine.

Usage:  python -m lob.benchmarks.benchmark [--sizes 1000 10000 ...] [--no-memory]
"""

from __future__ import annotations

import argparse
import gc
import json
import platform
import sys
import time
import tracemalloc

import numpy as np

from lob.matching.engine import MatchingEngine
from lob.simulation.simulator import MarketSimulator, SimulationConfig


def _events(n: int):
    return list(MarketSimulator(SimulationConfig(n_events=n, seed=1)).events())


def _run(events, engine: MatchingEngine) -> int:
    submit, cancel, n_trades = engine.submit, engine.cancel, 0
    for ev in events:
        if ev.cancel_id is not None:
            cancel(ev.cancel_id)
        else:
            n_trades += len(submit(ev.order))
    return n_trades


def bench(n: int, memory: bool = True) -> dict:
    events = _events(n)
    gc.collect()
    eng = MatchingEngine("SIM")
    t0 = time.perf_counter()
    n_trades = _run(events, eng)
    elapsed = time.perf_counter() - t0
    resting = len(eng.book)

    # latency pass (fresh events: orders are mutated by matching)
    events = _events(n)
    eng = MatchingEngine("SIM")
    lat = np.empty(len(events), dtype=np.int64)
    clock, submit, cancel = time.perf_counter_ns, eng.submit, eng.cancel
    for i, ev in enumerate(events):
        s = clock()
        if ev.cancel_id is not None:
            cancel(ev.cancel_id)
        else:
            submit(ev.order)
        lat[i] = clock() - s

    result = {
        "events": n,
        "trades": n_trades,
        "resting_orders_end": resting,
        "total_seconds": elapsed,
        "events_per_second": n / elapsed,
        "avg_latency_us": elapsed / n * 1e6,
        "timed_latency_p50_us": float(np.percentile(lat, 50)) / 1e3,
        "timed_latency_p99_us": float(np.percentile(lat, 99)) / 1e3,
        "timed_latency_max_us": float(lat.max()) / 1e3,
    }

    if memory:
        events = _events(n)
        eng = MatchingEngine("SIM")
        gc.collect()
        tracemalloc.start()
        base = tracemalloc.get_traced_memory()[0]
        _run(events, eng)
        cur, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        result["memory_growth_mb"] = (cur - base) / 1e6
        result["memory_peak_extra_mb"] = (peak - base) / 1e6
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="+", default=[1_000, 10_000, 100_000, 1_000_000])
    ap.add_argument("--no-memory", action="store_true")
    ap.add_argument("--out", default="benchmark_results.json")
    args = ap.parse_args()

    meta = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
    }
    print(meta)
    print(
        f"{'events':>10} {'seconds':>9} {'events/s':>11} {'avg us':>8} "
        f"{'p50 us':>8} {'p99 us':>8} {'mem MB':>8}"
    )
    rows = []
    for n in args.sizes:
        r = bench(n, memory=not args.no_memory)
        rows.append(r)
        print(
            f"{n:>10,} {r['total_seconds']:>9.3f} {r['events_per_second']:>11,.0f} "
            f"{r['avg_latency_us']:>8.2f} {r['timed_latency_p50_us']:>8.2f} "
            f"{r['timed_latency_p99_us']:>8.2f} {r.get('memory_growth_mb', float('nan')):>8.1f}"
        )
    with open(args.out, "w") as f:
        json.dump({"meta": meta, "results": rows}, f, indent=2)


if __name__ == "__main__":
    main()
