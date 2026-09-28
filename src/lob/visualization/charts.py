"""Plotly figure builders. Pure functions: data in, figure out (easy to test)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from lob.matching.order_book import OrderBook
from lob.models.order import Side


def depth_chart(book: OrderBook, levels: int = 15) -> go.Figure:
    """Cumulative bid/ask depth ("depth chart") plus per-level quantity."""
    bids = book.depth(Side.BUY, levels)
    asks = book.depth(Side.SELL, levels)
    fig = go.Figure()
    if bids:
        prices, qty = zip(*bids)
        cum, total = [], 0
        for q in qty:
            total += q
            cum.append(total)
        fig.add_trace(
            go.Scatter(x=prices, y=cum, name="Bids", fill="tozeroy", line_shape="hv", line_color="#2ca02c")
        )
    if asks:
        prices, qty = zip(*asks)
        cum, total = [], 0
        for q in qty:
            total += q
            cum.append(total)
        fig.add_trace(
            go.Scatter(x=prices, y=cum, name="Asks", fill="tozeroy", line_shape="hv", line_color="#d62728")
        )
    fig.update_layout(
        title="Cumulative depth",
        xaxis_title="Price (ticks)",
        yaxis_title="Cumulative quantity",
        height=340,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig


def ladder_chart(book: OrderBook, levels: int = 10) -> go.Figure:
    """Horizontal bars: quantity at each price level."""
    bids, asks = book.depth(Side.BUY, levels), book.depth(Side.SELL, levels)
    fig = go.Figure()
    fig.add_bar(
        y=[str(p) for p, _ in bids],
        x=[q for _, q in bids],
        orientation="h",
        name="Bid",
        marker_color="#2ca02c",
    )
    fig.add_bar(
        y=[str(p) for p, _ in asks],
        x=[q for _, q in asks],
        orientation="h",
        name="Ask",
        marker_color="#d62728",
    )
    fig.update_yaxes(type="category", autorange="reversed")
    fig.update_layout(title="Price levels", height=340, margin=dict(l=10, r=10, t=40, b=10))
    return fig


def price_panel(snap: pd.DataFrame) -> go.Figure:
    """Mid, VWAP, spread, imbalance and cumulative volume over time."""
    fig = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=("Mid price & VWAP", "Spread (ticks)", "Order-book imbalance", "Cumulative volume"),
    )
    if snap.empty:
        return fig
    x = snap["events"]
    fig.add_scatter(x=x, y=snap["mid"], name="Mid", row=1, col=1)
    fig.add_scatter(x=x, y=snap["vwap"], name="VWAP", row=1, col=1)
    fig.add_scatter(x=x, y=snap["spread"], name="Spread", row=2, col=1)
    fig.add_scatter(x=x, y=snap["imbalance"], name="Imbalance", row=3, col=1)
    fig.add_scatter(x=x, y=snap["cum_volume"], name="Volume", row=4, col=1)
    fig.update_xaxes(title_text="Events processed", row=4, col=1)
    fig.update_layout(height=700, showlegend=False, margin=dict(l=10, r=10, t=40, b=10))
    return fig


def execution_scatter(ex: pd.DataFrame) -> go.Figure:
    """Slippage and impact vs order size for market orders."""
    fig = go.Figure()
    if not ex.empty:
        fig.add_scatter(
            x=ex["quantity"], y=ex["slippage_bps"], mode="markers", name="Slippage (bps)", opacity=0.5
        )
        fig.add_scatter(
            x=ex["quantity"], y=ex["impact_bps"], mode="markers", name="Impact (bps)", opacity=0.5
        )
    fig.update_layout(
        title="Market orders: cost vs size",
        xaxis_title="Order quantity",
        yaxis_title="bps",
        height=340,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig
