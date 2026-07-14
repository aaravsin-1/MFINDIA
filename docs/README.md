# RESULTS_PROJECT — Corrected Indian Mutual-Fund Selection Engine

A cleaned, honestly-validated rebuild of `../z_FINAL_train`. It fixes a
target-poisoning data bug, replaces an unreliable negative control with a proper
seeded one, and — per the brief — legitimately identifies where a *real* edge
survives: **within-category manager selection, deployed category-neutral.**

For the full before/after evidence read **[`FINDINGS.md`](FINDINGS.md)**. This
README is the operating manual: what each file is, what it does, and how to run it.

---

## TL;DR

- ❌ The original "top-10 beats equal-weight" edge **fails its own negative
  control** — a model trained on *random* labels reproduces it (empirical p=0.125,
  monthly alpha p=0.075). It was a small-AUM + momentum selection tilt, not signal.
- ✅ There **is** genuine within-category ranking skill: out-of-sample rank
  **IC ≈ +0.09** (permutation p<0.001).
- ✅ A **category-neutral portfolio (top-2 per core category)** turns that skill
  into a defensible edge: **+2.37%** vs a category-matched benchmark, **7/7**
  cohorts positive, **passes the negative control (p=0.000)**, and the alpha stays
  significant after correcting for overlapping windows (**Newey-West t=3.30,
  p=0.001**; sign test 7/7, p=0.008).

---

## Requirements

- **Python 3.12** with: `pandas numpy lightgbm shap scikit-learn scipy sqlalchemy psycopg2 joblib python-dotenv`
- **PostgreSQL** `amfi_data` database reachable via `./.env` (RESULTS_PROJECT/.env)
  (keys: `DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME`; the website ETL also
  reads `SUPABASE_*` from the same file).
- The four validation/screening scripts query the DB live for NAV series; the
  ML/analysis reads the local `ml_dataset.csv`.

---

## The main files

### Code
| File | What it is | What it does |
|---|---|---|
| **`lib.py`** | Shared helpers (single source of truth) | DB engine, monthly-return queries, a fast returns-matrix, CAGR / info-ratio / excess-return math. Everything else imports this so the logic can't drift (the original copy-pasted it into 8 files). |
| **`prepare_features.py`** | Feature/target builder | Pulls returns, volatility, drawdown, hit-rate, AUM percentile, TER and manager tenure per cohort and writes `ml_dataset.csv`. **Contains the core data-bug fix**: NAV-sanity filter (drops 3-yr returns outside [−95%, +500%]) + a 5%-trimmed category benchmark so one corrupted NAV can't poison the `fwd_alpha` target. |
| **`train_model.py`** | Model trainer | Fits the LightGBM ranking model on cohorts **< 2022** (so the 2022 snapshot stays genuinely out-of-sample) and saves `model.pkl`. |
| **`run_validation.py`** | Honest validation harness | Walk-forward 2016–2022. Reports real vs equal-weight CAGR, a **40-seed** negative control judged against the **correct null** (scrambled-label model), the monthly-alpha t-test, turnover, and feature stability. This is where the original edge is shown to fail. |
| **`strengthen_edge.py`** | Edge-recovery experiments | (A) Out-of-sample **rank IC** (Spearman pred vs realised alpha) for raw / cohort-ranked / category-ranked features, each vs a permutation null. (B) **Category-neutral construction** (top-2 per core category) vs a category-matched benchmark and its own scrambled null. This is where the real edge is found. |
| **`robustness_check.py`** | Significance stress-test | Re-tests the category-neutral edge under overlapping-window corrections: naive t, **Newey-West HAC**, non-overlapping annual t, cohort **block bootstrap**, and a **sign test**. |
| **`red_team.py`** | Adversarial audit | Actively tries to disprove the edge: size robustness, seed sensitivity, leave-one-cohort-out, feature jackknife, "just momentum?", random-portfolio placebo, leakage audit. |
| **`test_vs_index.py`** | Relative-vs-absolute check | Compares the strategy to the **Nifty 50 market index**, decomposing the gap into selection skill vs a size/style tilt. |
| **`test_vs_category_index.py`** | Per-category fairness check | Tests each category's picks vs its **own** passive index (Nifty 50 / Midcap 150 / Smallcap 250); shows the fund benchmark tracks the index and that skill concentrates in high-dispersion categories. |
| **`test_turnover_tax.py`** | After-tax realism | Models LTCG (12.5%) + turnover across 1/2/3-year holds → **net** edge; shows the alpha is front-loaded and holding >12 months is essential. |
| **`validate_hold_periods.py`** | Short-hold validation | Runs the negative control + sign test on the 1- and 2-year holds (confirms the front-loaded edge is real, not noise). |
| **`test_buffer_rule.py`** | Turnover reduction | Simulates a "hold until out of top-K" buffer; a top-4 buffer cuts turnover ~46%→33% while keeping the edge. |
| **`manager_quality_screener.py`** | The deliverable (validation snapshot) | Scores the **2022** universe (**275 funds** — the last cohort whose 3-yr outcome can be graded) → 2D **Quality × Risk** matrix. Quality = *within-category* percentile; adds a `Recommended` flag (the validated top-2/category strategy); SHAP "Why" reasons; **no rank ties**. Writes `fund_screener_results.csv`. |
| **`prepare_features_live.py`** + **`score_live.py`** | The deliverable (live snapshot) | Feature-only path (no forward label) that scores the latest complete year-end. The 2025 run covers **381 funds** — larger than 2022's 275 because the industry grew and more funds now clear the 30-month history filter. Writes `fund_screener_results_<year>.csv`. See "Live scoring" below. |
| **`score_retail_list.py`** | The deliverable (retail list) | The **second product**: a full "rate every fund" within-category list (vs the concentrated top-2 STRATEGY list). Scored with the **de-tilted (V2) model** that gives a wider within-category quintile spread (~+13pp vs ~+8pp; see `tests/test_list_quality.py` / tests README §9). Groups funds into within-category **tiers** (not a precise 1-N rank — fund-level order is noisy), keeps the Risk band + holding period, and flags which funds are also strategy top-2 picks. Writes `retail_fund_list_<year>.csv`. |

### Data / artifacts (regenerated by the scripts)
| File | What it is |
|---|---|
| `ml_dataset.csv` | Cleaned feature+target table, 1,841 fund-cohorts (2013–2022, ~195→275 funds/cohort). Output of `prepare_features.py`. |
| `model.pkl` | Trained LightGBM model, cohorts <2022 (validation). Output of `train_model.py`. |
| `model_live.pkl` | Production model trained on ALL labeled cohorts (2013–2022). Output of `score_live.py`. |
| `fund_screener_results.csv` | Ranked **2022** universe (275 funds) — validation snapshot. Output of `manager_quality_screener.py`. |
| `fund_screener_results_2025.csv` | Ranked **2025** universe (381 funds) — current live deliverable (STRATEGY view). Output of `score_live.py`. |
| `retail_fund_list_2025.csv` | **2025** retail list (381 funds) — within-category tiers + risk overlay, de-tilted model. Output of `score_retail_list.py`. |
| `paper_trading/` | Live paper-trading system that runs the strategy forward vs a category benchmark. See `paper_trading/README.md`. |

### Docs
| File | What it is |
|---|---|
| `RESEARCH_FINDINGS.md` | **The consolidated research record** — all 12 empirical findings, methodology contributions, negative results, methods rationale, limitations, and paper framing. |
| `MANAGER_REPORT.md` | **Formal project report** — audit, correction, validated findings, limitations, and recommendation, for management. |
| `EXPLAINER.md` | **Start here for the plain-English version** — the 60-second pitch, what the final list means, and the Q&A people will ask. No jargon. |
| `tests/` | Exploratory attempts to *grow* the edge with new data (fund flows, holdings). See `tests/README.md` — flows tested (no gain; confirms a "dumb-money" effect already captured by AUM); holdings blocked by a data-linkage gap. |
| `FINDINGS.md` | Full validation report: the bugs, what reproduced, the fixes, and the surviving edge with all numbers. |
| `executive_summary.md` | One-page stakeholder pitch (corrected). |
| `research_journey.md` | The honest research narrative from failed heuristics → corrected edge. |
| `walkthrough.md` | How the screener + recommended portfolio is used, plus the validation suite. |

---

## How `ml_dataset.csv` is built

Built entirely by `prepare_features.py` querying the PostgreSQL `amfi_data` DB live,
one row per **fund × year-end cohort** (`t` = Dec-31 of 2013–2022), **1,841 rows**.
The file is fully regenerable — never hand-edited.

**Universe — active-equity Direct-Growth plans only.** Three filters, applied inside
every query, define which share class enters the data:

| Filter | SQL | Why |
|---|---|---|
| Direct plan | `sp.plan_type = 'direct'` | Regular plans bleed ~1%/yr to distributor commissions — Direct is the clean return stream. |
| Growth option | `sp.option_type = 'growth'` | Excludes Dividend/IDCW share classes whose payouts distort the NAV series. |
| Equity asset class | `c.asset_class = 'Equity'` | Excludes debt, hybrid, and passive/index funds — this is *active equity* selection. |

Plus a **≥30-month history gate** (`HAVING COUNT(months) >= 30`) and a **NAV-sanity
band** (drop any 3-yr return outside `[−95%, +500%]`) before anything is computed.

**Source tables (7):**

| Table | Supplies | Key columns |
|---|---|---|
| `plan_nav_monthly` | returns, volatility, drawdown, hit-rate, fwd/hist targets | `nav`, `month_end`, `scheme_plan_id` |
| `scheme_plan` | Direct-Growth filter; plan→scheme link | `scheme_id`, `plan_type`, `option_type` |
| `scheme` | fund name, category link | `name`, `category_id` |
| `category` | category name + Equity filter | `name`, `asset_class` |
| `scheme_manager` | manager tenure & team size | `manager_id`, `start_date`, `end_date`, `is_current` |
| `v_scheme_aum` (view) | fund size → `aum_percentile` | `period_end`, `avg_aum_lakh` |
| `ter` | expense ratio | `as_of_date`, `dir_total_ter` |

**Per-cohort pipeline** (four SQL pulls → merge):
1. **Forward target** ([`prepare_features.py:50-93`](../src/prepare_features.py#L50)) — `fwd_return = nav(t+3)/nav(t)−1`; category benchmark is a **5%-trimmed mean** on sanity-filtered returns; `fwd_alpha = fwd_return − benchmark` (the label).
2. **Historical features** ([`:96-125`](../src/prepare_features.py#L96)) — trailing 3-yr window `t-3→t`: `hist_return`, `hist_volatility`, `hist_hit_rate`, `max_drawdown`.
3. **Manager** ([`:128-138`](../src/prepare_features.py#L128)) — `max_tenure_years`, `num_managers`, `is_team`.
4. **Size & cost** ([`:141-153`](../src/prepare_features.py#L141)) — `aum_percentile` (within-cohort rank), `ter` (latest snapshot ≤ t).
5. **Merge & fill** ([`:155-185`](../src/prepare_features.py#L155)) — target ⋈ history (inner), then manager/AUM/TER (left); tenure/managers→0, remaining gaps→column median.

**Coverage caveats (documented, low-impact):** 2013–2014 have only 2 rows each
(India's Direct plans launched Jan 2013 — nothing had 30 months of history yet), so
effective data starts **2015** and validation at **2016**; `ter` is a median-filled
constant before 2018 (DB coverage starts 2018); AUM/TER use a global-median fill —
a mild look-ahead on those two columns only. See `FINDINGS.md` §4A.

---

## How to run

Run in this order from inside `RESULTS_PROJECT/` (each step depends on the previous
artifact; steps 3–6 are independent analyses you can run in any order once the
dataset + model exist):

```bash
# 1. Rebuild the corrected dataset from the DB  (writes ml_dataset.csv)
python prepare_features.py

# 2. Train the model                            (writes model.pkl)
python train_model.py

# 3. Honest validation — shows the original edge fails its own null
python run_validation.py

# 4. Edge recovery — rank IC + category-neutral construction
python strengthen_edge.py

# 5. Significance stress-test of the surviving edge
python robustness_check.py

# 6. Produce the deliverable screener            (writes fund_screener_results.csv)
python manager_quality_screener.py

# Optional — benchmark-fairness checks (relative vs absolute / market index)
python test_vs_index.py            # strategy vs Nifty 50 (skill vs style tilt)
python test_vs_category_index.py   # each category vs its own passive index

# Optional — after-tax realism, turnover, and holding-period design
python test_turnover_tax.py        # LTCG + turnover -> net edge by holding period
python validate_hold_periods.py    # negative control on 1/2/3-year holds
python test_buffer_rule.py         # top-K buffer to cut turnover
```

Runtime: steps 1, 3, 4, 5 hit the DB and take ~1–5 min each; steps 2 and 6 are
seconds. Everything is seeded, so results reproduce.

---

## Maintaining it going forward
To score a new year, keep four data streams current in the DB — monthly NAVs
(returns / drawdown / volatility / hit-rate), manager metadata (tenure / team
size, **reset tenure to 0 when a manager leaves**), monthly AUM (percentile), and
TER — then re-run `prepare_features.py → train_model.py → manager_quality_screener.py`.
Deploy the **`Recommended`** (category-neutral) set, not a global top-N, because
that is the only construction that survived validation.

## Live scoring — a current list for today's investors
`manager_quality_screener.py` scores the **2022** snapshot on purpose: 2022 is the
newest cohort whose 3-year outcome is already known, so it can be *graded*. That
makes it the right **validation** snapshot but the wrong thing to hand a new
investor. To make a pick you only need features as-of today — the forward window
is needed to grade a pick, not to make one.

`prepare_features_live.py` + `score_live.py` provide that live path:
```bash
python score_live.py         # auto-detects the latest complete Dec year-end in the DB
python score_live.py 2025    # or force an as-of year
```
It (1) retrains a production model on **all** labeled cohorts (2013–2022, vs
`train_model.py` which holds out 2022 for validation), (2) builds a feature-only
snapshot via `prepare_features_live.build_features` (identical feature SQL to
`prepare_features.py`, minus the forward-label inner join), and (3) applies the
exact screener logic, writing `fund_screener_results_<year>.csv`.

`fund_screener_results_2025.csv` is the current deliverable: an as-of **2025-12-31**
list of **381 funds** (DB NAVs run to 2026-06-30) for an investor buying now and holding
~3 years. That is up from **275** in the 2022 validation snapshot — not a methodology
change, just industry growth: ~106 more funds launched by 2022→2025 that now have the
30 months of history the pipeline requires. The core-category benchmark basket the paper
trader holds is 154 of those funds.
Same rule applies — deploy the 10 `Recommended` funds filtered to the investor's
risk band, not a global top-N. Note this live list is **not yet gradable** (its
2028 outcome hasn't happened); it inherits the validated method, not a fresh
out-of-sample proof.

---

## One-line summary of every change vs. the original
- **Data**: dropped a +4,367% corrupted NAV poisoning the Mid Cap 2021 target; category benchmark is now 5%-trimmed.
- **Validation**: negative control is seeded, run 40×, and judged against the correct (scrambled-label) null instead of one lucky draw.
- **Edge**: category-neutral construction replaces universal top-10 — the only version that passes the negative control; significance re-verified under Newey-West / bootstrap.
- **Screener**: within-category Quality, diversified `Recommended` set, zero rank ties.
