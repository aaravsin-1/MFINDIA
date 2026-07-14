# Research Findings — Machine-Learning Fund Selection in Indian Equity

*The consolidated research record for the corrected engine (`RESULTS_PROJECT/`).
Every empirical claim was reproduced against the live `amfi_data` database by the
scripts in this folder. This is the capstone document; `FINDINGS.md` holds the
step-by-step evidence and `MANAGER_REPORT.md` the stakeholder framing.*

---

## Abstract

Using 10 annual cohorts (2013–2022) of Indian active-equity funds (Direct-Growth,
≥30 months history; ~1,840 fund-cohorts), we test whether machine learning can
select outperforming funds. Our central result is cautionary and constructive: a
naive ML portfolio that "beats the market" **fails a negative-control test** — a
model trained on scrambled labels reproduces most of the apparent edge, which is
really a small-cap/momentum style tilt. After (a) fixing a data-quality bug that
corrupted the training target and (b) isolating skill via **category-neutral
construction**, a **genuine, modest, statistically significant within-category
selection edge survives**: ~**+2.4%/yr gross** (~+2.6% after tax) versus a
category-matched benchmark, positive in all 7 test cohorts, robust to
overlapping-window corrections (Newey-West t≈3.3, p≈0.001). The skill is
**concentrated in high-dispersion categories** (small/mid-cap) and near-zero in
efficient large-cap. Two attempts to enlarge the edge (fund flows, alternative
targets) failed honestly; the clearest remaining lever is a data-linkage task, not
a modelling one.

---

## 1. Empirical findings

**F1 — Single factors do not predict fund returns out-of-sample.**
Twelve single-signal strategies (momentum, TER, flows, Sharpe, category rotation,
etc.) failed after realistic OOS testing. *Cf. Carhart (1997).*

**F2 — Naive "buy the past winners" underperforms.** Top-10 by trailing return lost
to the equal-weight universe — mean reversion dominates.

**F3 — The naive ML "edge" is largely an artifact.** A universal top-10 ML portfolio
beat the equal-weight universe by +1.6%/yr, **but failed its negative control**:
scrambled-label models beat the baseline in ~29/40 seeds; the real model was only
~1 sd above the null (empirical p=0.125), and its alpha was insignificant (p=0.075).
The apparent edge was a **structural small-cap / momentum tilt**. *Cf. Harvey, Liu &
Zhu (2016); Bailey & López de Prado on backtest overfitting.*

**F4 — Genuine within-category ranking skill exists.** Out-of-sample rank IC between
predicted and realised forward alpha = **+0.096** (p<0.001) pooled, **+0.09 to +0.18
within category**. An IC ~0.05–0.10 is exploitable in equity selection. *Cf. Gu,
Kelly & Xiu (2020).*

**F5 — Category-neutral construction converts skill into a robust edge.** Selecting
top-2 per core category vs a category-matched benchmark yields **+2.37%/yr**,
positive in **7/7 cohorts**, and — unlike the universal top-10 — it **passes the
negative control (p=0.000)** with significant alpha under strict corrections
(Newey-West t=3.30, p=0.0010; bootstrap 95% CI [+1.37%, +3.36%]; sign test 7/7).

**F6 — Skill is concentrated where funds differ most.** Per-category selection edge:
small-cap **+3.4%**, large-cap only **+0.6%** (large-cap funds hug the index; small-cap
dispersion leaves room for skill). *Cf. SPIVA India; Cremers & Petajisto (2009).*

**F7 — AUM/capacity is the most robust single feature.** Its removal causes the
largest performance deterioration across ablations; fund size proxies capacity
constraints, biting small-caps hardest. *Cf. Chen, Hong, Huang & Kubik (2004);
Berk & Green (2004).*

**F8 — A "dumb-money" flow effect exists but adds no incremental value.** Trailing
organic flow has a real, significant **negative** IC (−0.063, p=0.007): high inflows
predict lower future alpha (return-chasing / capacity drag). But it points the same
direction as, and is weaker than, the AUM feature already in the model — adding it
does **not** improve the portfolio. *Cf. Frazzini & Lamont (2008).*

**F9 — The alpha is front-loaded.** The gross edge is largest at a 1-year hold
(+3.70%/yr) and decays to +2.47% by 3 years; all three horizons pass the negative
control (p=0.000).

**F10 — The edge survives tax if positions are held >12 months.** After 12.5% LTCG,
the net edge is ~**+2.6%** at a 1–2 year hold. A top-4 buffer cuts turnover ~46%→33%.
Holding <12 months triggers 20% STCG + exit loads and roughly erases the edge.
(Exit-load and lock-in data are absent/empty in the DB; statutory rules applied.)

**F11 — The raw-alpha target is already optimal.** Risk-adjusted / downside training
targets (Sharpe, Calmar, rank) all pass the null but do **not** improve information
ratio or drawdown — risk is better handled by the separate Risk engine.

**F12 — Data quality can silently bias fund research.** A single corrupted NAV
(+4,367% "3-yr return") inflated a category benchmark to +273% and poisoned the
target for an entire cohort×category. Fixed with an outlier filter + trimmed
benchmark. *Cf. Elton, Gruber & Blake (1996) on survivorship/data bias.*

---

## 2. Methodological contributions

*Framing note: label-permutation negative controls are **standard** (biology, medicine,
ML; in finance the cousins are White's Reality Check, the deflated Sharpe ratio, and
Bailey & López de Prado on backtest overfitting — see F3). We did **not** invent the
method. The contributions below are its **application and a case study**, not a new tool.*

**M1 — A negative control applied to fund selection, run to overturn a result.** Train
on scrambled labels over many seeds; the real model must beat that distribution, not
just the market. Novelty is contextual: mutual-fund selection backtests still validate
on CAGR-vs-benchmark, and here the control **caught a false positive that comparison
would have published**. *Caveat — see M2: we then redesigned the construction until it
passed, which carries residual selection risk; the forward paper trade is the mitigation.*

**M2 — Category-neutral construction to separate skill from style.** The same model
"passes" or "fails" depending on whether category tilt is neutralised — a transferable
evaluation lesson. **Honest limitation:** because the passing construction was *chosen*
after it passed, the in-sample p-values are researcher-selected; they are validated
against tests the construction was not tuned on (M3, red-team) but the only true
out-of-sample check is `paper_trading/`.

**M3 — Significance under overlapping windows.** Rank IC + Newey-West HAC + cohort
block bootstrap + sign test, reported together, rather than a single optimistic
t-stat. *Cf. Kosowski et al. (2006) on bootstrap for fund skill.*

---

## 3. Methods considered (why gradient-boosted trees)

Model choice was **not** the source of the edge, so we deliberately used a simple,
robust learner and did not chase model complexity:

- **Linear (Ridge):** tested (original ensemble) — weaker; cannot represent the
  interactions (e.g. momentum conditional on drawdown) that motivate the approach.
- **Gradient-boosted trees (LightGBM):** chosen. State-of-the-art for small tabular
  data; XGBoost/CatBoost are equivalent. Shallow config (depth 3, 50 trees) is a
  deliberate anti-overfitting choice for ~250 funds/year.
- **Neural nets:** rejected — require far more data than we have; overfit here.
- **Factor / latent-factor models (Fama-French, IPCA):** a different question
  (explaining returns), not fund ranking.
- **Hierarchical Bayesian shrinkage:** the one conceptually attractive alternative
  (pooling across categories on small samples) — **now tested**
  (`tests/test_bayesian_shrinkage.py`): empirical-Bayes shrinkage of each per-category
  model toward a global all-category model **hurts** at every weight (edge 2.47%→
  1.50–2.17%, IR 1.00→0.58–0.77, worst-cohort +0.82%→+0.15%). Categories are genuinely
  different — skill is small-cap-concentrated (F6) — so pooling dilutes the signal. A
  full MCMC hierarchical-*linear* model remains untested (model-family-confounded).

Rationale: with a weak signal (IC ~0.09) and small samples, a more complex model
cannot create signal — it can only overfit. *Cf. Grinsztajn et al. (2022), on why
trees beat deep learning on tabular data.*

---

## 4. Negative results (kept deliberately)

Honest science includes what didn't work:
- **Fund-flow features** — no portfolio improvement (F8).
- **Alternative training targets** — no improvement (F11).
- **Learning-to-rank (LambdaMART)** — no robust gain over regression-then-rank; a
  single relevance-bucket setting spiked but failed the sensitivity sweep
  (`tests/test_learning_to_rank.py`).
- **Hierarchical shrinkage across categories** — hurts at every weight; skill is
  category-specific, so pooling dilutes it (`tests/test_bayesian_shrinkage.py`).
- **Holdings-based features** — not testable: the holdings star schema is not linked
  to our schemes (only 27% name-match, 57 funds with in-period snapshots). A
  data-engineering gap, not a modelling one.
- **Hyperparameter tuning / other model families** — deliberately avoided as
  overfitting-prone with low expected payoff.

These strengthen confidence that the 9-feature model is a **robust local optimum
given the currently-linkable data**.

---

## 5. Limitations

1. **Relative, not absolute** — beats same-category funds; does not time the market.
2. **One market, one era** — Indian equity, bull-heavy 2013–2025; needs external
   replication (other markets / regimes).
3. **Survivorship** — tested: rebuilding the benchmark with dead/merged funds costs
   only ~0.25%/yr (edge +2.47%→+2.22%, still 7/7). Residual: picks side (choosing
   only from survivors) needs a censored-label rebuild — second-order.
4. **Short passive-index history** — small/mid-cap edge not yet proven vs a passive
   index over a full cycle (index funds too young).
5. **Overlapping windows** inflate naive t-stats (addressed via HAC/bootstrap).
6. **Modest magnitude** — ~2.4% gross; costs/tax matter, hence the >12-month rule.

---

## 6. Future work (in priority order)

1. **Link the holdings data** (add `amc_alias`/`amc_id` to `fund_dim`) → test active
   share, concentration, peer-overlap features. Highest-potential unexplored lever.
2. **Add survivorship handling** (include dead/merged funds) to firm up all figures.
3. **External replication** on another market or regime for portability evidence.
4. **Full MCMC hierarchical-linear model** — the empirical-Bayes tree-shrinkage
   version was tested and hurt (skill is category-specific); a true Bayesian *linear*
   hierarchy is a different, model-family-confounded question if pursued.

---

## 7. Suggested paper framing

> *"Where Does Fund-Selection Skill Live? Machine Learning, Survivorship, and Null
> Controls in Indian Equity Mutual Funds."*

The contributions are **applications and case studies, not new methods** — the negative
control, HAC, and bootstrap are all standard. Specifically: **(i)** a documented case
where a *standard* label-permutation negative control, applied to a mutual-fund selection
backtest (where it's underused), overturns an apparent ML edge — with the honest caveat
that the passing construction was *selected* after it passed (residual selection risk,
mitigated only by the forward paper trade); **(ii)** India-specific evidence that
within-category selection skill exists but concentrates in high-dispersion categories;
and **(iii)** a data-quality cautionary case. Most other findings *replicate* known
results, which validates the data. Before submission, pull each cited paper and verify
the exact claim/year — and do **not** claim the method itself as novel.

---

### Key references
Carhart (1997); Chen, Hong, Huang & Kubik (2004); Berk & Green (2004); Frazzini &
Lamont (2008); Kosowski, Timmermann, Wermers & White (2006); Cremers & Petajisto
(2009); Harvey, Liu & Zhu (2016); Gu, Kelly & Xiu (2020); Grinsztajn, Oyallon &
Varoquaux (2022); Elton, Gruber & Blake (1996); S&P SPIVA India Scorecard.

*Bottom line: a modest, honest, defensible within-category fund-selection edge
(~+2.4% gross / +2.6% net), strongest where funds differ most — not an all-weather
alpha machine, and not limited by the choice of LightGBM.*
