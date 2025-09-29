import pandas as pd, numpy as np, re, os
from datetime import datetime
from dateutil import parser as dateparser

# ---------- parsing helpers ----------
def _month_label(dt): return dt.strftime("%b %Y")
def _parse_month(text):
    try:
        dt = dateparser.parse(text, default=datetime(2025,1,1))
        return datetime(dt.year, dt.month, 1)
    except Exception:
        return None
def _extract_month(q):
    m = re.search(r'(jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|jun(e)?|jul(y)?|aug(ust)?|sep(t)?(ember)?|oct(ober)?|nov(ember)?|dec(ember)?)\s*\d{4}', q, flags=re.I)
    if m: return _parse_month(m.group(0))
    m = re.search(r'\b(20\d{2})-(0[1-9]|1[0-2])\b', q)
    if m: return _parse_month(m.group(0)+'-01')
    return None
def _is_trend(q): return any(w in q.lower() for w in ["trend","trends","over time","by month","chart","plot","line","graph","show"])
def _vs_budget(q): return any(k in q.lower() for k in ["vs budget","versus budget","variance","budget"])

# ---------- data load & transforms ----------
def _load(actuals_csv, budget_csv, fx_csv, cash_csv):
    a = pd.read_csv(actuals_csv, parse_dates=["date"])
    b = pd.read_csv(budget_csv,  parse_dates=["date"])
    fx = pd.read_csv(fx_csv,      parse_dates=["date"])
    cash = pd.read_csv(cash_csv,  parse_dates=["date"])
    for df in (a,b):
        if "entity" not in df.columns: df["entity"]="Total"
        if "currency" not in df.columns: df["currency"]="USD"
        df["account"] = df["account"].astype(str)
    fx["currency"] = fx["currency"].fillna("USD")
    if "rate_to_usd" not in fx.columns: fx["rate_to_usd"]=1.0
    fx = fx.drop_duplicates(subset=["date","currency"], keep="last")
    return a,b,fx,cash

def _to_usd(df, fx):
    m = pd.merge(df, fx, on=["date","currency"], how="left")
    m["rate_to_usd"] = m["rate_to_usd"].fillna(1.0)
    m["amount_usd"] = m["amount"] * m["rate_to_usd"]
    return m

def _build_pivots(a_usd, b_usd):
    def kind(acc):
        s = str(acc).lower()
        if s.startswith("opex"): return "Opex"
        if s.startswith("cogs"): return "Cogs"
        if s.startswith("revenue"): return "Revenue"
        return "Other"
    a_usd["Kind"] = a_usd["account"].map(kind)
    b_usd["Kind"] = b_usd["account"].map(kind)
    a = a_usd.pivot_table(index="date", columns="Kind", values="amount_usd", aggfunc="sum").fillna(0.0)
    b = b_usd.pivot_table(index="date", columns="Kind", values="amount_usd", aggfunc="sum").fillna(0.0)
    for col in ["Revenue","Cogs","Opex"]:
        if col not in a.columns: a[col]=0.0
        if col not in b.columns: b[col]=0.0
    def add(pv):
        pv = pv.copy().sort_index()
        pv["Gross Profit"]  = pv["Revenue"] - pv["Cogs"]
        pv["Gross Margin %"]= np.where(pv["Revenue"]!=0, pv["Gross Profit"]/pv["Revenue"], np.nan)*100
        pv["EBITDA"]        = pv["Revenue"] - pv["Cogs"] - pv["Opex"]
        pv["EBITDA %"]      = np.where(pv["Revenue"]!=0, pv["EBITDA"]/pv["Revenue"], np.nan)*100
        return pv
    return add(a), add(b), a_usd

def _opex_breakdown(df_usd, month_dt):
    d = df_usd[(df_usd["date"]==month_dt) & (df_usd["account"].str.lower().str.startswith("opex"))].copy()
    d["category"] = d["account"].str.split(":", n=1).str[1].fillna("Other").str.strip()
    return d.groupby("category")["amount_usd"].sum().reset_index().sort_values("amount_usd", ascending=False)

def _cash_runway_months(cash_df, a_pv):
    recent = a_pv.iloc[-3:]
    net_burn = (recent["Opex"] + recent["Cogs"] - recent["Revenue"]).mean()
    latest_cash = cash_df.sort_values("date").iloc[-1]["cash_balance"]
    if net_burn <= 0: return float("inf")
    return latest_cash / net_burn

# ---------- public: build_engine ----------
def build_engine(actuals_csv, budget_csv, fx_csv, cash_csv):
    a,b,fx,cash = _load(actuals_csv, budget_csv, fx_csv, cash_csv)
    a_usd = _to_usd(a, fx); b_usd = _to_usd(b, fx)
    a_pv, b_pv, a_usd_enriched = _build_pivots(a_usd, b_usd)

    def answer(q: str, plotting=True):
        import matplotlib.pyplot as plt
        month_dt = _extract_month(q) or a_pv.index.max()
        trend = _is_trend(q)
        compare = _vs_budget(q)

        ql = q.lower()

        # Cash runway
        if "cash runway" in ql or ("cash" in ql and "runway" in ql):
            m = _cash_runway_months(cash, a_pv)
            txt = "Cash runway: ∞ months (no net burn over last 3 months)." if m==float("inf") else f"Cash runway: {m:.1f} months based on last 3 months' average burn."
            return {"text": txt, "chart": None}

        # Gross Margin %
        if "gross margin" in ql:
            if trend:
                series = a_pv["Gross Margin %"]
                m = re.search(r"last\s+(\d+)\s+month", ql)
                bseries = b_pv["Gross Margin %"]
                if m:
                    n = int(m.group(1)); series = series.iloc[-n:]; bseries = bseries.iloc[-n:]
                if plotting:
                    plt.figure(figsize=(8,4.5))
                    plt.plot(series.index, series.values, label="Actual GM%")
                    if compare: plt.plot(bseries.index, bseries.values, linestyle="--", label="Budget GM%")
                    plt.title("Gross Margin % Trend"); plt.xlabel("Month"); plt.ylabel("Gross Margin %"); plt.legend(); plt.tight_layout(); plt.show()
                return {"text":"Displayed Gross Margin % trend"+(" vs Budget" if compare else ""), "chart":"rendered"}
            else:
                act = a_pv.loc[month_dt,"Gross Margin %"]; bud = b_pv.loc[month_dt,"Gross Margin %"]; var = act - bud
                return {"text": f"Gross Margin % — {_month_label(month_dt)}\nActual: {act:.1f}%\nBudget: {bud:.1f}%\nVariance: {var:+.1f} pp", "chart": None}

        # Opex breakdown
        if "opex" in ql and ("break down" in ql or "breakdown" in ql or "by category" in ql):
            br = _opex_breakdown(a_usd_enriched, month_dt)
            if plotting and len(br):
                plt.figure(figsize=(8,4.5)); plt.bar(br["category"], br["amount_usd"]); plt.title(f"Opex Breakdown — {_month_label(month_dt)}"); plt.xlabel("Category"); plt.ylabel("Amount (USD)"); plt.tight_layout(); plt.show()
            total = br["amount_usd"].sum() if len(br) else 0.0
            return {"text": f"Opex total — {_month_label(month_dt)}: ${total:,.0f}", "chart": "rendered" if len(br) else None, "table": br}

        # EBITDA
        if "ebitda" in ql:
            if trend:
                if plotting:
                    plt.figure(figsize=(8,4.5))
                    plt.plot(a_pv.index, a_pv["EBITDA"], label="Actual EBITDA")
                    if compare: plt.plot(b_pv.index, b_pv["EBITDA"], linestyle="--", label="Budget EBITDA")
                    plt.title("EBITDA Trend"); plt.xlabel("Month"); plt.ylabel("USD"); plt.legend(); plt.tight_layout(); plt.show()
                return {"text":"Displayed EBITDA trend"+(" vs Budget" if compare else ""), "chart":"rendered"}
            else:
                act=a_pv.loc[month_dt,"EBITDA"]; bud=b_pv.loc[month_dt,"EBITDA"]; var=act-bud; var_pct=(var/bud*100) if bud not in (0,np.nan) else np.nan
                return {"text": f"EBITDA — {_month_label(month_dt)}\nActual: ${act:,.0f}\nBudget: ${bud:,.0f}\nVariance: ${var:,.0f} ({var_pct:+.1f}%)", "chart": None}

        # Revenue
        if trend:
            if plotting:
                plt.figure(figsize=(8,4.5))
                plt.plot(a_pv.index, a_pv["Revenue"], label="Actual Revenue")
                if compare: plt.plot(b_pv.index, b_pv["Revenue"], linestyle="--", label="Budget Revenue")
                plt.title("Revenue Trend"); plt.xlabel("Month"); plt.ylabel("USD"); plt.legend(); plt.tight_layout(); plt.show()
            return {"text":"Displayed Revenue trend"+(" vs Budget" if compare else ""), "chart":"rendered"}
        else:
            act=a_pv.loc[month_dt,"Revenue"]; bud=b_pv.loc[month_dt,"Revenue"]; var=act-bud; var_pct=(var/bud*100) if bud not in (0,np.nan) else np.nan
            return {"text": f"Revenue — {_month_label(month_dt)}\nActual: ${act:,.0f}\nBudget: ${bud:,.0f}\nVariance: ${var:,.0f} ({var_pct:+.1f}%)", "chart": None}

    return answer
