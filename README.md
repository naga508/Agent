# Mini CFO Copilot (FP&A)

End-to-end mini agent that answers CFO-style questions from monthly CSVs and renders charts in Streamlit.

## Run Locally
```bash
python -m venv .venv && source .venv/bin/activate  # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

The app loads data from the CSV fixtures in `./fixtures` and returns numeric answers plus charts when appropriate.

## Data
CSV files in `fixtures/` (already exported from the provided `data.xlsx`):
- `fixtures/actuals.csv` — monthly actuals by entity/account
- `fixtures/budget.csv`  — monthly budget by entity/account
- `fixtures/fx.csv`      — currency exchange rates (`rate_to_usd`)
- `fixtures/cash.csv`    — monthly cash balances

**Schema**
- actuals/budget: `date`, `entity`, `account`, `amount`, `currency`
  - accounts include: `Revenue`, `COGS*`, and `Opex:*` categories (e.g., `Opex:S&M`, `Opex:R&D`)
- fx: `date`, `currency`, `rate_to_usd`
- cash: `date`, `cash_balance`

## Sample Questions
- What was June 2025 revenue vs budget in USD?
- Show Gross Margin % trend for the last 3 months.
- Break down Opex by category for June 2025.
- What is our cash runway right now?

## Tests
```bash
pytest -q
```
