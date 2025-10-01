import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from agent import build_engine

st.set_page_config(page_title="Mini CFO Copilot", page_icon="📈", layout="wide")
st.title("📈 Mini CFO Copilot")
st.write("Ask finance questions from monthly CSVs. Try:")
st.code("""What was June 2025 revenue vs budget in USD?\nShow Gross Margin % trend for the last 3 months.\nBreak down Opex by category for June 2025.\nWhat is our cash runway right now?""")

ACTUALS = "fixtures/actuals.csv"
BUDGET = "fixtures/budget.csv"
FX = "fixtures/fx.csv"
CASH = "fixtures/cash.csv"

engine = build_engine(ACTUALS, BUDGET, FX, CASH)

with st.form("query"):
    question = st.text_input("Your question", value="What was June 2025 revenue vs budget in USD?")
    submitted = st.form_submit_button("Ask")

if submitted and question:
    with st.spinner("Analyzing the numbers…"):
        result = engine(question)
    if result.get("figure") is not None:
        st.plotly_chart(result["figure"], use_container_width=True)
    st.success(result["text"])
    if result.get("table") is not None and not result["table"].empty:
        st.subheader("Details")
        st.dataframe(result["table"], hide_index=True, use_container_width=True)
    st.caption("Charts are rendered inline above, when applicable.")
