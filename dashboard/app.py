"""Streamlit dashboard.  Run from the project root:  streamlit run dashboard/app.py

The simulation lives in st.session_state so it survives Streamlit reruns.
"Step" advances it; "Auto-play" keeps stepping and rerunning to look live.
"""

import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

# Allow `streamlit run dashboard/app.py` without `pip install -e .` (e.g. Streamlit Cloud).
_SRC = Path(__file__).resolve().parents[1] / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from lob.analytics import metrics
from lob.models.order import Side
from lob.simulation import SimulationConfig, SimulationRun
from lob.visualization import charts

st.set_page_config(page_title="Limit Order Book Simulator", layout="wide")
st.title("Limit Order Book & Matching Engine (simulation)")
st.caption("Educational simulator with synthetic order flow. Not a real exchange.")

with st.sidebar:
    st.header("Simulation settings")
    n_events = st.number_input("Total events", 1_000, 200_000, 20_000, step=1_000)
    seed = st.number_input("Random seed", 0, 10_000, 42)
    rate = st.number_input("Arrival rate (events / sim-second)", 1.0, 100_000.0, 1_000.0)
    p_market = st.slider("Market-order share", 0.0, 0.5, 0.15, 0.01)
    p_cancel = st.slider("Cancel share", 0.0, 0.5, 0.20, 0.01)
    sigma = st.slider("Price dispersion (ticks)", 1.0, 40.0, 8.0)
    qty_mu = st.slider("Quantity log-mean", 2.0, 6.0, 4.0, 0.1)
    step_size = st.number_input("Events per step", 10, 5_000, 250, step=10)
    autoplay = st.checkbox("Auto-play")
    if st.button("(Re)start simulation", type="primary"):
        cfg = SimulationConfig(
            n_events=int(n_events),
            seed=int(seed),
            arrival_rate=rate,
            p_limit=round(1 - p_market - p_cancel, 10),
            p_market=p_market,
            p_cancel=p_cancel,
            price_sigma_ticks=sigma,
            qty_log_mean=qty_mu,
        )
        st.session_state.run = SimulationRun(cfg, snapshot_every=25)
        st.session_state.run.step(int(step_size))

if "run" not in st.session_state:
    st.info("Set parameters in the sidebar and press **(Re)start simulation**.")
    st.stop()

run: SimulationRun = st.session_state.run
if st.button("Step ▶") or (autoplay and not run.finished):
    run.step(int(step_size))

book = run.engine.book
snap, ex, trades = run.snapshots_df(), run.executions_df(), run.trades_df()

st.progress(
    min(run.events_processed / run.config.n_events, 1.0),
    text=f"{run.events_processed:,} / {run.config.n_events:,} events",
)

est = metrics.estimate_market_order(book, Side.BUY, 200)
vw = metrics.vwap(run.trades)
imb = metrics.order_book_imbalance(book, 5)
c = st.columns(6)
c[0].metric("Best bid", book.best_bid() or "–")
c[1].metric("Best ask", book.best_ask() or "–")
c[2].metric("Mid", f"{book.mid_price():.1f}" if book.mid_price() else "–")
c[3].metric("Spread", book.spread() if book.spread() is not None else "–")
c[4].metric("Imbalance (5 lvl)", f"{imb:+.2f}" if imb is not None else "–")
c[5].metric("VWAP", f"{vw:.2f}" if vw else "–")
c = st.columns(4)
c[0].metric("Trades", f"{len(run.trades):,}")
c[1].metric("Volume", f"{metrics.trade_volume(run.trades):,}")
c[2].metric("Avg slippage (bps)", f"{ex['slippage_bps'].mean():.2f}" if not ex.empty else "–")
c[3].metric("Avg impact (bps)", f"{ex['impact_bps'].mean():.2f}" if not ex.empty else "–")
if est.avg_price:
    st.caption(f"What-if: a market BUY of 200 would fill at avg {est.avg_price:.2f} right now.")

left, right = st.columns(2)
left.plotly_chart(charts.depth_chart(book), width="stretch")
right.plotly_chart(charts.ladder_chart(book), width="stretch")
st.plotly_chart(charts.price_panel(snap), width="stretch")
left, right = st.columns(2)
right.plotly_chart(charts.execution_scatter(ex), width="stretch")
left.subheader("Recent trades")
left.dataframe(
    trades.tail(15).iloc[::-1] if not trades.empty else pd.DataFrame(),
    width="stretch",
    hide_index=True,
)

if autoplay and not run.finished:
    time.sleep(0.3)
    st.rerun()
