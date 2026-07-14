# Project Report — ML Fund-Selection Engine (Indian Active Equity)

**Prepared for:** Reporting Manager
**Scope:** `RESULTS_PROJECT/` — the corrected, validated rebuild of the `z_FINAL_train` prototype
**Status:** Complete — a modest but statistically robust edge validated; two deliverables shipped; live forward test running
**Data basis:** ~250 funds/yr, cohorts 2013–2022; live snapshot 2025; all figures reproduced against the `amfi_data` database

---

## 1. Executive summary (bottom line up front)

We built and **honestly validated** a machine-learning engine that ranks Indian active-equity
funds *within their category*. Deployed as a category-neutral portfolio (top-2 funds per
category), it beats a like-for-like benchmark by:

- **+2.4% / year, positive in all 7 back-test years** (2016–2022);
- statistically significant after strict corrections (**Newey-West t = 3.30, p ≈ 0.001**);
- of which **+1.7%/yr is irreducible skill** after adjusting for size/momentum factors.

Critically, the **prototype's original "beats the market" claim did not hold up** — it failed a
standard negative-control test and rested on a corrupted data record. After fixing both, the
narrower edge above is what survives every test we ran.

**Recommendation:** adopt as a **decision-support fund-selection tool**, deployed category-neutral.
Do **not** market it as market-beating alpha. It is relative, modest, concentrated in small/mid-cap,
and still accruing forward out-of-sample evidence.

---

## 2. Objective & scope

- **Objective:** determine whether ML can select Indian equity funds that outperform their peers,
  and if so, quantify the edge honestly.
- **In scope:** active-equity Direct-Growth funds; feature engineering; model; walk-forward
  validation; a deployable screener; a live paper-trading control.
- **Out of scope (data-limited):** holdings-based features (data-linkage gap), full-cycle passive-index
  benchmarking (index-fund history too short).

---

## 3. What was built

| Component | Detail |
|---|---|
| **Universe** | Active equity, Direct-Growth plans, ≥30 months history → ~250 funds/cohort, 2013–2022 (1,841 rows) |
| **Features** | 9 per fund: 3-yr return, volatility, hit-rate, max drawdown, AUM percentile, TER, manager tenure, #managers, is-team |
| **Target** | 3-year forward **category-relative** alpha (beat your own category average) |
| **Model** | LightGBM (50 trees, depth 3) — captures feature interactions, deliberately small to resist overfitting |
| **Construction** | **Top-2 funds per core category** (Large/Mid/Small/Flexi/ELSS) → 10-fund, equal-weight, category-neutral portfolio |
| **Policy** | Re-rank yearly; hold ≥12 months (tax); sell only when a fund exits its category top-4 (buffer) → ~2-yr turnover |

---

## 4. Results — validated performance

| Metric | Result |
|---|---|
| **Edge vs category-matched benchmark** | **+2.37% / yr** |
| **Cohorts positive** | **7 / 7** (2016–2022) |
| Ranking skill (rank IC) | +0.09 pooled, up to +0.18 within-category (p < 0.001) |
| Negative control | **Passes** (real edge above all scrambled-label seeds, p = 0.000) |
| Significance (overlap-corrected) | Newey-West **t = 3.30, p = 0.001**; bootstrap 95% CI **[+1.37%, +3.36%]**; sign test 7/7 (p = 0.008) |
| **Factor-adjusted alpha** | **+1.72% / yr (t = 4.26)** — ~70% skill, ~30% within-category size tilt; momentum ≈ 0 |
| Cap-weighted-benchmark edge | +3.45% / yr, 7/7 (not a weighting artifact) |
| Where skill concentrates | Small-cap **+3.4%**, large-cap **+0.6%** |
| Survivorship-adjusted | +2.47% → **+2.22%** (dead/merged funds included) |
| After tax (hold >12 months) | ~**+2.6% net** at a 1–2 year hold |

> **Context:** the portfolio's ~20% headline CAGR is mostly the 2016–2025 bull market; the
> **benchmark did ~17.8%**. Our contribution is the **~2.4% on top**, not the 20%.

---

## 5. How it was validated (assurance)

Validation was deliberately adversarial — we tried to disprove our own result.

- **Negative control (standard method, applied here):** retrain on scrambled labels; a genuine
  model must beat that null, not just the market. The **prototype's edge failed it** (p = 0.125,
  a structural small-fund tilt); the category-neutral construction **passes** (p = 0.000).
- **Data-quality fix:** a corrupted NAV (+4,367% "3-yr return") was poisoning the training target;
  fixed with an outlier filter + trimmed benchmark (worst per-group error 1.85 → 0.157).
- **Red-team (6/6 survived):** portfolio size, model seed, leave-one-year-out, feature jackknife,
  "is it just momentum?", and a 2,000-draw random-portfolio placebo.
- **Harder benchmarks:** survives a cap-weighted peer and a market/size/momentum factor regression.
- **Forward control:** a live paper-trading account (real NAVs, daily marks) is now accumulating
  genuinely out-of-sample evidence.

*Honest caveat:* we selected the category-neutral construction *because* it passed — a residual
selection risk. It was theory-motivated (the skill diagnostic pointed to within-category first)
and passed many tests it was not tuned on, but the forward paper trade is its only true mitigation.

---

## 6. What was tested and rejected (diligence)

Five attempts to enlarge the edge were held to the same bar and **did not improve it** — evidence the
simple model is near-optimal on currently available data:

| Attempt | Outcome |
|---|---|
| Fund-flow features | No gain (redundant with the AUM feature) |
| Alternative training targets (Sharpe/Calmar) | No gain |
| Learning-to-rank model | No robust gain (single-setting artifact) |
| Hierarchical shrinkage across categories | Hurt (skill is category-specific) |
| De-tilted features (for the strategy) | Metric-only — *but* it powers the separate retail list (see §7) |

---

## 7. Deliverables

| Deliverable | What it is |
|---|---|
| **Strategy list** (`score_live.py`) | The validated 10-fund top-2/category portfolio (2025 snapshot: 381 funds ranked) |
| **Retail list** (`score_retail_list.py`) | A "rate every fund" within-category tiered list (a genuine second product; wider quintile spread than the base model) |
| **Screener** (`manager_quality_screener.py`) | 2D Quality × Risk map with plain-English SHAP reasons |
| **Paper trading** (`paper_trading/`) | Live forward test vs a category benchmark; annual rebalance + self-revalidation |
| **Maintenance** (`annual_maintenance.py`) | One-command yearly data refresh + retrain + list regeneration |

---

## 8. Limitations & risks

1. **Relative, not absolute** — beats same-category peers; does **not** protect against a falling market.
2. **Concentrated** — meaningful in small/mid-cap, near-zero in efficient large-cap.
3. **One market, one era** — Indian equity, bull-heavy 2013–2025; needs external replication.
4. **Modest magnitude** — ~2.4% gross / ~2.6% net; the >12-month hold rule is mandatory (else tax erases it).
5. **Young-fund dependence** — a ≥5-yr-history filter weakens the edge to +2.10% (borderline); part relies on young funds.
6. **Selection & forward risk** — see §5 caveat; only forward data can fully confirm it.

---

## 9. Recommendation & next steps

**Recommendation:** deploy as a **within-category decision-support screener**, category-neutral;
position it as *disciplined fund selection*, not market-beating alpha.

**Next steps (priority order):**
1. Continue the live paper trade; review **quarterly**, and add each new cohort (2023 unlocks ~Jan 2027) as a fresh out-of-sample test.
2. Close the **holdings data-linkage gap** — the highest-potential unexplored signal.
3. Acquire **index total-return series** to enable a full-cycle active-vs-passive benchmark.
4. Add full survivorship handling (censored-label rebuild) to firm up all figures.

---

## Appendix

- **Reproducibility:** every figure ↔ script — see `VALIDATION_CATALOG.md` §9 (run list). All seeded.
- **Supporting docs:** `STRATEGY_AND_RESULTS.md` (full results), `VALIDATION_CATALOG.md` (all tests indexed),
  `FINDINGS.md` (step-by-step evidence), `EXPLAINER.md` (plain-English version).
- **Note:** this report consolidates and updates the earlier `MANAGER_REPORT.md` with the current
  session's additions (factor-adjusted alpha, harder benchmarks, retail list, honesty corrections).

---

*All figures reproducible against `amfi_data`. Headline: **+2.37%/yr vs a category-matched benchmark,
7/7 cohorts, Newey-West p ≈ 0.001, +1.72%/yr factor-adjusted** — modest, relative, concentrated, and
honestly bounded.*
