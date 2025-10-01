import os

import streamlit as st

from agent import build_engine

st.set_page_config(page_title="Mini CFO Copilot", page_icon="📈", layout="centered")
st.title("📈 Mini CFO Copilot")
st.write("Ask finance questions from monthly CSVs. Try:")
st.code(
    "- What was June 2025 revenue vs budget in USD?\n"
    "- Show Gross Margin % trend for the last 3 months.\n"
    "- Break down Opex by category for June 2025.\n"
    "- What is our cash runway right now?"
)

# Resolve fixture paths relative to repo root
ROOT = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(ROOT, "fixtures")
ACTUALS = os.path.join(FIX, "actuals.csv")
BUDGET = os.path.join(FIX, "budget.csv")
FX = os.path.join(FIX, "fx.csv")
CASH = os.path.join(FIX, "cash.csv")

engine = build_engine(ACTUALS, BUDGET, FX, CASH)

query = st.text_input("Your question", value="What was June 2025 revenue vs budget in USD?")

if st.button("Ask") or query:
    with st.spinner("Thinking..."):
        result = engine(query)

    if result.get("chart") is not None:
        st.pyplot(result["chart"], clear_figure=False)

    st.success(result["text"])

    if result.get("table") is not None:
        st.subheader("Opex Breakdown")
        st.dataframe(result["table"])

    st.caption("Charts are rendered inline above when available.")
