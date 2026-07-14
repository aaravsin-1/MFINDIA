# website/ — retail fund-selection site

Everything needed to stand up the investor-facing website on top of the
`RESULTS_PROJECT` deliverable.

| File | What it is |
|---|---|
| `push_to_supabase.py` | ETL: reads the screener CSVs + enriches the live list with per-fund detail from the `amfi_data` DB, then pushes clean, public-read tables to Supabase. |
| `schema.sql` | Reference DDL for every Supabase table (the contract the website is built against). |
| `LOVABLE_PROMPT.md` | A ready-to-paste [Lovable](https://lovable.dev) prompt that builds the whole site against those tables. |
| `preview/` | Local JSON dump of each table (from `--dry-run --out`) — the exact shape the website sees. |

## What changed vs the old `Z_FINAL_PLATFORM/push_to_supabase.py`
The old script re-computed ratings live from the DB. The deliverable is now the
finished screener **CSVs** (`../fund_screener_results_2025.csv` = live 381 funds,
`../fund_screener_results.csv` = 2022 validation 275 funds), so this version reads
and shapes them — then adds a **shallow per-fund detail layer** pulled from
`amfi_data` for the on-click fund view.

## Tables pushed (8)
**From the CSVs:**
- **`funds`** — every rated fund (live + validation): Quality (0–100, within-category),
  Risk (0–100) + band, `recommended` flag, holding period, parsed reasons,
  `scheme_id` join key. The website's main list.
- **`research_log`** — the 12 findings (F1–F12) with verdicts. The "why trust it".
- **`engine_metrics`** — headline validated numbers (edge, IC, significance, sizes).
- **`category_summary`** — per-category counts + where selection skill lives (F6).

**Per-fund detail (LIVE funds only, from `amfi_data`, loaded on click):**
- **`fund_detail`** — AMC, inception, AUM (₹cr), TER, #managers, NAV point count.
- **`fund_nav`** — ~13 monthly NAV points (1-year sparkline).
- **`fund_managers`** — current managers + tenure.
- **`fund_holdings`** — top-10 holdings, **kept but NOT shown on the site** (partial
  coverage ~188/381). Combines two sources for best reach: `amfi`
  (portfolio_holding_fact, clean names) preferred, `morningstar` (linked by exact
  growth-ISIN, tickers resolved via `stock_prices`) fills the gaps. Retained in the
  DB for a future release once coverage improves.

## Run it
```powershell
cd C:\a_Coding\KOTAK-TASK\RESULTS_PROJECT\website

# inspect without touching Supabase (writes preview/*.json):
python push_to_supabase.py --dry-run --out

# CSV tables only (skip the amfi_data enrichment):
python push_to_supabase.py --no-detail --dry-run

# push for real (needs SUPABASE_* env + the amfi_data DB reachable):
python push_to_supabase.py
```
Credentials all live in **`RESULTS_PROJECT/.env`** (`../.env`): `SUPABASE_*` for the
destination and `DB_*` for the source `amfi_data` DB. If the source DB is
unreachable the script still pushes the 4 CSV tables and just skips the detail
layer.

Re-run after each yearly re-score (`score_live.py`) to refresh the site — no
redeploy needed.
