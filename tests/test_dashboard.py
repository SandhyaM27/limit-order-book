"""Smoke tests: charts build, and the Streamlit app runs without exceptions."""

from pathlib import Path

from lob.simulation import SimulationConfig, run_simulation
from lob.visualization import charts


def test_charts_build():
    run = run_simulation(SimulationConfig(n_events=2000), snapshot_every=50)
    b = run.engine.book
    assert charts.depth_chart(b).data and charts.ladder_chart(b).data
    assert charts.price_panel(run.snapshots_df()).data
    assert charts.execution_scatter(run.executions_df()).data
    charts.price_panel(run.snapshots_df().iloc[0:0])  # empty must not crash


def test_streamlit_app_starts():
    from streamlit.testing.v1 import AppTest

    app = Path(__file__).parents[1] / "dashboard" / "app.py"
    at = AppTest.from_file(str(app), default_timeout=60).run()
    assert not at.exception
    at.sidebar.button[0].click().run()
    assert not at.exception
