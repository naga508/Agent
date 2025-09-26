
import pandas as pd
import numpy as np
import re
from datetime import datetime
from dateutil import parser as dateparser

METRIC_ALIASES = {
    "revenue": ["revenue","sales","top line","topline"],
    "cogs": ["cogs","cost of goods","costs"],
    "gross profit": ["gross profit","gp"],
    "gross margin %": ["gross margin","gm%","gross margin %","margin %","gross%"],
    "opex": ["opex","operating expenses","expenses"],
    "ebitda": ["ebitda","operating income"],
    "ebitda %": ["ebitda margin","ebitda %","operating margin"]
}

metric_to_col = {
    "revenue": "Revenue",
    "cogs": "Cogs",
    "opex": "Opex",
    "gross profit": "Gross Profit",
    "gross margin %": "Gross Margin %",
    "ebitda": "EBITDA",
    "ebitda %": "EBITDA %",
}

def load_data(actual_csv, budget_csv):
    a = pd.read_csv(actual_csv, parse_dates=["date"])
    b = pd.read_csv(budget_csv, parse_dates=["date"])
    df = pd.concat([a, b], ignore_index=True)
    df["account"] = df["account"].str.strip().str.title()
    df["type"] = df["type"].str.strip().str.title()
    return df

def pivot_pl(df, kind="Actual"):
    sub = df[df["type"] == kind]
    pv = sub.pivot_table(index="date", columns="account", values="amount", aggfunc="sum").fillna(0.0)
    for col in ["Revenue","Cogs","Opex"]:
        if col not in pv.columns: pv[col] = 0.0
    pv["Gross Profit"]  = pv["Revenue"] - pv["Cogs"]
    pv["Gross Margin %"]= np.where(pv["Revenue"]!=0, pv["Gross Profit"]/pv["Revenue"], np.nan) * 100
    pv["EBITDA"]        = pv["Revenue"] - pv["Cogs"] - pv["Opex"]
    pv["EBITDA %"]      = np.where(pv["Revenue"]!=0, pv["EBITDA"]/pv["Revenue"], np.nan) * 100
    return pv.sort_index()

def parse_month(text):
    try:
        dt = dateparser.parse(text, default=datetime(2025,1,1))
        return datetime(dt.year, dt.month, 1)
    except Exception:
        return None

def match_metric(q):
    ql = q.lower()
    for m, aliases in METRIC_ALIASES.items():
        if any(a in ql for a in aliases):
            return m
    return "revenue"

def detect_trend(q):
    return any(w in q.lower() for w in ["trend","trends","over time","by month","chart","plot","line","graph","show me"])

def detect_vs_budget(q):
    ql = q.lower()
    return ("vs budget" in ql) or ("versus budget" in ql) or ("budget vs" in ql) or ("variance" in ql)

def extract_month(q):
    m = re.search(r'(jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|jun(e)?|jul(y)?|aug(ust)?|sep(t)?(ember)?|oct(ober)?|nov(ember)?|dec(ember)?)\s*\d{4}', q, flags=re.I)
    if m:
        return parse_month(m.group(0))
    m = re.search(r'\b(20\d{2})-(0[1-9]|1[0-2])\b', q)
    if m:
        return parse_month(m.group(0) + "-01")
    return None

def month_label(dt):
    return dt.strftime("%b %Y")

def build_engine(actual_csv, budget_csv):
    df = load_data(actual_csv, budget_csv)
    pv_act = pivot_pl(df, "Actual")
    pv_bud = pivot_pl(df, "Budget")

    def colname(metric):
        return metric_to_col.get(metric, metric)

    def compute_point(metric, dt):
        mcol = colname(metric)
        act = pv_act.loc[dt, mcol] if dt in pv_act.index else np.nan
        bud = pv_bud.loc[dt, mcol] if dt in pv_bud.index else np.nan
        var = act - bud if (pd.notna(act) and pd.notna(bud)) else np.nan
        var_pct = (var / bud * 100) if (pd.notna(var) and bud not in (0,np.nan)) else np.nan
        return act, bud, var, var_pct

    def answer(q):
        import matplotlib.pyplot as plt
        is_trend = detect_trend(q)
        metric = match_metric(q)
        mcol = colname(metric)
        mdt = extract_month(q)
        vs_budget = detect_vs_budget(q) or (not is_trend and "budget" in q.lower())

        if is_trend:
            fig = plt.figure(figsize=(8,4.5))
            x = pv_act.index
            y_act = pv_act[mcol]
            plt.plot(x, y_act, label=f"Actual {mcol}")
            if vs_budget:
                plt.plot(pv_bud.index, pv_bud[mcol], linestyle='--', label=f"Budget {mcol}")
            plt.title(f"{mcol} Trend — {x.min().year}")
            plt.xlabel("Month")
            plt.ylabel(mcol)
            plt.legend()
            plt.tight_layout()
            plt.show()
            return f"Displayed {mcol} trend{' vs Budget' if vs_budget else ''}."
        else:
            dt = mdt or pv_act.index.max()
            act, bud, var, var_pct = compute_point(metric, dt)
            lines = [f"{mcol} — {month_label(dt)}"]
            if pd.notna(act):
                val = f"${act:,.0f}" if "%" not in mcol else f"{act:,.1f}%"
                lines.append(f"Actual: {val}")
            if vs_budget or pd.notna(bud):
                if pd.notna(bud):
                    budv = f"${bud:,.0f}" if "%" not in mcol else f"{bud:,.1f}%"
                    lines.append(f"Budget: {budv}")
                if pd.notna(var):
                    varv = f"${var:,.0f}" if "%" not in mcol else f"{var:,.1f}%"
                    if pd.notna(var_pct) and "%" not in mcol:
                        lines.append(f"Variance: {varv} ({var_pct:+.1f}%)")
                    else:
                        lines.append(f"Variance: {varv}")
            return "\n".join(lines)

    return answer
