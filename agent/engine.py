"""Agent engine that orchestrates planning and execution."""

from __future__ import annotations

from typing import Callable, Dict, Optional

import numpy as np
import pandas as pd
try:
    import plotly.graph_objects as go
except ImportError:  # pragma: no cover - plotting optional in tests
    go = None

from .planner import Planner
from .tools import FinanceTools


def build_engine(
    actuals_csv: str,
    budget_csv: str,
    fx_csv: str,
    cash_csv: str,
) -> Callable[[str], Dict[str, object]]:
    """Create an agent callable that answers finance questions."""

    tools = FinanceTools(actuals_csv, budget_csv, fx_csv, cash_csv)
    planner = Planner()

    def run(question: str, plotting: bool = True) -> Dict[str, object]:
        plan = planner.parse(question)
        text: Optional[str] = None
        figure = None
        table = None

        if plan.intent == "cash_runway":
            metrics = tools.cash_runway()
            text = _format_cash_runway(metrics)
            if plotting:
                figure = _plot_cash_runway(metrics)
        elif plan.intent == "breakdown":
            month = plan.month or tools.latest_month
            if month is None:
                text = "I could not find any actuals to report on."
            else:
                table = tools.opex_breakdown(month)
                text = _format_opex_breakdown(month, table)
                if plotting and not table.empty:
                    figure = _plot_opex_breakdown(month, table)
        elif plan.intent == "trend" and plan.metric:
            trend_df = tools.metric_trend(plan.metric, plan.months)
            if trend_df.empty:
                text = "I could not find data for that metric."
            else:
                text = _format_trend(plan.metric, trend_df)
                if plotting:
                    figure = _plot_trend(plan.metric, trend_df)
        elif plan.intent == "point" and plan.metric:
            month = plan.month or tools.latest_month
            if month is None:
                text = "I could not find any actuals to report on."
            else:
                point = tools.metric_point(plan.metric, month)
                text = _format_point(plan.metric, month, point)
                if plotting:
                    figure = _plot_point(plan.metric, month, point)
        else:
            text = "I'm not sure how to answer that yet."

        return {"text": text or "I wasn't able to compute that.", "figure": figure, "table": table}

    return run


def _format_currency(value: float) -> str:
    if np.isnan(value):
        return "—"
    return f"${value:,.0f}"


def _format_percent(value: float) -> str:
    if np.isnan(value):
        return "—"
    return f"{value:,.1f}%"


def _format_point(metric: str, month: pd.Timestamp, point) -> str:
    label = month.strftime("%b %Y")
    is_percent = "%" in metric
    actual = _format_percent(point.actual) if is_percent else _format_currency(point.actual)
    budget = _format_percent(point.budget) if is_percent else _format_currency(point.budget)
    variance = _format_percent(point.variance) if is_percent else _format_currency(point.variance)
    parts = [f"{metric.title()} — {label}", f"Actual: {actual}"]
    if not np.isnan(point.budget):
        parts.append(f"Budget: {budget}")
    if not np.isnan(point.variance):
        if not np.isnan(point.variance_pct) and not is_percent:
            parts.append(f"Variance: {variance} ({point.variance_pct:+.1f}%)")
        else:
            parts.append(f"Variance: {variance}")
    return "\n".join(parts)


def _format_trend(metric: str, df: pd.DataFrame) -> str:
    periods = df.index.min().strftime("%b %Y"), df.index.max().strftime("%b %Y")
    return f"Showing {metric.title()} trend from {periods[0]} to {periods[1]}."


def _format_opex_breakdown(month: pd.Timestamp, table: pd.DataFrame) -> str:
    label = month.strftime("%b %Y")
    total = table["Actual"].sum()
    return f"Opex breakdown for {label}. Total actual spend: {_format_currency(total)}."


def _format_cash_runway(metrics: dict) -> str:
    cash = metrics["cash"]
    burn = metrics["burn"]
    runway = metrics["runway"]
    if np.isinf(runway):
        return (
            f"Cash runway: {_format_currency(cash)} of cash and a positive or neutral operating run rate. "
            "The company is not burning cash over the trailing period."
        )
    months = runway
    return (
        f"Cash runway: {_format_currency(cash)} on hand, average burn {_format_currency(burn)} per month. "
        f"Runway ≈ {months:.1f} months."
    )


def _plot_point(metric: str, month: pd.Timestamp, point):
    if go is None:
        return None
    label = month.strftime("%b %Y")
    is_percent = "%" in metric
    actual = point.actual
    budget = point.budget if not np.isnan(point.budget) else None
    values = {"Actual": actual}
    if budget is not None:
        values["Budget"] = budget
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=list(values.keys()),
            y=list(values.values()),
            marker_color=["#2E86DE", "#1ABC9C"][: len(values)],
        )
    )
    fig.update_layout(
        title=f"{metric.title()} — {label}",
        yaxis_title="%" if is_percent else "USD",
        template="plotly_white",
    )
    return fig


def _plot_trend(metric: str, df: pd.DataFrame):
    if go is None:
        return None
    fig = go.Figure()
    for column in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df[column],
                mode="lines+markers",
                name=column,
            )
        )
    fig.update_layout(
        title=f"{metric.title()} Trend",
        xaxis_title="Month",
        yaxis_title="%" if "%" in metric else "USD",
        template="plotly_white",
    )
    return fig


def _plot_opex_breakdown(month: pd.Timestamp, table: pd.DataFrame):
    if go is None:
        return None
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=table["Category"],
            y=table["Actual"],
            name="Actual",
            marker_color="#2E86DE",
        )
    )
    if "Budget" in table:
        fig.add_trace(
            go.Bar(
                x=table["Category"],
                y=table["Budget"],
                name="Budget",
                marker_color="#1ABC9C",
            )
        )
    fig.update_layout(
        barmode="group",
        title=f"Opex Breakdown — {month.strftime('%b %Y')}",
        xaxis_title="Category",
        yaxis_title="USD",
        template="plotly_white",
    )
    return fig


def _plot_cash_runway(metrics: dict):
    if go is None:
        return None
    fig = go.Figure()
    fig.add_trace(
        go.Indicator(
            mode="number+delta",
            value=metrics["runway"] if not np.isinf(metrics["runway"]) else 0,
            number={"suffix": " months"},
            delta={"reference": 0, "increasing": {"color": "#2E86DE"}},
            title={"text": "Cash Runway"},
        )
    )
    fig.update_layout(template="plotly_white")
    return fig
