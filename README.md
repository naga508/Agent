# Mini CFO Copilot (FP&A)

An end-to-end Streamlit app that lets finance leaders ask natural-language questions about monthly actuals, budgets, FX, and cash data. The agent classifies the question, runs the appropriate calculations, and returns concise answers with charts that are ready for board decks.

## Features
- Point-in-time answers for revenue, gross margin, opex, EBITDA, and more.
- Trend visualisations that compare actuals to budget.
- Opex category breakdown tables and charts.
- Cash runway calculation using the trailing three-month net burn.

## Getting Started
1. **Create a virtual environment & install dependencies**
   ```bash
   cd Agent
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. **Run the Streamlit app**
   ```bash
   streamlit run app.py
   ```
3. **Run the unit tests**
   ```bash
   pytest -q
   ```

## Data Fixtures
Sample CSVs live in `fixtures/` and mirror typical FP&A exports:
- `fixtures/actuals.csv` — monthly actuals by entity/account.
- `fixtures/budget.csv` — monthly budget by entity/account.
- `fixtures/fx.csv` — FX rates into USD (`rate_to_usd`).
- `fixtures/cash.csv` — monthly cash balances.

Each file includes a `date` column (parsed monthly). Income statement accounts follow `Revenue`, `COGS`, and `Opex:*` naming conventions so that the agent can derive gross margin, EBITDA, and category-level expense summaries.

## Example Prompts
```
What was June 2025 revenue vs budget in USD?
Show Gross Margin % trend for the last 3 months.
Break down Opex by category for June 2025.
What is our cash runway right now?
```

Feel free to swap in your own CSVs as long as they use the same column names.
