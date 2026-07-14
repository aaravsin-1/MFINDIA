# The Research Journey — From a Flawed Prototype to a Validated Edge

This is the honest chronological account of how the engine was built, where the
first version went wrong, and what survived rigorous re-testing. It supersedes the
original `z_FINAL_train/research_journey.md`, whose central claim did not hold up.

---

## Phase 1 — Building a clean universe
The AMFI database holds 8,000+ share classes: debt, passive, hybrid, regular and
direct plans. We isolated **active equity, Direct-Growth plans only** (regular
plans bleed return to distributor commissions) and required **≥30 months of
history** to compute stable risk metrics. This yields ~200–275 clean funds per
annual cohort (2013–2022).

## Phase 2 — Disproving "buy the past winners"
The first test needed no ML: buy the top-10 funds by trailing 3-year return. It
**underperformed** the equal-weight universe. Chasing raw momentum doesn't work —
mean reversion and hidden risk-taking erase the lead. Motivation for a model that
weighs momentum *in context*.

## Phase 3 — A gradient-boosted ranking model
We built a LightGBM model to predict **forward category-relative alpha** from nine
features: trailing return, volatility, hit-rate, max drawdown, AUM percentile,
TER, manager tenure, team size. Tree models capture interactions a single factor
misses (e.g. *high momentum + low drawdown* good, *high momentum + high drawdown*
bad). Validation was walk-forward: train on all prior cohorts, predict the next.

## Phase 4 — The audit that changed everything
Before publishing the prototype's "we beat the market" result, we stress-tested
it. Two things broke:

**4a. A corrupted NAV was poisoning the target.** The training label is
`forward return − category-average forward return`. The category average was a
plain mean with no outlier handling. One fund (HSBC Midcap) had a broken NAV
series reading a **+4,367%** three-year return, which dragged the **Mid Cap 2021**
category benchmark to **+273%** and gave all 19 mid-cap funds fake target alphas of
−170% to −220%. The worst per-group mean alpha in the dataset was **−1.85**.
→ *Fix:* drop 3-year returns outside a sane band and compute the benchmark as a
5%-trimmed mean. Worst per-group mean alpha fell to **0.157**; Mid Cap 2021 went
from −185% to +3%.

**4b. The negative control did not support the headline.** The proper test of "did
the model learn signal?" is to **scramble the training labels** — performance
should collapse to the baseline. The prototype ran this **once, unseeded**, drew a
lucky-low **16.2%**, and declared victory. Re-run over 40 seeds:

- Scrambled-label model CAGR: **mean ~18.2%** (range ~16–21%).
- It **beat** the equal-weight baseline (17.7%) in **29 of 40 seeds**.
- The "real" model (19.3%) sat only **~1 sd** above the scrambled mean —
  empirical **p = 0.125**. Its monthly alpha was **t=1.79, p=0.075** (not
  significant).

Conclusion: the prototype's edge was **mostly a structural tilt** — selecting a
concentrated basket of small, high-momentum funds beats a broad equal-weight
average regardless of whether the model learned anything.

## Phase 5 — Recovering a real edge (the breakthrough)
Rather than abandon the model, we asked the sharper question: *is there ANY genuine
skill, and if so where?*

**5a. Measure skill directly with rank IC.** Pooled across ~1,640 out-of-sample
fund-cohorts, the Spearman correlation between predicted and **realised** forward
alpha is **+0.096** (permutation p<0.001), and **+0.09 to +0.18 within category**.
An information coefficient near 0.1 is genuinely useful in equity selection. So the
skill exists — it is **within-category ranking**, not cross-category timing.

**5b. Harvest it category-neutral.** The universal top-10 squanders that skill by
tilting into whichever category looks hottest (which a random model also does). So
we **pick the top 2 funds per core category** (Large, Mid, Small, Flexi, ELSS) and
benchmark against those **same categories**:

| | Universal Top-10 | **Category-neutral** |
|---|---|---|
| CAGR | 19.30% | **20.18%** |
| Benchmark | equal-weight 17.74% | category-matched 17.81% |
| Edge | +1.57% | **+2.37%** |
| Negative control | fails (p=0.125) | **passes (p=0.000)** |
| Monthly alpha | t=1.79 (n.s.) | **t=4.23** |
| Cohort hit rate | — | **7/7** |

## Phase 6 — Confirming significance under overlapping windows
Because 3-year forward windows overlap, the naive monthly t-stat is optimistic. We
re-tested under weaker assumptions:

- **Newey-West HAC (36 lags): t=3.30, p=0.0010** — the honest headline.
- Non-overlapping annual test (7 obs): t=4.29, p=0.0051.
- Cohort block bootstrap: 95% CI **[+1.37%, +3.36%]**, P(edge≤0)=0.000.
- Sign test: **7/7 positive, p=0.0078**.

The edge is smaller than the naive number but **robustly positive**.

## Phase 7 — The deliverable
The final architecture is unchanged in spirit — **the machine ranks, the human
interprets** — but honest about scope:
- **Quality Engine (ML):** within-category percentile of predicted alpha.
- **Risk Engine (math):** trailing volatility + max drawdown → 0–100.
- **SHAP:** plain-English reasons per fund.
- **Recommended set:** the validated category-neutral top-2-per-category portfolio.

## Conclusion
The original prototype's specific claim — a universal ML portfolio that beats the
market on genuine signal — **did not survive its own negative control**, and a data
bug was corrupting its target. After fixing both, a **narrower but real edge
remains**: statistically significant **within-category selection skill**, best
deployed **category-neutral**, worth roughly **+2.4%/year** against a like-for-like
benchmark across every cohort tested. It is modest, market-specific, and needs
forward confirmation — but it is real, and it is honestly measured.
