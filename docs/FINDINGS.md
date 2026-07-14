# Validation & Correction Findings

*Corrected rebuild of `z_FINAL_train`. Every number below was reproduced against
the live `amfi_data` PostgreSQL database using the scripts in this folder.*

---

## 1. What was wrong in the original

### 1.1 A corrupted NAV poisoned the training target (critical data bug)
The label `fwd_alpha = fwd_return − AVG(category fwd_return)` was built with **no
outlier handling**. One fund — **HSBC Midcap Fund** — has a broken NAV series
(NAV **10.26 → 458.50**, a **+4,367%** "3-year return", almost certainly a
rebased/merged series). Because it entered the plain category average, it dragged
the **Mid Cap 2021** benchmark to **+273%**, which forced the `fwd_alpha` of *all
19* mid-cap funds that year to a nonsensical **−170% to −220%**.

- Symptom in the data: worst `|mean fwd_alpha|` within a cohort×category = **1.85**.
- After fix: **0.157**, and Mid Cap 2021 mean alpha `−1.85 → +0.03`.

### 1.2 The negative control did not support its headline claim
`walkthrough.md` states the scrambled-label model "collapsed to 16.2%, worse than
the baseline (17.7%) … strong evidence the edge is genuine signal."

That number came from a **single, unseeded** `np.random.permutation`. Run properly
over many seeds, the scrambled-label model:

| | Original (as reported) | Reproduced distribution |
|---|---|---|
| Scrambled CAGR | 16.2% (one lucky-low draw) | **mean 17.9–18.2%**, range ~16–21% |
| Beats equal-weight (17.7%)? | "No" | **Yes in ~½ to ¾ of seeds** |

So a model trained on **random** labels selects funds that beat the equal-weight
universe about as often as the "real" model. The reported edge was largely a
**structural artifact of concentrated top-10 selection** (a small-AUM + momentum
tilt), not learned signal. This is consistent with the original's own
t-test (t=1.75, **p=0.08**, not significant).

### 1.3 Smaller issues
- `run_benchmarks.py` printed **"Averaged 2016-2022"** but only tested cohorts
  **2018–2022** (5 years). The "7-year / 71% hit / 0.45 IR" numbers came from a
  different configuration than the script the README pointed to.
- `Rank` was computed on the **rounded integer** Quality → duplicate ranks
  (two "Rank 5" funds in the shipped CSV).
- The live screener's top picks were dominated by a **single AMC** ("quant" ×5)
  and almost entirely by "[+] Ideal AUM agility" — confirming the size tilt.
- Survivorship: funds missing a t+3 NAV are dropped from both target and
  benchmark. Measured at **1–3% per cohort** — real but minor.

---

## 2. What reproduced faithfully (the original wasn't faked)
| Claim | Result |
|---|---|
| 5-yr (2018–22): ML 23.7% vs EW 21.5%, IR 0.67, 100% hit | ✅ exact |
| 7-yr: ML 19.2% vs EW 17.7% | ✅ exact (19.30% / 17.74%) |
| Turnover ~87% | ✅ (80–87%) |
| Top 5 = 20.06%, Top 10 = 19.23% | ✅ exact |
| t-stat 1.75 / p 0.08 | ✅ exact |

The engineering and arithmetic were honest; the **interpretation** overreached.

---

## 3. The fixes applied here
1. **`prepare_features.py`** — NAV-sanity filter (drop 3-yr returns outside
   [−95%, +500%] before they touch the benchmark) **+** a **5%-trimmed** category
   benchmark so no single glitch can dominate. Regenerated `ml_dataset.csv`.
2. **`run_validation.py`** — negative control is **seeded and run over 40 seeds**;
   the model is judged against the **correct null (the scrambled-label model)**,
   not just the equal-weight universe; window correctly labelled 2016–2022.
3. **`manager_quality_screener.py`** — rank ties removed (stable rank on the
   continuous score); Quality is now a **within-category** percentile (the axis on
   which the model actually has skill).

---

## 4. Does a real edge survive? (`strengthen_edge.py`)

### 4.1 The honest skill metric — out-of-sample rank IC
Pooled Spearman correlation between predicted and **realised** forward alpha
across ~1,640 out-of-sample fund-cohorts:

| Feature encoding | Pooled IC | Within-category IC | Permutation p |
|---|---|---|---|
| Raw features | **+0.096** | +0.091 | <0.001 |
| Cohort-ranked | +0.187 | +0.087 | <0.001 |
| Cohort×category-ranked (de-tilted) | +0.169 | **+0.184** | <0.001 |

An IC of ~0.05–0.10 is considered good in quant equity. There is **genuine,
statistically significant within-category ranking skill** — the model *can* tell
better funds from worse *inside a category*.

### 4.2 Turning skill into a robust edge — category-neutral construction
The universal top-10 wastes that skill by tilting into whichever category looks
best (which a random model also does). Forcing **top-2 per core category** and
benchmarking against the **same categories** isolates the real signal:

| Metric | Universal Top-10 (original) | **Category-neutral (fixed)** |
|---|---|---|
| CAGR | 19.30% | **20.18%** |
| Benchmark | EW 17.74% | Category-matched 17.81% |
| Edge | +1.57% | **+2.37%** |
| Beats negative control? | ✗ (empirical p=0.125) | ✅ **p=0.000** (above all 20 seeds) |
| Monthly alpha significance | t=1.79, p=0.075 (ns) | **t=4.23, p<0.0001** |
| Per-cohort hit rate | — | **7/7 years** (+0.6% to +4.1%) |

The category-neutral portfolio is the construction that **passes** the negative
control and produces significant, consistent alpha.

### 4.3 Robustness of the edge to overlapping windows (`robustness_check.py`)
The 3-year forward windows overlap, so the naive monthly t-stat is inflated by
autocorrelation. Correcting for it, the edge still holds under every
weaker-assumption estimator:

| Test | Assumption | Result |
|---|---|---|
| Naive monthly t | independent months (optimistic) | t=4.23, p<0.0001 |
| **Newey-West HAC** (36 lags) | corrects 3-yr overlap | **t=3.30, p=0.0010** |
| Non-overlapping annual t (7 obs) | 1 obs/cohort | t=4.29, p=0.0051 |
| Cohort block bootstrap | non-parametric | 95% CI **[+1.37%, +3.36%]**, P(edge≤0)=0.000 |
| Sign test | distribution-free | **7/7 positive, p=0.0078** |

The honest headline number is the **HAC t≈3.3 (p≈0.001)** — the naive t=4.23 is an
overstatement, but the edge is significant under the correct correction.

### 4.4 Remaining caveats
- Within-category IC of +0.18 (de-tilted) is optimistic; the **+0.09 raw** figure is
  the conservative read of ranking skill. **Now confirmed empirically**
  (`tests/test_detilted_features.py`): feeding de-tilted features into the actual
  top-2/category portfolio adds only **+0.16%/yr** over raw (beats raw in just 3/7
  cohorts) despite the IC doubling — a better IC did not become better picks, so the
  raw-feature construction is kept.
- All 7 cohorts still share calendar time; "7 independent years" is a slight
  overstatement, which is exactly why the HAC and bootstrap are reported alongside.
- Edge is **real but modest** and rests on ~250 funds/yr of Indian equity data;
  it needs out-of-sample confirmation on new years and other markets.

### 4.5 Market regimes the training actually spans
Each cohort `t` uses a 3-yr **feature** window (`t-3→t`) and a 3-yr **label** window
(`t→t+3`), so the NAV price action the model learns from runs ~**2012 → 2025** of
Indian active-equity (cohorts 2013–2022; 2013–14 are ~empty, effective start 2015,
validation from 2016). The label windows cover the major Indian regimes:

| Cohort | Label window `t→t+3` | Regime captured |
|---|---|---|
| 2015 | 2015–2018 | China-slowdown correction → demonetisation → 2017 mid/small-cap boom |
| 2016 | 2016–2019 | Recovery → 2018 mid/small-cap **crash** + IL&FS credit crisis |
| 2017 | 2017–2020 | Boom → narrow market → **COVID crash** (Mar'20 ~−35%) |
| 2018 | 2018–2021 | Crash → COVID → **2021 everything-rally** |
| 2019 | 2019–2022 | Slowdown → COVID → boom → 2022 rate-hike drawdown |
| 2020 | 2020–2023 | COVID V-recovery → 2021 bull → 2022 inflation/sideways |
| 2021 | 2021–2024 | Peak bull → 2022 correction → 2023–24 small/mid-cap boom |
| 2022 | 2022–2025 | Rate hikes/war → 2023–24 bull → 2025 correction |

**Three caveats on "regime coverage":** (i) it is **one market/currency/regulatory
regime** — zero cross-market evidence; (ii) the 3-yr windows **overlap heavily**, so
this is better read as *one Indian equity cycle with several sub-episodes* than as ~10
independent regimes (see the "share calendar time" caveat in §4.4 — the reason HAC and
the block bootstrap are reported); (iii) the label is **category-relative**, so the
model learned *cross-sectional dispersion* within each regime, not market direction —
which is why the skill concentrates in high-dispersion regimes/categories (§5) and the
`paper_trading/` harness is the only genuinely forward, unseen-regime test.

---

## 4A. Adversarial red-team — actively trying to disprove the edge (`red_team.py`)
Beyond the negative control, we ran every attack a hostile referee would use. The
edge **survived all six**, but the caveats matter and are stated.

| Attack | Result | Survives? |
|---|---|---|
| **A. Portfolio size** (top-1…5/cat) | +1.44% to +2.47%, positive at every k | ✅ not cherry-picked on "top-2" |
| **B. Model seed** (8 seeds) | identical edge | ✅ but *trivial* (model is deterministic — no bagging) |
| **C. Leave-one-cohort-out** | worst (drop 2019) still **+2.19%** | ✅ not one lucky year |
| **D. Feature jackknife** | worst (drop `aum_percentile`) still **+1.38%** | ✅ no single-feature dependence |
| **E. "Is it just momentum?"** | picks' momentum pct = 0.54 (neutral); edge w/o momentum = **+2.41%** | ✅ **not disguised momentum** |
| **F. Random-portfolio placebo** (2,000 draws) | real +2.47% vs random 95th-pct +1.32%, **p=0.0000** | ✅ far beyond chance |

**Honest caveats:** (i) the seed test is trivially passed because the model is
deterministic; (ii) random 2/category portfolios already average **+0.47%** vs the
broad benchmark (a small non-skill concentration/survivorship baseline) — the real
edge clears it comfortably but the *net* skill nets this out; (iii) these are all
**internal** tests (same data/period) — they disprove a within-sample fluke, not
external invalidity.

**Look-ahead audit:** features are strictly as-of the eval date; training is strictly
prior cohorts; the target's use of forward data is the label, not a feature. One
**minor imperfection**: `prepare_features` fills a few missing AUM/TER values with a
global median (spanning all cohorts) — affects a handful of rows' *level*, not their
within-category rank; low impact, worth fixing to a cohort-wise fill.

**Survivorship — tested (`tests/test_survivorship.py`).** We rebuilt the benchmark
from *all funds alive at t* (from the DB, not just survivors), with dead/merged funds
contributing real returns until they vanish then reinvested at benchmark (standard
convention). Result: **benchmark survivorship bias is only +0.25%/yr** (including
dead funds slightly *raises* the benchmark — in Indian MFs most "deaths" are mergers
into larger funds, not failures). **The edge holds: +2.47% → +2.22% survivorship-
adjusted, still 7/7 cohorts positive.** *(A neat by-product: the raw-DB "all alive"
universe re-imported the HSBC Midcap +4,367% NAV error we fixed upstream, which
alone flipped 2021 negative — so the same NAV-sanity filter had to be applied here;
concrete proof of why the §1.1 data fix matters.)* Residual: **picks** are still
chosen from survivors (dead funds lack a forward label); fully closing that needs a
dataset rebuild with censored labels — a second-order effect on top of the +0.25%
benchmark result.

---

## 5. Is the benchmark fair? Relative vs absolute, and per-category index tests
The +2.4% edge is measured against a **category-matched benchmark** (all funds in
the same 5 categories) — a *relative* benchmark, not a market index. Two tests
check whether that is honest. (`test_vs_index.py`, `test_vs_category_index.py`)

### 5.1 Against the market index (Nifty 50) — `test_vs_index.py`
| Comparison | Mean/yr | Cohorts won | What it is |
|---|---|---|---|
| picks − category benchmark | **+2.37%** | **7/7** | pure selection skill (validated) |
| category benchmark − Nifty 50 | +2.84% | — | a size/style tilt, **not** skill |
| picks − Nifty 50 | +5.22% | 5/7 | total gap (skill + tilt) |

The strategy beat the Nifty 50 by ~5.2%/yr **but only in 5 of 7 years** — it *lost*
to the index in 2016–17 (large-cap-led years). Roughly **half** of the market-beating
gap is a mid/small-cap style tilt, not selection. Conclusion: the *reliable* edge is
**relative** (vs same-category funds); "beats the market" is period- and style-dependent.

### 5.2 Against each category's own index — `test_vs_category_index.py`
Index funds for Midcap 150 / Smallcap 250 only launched in 2020–21 (Nifty 500 in
2024), so a full-cycle test exists **only for large cap**; mid/small are limited to
3 recent (boom) cohorts.

**Finding A — the fund benchmark tracks the index** (`funds − index` ≈ 0):
Large +0.3%, Mid +0.6%, Small +1.4% per year. So "+2.4% vs category funds" is
effectively "+2.4% vs the category index" — the relative benchmark was fair.

**Finding B — the skill is concentrated in high-dispersion categories**, not uniform:

| Category | Selection edge (picks − funds) | Data |
|---|---|---|
| Large Cap | **+0.6%/yr** (lost 2/7 yrs; efficient, funds hug the index) | 7 cohorts ✅ |
| Mid Cap | +0.1%/yr (≈ none on limited data) | 3 cohorts ⚠️ |
| Small Cap | **+3.4%/yr** | 3 cohorts ⚠️ |

Selection only pays where funds actually differ (small/mid-cap dispersion); in
efficient large-cap it is close to a coin flip. Economically sensible, and it means
the headline +2.4% is driven by the higher-dispersion sleeves.

**Limitation:** we cannot yet prove the small/mid-cap edge against a *passive index*
over a full cycle — those index funds are too young (only the small-cap boom is
covered). This is a data limitation to revisit as index history accrues.

---

## 6. Tax, turnover, and holding period (net-of-cost realism)
The +2.4% is **gross**. Because the strategy trades, real investors face capital-gains
tax and (potentially) exit loads. We checked the data and modelled the impact.
(`test_turnover_tax.py`, `validate_hold_periods.py`, `test_buffer_rule.py`)

**Data availability (checked in `amfi_data`):**
- **Exit load — not stored** anywhere in the database.
- **Lock-in — column exists but is empty** (`scheme_plan.lock_in_months` and
  `bse_scheme.lock_in_months` are all 0/NULL, *including for ELSS*, which is wrong).
- So we apply **domain rules**: LTCG **12.5%** if held **>12 months**; **ELSS is
  statutorily locked 3 years**; ₹1.25 lakh/yr LTCG exemption ignored (conservative).
- **Exit loads are negligible by design.** The dominant industry structure (~80–90%
  of equity funds) is "1% if redeemed within 365 days, **Nil thereafter**"; the rare
  variants use even shorter 30/60/90-day windows. Holding **>12 months** — the same
  rule that secures LTCG — clears **all** of them, so exit load = 0 in practice. It
  only matters if you break the >12-month rule (which also costs you 20% STCG).

**6.1 The gross edge is front-loaded — and validated at every hold length.**
Re-running the full negative control per holding period:

| Hold | Gross edge | Negative control | Sign test |
|---|---|---|---|
| 1 year | **+3.70%/yr** | **passes** (p=0.000, null ≈ +1.1%) | 6/7 (p=0.06) |
| 2 years | +3.28%/yr | passes (p=0.000, null ≈ +0.7%) | 6/7 (p=0.06) |
| 3 years | +2.47%/yr | passes (p=0.000, null ≈ +1.0%) | 7/7 (p=0.008) |

The edge is **largest at a 1-year hold and decays with time** — and all three
survive the null, so the front-loaded alpha is real (the 3-year hold is still the
most bulletproof on the sign test).

**6.2 After tax, a 1–2 year hold keeps the most.** Modelling LTCG on realised gains
(both strategy and a buy-and-hold benchmark taxed fairly):

| Hold | Turnover/yr | **Net edge after tax** |
|---|---|---|
| 1 year | ~70% | +2.60% |
| **2 years** | ~44% | **+2.69%** (best) |
| 3 years | ~29% | +1.90% |

Cutting turnover does **not** help net return here, because the gross alpha decays
faster than the tax saving grows. Tax drag is ~1.5–1.7%/yr but **does not erase the
edge, provided you hold >12 months** (holding <12 months triggers 20% STCG + exit
loads and roughly wipes it out).

**6.3 A buffer rule cuts churn at almost no cost.** Holding each fund until it drops
out of the category **top-4** (instead of forcing exactly top-2):

| Rule | Edge/yr | Turnover/yr |
|---|---|---|
| Top-2 (no buffer) | +3.20% | 46% |
| **Hold until out of top-4** | +2.98% | **33%** |
| Hold until out of top-6 | +1.67% (too loose) | 29% |

**Implementation rules that follow:** (i) **never rebalance under 12 months** — the
single most important tax rule; (ii) prefer a **~2-year hold or a top-4 buffer**;
(iii) **ELSS** is naturally tax-efficient (its 3-year lock-in forces low turnover,
LTCG, zero load). *(Caveat: 1- and 2-year edges pass the null but have one down year
each; the buffer figures are a valid relative comparison across K.)*

---

## 7. Bottom line
- The original's central "edge" claim, as written, **did not survive its own
  negative control** — and a data bug was corrupting the target.
- After fixing the data and testing honestly, a **genuine within-category
  selection skill does exist** (IC ~0.09, p<0.001), and a **category-neutral
  construction converts it into a defensible, statistically significant edge**
  (+2.4% vs a category-matched benchmark, 7/7 years, passes the negative control,
  Newey-West p≈0.001).
- That edge is **relative** (vs same-category funds ≈ category index), **not** a
  claim to beat the market index in all conditions, and it is **concentrated in
  high-dispersion categories** (small/mid-cap) rather than efficient large-cap.
- **After tax it survives:** ~**+2.6% net** at a 1–2 year hold (LTCG 12.5%), *if*
  positions are held **>12 months** to avoid 20% STCG and exit loads; a top-4 buffer
  keeps the edge while cutting turnover.
- Framed honestly, this is a sound **within-category manager-selection engine** —
  strongest where funds differ most — not an all-weather, beat-the-market alpha
  machine.

---

## 8. From validation to a live deliverable (2023 onward)
Everything in §1–§7 is measured on the **validation universe: ~250 funds/yr, cohorts
2013–2022**. Those numbers are and stay the record of what was validated. Two additions
carry the method forward without changing it:

- **Live scoring (`prepare_features_live.py` + `score_live.py`).** `manager_quality_screener.py`
  scores the 2022 snapshot on purpose — 2022 is the newest cohort whose 3-yr outcome can
  be *graded*. To advise an investor buying **now**, the live path scores the latest
  complete year-end using features only (the forward label is needed to grade a pick, not
  to make one). The **2025 live snapshot covers 381 funds vs 275 in 2022** — purely
  industry growth (more funds now clear the 30-month history filter), not a methodology
  change. This list inherits the validated method; it is **not itself a fresh
  out-of-sample proof** (its 2028 outcome hasn't happened).

- **Paper trading (`paper_trading/`).** Runs the category-neutral strategy forward against
  real daily NAVs vs a category-matched benchmark of 154 core-category funds, marking
  daily and rebalancing annually (top-4 buffer, 12-month min-hold). This is the genuine
  live out-of-sample control §7 calls for — the honest test the internal battery could not
  provide.

- **Retrain cadence.** The model gains one new labelable cohort per year (a cohort's
  3-yr label closes each December). Latest trained: **2022**; next (**2023**) unlocks once
  monthly NAVs reach 2026-12-31 (~Jan 2027). `annual_maintenance.py` does the yearly data
  refresh + retrain; the daily paper-trade run prints when it is due.

> **Number hygiene:** "~250 funds/yr" = validation cohorts (2013–2022). "381 funds" =
> the 2025 live snapshot. Both are correct; they describe different universes and should
> not be conflated.
