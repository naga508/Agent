import os

from agent import build_engine


def _engine():
    root = os.path.dirname(__file__)
    return build_engine(
        os.path.join(root, "fixtures", "actuals.csv"),
        os.path.join(root, "fixtures", "budget.csv"),
        os.path.join(root, "fixtures", "fx.csv"),
        os.path.join(root, "fixtures", "cash.csv"),
    )


def test_revenue_point():
    res = _engine()("What was June 2025 revenue vs budget in USD?", plotting=False)
    text = res["text"].lower()
    assert "revenue" in text
    assert "actual" in text
    assert "budget" in text


def test_gross_margin_trend():
    res = _engine()("Show Gross Margin % trend for the last 3 months.", plotting=False)
    assert "trend" in res["text"].lower()


def test_cash_runway():
    res = _engine()("What is our cash runway right now?", plotting=False)
    assert "cash runway" in res["text"].lower()
