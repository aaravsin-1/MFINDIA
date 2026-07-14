# Walkthrough — Using the 2D Quality × Risk Screener

The deliverable is `fund_screener_results.csv`, produced by
`manager_quality_screener.py`. This explains how to read it, how different
investors use it, and the validation that stands behind it. It supersedes the
original `z_FINAL_train/walkthrough.md`.

---

## Why two dimensions
A single "risk" cutoff on volatility is misleading — two funds with identical
volatility can have very different **maximum drawdowns** (what actually causes
investors to panic-sell). So funds are placed on a 2D plane:

- **Quality (0–100)** — the ML model's **within-category** percentile. *Within*
  category matters: the validation showed the model ranks funds against their
  peers well, but is not good at predicting which *category* will win. A Quality of
  95 means "top-5% fund inside its own category," not "better than a 90 in another
  category."
- **Risk (0–100)** — absolute, model-free: standardised trailing volatility +
  maximum drawdown, clipped and mapped to 0–100, then bucketed:
  - **Conservative** (≤30) → horizon 5+ years
  - **Balanced** (31–60) → horizon 3–5 years
  - **Aggressive** (>60) → horizon 1–3 years

Each row also carries a plain-English **`Why`** (top-2 SHAP drivers) and a
**`Recommended`** flag.

## The columns
`Rank | Fund | Category | Quality | Risk | RiskBand | Recommended | Expected Holding Period | Why`

- `Recommended = Yes` marks the **validated strategy**: the top-2 funds per core
  category (Large, Mid, Small, Flexi, ELSS). This is the set the back-test
  actually supports — **use this, not a global top-N.**
- `Rank` is a stable, tie-free ordering (recommended funds first, then by score).

## The recommended portfolio (2022 snapshot, out-of-sample)
Ten funds, diversified by construction (2 per core category):

| Category | Fund | Quality | Risk | Band |
|---|---|---|---|---|
| Large Cap | JM Large Cap Fund | 100 | 0 | Conservative |
| Large Cap | Union Largecap Fund | 96 | 35 | Balanced |
| Mid Cap | Aditya Birla Sun Life Midcap Fund | 100 | 54 | Balanced |
| Mid Cap | HDFC Mid Cap Fund | 95 | 50 | Balanced |
| Small Cap | Franklin India Small Cap Fund | 100 | 66 | Aggressive |
| Small Cap | Aditya Birla Sun Life Small Cap Fund | 95 | 74 | Aggressive |
| Flexi Cap | JM Flexicap Fund | 100 | 33 | Balanced |
| Flexi Cap | HDFC Flexi Cap Fund | 96 | 53 | Balanced |
| ELSS | JM ELSS Tax Saver Fund | 100 | 42 | Balanced |
| ELSS | Groww ELSS Tax Saver Fund | 97 | 29 | Conservative |

Note the spread across AMCs and categories — a direct improvement over the
original screener, whose top picks were 5 funds from a single house (a symptom of
the size tilt that failed validation).

## How each investor uses it
- **Conservative (5+ yr):** filter `RiskBand = Conservative`, then take the highest
  Quality within each category — e.g. JM Large Cap (Q100, R0) or Groww ELSS
  (Q97, R29).
- **Balanced (3–5 yr):** the bulk of the recommended set sits here; hold the
  category-neutral ten and follow the rebalancing playbook below.
- **Aggressive (1–3 yr):** willing to accept the small-cap drawdowns for the
  highest expected return — e.g. Franklin India Small Cap (Q100, R66).

Quality never changes with appetite; only the **risk filter** the investor applies
does. Equal-weight the chosen funds.

### The rebalancing rule (one policy, not three)
"Yearly," "2-year," and "top-4" are the *same* policy, not options:
1. **Re-rank once a year.**
2. **Hold every fund ≥12 months** — mandatory: this secures the 12.5% LTCG rate and
   zeroes exit loads. A sub-12-month sale triggers 20% STCG and roughly erases the edge.
3. **Sell only when a fund drops out of its category's top-4** (a "buffer").

Because you only sell on a top-4 exit, funds naturally turn over about **every 2
years** — cutting trading from ~46% to ~33%/yr while keeping the edge and the low tax
bracket. (See `FINDINGS.md` §6 for the tax/turnover evidence.)

---

## The validation behind it

**1. Negative control (the test the original failed).** Train the model on
**scrambled** labels 40 times; a genuine model should collapse to the baseline.
- Original universal top-10: scrambled model beats the baseline in 29/40 seeds,
  real model only ~1 sd above → **empirical p=0.125 (fails)**.
- Category-neutral strategy: real edge is above **all 20** scrambled seeds →
  **p=0.000 (passes)**.

**2. Out-of-sample ranking skill (IC).** Spearman(predicted, realised alpha) across
~1,640 fund-cohorts = **+0.096**, permutation **p<0.001**; **+0.09 to +0.18**
within category. Real, useful selection skill.

**3. Edge size and consistency.** Category-neutral portfolio beats a
category-matched benchmark by **+2.37%/yr**, positive in **7 of 7** cohorts
(+0.6% to +4.1%).

**4. Significance under overlapping windows.** Naive monthly t=4.23 is optimistic;
corrected:
- **Newey-West HAC (36 lags): t=3.30, p=0.0010**
- Non-overlapping annual: t=4.29, p=0.0051
- Bootstrap 95% CI: **[+1.37%, +3.36%]**
- Sign test: **7/7, p=0.0078**

**5. Turnover & tax.** Naive top-2 churns ~46–80%/yr; a **top-4 buffer cuts it to
~33%**. After 12.5% LTCG (holding >12 months), the ~2.4% gross edge is **~+2.6% net**
at a 1–2 year hold — the edge survives tax. (`FINDINGS.md` §6.)

**6. Feature stability.** Year to year the model leans on the same core drivers —
`max_drawdown`, `hist_return`, `aum_percentile`, `max_tenure_years` — not shifting
noise.

> **Bottom line:** a within-category manager-selection engine, deployed
> category-neutral, that produces a **modest but statistically robust** edge
> (~+2.4%/yr, p≈0.001 after honest corrections) — and, unlike the original, one
> that survives its own negative control.
