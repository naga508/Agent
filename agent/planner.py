"""Lightweight rule-based planner for finance questions."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional

import pandas as pd
from dateutil import parser as dateparser


@dataclass
class Plan:
    intent: str
    metric: Optional[str] = None
    month: Optional[pd.Timestamp] = None
    months: Optional[int] = None
    compare_budget: bool = False


METRIC_KEYWORDS = {
    "revenue": ["revenue", "sales", "top line"],
    "gross margin %": ["gross margin", "gm%", "margin%", "margin %"],
    "gross profit": ["gross profit", "gp"],
    "cogs": ["cogs", "cost of goods", "costs"],
    "opex": ["opex", "operating expense", "expenses"],
    "ebitda": ["ebitda", "operating income"],
    "ebitda %": ["ebitda %", "ebitda margin"],
}


class Planner:
    """Simple heuristic planner that maps natural language to tool calls."""

    def parse(self, question: str) -> Plan:
        ql = question.lower()
        if "cash runway" in ql or "runway" in ql:
            return Plan(intent="cash_runway")

        metric = self._detect_metric(ql)
        month = self._detect_month(question)
        months = self._detect_trailing_months(ql)
        compare_budget = self._detect_vs_budget(ql)

        if "break down" in ql or "breakdown" in ql:
            return Plan(intent="breakdown", metric="opex", month=month, compare_budget=compare_budget)

        if any(word in ql for word in ["trend", "over time", "chart", "plot", "line", "last", "history", "trailing"]):
            return Plan(intent="trend", metric=metric, months=months, compare_budget=compare_budget)

        return Plan(intent="point", metric=metric, month=month, compare_budget=compare_budget)

    @staticmethod
    def _detect_metric(text: str) -> str:
        for metric, keywords in METRIC_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                return metric
        return "revenue"

    @staticmethod
    def _detect_vs_budget(text: str) -> bool:
        return any(phrase in text for phrase in ["vs budget", "versus budget", "budget", "variance"])

    @staticmethod
    def _detect_trailing_months(text: str) -> Optional[int]:
        match = re.search(r"last (\d+) month", text)
        if match:
            return int(match.group(1))
        match = re.search(r"trailing (\d+)", text)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def _detect_month(text: str) -> Optional[pd.Timestamp]:
        match = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+20\d{2}", text, re.I)
        if match:
            dt = dateparser.parse(match.group(0))
            return pd.Timestamp(year=dt.year, month=dt.month, day=1)
        match = re.search(r"20\d{2}-(0[1-9]|1[0-2])", text)
        if match:
            dt = dateparser.parse(match.group(0) + "-01")
            return pd.Timestamp(year=dt.year, month=dt.month, day=1)
        return None
