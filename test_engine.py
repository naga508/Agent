from agent import build_engine
import os

def _engine():
    root = os.path.dirname(os.path.dirname(__file__))
    return build_engine(
        os.path.join(root,"fixtures","actuals.csv"),
        os.path.join(root,"fixtures","budget.csv"),
        os.path.join(root,"fixtures","fx.csv"),
        os.path.join(root,"fixtures","cash.csv"),
    )

def test_revenue_point():
    res = _engine()("Revenue Jun 2025 vs budget", plotting=False)
    assert "Revenue —" in res["text"]
    assert "Actual:" in res["text"]
    assert "Budget:" in res["text"]

def test_gm_trend():
    res = _engine()("Show Gross Margin % trend for the last 3 months.", plotting=False)
    assert "trend" in res["text"].lower()
