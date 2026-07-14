# Executive Summary — Indian Active-Equity Fund Selection Engine (Corrected)

*A within-category manager-selection engine for Indian active equity, rebuilt after
a full validation audit of the original `z_FINAL_train` prototype. Every figure
here is reproduced against the live AMFI database by the scripts in this folder.*

---

## The one-sentence pitch
We cannot reliably predict which *category* will win, but we **can** rank funds
**within** a category better than chance — and a **category-neutral** portfolio
built on that skill beats a like-for-like benchmark by **~2.4% a year, in all 7
back-test cohorts, and survives the tests that broke the original claim.**

---

## What we inherited, and what the audit found
The original prototype claimed a machine-learning "Quality Engine" that beat the
equal-weight universe by ~1.5%/yr. The audit found two problems that had to be
fixed before any claim could be trusted:

1. **A corrupted price series was poisoning the training target.** One fund's NAV
   jumped 10.26 → 458.50 (a +4,367% "3-year return" — a data error). Because the
   benchmark was a plain average, it inflated the Mid Cap 2021 category return to
   +273% and gave every mid-cap fund a nonsensical target. Fixed with a NAV-sanity
   filter and a trimmed benchmark.
2. **The "proof" the edge was real did not hold up.** The original negative
   control (train on scrambled labels; performance should collapse) was run once,
   unseeded, and reported a lucky-low 16.2%. Run 40 times, the scrambled model
   averages ~18% and **beats the baseline more often than not**. In other words,
   the original edge was mostly a **structural tilt toward small, high-momentum
   funds** that *any* selection — even a random one — reproduces.

## What survived honest testing
After fixing the data and testing correctly, a genuine but narrower edge remains:

- **Ranking skill is real.** Out-of-sample, the model's fund ranking correlates
  with realised results at an information coefficient of **~0.09** (permutation
  p<0.001) — solid for equity selection.
- **You must neutralise the category tilt to harvest it.** Picking the **top 2
  funds per core category** (Large, Mid, Small, Flexi, ELSS) and judging against a
  **category-matched** benchmark isolates true skill from the size tilt.

| Metric | Original universal Top-10 | **Category-neutral (this engine)** |
|---|---|---|
| Edge vs its benchmark | +1.57% (vs equal-weight) | **+2.37% (vs category-matched)** |
| Passes the negative control? | **No** (p=0.125) | **Yes** (p=0.000) |
| Cohorts beating benchmark | — | **7 of 7** (2016–2022) |
| Alpha significance (overlap-corrected) | t=1.79, p=0.075 (n.s.) | **Newey-West t=3.30, p=0.001** |

## The product
A **2D Quality × Risk screener** over the current fund universe:
- **Quality** — the model's *within-category* percentile (the axis where it has
  skill), explained in plain English via SHAP (e.g. `[+] Excellent downside
  protection`, `[-] Fund size acting as a drag`).
- **Risk** — absolute trailing volatility + maximum drawdown, mapped 0–100 into
  Conservative / Balanced / Aggressive bands with matched holding periods.
- **Recommended** — the validated category-neutral set (top-2 per core category),
  which is what the back-test actually supports deploying.

## How it's run, and what's left after tax
One policy, not three: **re-rank yearly → hold each fund ≥12 months → sell only when
it drops out of its category top-4.** The 12-month floor secures the 12.5% long-term
capital-gains rate and zeroes exit loads; the top-4 buffer means funds naturally turn
over ~every 2 years (turnover ~33%/yr). **After tax, the ~2.4% gross edge is
~+2.6% net** — it survives, provided the 12-month rule is never broken.

## Honest limits
The edge is **real but modest**, rests on ~250 funds/year of one market, and the
back-test cohorts overlap in calendar time (which is exactly why we report the
conservative Newey-West and bootstrap results, not just the raw t-stat). It should
be confirmed on future years and other markets before scaling. This is a
disciplined **fund-selection engine**, not an all-weather alpha machine.
