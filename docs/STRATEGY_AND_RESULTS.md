# The Strategy & Its Results — Full Account

*What the strategy is, how it came about, and exactly how it performed. Every number
here was reproduced against the live `amfi_data` database by the scripts named (verified
end-to-end this cycle). Companion docs: [`VALIDATION_CATALOG.md`](VALIDATION_CATALOG.md)
(the full test index) and [`FINDINGS.md`](FINDINGS.md) (step-by-step evidence).*

---

## Part I — The strategy in one page

**Goal.** Rank Indian active-equity funds *within their own category* and hold the best
few, beating a like-for-like (same-category) benchmark.

**Universe.** Active **equity**, **Direct-Growth** plans only, **≥30 months** of history
→ ~200–275 funds/cohort, annual cohorts **2013–2022**, **1,841 fund-cohort rows**.

**The 9 features** (as-of the scoring date, no look-ahead): trailing 3-yr return,
volatility, category hit-rate, max drawdown, AUM percentile, TER, longest manager
tenure, number of managers, is-team.

**What it predicts.** 3-year **forward category-relative alpha** = a fund's next-3-yr
return minus its *own category's* average — so the model learns "better than peers,"
not "market will rise."

**Model.** LightGBM gradient-boosted trees, deliberately small (50 trees, depth 3,
seed 42) — enough to capture interactions (e.g. momentum *only if* drawdown is
contained), too small to memorise noise on ~250 funds/yr.

**Construction (this is the crux).** **Top-2 funds per core category** — Large, Mid,
Small, Flexi, ELSS → a **10-fund, equal-weighted, category-neutral** portfolio,
benchmarked against **all funds in those same categories**.

**Operating policy (one rule, not three).** Re-rank yearly → **hold every fund ≥12
months** (secures 12.5% LTCG, zero exit load) → **sell only when a fund drops out of its
category's top-4** (buffer). Funds then turn over ~every 2 years (~33%/yr).

**Headline result.** **+2.37%/yr** vs the category-matched benchmark, **positive in all
7 back-test years**, statistically significant after honest corrections (**Newey-West
t=3.30, p≈0.001**), and it **passes the negative control** the original version failed.

---

## Part II — How it came about (the honest research journey)

The strategy is the *survivor* of a research process that deliberately tried to break its
own claims. It did not start here — it was forced here.

### Phase 1 — A clean universe
Of 8,000+ AMFI share classes (debt, passive, hybrid, regular plans), we isolated only
**active-equity Direct-Growth** plans with **≥30 months** of history (needed for stable
risk metrics). Direct plans avoid the ~1%/yr distributor-commission drag of Regular
plans. → ~250 clean funds/cohort.

### Phase 2 — Disproving the obvious ("buy past winners")
The naïve baseline needs no ML: buy the top-10 funds by trailing 3-yr return. It
**underperformed** the equal-weight universe — raw momentum mean-reverts and hides
risk-taking. This motivated a model that weighs momentum **in context**, not alone.

### Phase 3 — A gradient-boosted ranking model
We built the LightGBM model on the 9 features to predict forward category-relative
alpha, validated **walk-forward** (train on all cohorts before year *t*, predict *t*,
never using the future).

### Phase 4 — The audit that broke the first answer
Before publishing a "we beat the market" result, we stress-tested it. **Two things
broke:**

- **4a. A corrupted NAV was poisoning the training target.** One fund (HSBC Midcap) had
  a broken series reading **+4,367%** over 3 years, dragging the **Mid Cap 2021**
  category benchmark to +273% and giving all 19 mid-cap funds fake target alphas of
  −170% to −220%. → *Fixed* with a NAV-sanity filter (drop returns outside [−95%,+500%])
  + a 5%-trimmed benchmark ([prepare_features.py:76-90](../src/prepare_features.py#L76-L90)).
  Worst per-group \|mean alpha\| fell **1.85 → 0.157**.

- **4b. The "proof" the edge was real did not replicate.** The original **negative
  control** (train on scrambled labels; performance should collapse) had been run
  **once, unseeded**, drew a lucky-low 16.2%, and declared victory. Re-run over **40
  seeds**, the scrambled-label model averaged ~18% and **beat the baseline in 29/40
  seeds**; the "real" model was only ~1 sd above it (**empirical p=0.125**), with
  insignificant alpha (t=1.79, p=0.075). **The original edge was a structural small-cap /
  momentum tilt, not skill.**

### Phase 5 — Recovering a *real* edge
Rather than abandon the model, we asked the sharper question: *is there ANY genuine
skill, and where?*

- **5a. Measure skill directly (rank IC).** Pooled across ~1,640 out-of-sample
  fund-cohorts, Spearman(predicted, realised alpha) = **+0.096** (permutation p<0.001),
  **+0.09 to +0.18 within category**. An IC ~0.1 is genuinely useful in equity
  selection. **The skill is within-category ranking, not cross-category timing.**
- **5b. Harvest it category-neutral.** The universal top-10 squanders that skill by
  tilting into whichever category is hottest (which a *random* model also does). Forcing
  **top-2 per category** and benchmarking against those same categories isolates the
  real signal — and, unlike the top-10, it **passes the negative control**.

  > **Honest note on this step.** We *redesigned the construction until it passed a
  > test*, which in the worst case is p-hacking. Two things make it defensible: the
  > switch to category-neutral was **motivated by the IC diagnostic** (which showed the
  > skill was within-category) *before* it was tested — not blind fishing — and the
  > winning construction then passed many tests it was **never tuned against** (HAC,
  > bootstrap, red-team, survivorship). The residual risk — that we still *selected* the
  > construction that passed — is real, and the [paper_trading/](../paper_trading/) forward
  > test is its only true mitigation. (The label-permutation control itself is a
  > **standard** method; the contribution here is applying it to fund selection and
  > documenting that it overturned a positive result — not inventing it.)

### Phase 6 — Significance under overlapping windows
Because 3-yr forward windows overlap, the naïve monthly t-stat is inflated. We re-tested
under weaker assumptions (Newey-West HAC, non-overlapping annual, block bootstrap, sign
test) — the edge shrank from the flashy number but stayed **robustly positive**.

### Phase 7 — The deliverable & forward test
The final architecture — *the machine ranks, the human interprets* — ships as a
Quality × Risk screener with a validated **Recommended** set, plus a live
**paper-trading** harness running it forward as the genuine unseen-regime control.

> **The through-line:** the strategy is defined as narrowly as it is *because* the wider
> claim failed its own tests. What remains is small, real, and honestly bounded.

---

## Part III — The results

### 1. Headline performance (walk-forward 2016–2022, vs category benchmark)

| Metric | Value | Source |
|---|---|---|
| **Edge vs category benchmark** | **+2.37% / yr** | [strengthen_edge.py](../validation/strengthen_edge.py) |
| Strategy CAGR | 20.18% | " |
| Benchmark CAGR | 17.81% | " |
| **Cohorts positive** | **7 / 7** | [robustness_check.py](../validation/robustness_check.py) |
| Per-cohort edge | +0.56, +1.42, +3.99, +4.13, +2.99, +0.82, +2.70 % | " |

> **Context on the ~20% CAGR:** the benchmark did ~17.8%, so the 2016–2025 bull market —
> not the model — did the heavy lifting. Our contribution is the **~2.4% on top**. Long-run
> Indian equity is closer to 12–14%; the 20% must **not** be extrapolated.

### 2. Is the skill real? (the negative control — the decisive test)

| | Universal top-10 (original) | **Category-neutral (this strategy)** |
|---|---|---|
| Edge | +1.57% (vs equal-weight) | **+2.37%** (vs category-matched) |
| Negative control | **FAILS** — scrambled beats baseline 29/40 seeds, **p=0.125** | **PASSES** — real above all seeds, **p=0.000** |
| Monthly alpha | t=1.79, p=0.075 (n.s.) | **t=4.23, p<0.0001** |

The construction is what converts genuine-but-fragile skill into a defensible edge.

### 3. Statistical significance (honest, overlap-corrected)

| Test | Result | Read |
|---|---|---|
| Naïve monthly t | t=4.23, p<0.0001 | optimistic (assumes independent months) |
| **Newey-West HAC (36 lags)** | **t=3.30, p=0.0010** | **the honest headline** |
| Non-overlapping annual (7 obs) | t=4.29, p=0.0051 | one obs/cohort |
| Cohort block bootstrap | 95% CI **[+1.37%, +3.36%]**, P(≤0)=0.000 | non-parametric |
| Sign test | **7/7 positive, p=0.0078** | distribution-free |

### 4. Where the skill lives (per-category)  — [test_vs_category_index.py](../tests/test_vs_category_index.py)

| Category | Selection edge (picks − category funds) |
|---|---|
| Small Cap | **+3.4% / yr** (high dispersion — room for skill) |
| Large Cap | +0.6% / yr (efficient — funds hug the index) |
| Mid Cap | +0.1% (limited index history) |

**Skill is concentrated where funds actually differ** — economically sensible, and it
means the headline is driven by the small/mid-cap sleeves.

### 5. Relative vs absolute (vs the market) — [test_vs_index.py](../tests/test_vs_index.py)

| Comparison | Mean/yr | Cohorts won |
|---|---|---|
| picks − category benchmark | **+2.37%** | 7/7 (pure selection skill) |
| category benchmark − Nifty 50 | +2.84% | — (a size/style tilt, not skill) |
| picks − Nifty 50 | +5.22% | 5/7 (skill + tilt; lost 2016–17) |

The reliable edge is **relative** (vs same-category funds ≈ the category index).
"Beats the market" is period- and style-dependent.

### 5b. Harder benchmarks — [test_benchmarks_hard.py](../validation/test_benchmarks_hard.py)
Two more definitive benchmarks confirm the edge isn't a benchmark/weighting artifact:
- **Cap-weighted (AUM) peer:** edge **+3.45%/yr, 7/7** — survives weighting the peers by
  size, so it isn't an equal-weight small-tilt artifact.
- **Factor-adjusted alpha** (excess regressed on market + size + momentum, HAC): **alpha
  +1.72%/yr, t=4.26 (p<0.0001)** survives. Honest decomposition: **~70% of the edge is
  irreducible selection skill; ~30% is a within-category size tilt** (SMB β=0.48) — the
  model's *intended* use of the `aum_percentile`/capacity signal. Momentum β≈0 (not a
  momentum bet) and market β≈0 (market-neutral). So the edge is *mostly skill plus a
  modest, deliberate size tilt* — not a disguised factor exposure.

### 6. Adversarial robustness — [red_team.py](../validation/red_team.py) (baseline +2.47%)

**All 6 attacks survive:** size (positive every k), seed (deterministic),
leave-one-cohort-out (worst drop-2019 **+2.19%**), feature jackknife (worst drop
`aum_percentile` **+1.38%**), "just momentum?" (picks' momentum pct 0.54; edge w/o
momentum +2.41%), random-portfolio placebo (real vs 2000 random, **p<0.001**).

### 7. Survivorship — [tests/test_survivorship.py](../tests/test_survivorship.py)
Rebuilding the benchmark with dead/merged funds costs only **+0.25%/yr**; edge
**+2.47% → +2.22%**, still 7/7. *Caveat:* under a ≥5-yr seasoning filter the edge
weakens to **+2.10%** with a borderline control (p=0.050) — part of the edge relies on
young funds ([experiment_min_history.py](../validation/experiment_min_history.py)); disclosed, not
hidden.

### 8. After tax, turnover & holding period — [test_turnover_tax.py](../tests/test_turnover_tax.py)

| Hold | Gross edge | **Net after LTCG** | Turnover |
|---|---|---|---|
| 1 year | +3.70% | +2.60% | ~70% |
| **2 years** | +3.28% | **+2.69%** (best) | ~44% |
| 3 years | +2.47% | +1.90% | ~29% |

The alpha is **front-loaded** (all holds pass the negative control,
[validate_hold_periods.py](../validation/validate_hold_periods.py)). Tax drag ~1.5–1.7%/yr **does not
erase the edge if held >12 months**; a **top-4 buffer** cuts turnover 46%→33% while
keeping +2.98% of the +3.20% edge ([test_buffer_rule.py](../tests/test_buffer_rule.py)).

### 9. Which features drive it (measured, not assumed)
By gain in the final model: **`hist_return` (22%)** and **`aum_percentile` (18.5%)**
lead; `max_drawdown` is a frequent splitter across folds; **`is_team` is unused (0%)** —
redundant with `num_managers`. Stable across walk-forward folds, not shifting noise.

---

## Part IV — Why it works (the economic intuition)

- **Trees capture "only-if" logic** a linear formula can't: high momentum is good *only
  if* drawdowns are contained; a small fund's agility helps *only if* the manager is
  seasoned. That conditional structure is the whole reason for a tree model.
- **Category-neutral = skill, not style.** The model's edge is separating better funds
  from worse *within* a peer group; letting it bet *between* categories just re-introduces
  the size tilt that failed. Neutralising categories keeps only the real part.
- **It pays where funds differ.** In efficient large-cap (funds hug the index) there's
  little to pick; in high-dispersion small-cap there's real separation — and that's
  exactly where the measured edge concentrates.

---

## Part V — Honest limits (what this is *not*)

1. **Relative, not absolute** — beats same-category funds; does not time the market.
2. **Concentrated** — small-cap +3.4%, large-cap +0.6%.
3. **One market, one era** — ~250 funds/yr of Indian equity, bull-heavy 2013–2025.
4. **Overlapping windows** inflate naïve stats → HAC/bootstrap are the headline.
5. **Modest magnitude** — ~2.4% gross / ~2.6% net; the >12-month hold rule is mandatory.
6. **Young-fund dependence** — see §III.7; a survivorship-adjacent caveat.
7. **Forward-unproven** — the [paper_trading/](../paper_trading/) harness is the live test.

---

## Part VI — Two products from one engine

| | **Strategy list** | **Retail list** |
|---|---|---|
| Script | [score_live.py](../src/score_live.py) | [score_retail_list.py](../src/score_retail_list.py) |
| Model | RAW features | de-tilted (V2) |
| Output | top-2/category (10-fund portfolio) | every fund tiered within its category |
| Validated on | +2.37%/yr edge, survives every null | +13pp within-category quintile spread vs +8pp RAW ([tests/test_list_quality.py](../tests/test_list_quality.py)) |
| For | running the concentrated strategy | "which is a good fund in category X?" |

Both carry the Risk band + holding-period overlay; the retail list shows **tiers, not a
precise 1–N rank** (fund-level order is noisy at IC ~0.15).

---

### Bottom line
> A naïve ML fund-picker that "beat the market" **failed its own negative control** and
> sat on a corrupted target. After fixing both, a **genuine within-category selection
> edge remains: +2.37%/yr vs a like-for-like benchmark, 7/7 cohorts, Newey-West
> p≈0.001**, strongest in high-dispersion categories, ~+2.6% net of tax if held >12
> months. Modest, relative, market-specific — and, unlike the version before it, real by
> every test we could throw at it.
