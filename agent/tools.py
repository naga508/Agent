"""Data access and metric utilities for the finance agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class MetricPoint:
    """Container for point-in-time metric values."""

    actual: Optional[float]
    budget: Optional[float]
    variance: Optional[float]
    variance_pct: Optional[float]


class FinanceTools:
    """Utility wrapper that loads CSVs and exposes finance calculations."""

    def __init__(self, actuals_csv: str, budget_csv: str, fx_csv: str, cash_csv: str) -> None:
        fx = pd.read_csv(fx_csv, parse_dates=["date"]) if fx_csv else pd.DataFrame()
        if not fx.empty:
            fx["currency"] = fx["currency"].str.upper()

        self.actuals = self._prepare_pl(actuals_csv, fx)
        self.budget = self._prepare_pl(budget_csv, fx)
        self.cash = self._prepare_cash(cash_csv)

        self.actual_summary = self._summarise_pl(self.actuals)
        self.budget_summary = self._summarise_pl(self.budget)

        self.opex_actual = self._opex_breakdown(self.actuals)
        self.opex_budget = self._opex_breakdown(self.budget)

        self.metric_names = {
            "revenue": "Revenue",
            "cogs": "COGS",
            "gross profit": "Gross Profit",
            "gross margin %": "Gross Margin %",
            "opex": "Opex",
            "ebitda": "EBITDA",
            "ebitda %": "EBITDA %",
        }

    @staticmethod
    def _prepare_pl(csv_path: str, fx: pd.DataFrame) -> pd.DataFrame:
        df = pd.read_csv(csv_path, parse_dates=["date"])
        if df.empty:
            return df
        df["currency"] = df["currency"].str.upper()
        if not fx.empty:
            df = df.merge(fx, on=["date", "currency"], how="left")
            df["rate_to_usd"] = df["rate_to_usd"].fillna(1.0)
            df["amount_usd"] = df["amount"] * df["rate_to_usd"]
        else:
            df["amount_usd"] = df["amount"]
        df["account"] = df["account"].str.strip()
        df["account_group"] = df["account"].str.split(":").str[0]
        df["account_category"] = df.apply(
            lambda row: row["account"].split(":", 1)[1]
            if row["account_group"].lower() == "opex" and ":" in row["account"]
            else row["account_group"],
            axis=1,
        )
        df.sort_values("date", inplace=True)
        return df

    @staticmethod
    def _prepare_cash(csv_path: str) -> pd.DataFrame:
        df = pd.read_csv(csv_path, parse_dates=["date"])
        df.sort_values("date", inplace=True)
        return df

    @staticmethod
    def _summarise_pl(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()
        pivot = (
            df.groupby(["date", "account_group"], as_index=False)["amount_usd"].sum()
            .pivot(index="date", columns="account_group", values="amount_usd")
            .sort_index()
        ).fillna(0.0)
        for col in ["Revenue", "COGS", "Opex"]:
            if col not in pivot:
                pivot[col] = 0.0
        pivot["Gross Profit"] = pivot["Revenue"] - pivot["COGS"]
        pivot["Gross Margin %"] = np.where(
            pivot["Revenue"] != 0, pivot["Gross Profit"] / pivot["Revenue"] * 100, np.nan
        )
        pivot["EBITDA"] = pivot["Revenue"] - pivot["COGS"] - pivot["Opex"]
        pivot["EBITDA %"] = np.where(
            pivot["Revenue"] != 0, pivot["EBITDA"] / pivot["Revenue"] * 100, np.nan
        )
        pivot.index = pd.to_datetime(pivot.index)
        return pivot

    @staticmethod
    def _opex_breakdown(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()
        breakdown = (
            df[df["account_group"].str.lower() == "opex"]
            .groupby(["date", "account_category"], as_index=False)["amount_usd"].sum()
            .pivot(index="date", columns="account_category", values="amount_usd")
            .fillna(0.0)
            .sort_index()
        )
        breakdown.index = pd.to_datetime(breakdown.index)
        return breakdown

    @property
    def latest_month(self) -> Optional[pd.Timestamp]:
        if self.actual_summary.empty:
            return None
        return pd.Timestamp(self.actual_summary.index.max())

    def _series_for_metric(self, metric: str, table: str = "actual") -> pd.Series:
        name = self.metric_names.get(metric, metric)
        summary = self.actual_summary if table == "actual" else self.budget_summary
        if summary.empty:
            return pd.Series(dtype=float)
        if name not in summary.columns:
            return pd.Series(0.0, index=summary.index)
        return summary[name]

    def metric_point(self, metric: str, month: pd.Timestamp) -> MetricPoint:
        series_act = self._series_for_metric(metric, "actual")
        series_bud = self._series_for_metric(metric, "budget")
        actual = float(series_act.get(month, np.nan)) if not series_act.empty else np.nan
        budget = float(series_bud.get(month, np.nan)) if not series_bud.empty else np.nan
        variance = actual - budget if not np.isnan(actual) and not np.isnan(budget) else np.nan
        if not np.isnan(variance) and budget not in (0, np.nan):
            variance_pct = variance / budget * 100
        else:
            variance_pct = np.nan
        return MetricPoint(actual, budget, variance, variance_pct)

    def metric_trend(self, metric: str, months: Optional[int] = None) -> pd.DataFrame:
        series_act = self._series_for_metric(metric, "actual")
        series_bud = self._series_for_metric(metric, "budget")
        df = pd.DataFrame({"Actual": series_act})
        if not series_bud.empty:
            df["Budget"] = series_bud
        df = df.dropna(how="all")
        if months is not None and months > 0:
            df = df.tail(months)
        df.index.name = "date"
        return df

    def opex_breakdown(self, month: pd.Timestamp) -> pd.DataFrame:
        actual_row = self.opex_actual.loc[[month]] if month in self.opex_actual.index else pd.DataFrame()
        budget_row = self.opex_budget.loc[[month]] if month in self.opex_budget.index else pd.DataFrame()
        categories = sorted(set(actual_row.columns).union(budget_row.columns))
        data = []
        for cat in categories:
            actual_val = float(actual_row[cat].iloc[0]) if not actual_row.empty and cat in actual_row else 0.0
            budget_val = float(budget_row[cat].iloc[0]) if not budget_row.empty and cat in budget_row else 0.0
            data.append({"Category": cat, "Actual": actual_val, "Budget": budget_val})
        return pd.DataFrame(data)

    def cash_runway(self, trailing_months: int = 3) -> dict:
        if self.cash.empty or self.actual_summary.empty:
            return {"cash": np.nan, "burn": np.nan, "runway": np.nan}
        latest_cash = float(self.cash.sort_values("date").iloc[-1]["cash_balance"])
        ebitda = self.actual_summary["EBITDA"].dropna()
        if trailing_months > 0:
            ebitda = ebitda.tail(trailing_months)
        net_burn = (-ebitda).clip(lower=0)
        avg_burn = float(net_burn.mean()) if not net_burn.empty else 0.0
        if avg_burn <= 0:
            runway = np.inf
        else:
            runway = latest_cash / avg_burn
        return {"cash": latest_cash, "burn": avg_burn, "runway": runway}

    def display_name(self, metric: str) -> str:
        return self.metric_names.get(metric, metric.title())
