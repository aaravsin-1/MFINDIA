# Exploratory feature experiments

Attempts to **grow the validated edge** by adding data beyond the core 9 features.
Everything here is held to the same bar as the main pipeline: a new feature only
"counts" if the augmented model beats its **own scrambled-label negative control**.
Negative results are kept — they're evidence the 9-feature model isn't leaving
obvious money on the table.

---

## 1. Fund-flow features — TESTED, no improvement (`test_flow_features.py`)

**Idea:** investor flows (money in/out, net of performance) may predict returns —
the "smart money / dumb money" literature (Berk & Green 2004; Frazzini–Lamont).

**Built** from `v_scheme_aum` + NAV (100% coverage of our universe):
- `aum_growth_1y` — trailing 1-yr change in AUM
- `flow_1y` — *organic* flow = AUM growth stripped of the fund's own return

**Result (category-neutral strategy, walk-forward 2016–2022):**

| Model | Gross edge | Negative control |
|---|---|---|
| Baseline (9 features) | +2.47%/yr | — |
| Augmented (9 + 2 flow) | **+2.32%/yr** | passes (p=0.000) |
| Change from flows | **−0.15%/yr** | — |

**Flows do NOT improve the edge** — they slightly hurt it.

**Why (diagnosed):** flow *does* carry a weak, real, statistically significant
signal — but a **negative** one:

| Feature | IC vs fwd_alpha |
|---|---|
| `flow_1y` | **−0.063** (p=0.007) |
| `aum_growth_1y` | −0.061 (p=0.009) |
| `aum_percentile` (already used) | −0.084 (p<0.001) |

High inflows → **lower** future alpha — the classic **return-chasing "dumb money"**
effect (money floods hot funds, which then mean-revert / hit capacity limits). This
is a genuine finding and matches the academic literature. **But** it points the same
direction as, and is weaker than, the **AUM signal we already use** — so it adds no
incremental value to the top-2 selection and just injects noise.

**Decision:** keep the simpler 9-feature model. (Bonus finding: the dumb-money
effect is present in Indian equity funds, but already captured by structural size
features.)

---

## 2. Target definition — TESTED, current target already best (`test_target_definition.py`)

**Idea:** train the model to predict a *different* quantity than raw 3-yr alpha — a
risk-adjusted or downside target might pick funds with better risk-adjusted returns
/ shallower drawdowns (valuable for the Conservative bucket).

**Targets compared** (all category-neutral, top-2/cat, evaluated on edge **and**
information ratio **and** portfolio max drawdown):

| Target | Edge/yr | Info Ratio | Port. MaxDD | Neg-control |
|---|---|---|---|---|
| **T0 raw alpha (current)** | **+2.47%** | **1.00** | **−18.5%** | passes (p=0.000) |
| T1 rank of alpha | +2.14% | 0.92 | −19.0% | passes |
| T2 forward Sharpe | +2.02% | 0.95 | −18.8% | passes |
| T3 forward Calmar (downside) | +2.49% | 0.93 | −18.5% | passes |

**Result: no alternative target improves anything.** All are legitimate (pass the
null), but the **current raw-alpha target already has the best information ratio
(1.00) and the equal-best drawdown** — the risk-adjusted targets did *not* lift IR
or shrink drawdown as hoped; they slightly underperform.

**Why:** (a) the features already include volatility and drawdown, so the raw-alpha
model *implicitly* accounts for risk; (b) dividing by *forward* Sharpe/Calmar adds
estimation noise to the label without adding signal; (c) rank targets discard
magnitude information. Risk is better handled where it already is — in the separate
**Risk engine** of the screener — not by contorting the training target.

**Decision:** keep the raw-alpha target. (The experiment confirms it's a
well-chosen default, not an arbitrary one.)

---

## 4. Survivorship stress test — PASSED (`test_survivorship.py`)

Rebuilds the benchmark from **all funds alive at t** (dead/merged funds included,
reinvested at benchmark after they vanish) instead of survivors only.

- Benchmark survivorship bias: **+0.25%/yr** (small; dead funds slightly *raise* the
  benchmark — Indian "deaths" are mostly mergers into larger funds).
- Edge: **+2.47% → +2.22%** survivorship-adjusted, **still 7/7 cohorts positive**.
- By-product: the raw-DB universe re-imported the HSBC Midcap +4,367% NAV error, so
  the same sanity filter had to be applied — concrete proof the upstream data fix
  matters. Residual: picks still come from survivors (need a forward label);
  second-order, needs a censored-label dataset rebuild to fully close.

---

## 3. Holdings-based features — NOT PURSUED (data-infeasible)

**Idea:** active share, sector concentration, top-10 weight, peer-overlap, cash %
— from the 2.49M-row `portfolio_holding_fact` star schema.

**Blocker:** the holdings layer (`fund_dim`) is **not FK-linked** to our schemes and
must be name-matched. Reality check:
- Only **27%** of our funds (76/283) name-match `fund_dim`.
- Only **57 funds** have holdings snapshots in 2013–2023.

Building features on ~1/4 of the universe (concentrated in recent years) would inject
more missing-data bias than signal. **Not pursued** until the holdings→scheme linkage
is properly resolved (see DATABASE.md §7: add `amc_alias` entries / an `amc_id` FK to
`fund_dim`). This is a data-engineering task, not a modelling one.

---

## 5. Learning-to-rank loss — TESTED, no robust gain (`test_learning_to_rank.py`)

**Idea:** the production model is an `LGBMRegressor` on raw `fwd_alpha` whose output
we only ever consume as a *rank*. The theoretically-aligned tool is **LambdaMART
(`LGBMRanker`)**, which optimises rank ordering (NDCG) directly per query group
(cohort × category). Unlike the rank-*target* T1 in §2 (which discarded magnitude and
lost), LambdaMART keeps pairwise magnitude via NDCG-weighted gradients — so it's a
genuinely different experiment.

**Result (category-neutral, top-2/cat, walk-forward 2016–2022):**

| Setting | Edge/yr | IR | vs T0 |
|---|---|---|---|
| **T0 regressor (base)** | **+2.47%** | **1.00** | — |
| Ranker N_REL=2 | +2.05% | 0.97 | −0.43% |
| Ranker N_REL=3 | +2.20% | 0.94 | −0.27% |
| Ranker **N_REL=4** | **+3.29%** | **1.35** | **+0.81%** |
| Ranker N_REL=5 | +2.54% | 1.03 | +0.07% |
| Ranker N_REL=8 | +2.37% | 0.97 | −0.10% |

**A single setting (N_REL=4) beats T0 by +0.81%/yr and passes its own negative
control (p=0.000) — but it is a hyperparameter artifact.** Across the sensible range
of relevance-bucketing the ranker beats T0 in only **2/5** settings and clusters
around the regressor's +2.47% (mostly negative). Had we picked N_REL=3 or 5 we'd have
concluded "no gain."

**Why:** query groups are tiny (~10–50 funds per cohort×category, ~35 groups total)
and the signal is weak (IC~0.09), so LambdaMART's ordering advantage has little to
bite on — exactly the prior. **Decision: keep the simpler regressor.** This is also a
worked example of the red-team discipline catching a single-config false positive
(cf. the original prototype's unseeded negative control in `FINDINGS.md` §1.2).

---

## 6. Hierarchical Bayesian shrinkage — TESTED, no gain (`test_bayesian_shrinkage.py`)

**Idea:** the category-neutral construction trains a separate model **per category** on
a small data slice. Hierarchical shrinkage / partial pooling should stabilise those
small-sample models by shrinking each toward a **global all-category model**, more so
where a category has less data. Flagged in `RESEARCH_FINDINGS.md` §3 as the one
attractive untried alternative. Operationalised as empirical-Bayes shrinkage between two
LightGBM predictions (no model-family confound): `pred = w·local + (1−w)·global`.

**Result (category-neutral, top-2/cat, walk-forward 2016–2022):**

| Setting | Edge/yr | IR | Worst cohort | vs baseline |
|---|---|---|---|---|
| w=0.00 (pure global) | +1.97% | 0.74 | +0.15% | −0.50% |
| w=0.25 | +1.92% | 0.67 | +0.15% | −0.55% |
| w=0.50 | +2.17% | 0.75 | +0.15% | −0.30% |
| w=0.75 | +1.50% | 0.58 | +0.15% | −0.97% |
| **w=1.00 (pure per-category, base)** | **+2.47%** | **1.00** | **+0.82%** | — |
| adaptive n/(n+100) | +2.13% | 0.77 | +0.15% | −0.34% |

**Pooling hurts on every meaningful metric** — edge down in **0/4** pooled settings,
IR 1.00→0.58–0.77, worst-cohort +0.82%→+0.15%. (Raw cohort-std dips slightly at w=0.5,
but that's a mean-shrinkage artifact — pulling toward a mediocre global model lowers the
mean *and* the variance; IR, the proper risk-adjusted measure, falls.)

**Why:** the validated skill is **within-category and small-cap-concentrated** (F6), so
pooling across categories dilutes exactly the category-specific signal the construction
exists to exploit. **Decision: keep the per-category models.** (A full MCMC
hierarchical-linear model is a separate, model-family-confounded question, not tested
here.)

---

## 7. De-tilted features — TESTED, IC-only (no real portfolio gain) (`test_detilted_features.py`)

**Idea / question raised:** `strengthen_edge.py` reports out-of-sample rank IC rising
from **+0.09** (raw features) to **+0.18** when features are rank-transformed within
cohort × category ("de-tilted", encoding V2). But that +0.18 was only ever used to
*measure* IC — the actual +2.37% category-neutral portfolio uses **raw** features. Does
feeding de-tilted features into the real top-2/category construction beat raw?

**Result (category-neutral, top-2/cat, walk-forward 2016–2022):**

| Feature encoding | Edge/yr | IR | Beats RAW | vs RAW |
|---|---|---|---|---|
| **RAW (current)** | **+2.47%** | **1.00** | — | — |
| V1 cohort-ranked | +3.20% | 1.23 | 4/7 cohorts | +0.73% |
| **V2 cohort×cat (de-tilted)** | +2.63% | 1.08 | **3/7 cohorts** | **+0.16%** |

**De-tilting (V2) is IC-only.** Its IC roughly *doubled* (0.09→0.18) but the portfolio
edge moved only **+0.16%/yr** and it beats RAW in just **3/7** cohorts (worse than a
coin flip). **This confirms the "+0.18 is optimistic" label with a portfolio number:**
a better IC did not become better picks. Mechanistically, the pipeline *already* ranks
within category on the **output** (Quality = within-category percentile; top-2/cat), so
rank-transforming the **inputs** within category is largely redundant — the IC jump was
the metric flattering the axis it was built for. **Keep RAW features.**

**Honest bonus lead:** V1 (cohort-ranked, *not* de-tilting) is larger — +0.73%/yr,
IR +0.23 — but only 4/7 cohorts and a single untested config. Per this folder's own
discipline (cf. the ranker's one-config spike, §5), it is **not** claimed as a win; it
is flagged as the one lead worth a full robustness battery (portfolio-size sweep,
per-cohort, HAC/bootstrap) before belief.

---

## 8. V1 cohort-ranked features — robustness battery: MIRAGE (`test_v1_robustness.py`)

**Follow-up to §7:** V1 (rank-transform the 9 features *within cohort*, across all
categories) beat RAW by +0.73%/yr in one run. Before believing it, we ran the same
battery the headline edge cleared. The decisive object is the **paired improvement**
(V1 picks − RAW picks), because "V1 beats the benchmark" is not the claim (so does RAW).

| Battery test | Result | Verdict |
|---|---|---|
| Portfolio-size sweep k=1–5 | V1>RAW at **5/5** k (delta +1.34%→+0.17%, shrinks with k) | ok |
| Per-cohort (k=2) | V1>RAW in **4/7** cohorts; sign test **p=0.50** | **FAIL** |
| V1's *own* edge vs benchmark | HAC t=3.79 — significant (V1 is a valid strategy itself) | ok |
| **Improvement (V1−RAW) significance** | naive t=2.06 (p=0.04) but **HAC t=1.47 (p=0.14)**; bootstrap 95% CI **[−0.65%, +2.04%]**, P(≤0)=0.14 | **FAIL** |

**Verdict: [MIRAGE / WITHIN NOISE].** The size sweep looked encouraging (5/5), but the
improvement over RAW is **not** consistent across cohorts (coin-flip 4/7) and **not**
significant once overlapping 3-yr windows are corrected — the marginal naive t=2.06 is
exactly the overlap-inflation trap the project warns about, and HAC/bootstrap kill it.
The +0.73% was driven by three bull cohorts (2019–2021) against a bad 2018 (−2.46%),
i.e. likely a regime/style wobble, not skill. **Keep RAW features.** (Note V1's *own*
edge is significant — it's a legitimate alternative encoding — but it is not a
*demonstrable improvement* on RAW, so there is no reason to add the complexity.)

That makes **four** metric-level "wins" this cycle (ranker, shrinkage, de-tilting, V1)
that all evaporated under a proper portfolio + significance check — strong convergent
evidence the raw-feature per-category model is a genuine local optimum.

---

## 9. Retail list quality — de-tilted/cohort-ranked features WIN (`test_list_quality.py`)

**Different product, different question.** §5–§8 all tested the **top-2 strategy**, which
consumes only the tip of each category's ranking — so encoding gains in the middle of
the list were wasted. A **retail "rate every fund" list** uses the *whole* ranking, so
overall ranking quality (what IC measures) matters here. Metric: out-of-sample
**within-category quintile spread** of realised `fwd_alpha` — do funds rated top-20% of
their category actually beat funds rated bottom-20%? (Global model, as the live
screener uses; computed from realised `fwd_alpha`, no portfolio/DB.)

**Result (top-minus-bottom quintile spread, over 3y, category-relative):**

| Encoding | Spread | Monotone | Cohorts +ve | Wider than RAW across buckets |
|---|---|---|---|---|
| **RAW (current list)** | **+7.8pp** | 4/4 | 7/7 | — |
| V2 de-tilted (cohort×cat) | +12.6pp | 4/4 | 7/7 | 4/4 bucket counts |
| **V1 cohort-ranked** | **+13.1pp** | 4/4 | 7/7 | 4/4 bucket counts |

**Both alt encodings give a ~60% wider, monotone spread, positive in all 7 cohorts, and
robust across bucket counts (3/4/5/10)** — permutation p=0.000. Unlike the four earlier
mirages, this **survives its relevant test** because IC and the objective are finally
aligned: a list uses the whole ranking. (Note the beautiful consistency: V1 was a
*mirage for the top-2 strategy* — §8 — yet *wins for the list*. Same encoding, opposite
verdict, because top-2 uses only the tip where V1≈RAW, while the list uses the whole
order where V1 genuinely ranks better.)

**Caveats (real, must be stated):** (i) the per-cohort *improvement over RAW* is 6/7 for
V1 (sign p=0.06) — aggregate is strong but per-cohort is under-powered on 7 points, so
confirm on live/next cohorts; (ii) even +13pp is a **quintile-level** tilt — fund-level
ordering is still noisy (Spearman ~0.15), so a retail product must show **tiers/bands,
not a precise 1–N ranking**, and keep the Risk/horizon overlay.

**Decision → two products:** **STRATEGY list** = top-2/category on **RAW** features
(validated, +2.37%/yr); **RETAIL list** = full within-category ranking on an **alt
encoding** (V1/V2, ~+13pp quintile spread), framed as tiers with the risk overlay.

---

## Takeaway for the "did we search exhaustively?" question
We probed every legitimate axis — **features** (flows: real but redundant; holdings:
blocked by a fixable data-linkage gap, not modelling), **feature encoding** (§7
de-tilting IC-only; §8 V1 cohort-ranked was a mirage under the full battery), the
**training target** (§2: raw alpha already best), the **learning objective** (§5:
learning-to-rank gives no robust gain), and the **model architecture** (§6:
hierarchical shrinkage across categories hurts — the skill is category-specific). All
came up empty or infeasible. So the 9-feature per-category regressor on raw features is
a **robust local optimum given the currently-linkable data**, and the clearest path to
a *bigger* edge runs through **linking the holdings data**, not through more
feature/encoding/target/loss/architecture tuning.

Four separate metric-level "wins" (ranker §5, shrinkage §6, de-tilting §7, V1 §8) all
evaporated under a proper portfolio + overlap-corrected significance check — convergent
evidence the **top-2 strategy** construction is not leaving easy money on the table.

**The one real win is product-specific (§9):** for a *retail full-list* product (not the
top-2 strategy), de-tilted/cohort-ranked features give a materially wider, monotone,
bucket-count-robust within-category spread (~+13pp vs +7.8pp). It survives because it is
the first encoding tested on the use case IC actually governs — the whole ranking. Hence
two products: RAW top-2 for the strategy list, an alt encoding for the retail list.

*Run from the RESULTS_PROJECT dir:* `python tests/test_flow_features.py`
