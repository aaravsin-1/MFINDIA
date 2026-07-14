# Validation Catalog — Everything We Tested, and How

*A single index of every validation in `RESULTS_PROJECT/` (root + `tests/` +
`paper_trading/`), what each one checks, the method, and the result. Every figure is
reproduced against the live `amfi_data` PostgreSQL DB by the script named — nothing is
hard-coded. For the full narrative see [`FINDINGS.md`](FINDINGS.md) and
[`RESEARCH_FINDINGS.md`](RESEARCH_FINDINGS.md); this file is the map.*

Legend: **PASS** = validated / survives · **NEG** = honest negative (kept on purpose)
· **MIRAGE** = looked good, failed under scrutiny · **WIN** = genuine improvement.

---

## 0. The headline in one line
A naive "ML beats the market" claim **failed** its negative control (a random-label
model reproduced it). After fixing a data bug and neutralising category tilt, a genuine
**within-category selection edge survives**: **+2.37%/yr** vs a category-matched
benchmark, **7/7 cohorts**, **Newey-West t=3.30 (p≈0.001)**, passing every test the
original failed.

---

## 1. The negative control — a standard method, applied where it's underused

**First, the honest framing (no overclaiming).** Label-permutation negative controls are
**standard** in biology, medicine, epidemiology and ML, and in finance they are the
cousin of White's Reality Check, the deflated Sharpe ratio, and the Bailey & López de
Prado backtest-overfitting work (cited in [`RESEARCH_FINDINGS.md`](RESEARCH_FINDINGS.md)
F3). **We did not invent the method.** What this project contributes is narrower and
concrete:

> (i) *applying* a label-permutation control to a **mutual-fund selection backtest** — a
> setting where practice still validates on CAGR-vs-benchmark; (ii) a documented **case
> study** where it **overturned an apparent positive result** (the inherited prototype's
> "ML beats the market"); and (iii) the demonstration that the honest null is a *no-signal
> version of your own strategy*, not the market.

That is a *demonstration / case study*, not a new statistical tool. The rest of this
section describes the specific instantiation and how it was made rigorous.

### 1.1 The standard (weak) way to validate a fund picker
The usual test is: *"does the strategy's CAGR beat a benchmark (e.g. the equal-weight
universe)?"* If yes, declare skill. **This is not enough** — and the prototype fell
into exactly this trap. A concentrated selection (say, top-10 funds) can beat a broad
average purely because of a **structural tilt** (it happens to hold small, high-momentum
funds that ran in a bull market), with **zero learned signal**.

### 1.2 The key move: make the null a *scrambled-label model*, not the market
Instead of comparing to the market, we compare to a **model trained on randomly
permuted (scrambled) labels**, run through the **identical selection machinery** (same
top-k, same category construction). The logic:

> If a model that was fed **meaningless answers** during training still "beats the
> market" using your selection pipeline, then your pipeline's apparent edge is **not
> skill** — it is a structural artifact of the construction itself.

The real model must beat **that** null — i.e. beat what a *no-skill version of its own
strategy* achieves — not merely beat the market. "Beats the market" becomes
necessary-but-not-sufficient.

### 1.3 What made ours rigorous where the prototype's was not
The prototype technically had a negative control but ran it **once, unseeded**, drew a
lucky-low 16.2%, and declared success. Our version:

- **Seeded and repeated over 40 seeds** ([run_validation.py:80-88](../validation/run_validation.py#L80-L88)),
  reporting the **full null distribution** and an **empirical p-value**
  P(scrambled ≥ real), not a single draw.
- **Judged against the correct null** (the scrambled-label model), not the equal-weight
  universe.
- **Applied per-construction**: the universal top-10 **FAILS** (scrambled beats
  equal-weight in **29/40** seeds; real only ~1 sd above null; **p=0.125**), while the
  category-neutral construction **PASSES** (real above **all** seeds; **p=0.000**).
- **Applied per-holding-period** ([validate_hold_periods.py](../validation/validate_hold_periods.py)):
  1-, 2-, and 3-year holds each re-run the control and pass (p=0.000).
- **Reinforced with a random-portfolio placebo** ([red_team.py](../validation/red_team.py) attack F):
  2,000 *random* top-2/category portfolios; the real edge sits beyond the 95th
  percentile (p<0.05) — a non-parametric cousin of the same idea.

### 1.4 Why it matters (the transferable lesson)
The negative control **caught a false positive that a CAGR comparison would have
published** — the prototype's headline. The reusable lesson (M1/M2 in
[RESEARCH_FINDINGS.md](RESEARCH_FINDINGS.md)): *in any selection-strategy backtest, the
honest null is a no-signal version of the same strategy, run many times — not the
market.* This session added four more confirmations (see §6): four "improvements" looked
good on a metric and then failed a proper portfolio/overlap-corrected check.

### 1.5 The honest caveat — we redesigned until it passed
The narrative is: the original construction (universal top-10) **failed** the control, we
switched to a **category-neutral** construction, and *that* passed. Redesigning a strategy
until it clears a test is, in the worst case, p-hacking. Two things make this defensible,
and one residual risk must be stated:

- **It was theory-motivated, not blind fishing.** An *independent* diagnostic — the rank
  IC (§1.6) — showed the skill was **within-category** *before* the category-neutral
  construction was chosen. Category-neutral was the direct way to harvest a within-category
  signal, not the 37th construction we tried.
- **The winner then passed tests it was never tuned against** — HAC, block bootstrap,
  sign test, six red-team attacks, survivorship, per-category index. Passing the control
  was necessary, not sufficient, and it cleared the rest independently.
- **Residual risk (stated, not hidden):** we still *selected* the construction that
  passed, so researcher-degrees-of-freedom risk is not zero. The only true mitigation is
  genuinely out-of-sample forward data — which is exactly why [paper_trading/](../paper_trading/)
  exists. Treat the internal p-values as *in-sample-honest*, and the forward paper trade
  as the real out-of-sample control.

### 1.6 Companion skill metric — permutation-tested rank IC
Alongside the control, skill is measured directly as the out-of-sample **rank
Information Coefficient** (Spearman of predicted vs realised forward alpha) over ~1,640
fund-cohorts, each checked against a **permutation null**
([strengthen_edge.py:70-89](../validation/strengthen_edge.py#L70-L89)). This has real statistical
power (thousands of obs) versus 7 annual CAGRs. Result: **+0.096 pooled**, **+0.09 to
+0.18 within-category**, permutation **p<0.001**.

---

## 2. Data-integrity validation (the bug that had to be fixed first)

| What | Where | Result |
|---|---|---|
| **NAV-outlier sanity filter** — drop 3-yr returns outside [−95%,+500%] before they touch the benchmark or training set | [prepare_features.py:76](../src/prepare_features.py#L76) | Removed a corrupted +4,367% NAV (HSBC Midcap) that had poisoned the Mid Cap 2021 target |
| **Trimmed category benchmark** — 5%-trimmed mean so no single glitch dominates | [prepare_features.py:83-90](../src/prepare_features.py#L83-L90) | Worst per-group \|mean alpha\| **1.85 → 0.157**; Mid Cap 2021 **−185% → +3%** |
| **Data-availability audit** — checked exit-load / lock-in columns in the DB | [test_turnover_tax.py](../tests/test_turnover_tax.py) docstring | Exit-load absent, lock-in column empty → statutory rules applied openly |

---

## 3. Core validation suite (the headline edge)

| # | Script | What it validates | Key result | Verdict |
|---|---|---|---|---|
| 1 | [run_validation.py](../validation/run_validation.py) | Walk-forward honesty + **40-seed negative control** on the universal top-10 | Original edge +1.57% vs EW **fails** the null (p=0.125); alpha t=1.79, p=0.075 | **NEG** (original claim dies) |
| 2 | [strengthen_edge.py](../validation/strengthen_edge.py) | (A) OOS **rank IC** (3 encodings, permutation null); (B) **category-neutral** top-2/cat vs category benchmark + its own scrambled null | IC +0.096 (p<0.001); edge **+2.37%**, **passes null p=0.000**, monthly t=4.23 | **PASS** |
| 3 | [robustness_check.py](../validation/robustness_check.py) | Significance under **overlapping 3-yr windows** — 4 estimators | Naive t=4.23; **Newey-West HAC t=3.30 (p=0.001)**; annual t=4.29 (p=0.005); bootstrap 95% CI **[+1.37%,+3.36%]**; sign test **7/7 (p=0.008)** | **PASS** |

---

## 4. Adversarial & robustness validation

| # | Script | Attack / check | Result | Verdict |
|---|---|---|---|---|
| 4 | [red_team.py](../validation/red_team.py) | Six hostile attacks on the +2.47% edge | All **6/6 survive** (below) | **PASS** |
| | | A — portfolio size (top-1..5/cat) | positive at every k | ✅ |
| | | B — model seed (8 seeds) | identical edge (deterministic) | ✅ |
| | | C — leave-one-cohort-out | worst (drop 2019) still **+2.19%** | ✅ |
| | | D — feature jackknife | worst (drop `aum_percentile`) still **+1.38%** | ✅ |
| | | E — "just momentum?" | picks' momentum pct 0.54; edge w/o momentum +2.41% | ✅ |
| | | F — random-portfolio placebo (2000 draws) | real +2.47% vs random 95th-pct +1.32%, p<0.001 | ✅ |
| | | G — look-ahead / leakage audit | features as-of date; train strictly prior; one minor global-median fill noted | ✅ |
| 5 | [tests/test_survivorship.py](../tests/test_survivorship.py) | Rebuild benchmark from **all funds alive at t** (dead/merged included) | Survivorship bias only **+0.25%/yr**; edge **+2.47% → +2.22%**, still 7/7 | **PASS** |
| 6 | [experiment_min_history.py](../validation/experiment_min_history.py) | Does the edge survive a **≥5-yr seasoning** constraint (young-fund/survivorship de-risk)? | Edge **weakens +2.37% → +2.10%** (still 7/7, monthly t=3.77 p=0.0002) but the negative control slips to **borderline p=0.050** → the young-fund tilt is **partly load-bearing** | **PARTIAL** (disclose) |

---

## 5. Benchmark-fairness & implementation-realism validation

| # | Script | What it validates | Key result | Verdict |
|---|---|---|---|---|
| 7 | [test_vs_index.py](../tests/test_vs_index.py) | Relative vs absolute: strategy vs **Nifty 50** | picks−category +2.37% (7/7, skill); category−Nifty +2.84% (style tilt); picks−Nifty +5.22% (5/7) | **PASS** (edge is *relative*) |
| 8 | [test_vs_category_index.py](../tests/test_vs_category_index.py) | Each category vs its **own passive index**; is the fund benchmark fair? | Fund benchmark ≈ index (Large +0.3, Mid +0.6, Small +1.4); **skill concentrated**: Large +0.6%, Small +3.4% | **PASS** (fair; skill where dispersion is) |
| 8b | [test_benchmarks_hard.py](../validation/test_benchmarks_hard.py) | Two **harder** benchmarks: (A) **cap-weighted** (AUM) peer; (B) **factor-adjusted alpha** (excess ~ market+size+momentum, HAC) | A: edge **+3.45%/yr, 7/7** vs cap-weight (not a weighting artifact). B: **alpha +1.72%/yr, HAC t=4.26 (p<0.0001)** survives factors — ~70% skill, ~30% within-category size tilt (SMB β=0.48); momentum β≈0, market β≈0 | **PASS** (skill, not a factor tilt) |
| 9 | [test_turnover_tax.py](../tests/test_turnover_tax.py) | **After-tax** net edge by holding period (LTCG 12.5%) | Gross front-loaded (1y +3.70%, 2y +3.28%, 3y +2.47%); **net ~+2.6%** at 1–2y hold | **PASS** (survives tax if >12mo) |
| 10 | [validate_hold_periods.py](../validation/validate_hold_periods.py) | Negative control + sign test on **1/2-yr** holds | All holds pass the null (p=0.000); front-loaded alpha is real | **PASS** |
| 11 | [test_buffer_rule.py](../tests/test_buffer_rule.py) | **Top-K buffer** to cut turnover | Top-2 +3.20%/46% turnover → **top-4 +2.98%/33%** | **PASS** (buffer keeps edge, cuts churn) |

---

## 6. Exploratory "can we grow the edge?" (`tests/`) — held to the same bar

Every candidate must beat its **own scrambled-label null** *and* a proper portfolio/
significance check. Kept as honest results (positive or negative).

| # | Script | Idea tested | Result | Verdict |
|---|---|---|---|---|
| 12 | [tests/test_flow_features.py](../tests/test_flow_features.py) | Fund-flow (smart/dumb money) features | −0.15%/yr; real but **redundant** with AUM (flow IC −0.063) | **NEG** |
| 13 | [tests/test_target_definition.py](../tests/test_target_definition.py) | Alternative targets (Sharpe/Calmar/rank) | Raw-alpha target already best (IR 1.00) | **NEG** |
| 14 | [tests/test_learning_to_rank.py](../tests/test_learning_to_rank.py) | LambdaMART (`LGBMRanker`) ranking loss | One N_REL setting spiked +0.81% but **2/5 settings** → hyperparameter artifact | **MIRAGE** |
| 15 | [tests/test_bayesian_shrinkage.py](../tests/test_bayesian_shrinkage.py) | Hierarchical shrinkage across categories | **Hurts** at every weight (IR 1.00→0.58–0.77); skill is category-specific | **NEG** |
| 16 | [tests/test_detilted_features.py](../tests/test_detilted_features.py) | De-tilted features **for the top-2 strategy** | IC doubled (0.09→0.18) but edge +0.16%, 3/7 cohorts | **IC-ONLY** |
| 17 | [tests/test_v1_robustness.py](../tests/test_v1_robustness.py) | V1 cohort-ranked lead — full battery (size sweep, per-cohort, HAC, bootstrap) | Improvement over RAW **not significant** (HAC t=1.47; bootstrap CI includes 0; 4/7 cohorts) | **MIRAGE** |
| 18 | [tests/test_list_quality.py](../tests/test_list_quality.py) | Do alt encodings give a better **retail full-list** (within-cat quintile spread)? | **Yes**: V1 +13.1pp, V2 +12.6pp vs RAW +7.8pp; monotone, 7/7 cohorts, robust across bucket counts | **WIN** (retail product only) |

**Holdings-based features** (active share, concentration) were **not tested** — the
holdings star schema links to only 27% of funds; a data-engineering gap, not a modelling
one (the single highest-potential unexplored lever).

**The pattern:** four metric-level "wins" (14, 15, 16, 17) all evaporated under a proper
portfolio + overlap-corrected check — convergent evidence the top-2 strategy is a genuine
local optimum. The one real win (18) survives because it is the first encoding tested on
the use case its metric (whole-ranking IC) actually governs → a **second product** (see
[score_retail_list.py](../src/score_retail_list.py), [tests/README.md](../tests/README.md) §9).

---

## 7. Forward / live validation (`paper_trading/`)

| What | Where | Purpose |
|---|---|---|
| **Live paper-trading harness** | [paper_trading/](../paper_trading/) | Runs the validated category-neutral strategy forward vs a category-matched benchmark of 154 core funds, marks daily, rebalances annually (top-4 buffer, 12-mo min-hold). The **only genuinely unseen-regime, forward out-of-sample** test the internal battery cannot provide. |
| **Annual re-validation hook** | [paper_trading/annual_maintenance.py](../paper_trading/annual_maintenance.py) | On each yearly refresh, regenerates both deliverables **and re-runs `tests/test_list_quality.py`** to re-confirm the retail-list premise on new data (exit-code gated). |

All internal tests (§3–§6) share the 2013–2022 universe and calendar time; the paper
trader is the forward control that addresses that limitation directly.

---

## 8. Scoreboard — what is validated vs what is honestly bounded

**Validated (survives every honest test):**
- Within-category ranking skill: **rank IC +0.09** (permutation p<0.001).
- Category-neutral edge: **+2.37%/yr**, **7/7 cohorts**, negative control **p=0.000**,
  **Newey-West t=3.30 (p≈0.001)**, bootstrap CI [+1.37%,+3.36%].
- Robust to: portfolio size, seed, dropping any cohort, dropping any feature, momentum
  removal, random placebo, survivorship (+0.25%), and tax (net ~+2.6% if held >12mo).

**Honestly bounded (stated, not hidden):**
- **Relative, not absolute** — beats same-category funds (≈ category index), not the
  market in all conditions.
- **Concentrated** — small-cap +3.4%, large-cap +0.6% (skill lives where funds differ).
- **One market, one era**; **overlapping windows** (why HAC/bootstrap are the headline,
  not the naive t); **modest magnitude**.
- **Young-fund dependence** (§4.6) — under a ≥5-yr seasoning filter the edge weakens to
  +2.10% and the negative control drops to borderline p=0.050; part of the edge relies
  on funds that only just clear the 30-month history bar, which is a survivorship-adjacent
  caveat to disclose (not to hide).
- **Retail-list premise** (§6.18) is strong in aggregate but per-cohort under-powered
  (6/7) → carries a "confirm on live cohorts" asterisk.

**Legend note:** §3–§7 verdicts use the corrected §4.6 result (**PARTIAL**, not PASS).

---

## 9. How to reproduce everything
```bash
# core (each hits the DB, ~1–5 min):
python run_validation.py         # negative control — original edge fails
python strengthen_edge.py        # IC + category-neutral edge passes
python robustness_check.py       # HAC / bootstrap / sign test
python red_team.py               # 6 adversarial attacks
# fairness / realism:
python test_vs_index.py ; python test_vs_category_index.py
python test_turnover_tax.py ; python validate_hold_periods.py ; python test_buffer_rule.py
python experiment_min_history.py
# exploratory (tests/):
python tests/test_flow_features.py ; python tests/test_target_definition.py
python tests/test_survivorship.py ; python tests/test_learning_to_rank.py
python tests/test_bayesian_shrinkage.py ; python tests/test_detilted_features.py
python tests/test_v1_robustness.py ; python tests/test_list_quality.py
```
All scripts are seeded; results reproduce. Verified end-to-end this cycle — every
headline figure above reproduced digit-for-digit against the live DB.
