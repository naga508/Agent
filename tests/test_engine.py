import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from agent import build_engine

_ENGINE = build_engine(
    os.path.join(_ROOT, "fixtures", "actuals.csv"),
    os.path.join(_ROOT, "fixtures", "budget.csv"),
    os.path.join(_ROOT, "fixtures", "fx.csv"),
    os.path.join(_ROOT, "fixtures", "cash.csv"),
)


def _engine():
    return _ENGINE


def test_revenue_point():
    res = _engine()("Revenue Sep 2025 vs budget", plotting=False)
    assert "Revenue —" in res["text"]
    assert "Actual:" in res["text"]
    assert "Budget:" in res["text"]
    assert res["chart"] is None


def test_gm_trend():
    res = _engine()("Show Gross Margin % trend for the last 3 months.", plotting=False)
    assert "trend" in res["text"].lower()


def test_opex_breakdown_returns_table():
    res = _engine()("Break down Opex by category for September 2025.", plotting=False)
    assert res["table"] is not None
