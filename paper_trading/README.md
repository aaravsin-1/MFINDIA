# Paper Trading System — Category-Neutral Strategy

A self-contained paper-trading harness that runs the **validated category-neutral
strategy** live against real AMFI NAVs, marks it to market every day, rebalances
automatically, and reports the **actual** edge vs a category-matched benchmark — so
we can watch the +2.4% research claim play out (or not) on out-of-sample days.

It reuses the project's data plumbing:
- **NAVs** from postgres `amfi_data.nav`, refreshed by `../../scraper/load_navall.py`
  (the same loader `daily_updater.py` uses).
- **Model & features** from `../model_live.pkl` + `../prepare_features_live.py`.
- **Paper-account state** in a local **SQLite** file (`paper_trading.db`) — isolated
  from the market DB, fully auditable, portable.

---

## What it trades

Two books share one account so the comparison is apples-to-apples, each seeded with
₹10,00,000 notional:

| Book | What it holds | Purpose |
|---|---|---|
| **strategy** | top-2 per core category (10 funds), equal weight | the validated portfolio |
| **benchmark** | equal-weight basket of **all** core-category funds | the category-matched benchmark the +2.4% was measured against |

Core categories: Large Cap, Mid Cap, Small Cap, Flexi Cap, ELSS.

**Rebalance rules (mirror the research):**
- Annual cadence (`REBALANCE_INTERVAL_DAYS = 365`).
- **Top-4 buffer** — a held fund is sold only when it drops out of its category's
  top-4 (cuts turnover ~46%→33%, per `../test_buffer_rule.py`).
- **12-month min-hold** — never sell a lot under a year (LTCG 12.5% + zero exit load;
  selling earlier would trigger 20% STCG). Enforced on every sell.

All returns are **gross**; `report.py` also prints a rough after-LTCG net figure.

---

## Files

| File | Role |
|---|---|
| `config.py` | paths, strategy params, DB credentials helper |
| `state_db.py` | SQLite schema + helpers (account, positions, ledger, value history) |
| `market_data.py` | read-only postgres accessors (direct/growth NAV on/before a date) |
| `strategy.py` | scores the live universe as-of a date → target top-2/category + benchmark set |
| `engine.py` | buy/sell, mark-to-market, buffered rebalance |
| `init_account.py` | **one-time** — create the account and form the initial portfolio |
| `backfill.py` | replay daily marks from inception → latest stored NAV (instant track record) |
| `update_daily.py` | **the cron entrypoint** — fetch NAVs, mark, rebalance-if-due |
| `report.py` | status: holdings, live edge, net-of-tax, trades, rebalance log; writes `reports/paper_report.csv` |
| `run_paper_trading.bat` | Windows Task Scheduler wrapper (dated logging) |

---

## Quick start

```powershell
cd C:\a_Coding\KOTAK-TASK\RESULTS_PROJECT\paper_trading

# 1. Create the account + initial portfolio at the latest available NAV date
python init_account.py
#    (or pin a start date:  python init_account.py --date 2025-12-31)

# 2. (optional) Backfill a real track record up to today's stored NAVs
python backfill.py

# 3. See where it stands
python report.py

# 4. From now on, this runs daily (the .bat calls it):
python update_daily.py
```

`update_daily.py` is safe to run repeatedly — it no-ops if the latest NAV date is
already marked, and only rebalances when a year has elapsed.

---

## Automating it (Windows Task Scheduler ≈ cron)

Schedule `run_paper_trading.bat` daily at **21:00** (AMFI usually publishes daily NAVs
by ~8–9 PM IST). From an **admin** PowerShell:

```powershell
schtasks /Create /TN "KotakPaperTrade" /TR "C:\a_Coding\KOTAK-TASK\RESULTS_PROJECT\paper_trading\run_paper_trading.bat" /SC DAILY /ST 21:00 /RL HIGHEST /F
```

Verify / run-now / remove:
```powershell
schtasks /Query  /TN "KotakPaperTrade"
schtasks /Run    /TN "KotakPaperTrade"
schtasks /Delete /TN "KotakPaperTrade" /F
```

Each run appends to `logs\paper_<date>.log`. The `.bat` uses `python` on PATH — if you
run inside a virtualenv, edit it to point at that venv's `python.exe`.

> **Weekends/holidays:** markets are closed, AMFI republishes the prior NAV, so a run
> just re-marks the same values — harmless. The daily fetch is wrapped so an AMFI
> download or DB hiccup is **non-fatal**: it logs a warning and marks on stored NAVs.

---

## Data cadence — what's fetched when, and when to retrain

The daily job and the model need **different** data. This is the important bit:

| Data | Source | Table | Needed for | Cadence |
|---|---|---|---|---|
| Daily NAV | `scraper/load_navall.py` | `nav` | **daily marking** | every run (the `.bat`) |
| Monthly NAV rollup | `amfi-database/build_returns.sql` | `plan_nav_monthly` | model features + label | rebuild at refresh |
| AUM | `scraper/load_aum.py` | `v_scheme_aum` | model feature | quarterly |
| TER | `scraper/load_ter.py` | `ter` | model feature | quarterly |
| Managers (Morningstar) | `m_h.ts` → `ingest_managers.py` | `scheme_manager` | model feature | ~yearly |

So the **daily `.bat` fetches only NAVs** — that's all marking needs. AUM, TER and
Morningstar are **not** pulled daily (they don't change daily and marking doesn't use
them). They only matter for the model, which is used at the annual rebalance and retrain.

### When do we retrain? (once a year)
The model can only learn from a cohort whose **3-year forward label has closed**. The
latest trained cohort is 2022 (its window closed Dec-2025). The next one, **2023,
unlocks only when monthly NAVs reach 2026-12-31** — i.e. around **January 2027**. After
that it's one new cohort every January. So retraining is a genuine once-a-year event,
and every daily run and `report.py` prints a **DATA / RETRAIN STATUS** panel telling you:
- how stale each model input is vs the latest NAV, and
- whether a retrain is due yet (and the exact date the next cohort unlocks).

### Doing the yearly maintenance (one command)
```powershell
# just check status (non-destructive):
python annual_maintenance.py

# pull fresh data (NAV+TER+AUM via daily_updater, rebuild plan_nav_monthly, re-ingest managers):
python annual_maintenance.py --refresh-data

# rebuild ml_dataset.csv with the newly-unlocked cohort + retrain model_live.pkl:
python annual_maintenance.py --retrain

# do both:
python annual_maintenance.py --refresh-data --retrain
```

> **Morningstar is not auto-scraped.** `ingest_managers.py` rebuilds `scheme_manager`
> from the `morningstar_clean/*.csv` files produced by `m_h.ts`. Manager *tenure*
> advances automatically as the as-of date moves, so you only need to re-run `m_h.ts`
> (which needs live Morningstar auth headers) once a year to catch manager **changes**
> before running `--refresh-data`.

---

## Interpreting the result

`report.py` prints the **live edge** = strategy total − benchmark total. This is the
honest out-of-sample test: the research edge is **relative** (vs same-category funds),
concentrated in high-dispersion sleeves (small/mid-cap), and **modest** — expect it to
show up over quarters, not days, and to be noisy on any single week. See
`../FINDINGS.md` for the full validated claim this is testing.
