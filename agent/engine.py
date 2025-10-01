"""Core agent logic for answering FP&A questions."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from dateutil import parser as dateparser
import matplotlib.pyplot as plt


# ---------- parsing helpers ----------

def _month_label(dt: datetime) -> str:
    return dt.strftime("%b %Y")


def _parse_month(text: str) -> Optional[datetime]:
    try:
        dt = dateparser.parse(text, default=datetime(2025, 1, 1))
        return datetime(dt.year, dt.month, 1)
    except Exception:
        return None


def _extract_month(question: str) -> Optional[datetime]:
    month_pattern = (
        r"(jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|jun(e)?|jul(y)?|aug(ust)?|"
        r"sep(t)?(ember)?|oct(ober)?|nov(ember)?|dec(ember)?)\s*\d{4}"
    )
    match = re.search(month_pattern, question, flags=re.IGNORECASE)
    if match:
        return _parse_month(match.group(0))

    iso_match = re.search(r"\b(20\d{2})-(0[1-9]|1[0-2])\b", question)
    if iso_match:
        return _parse_month(iso_match.group(0) + "-01")
    return None


def _is_trend(question: str) -> bool:
    keywords = ["trend", "trends", "over time", "by month", "chart", "plot", "line", "graph", "show"]
    ql = question.lower()
    return any(word in ql for word in keywords)


def _vs_budget(question: str) -> bool:
    triggers = ["vs budget", "versus budget", "variance", "budget"]
    ql = question.lower()
    return any(trigger in ql for trigger in triggers)


# ---------- data load & transforms ----------

def _load(actuals_csv: str, budget_csv: str, fx_csv: str, cash_csv: str):
    actuals = pd.read_csv(actuals_csv, parse_dates=["date"])
    budget = pd.read_csv(budget_csv, parse_dates=["date"])
    fx = pd.read_csv(fx_csv, parse_dates=["date"])
    cash = pd.read_csv(cash_csv, parse_dates=["date"])

    for df in (actuals, budget):
        if "entity" not in df.columns:
            df["entity"] = "Total"
        if "currency" not in df.columns:
            df["currency"] = "USD"
        df["account"] = df["account"].astype(str)

    fx["currency"] = fx["currency"].fillna("USD")
    if "rate_to_usd" not in fx.columns:
        fx["rate_to_usd"] = 1.0
    fx = fx.drop_duplicates(subset=["date", "currency"], keep="last")
    return actuals, budget, fx, cash


def _to_usd(df: pd.DataFrame, fx: pd.DataFrame) -> pd.DataFrame:
    merged = pd.merge(df, fx, on=["date", "currency"], how="left")
    merged["rate_to_usd"] = merged["rate_to_usd"].fillna(1.0)
    merged["amount_usd"] = merged["amount"] * merged["rate_to_usd"]
    return merged


def _build_pivots(actuals_usd: pd.DataFrame, budget_usd: pd.DataFrame):
    def classify(account: str) -> str:
        lowered = str(account).lower()
        if lowered.startswith("opex"):
            return "Opex"
        if lowered.startswith("cogs"):
            return "Cogs"
        if lowered.startswith("revenue"):
            return "Revenue"
        return "Other"

    actuals_usd["Kind"] = actuals_usd["account"].map(classify)
    budget_usd["Kind"] = budget_usd["account"].map(classify)

    actuals_pivot = (
        actuals_usd.pivot_table(index="date", columns="Kind", values="amount_usd", aggfunc="sum").fillna(0.0)
    )
    budget_pivot = (
        budget_usd.pivot_table(index="date", columns="Kind", values="amount_usd", aggfunc="sum").fillna(0.0)
    )

    for column in ["Revenue", "Cogs", "Opex"]:
        if column not in actuals_pivot.columns:
            actuals_pivot[column] = 0.0
        if column not in budget_pivot.columns:
            budget_pivot[column] = 0.0

    def enrich(pivot: pd.DataFrame) -> pd.DataFrame:
        enriched = pivot.copy().sort_index()
        enriched["Gross Profit"] = enriched["Revenue"] - enriched["Cogs"]
        enriched["Gross Margin %"] = np.where(
            enriched["Revenue"] != 0, enriched["Gross Profit"] / enriched["Revenue"], np.nan
        ) * 100
        enriched["EBITDA"] = enriched["Revenue"] - enriched["Cogs"] - enriched["Opex"]
        enriched["EBITDA %"] = np.where(
            enriched["Revenue"] != 0, enriched["EBITDA"] / enriched["Revenue"], np.nan
        ) * 100
        return enriched

    return enrich(actuals_pivot), enrich(budget_pivot), actuals_usd


def _opex_breakdown(df_usd: pd.DataFrame, month_dt: datetime) -> pd.DataFrame:
    data = df_usd[(df_usd["date"] == month_dt) & (df_usd["account"].str.lower().str.startswith("opex"))].copy()
    data["category"] = data["account"].str.split(":", n=1).str[1].fillna("Other").str.strip()
    grouped = data.groupby("category")["amount_usd"].sum().reset_index()
    return grouped.sort_values("amount_usd", ascending=False)


def _cash_runway_months(cash_df: pd.DataFrame, actuals_pivot: pd.DataFrame) -> float:
    recent = actuals_pivot.sort_index().iloc[-3:]
    net_burn = (recent["Opex"] + recent["Cogs"] - recent["Revenue"]).mean()
    latest_cash = cash_df.sort_values("date").iloc[-1]["cash_balance"]
    if net_burn <= 0:
        return float("inf")
    return latest_cash / net_burn


# ---------- chart helpers ----------

def _line_chart(
    series: pd.Series,
    title: str,
    ylabel: str,
    compare_series: Optional[pd.Series] = None,
    compare_label: str = "Budget",
    series_label: str = "Actual",
):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(series.index, series.values, label=f"{series_label}")
    if compare_series is not None:
        ax.plot(compare_series.index, compare_series.values, linestyle="--", label=f"{compare_label}")
    ax.set_title(title)
    ax.set_xlabel("Month")
    ax.set_ylabel(ylabel)
    ax.legend()
    fig.tight_layout()
    return fig


def _bar_chart(data: pd.DataFrame, title: str, ylabel: str):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(data["category"], data["amount_usd"])
    ax.set_title(title)
    ax.set_xlabel("Category")
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=45, ha="right")
    fig.tight_layout()
    return fig


# ---------- public: build_engine ----------

def build_engine(actuals_csv: str, budget_csv: str, fx_csv: str, cash_csv: str):
    actuals, budget, fx, cash = _load(actuals_csv, budget_csv, fx_csv, cash_csv)
    actuals_usd = _to_usd(actuals, fx)
    budget_usd = _to_usd(budget, fx)
    actuals_pivot, budget_pivot, actuals_enriched = _build_pivots(actuals_usd, budget_usd)

    def answer(question: str, plotting: bool = True) -> Dict[str, Any]:
        month_dt = _extract_month(question) or actuals_pivot.index.max()
        if month_dt not in actuals_pivot.index:
            month_dt = actuals_pivot.index.max()

        trend = _is_trend(question)
        compare_budget = _vs_budget(question)
        lower_question = question.lower()

        # Cash runway
        if "cash runway" in lower_question or ("cash" in lower_question and "runway" in lower_question):
            months = _cash_runway_months(cash, actuals_pivot)
            if months == float("inf"):
                text = "Cash runway: ∞ months (no net burn over last 3 months)."
            else:
                text = f"Cash runway: {months:.1f} months based on last 3 months' average burn."
            return {"text": text, "chart": None}

        # Gross Margin %
        if "gross margin" in lower_question:
            if trend:
                series = actuals_pivot["Gross Margin %"].dropna()
                budget_series = budget_pivot["Gross Margin %"].dropna()
                match = re.search(r"last\s+(\d+)\s+month", lower_question)
                if match:
                    last_n = int(match.group(1))
                    series = series.iloc[-last_n:]
                    budget_series = budget_series.iloc[-last_n:]
                fig = None
                if plotting and not series.empty:
                    fig = _line_chart(
                        series,
                        "Gross Margin % Trend",
                        "Gross Margin %",
                        compare_series=budget_series if compare_budget else None,
                        compare_label="Budget GM%",
                        series_label="Actual GM%",
                    )
                suffix = " vs Budget" if compare_budget else ""
                return {"text": f"Displayed Gross Margin % trend{suffix}", "chart": fig}
            actual = actuals_pivot.loc[month_dt, "Gross Margin %"]
            budget_value = budget_pivot.loc[month_dt, "Gross Margin %"]
            variance = actual - budget_value
            text = (
                f"Gross Margin % — {_month_label(month_dt)}\n"
                f"Actual: {actual:.1f}%\nBudget: {budget_value:.1f}%\nVariance: {variance:+.1f} pp"
            )
            return {"text": text, "chart": None}

        # Opex breakdown
        if "opex" in lower_question and ("break down" in lower_question or "breakdown" in lower_question or "by category" in lower_question):
            breakdown = _opex_breakdown(actuals_enriched, month_dt)
            fig = None
            if plotting and not breakdown.empty:
                fig = _bar_chart(breakdown, f"Opex Breakdown — {_month_label(month_dt)}", "Amount (USD)")
            total = breakdown["amount_usd"].sum() if not breakdown.empty else 0.0
            text = f"Opex total — {_month_label(month_dt)}: ${total:,.0f}"
            return {"text": text, "chart": fig, "table": breakdown if not breakdown.empty else None}

        # EBITDA
        if "ebitda" in lower_question:
            if trend:
                fig = None
                if plotting:
                    fig = _line_chart(
                        actuals_pivot["EBITDA"],
                        "EBITDA Trend",
                        "USD",
                        compare_series=budget_pivot["EBITDA"] if compare_budget else None,
                        compare_label="Budget EBITDA",
                        series_label="Actual EBITDA",
                    )
                suffix = " vs Budget" if compare_budget else ""
                return {"text": f"Displayed EBITDA trend{suffix}", "chart": fig}
            actual_value = actuals_pivot.loc[month_dt, "EBITDA"]
            budget_value = budget_pivot.loc[month_dt, "EBITDA"]
            variance = actual_value - budget_value
            variance_pct = (variance / budget_value * 100) if budget_value not in (0, np.nan) else np.nan
            text = (
                f"EBITDA — {_month_label(month_dt)}\n"
                f"Actual: ${actual_value:,.0f}\nBudget: ${budget_value:,.0f}\nVariance: ${variance:,.0f} ({variance_pct:+.1f}%)"
            )
            return {"text": text, "chart": None}

        # Revenue
        if trend:
            fig = None
            if plotting:
                fig = _line_chart(
                    actuals_pivot["Revenue"],
                    "Revenue Trend",
                    "USD",
                    compare_series=budget_pivot["Revenue"] if compare_budget else None,
                    compare_label="Budget Revenue",
                    series_label="Actual Revenue",
                )
            suffix = " vs Budget" if compare_budget else ""
            return {"text": f"Displayed Revenue trend{suffix}", "chart": fig}
        actual_value = actuals_pivot.loc[month_dt, "Revenue"]
        budget_value = budget_pivot.loc[month_dt, "Revenue"]
        variance = actual_value - budget_value
        variance_pct = (variance / budget_value * 100) if budget_value not in (0, np.nan) else np.nan
        text = (
            f"Revenue — {_month_label(month_dt)}\n"
            f"Actual: ${actual_value:,.0f}\nBudget: ${budget_value:,.0f}\nVariance: ${variance:,.0f} ({variance_pct:+.1f}%)"
        )
        return {"text": text, "chart": None}

    return answer
