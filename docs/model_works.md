# How the Model Works — LightGBM, Our Data, and the Whole Pipeline

*A from-scratch, plain-English walkthrough of the machine-learning engine — what
data it eats, how LightGBM actually learns, and how a fund ends up with a score.
Every step links to the exact line of code so you can see it yourself.*

> File links point to files in this same folder (`RESULTS_PROJECT/`).

---

## 0. The 30-second mental model

We give the model a table. **Each row is one fund at one point in time**, described
by **9 numbers** (its returns, risk, size, fees, manager). We also tell it, for
historical rows, **what happened next** — did the fund beat its category over the
following 3 years. The model studies thousands of these and learns which
*combinations* of the 9 numbers tend to come before out-performance. Then, for
today's funds, it outputs a **score** = "how much this fund is likely to beat its
category." We rank funds by that score.

That's it. The rest of this document unpacks each piece.

---

## 1. The data we give it

### 1.1 The 9 input features (the "X")
Defined once in [lib.py:13](../src/lib.py#L13) and reused everywhere:

| # | Feature | Plain meaning | Built in code at |
|---|---|---|---|
| 1 | `hist_return` | trailing 3-yr total return | [prepare_features.py:114](../src/prepare_features.py#L114) |
| 2 | `hist_volatility` | how bumpy those returns were (annualised std) | [prepare_features.py:115](../src/prepare_features.py#L115) |
| 3 | `hist_hit_rate` | % of months it beat its category average | [prepare_features.py:116](../src/prepare_features.py#L116) |
| 4 | `max_drawdown` | worst peak-to-trough fall in the window | [prepare_features.py:111](../src/prepare_features.py#L111) |
| 5 | `aum_percentile` | fund size rank (0=smallest, 1=biggest) | [prepare_features.py:146](../src/prepare_features.py#L146) |
| 6 | `ter` | total expense ratio (annual fee) | [prepare_features.py:152](../src/prepare_features.py#L152) |
| 7 | `max_tenure_years` | longest-serving manager's tenure | [prepare_features.py:133](../src/prepare_features.py#L133) |
| 8 | `num_managers` | how many managers run it | [prepare_features.py:133](../src/prepare_features.py#L133) |
| 9 | `is_team` | 1 if more than one manager, else 0 | [prepare_features.py:164](../src/prepare_features.py#L164) |

These come straight out of the PostgreSQL database via SQL (monthly NAV prices → returns,
volatility, drawdown; separate queries for managers, AUM, TER), then merged into one
row per fund per cohort at [prepare_features.py:157-164](../src/prepare_features.py#L157-L164).

**Key rule: no peeking.** Every feature uses only data available *on the scoring
date*. Nothing from the future is in X.

### 1.2 The target — what we ask it to predict (the "y")
The target is **`fwd_alpha`** = the fund's **next-3-year return minus its own
category's average** next-3-year return. Built at
[prepare_features.py:92](../src/prepare_features.py#L92):

```python
fr['fwd_alpha'] = fr['fwd_return'] - fr['cat_avg_return']
```

Why *category-relative* and not raw return? Because we want the model to learn
**"is this a good fund vs its peers"**, not "will the market go up" (which it can't
know). A `fwd_alpha` of +0.05 means "beat its category by 5% over 3 years."

*(The category average is computed robustly — impossible NAV values are filtered at
[prepare_features.py:76](../src/prepare_features.py#L76) and the average is 5%-trimmed at
[prepare_features.py:83](../src/prepare_features.py#L83) — this is the data-bug fix
described in `FINDINGS.md`.)*

### 1.3 The shape of the training table
~1,841 rows (funds × years 2013–2022), 9 feature columns + 1 target column. A
snippet lives in `ml_dataset.csv`. Conceptually:

```
scheme_name          hist_return  ...  aum_percentile  max_drawdown | fwd_alpha (y)
Quant Small Cap Fund     0.62      ...      0.18           -0.31     |   +0.14
HDFC Large Cap Fund      0.41      ...      0.95           -0.19     |   -0.02
...
```

The model learns the mapping from the left block (X) to the right column (y).

---

## 2. LightGBM, built up from nothing

LightGBM is a **gradient-boosted decision-tree** model. Let's assemble that phrase
one word at a time.

### 2.1 A single decision tree
A decision tree is just a flowchart of yes/no questions that ends in a number.
Example (a made-up tree predicting `fwd_alpha`):

```
                Is max_drawdown worse than -30%?
                  /                        \
                YES                         NO
                 |                           |
      Is aum_percentile > 0.8?      Is manager tenure > 5 yrs?
        /            \                 /              \
      YES            NO              YES              NO
   predict -0.04  predict +0.01   predict +0.06   predict +0.02
```

You drop a fund in at the top, answer the questions, and land on a predicted number.
The tree "learns" by choosing the questions (which feature, which threshold) that
best separate high-alpha funds from low-alpha funds.

**A single shallow tree is weak** — it can only ask a few questions, so it's a rough
guess. That's intentional (see boosting next).

**`max_depth=3`** in our config ([train_model.py:20](../src/train_model.py#L20)) means each
tree asks at most 3 questions deep → it can capture up to a 3-way *interaction*
(e.g. "small fund **and** low drawdown **and** veteran manager"), but no more. This
is what lets the model learn *context* that single-factor rules miss.

### 2.2 Boosting — many weak trees, each fixing the last one's mistakes
Instead of one big tree, boosting builds **many small trees in sequence**, where
each new tree tries to correct the **leftover error (residual)** of all the trees
before it.

Walk through it:

1. **Start** with a baseline guess for every fund = the average `fwd_alpha` (≈ 0).
2. **Tree 1** looks at the errors (actual − baseline) and learns a rough pattern,
   e.g. "smaller funds tended to have higher alpha." Add its correction.
3. Now every fund has a *residual* — how wrong we still are.
4. **Tree 2** fits *those residuals*, finding the next pattern (e.g. "…but only if
   drawdown wasn't severe"). Add its correction.
5. Repeat. Each tree nudges the prediction closer.

Final prediction = **baseline + tree₁ + tree₂ + … + tree₅₀** (each scaled down by a
learning rate so no single tree dominates). We use **`n_estimators=50`** trees
([train_model.py:20](../src/train_model.py#L20)).

Tiny numeric intuition for one fund whose true alpha is +0.06:

| Step | Correction added | Running prediction | Remaining error |
|---|---|---|---|
| baseline | +0.00 | 0.00 | 0.06 |
| + tree 1 | +0.03 | 0.03 | 0.03 |
| + tree 2 | +0.02 | 0.05 | 0.01 |
| + tree 3 | +0.008 | 0.058 | 0.002 |
| … | … | → 0.06 | → 0 |

The forest of small trees **converges** on a good prediction that no single tree
could make.

### 2.3 Why "gradient"?
"Gradient boosting" just means: each tree is fit to the **gradient of the loss** —
the mathematical direction that reduces error fastest. For the squared-error loss we
effectively use, that gradient *is* the residual (actual − predicted). So "fit the
residuals" and "follow the gradient" are the same thing here. The word "gradient"
sounds fancy but the intuition in 2.2 is exactly it.

### 2.4 What makes it specifically *LightGBM* (vs plain gradient boosting)
LightGBM is a fast, modern implementation with two clever tricks — you don't need
them to use it, but they're why it's the industry default for tabular data:
- **Histogram binning:** instead of testing every possible split value, it buckets
  each feature into ~255 bins → dramatically faster with almost no accuracy loss.
- **Leaf-wise growth:** it grows the branch that reduces error the most next, rather
  than growing the tree evenly — more accurate for a given number of splits.

For us the practical benefits: it trains in **milliseconds** on our ~1,500 rows,
handles the 9 features on different scales without any normalisation, and is
naturally good at **interactions** — the whole point of the project.

### 2.5 Our exact settings and why
From [train_model.py:20](../src/train_model.py#L20):
```python
lgb.LGBMRegressor(random_state=42, n_estimators=50, max_depth=3, verbose=-1)
```
- `n_estimators=50` — 50 trees. Enough to learn the signal, few enough to not
  memorise noise on a small dataset.
- `max_depth=3` — shallow trees. Deliberately **weak learners** → captures up to
  3-way interactions, resists overfitting.
- `random_state=42` — fixes the randomness so results **reproduce exactly**.
- `Regressor` (not Classifier) — we predict a continuous number (`fwd_alpha`), then
  rank by it.

**Deliberately simple.** With only ~250 funds/year, a bigger/deeper model would fit
noise and fail out-of-sample — exactly the trap the validation guards against.

---

## 3. Training — turning the table into a model

The whole training step is 4 lines in
[train_model.py:18-22](../src/train_model.py#L18-L22):

```python
train_df = df[df['cohort'] < TRAIN_BEFORE]          # only past data (no peeking)
model = lgb.LGBMRegressor(random_state=42, n_estimators=50, max_depth=3, verbose=-1)
model.fit(train_df[FEATURES], train_df['fwd_alpha']) # learn X -> y
joblib.dump(model, 'model.pkl')                      # save the trained model
```

`.fit(X, y)` is where all of Section 2 happens: it builds the 50 trees. `model.pkl`
is the frozen result — the 50 trees and their thresholds.

**The golden rule — walk-forward.** We only ever train on cohorts *before* the year
we score, so the test is genuinely out-of-sample. In the validation harness this is
the line [run_validation.py:60](../validation/run_validation.py#L60) (`cohort < t`), and in the
production model it's `cohort < 2022` so the 2022 snapshot stays unseen.

---

## 4. Scoring and ranking — from model to a fund list

In the screener [manager_quality_screener.py:71](../src/manager_quality_screener.py#L71):
```python
df['ml_score'] = model.predict(df[FEATURES])   # each fund gets a predicted alpha
```
`.predict()` runs every fund down all 50 trees and sums the corrections → one number
per fund.

Then we turn scores into a **within-category percentile** (the axis where the model
has skill) at [manager_quality_screener.py:72](../src/manager_quality_screener.py#L72):
```python
df['Quality'] = (df.groupby('category_name')['ml_score'].rank(pct=True) * 100)...
```

And the validated strategy picks the **top 2 per category**
([manager_quality_screener.py:75-78](../src/manager_quality_screener.py#L75-L78)). In the
back-test the equivalent step is "sort by score, take the top" at
[run_validation.py:65](../validation/run_validation.py#L65).

---

## 5. Explaining a score — SHAP

A score alone is a black box, so we crack it open with **SHAP**, which attributes
each fund's score to its individual features
([manager_quality_screener.py:90-91](../src/manager_quality_screener.py#L90-L91)):
```python
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(df[FEATURES])
```
For each fund SHAP says, e.g., "`max_drawdown` pushed this score **+0.03**,
`aum_percentile` pushed it **−0.01**." We keep the top 2 drivers and translate them
into English (`[+] Excellent downside protection`, `[-] Fund size acting as a
drag`) via the dictionary at
[manager_quality_screener.py:31-54](../src/manager_quality_screener.py#L31-L54).

SHAP is theoretically grounded (it's based on Shapley values from game theory —
"how much did each player/feature contribute to the outcome"), which is why it's
trusted for model explanations.

---

## 6. Which features actually matter (learned, not assumed)

After training, LightGBM can report how often each feature was used to split — the
"feature importance." We print the top 3 each year at
[run_validation.py:67-68](../validation/run_validation.py#L67-L68). Across years the model leans on
`max_drawdown` (top-3 in 6/7 folds), `hist_return` (5/7), `aum_percentile` (5/7), and
`max_tenure_years` (2/7) — stable, not random.

Importance here is measured as **split-frequency** across the walk-forward folds; the
final `model.pkl` ranked by **gain** (error actually reduced) leads instead with
`hist_return` and `aum_percentile` — the same top cluster, a different lens.
`max_drawdown` is a workhorse *splitter* (branched on often, low gain per split),
while `hist_return` makes fewer but higher-gain cuts; `aum_percentile` is top-tier on
both metrics and every fold. `is_team` is **unused (0%) under both** — fully redundant
with `num_managers`, so the model could drop to 8 features with no loss. (The deeper,
portfolio-level test of *which feature truly drives returns* lives in the validation
docs; here the point is just: importance is measured, not hand-picked.)

---

## 7. Why a tree model at all? (vs a simple formula)

A linear formula (`score = a·return + b·fee + …`) assumes each feature helps by a
fixed amount regardless of the others. But our whole thesis is that **context
matters** — high momentum is good *only if* drawdowns are contained. A linear model
literally cannot express "only if"; a tree can, because its branches are conditional
("if drawdown < −30% **then** look at momentum differently"). That conditional,
interaction-capturing ability is the entire reason LightGBM is the right tool here.

---

## 8. The end-to-end flow in one picture

```
 PostgreSQL (NAVs, AUM, TER, managers)
        │   prepare_features.py  (SQL → features + fwd_alpha target, with the NAV fix)
        ▼
 ml_dataset.csv   (1,841 rows: 9 features + target)
        │   train_model.py  (.fit → 50 boosted trees, past data only)
        ▼
 model.pkl        (the frozen model)
        │   manager_quality_screener.py  (.predict → score → within-category rank → top-2/category)
        ▼
 fund_screener_results.csv  (+ SHAP "Why" for each fund)
```

---

## 9. Quick FAQ

**"Is it just curve-fitting?"** Guarded against three ways: shallow/small model,
strict walk-forward (Section 3), and the negative-control + robustness tests in
`FINDINGS.md`.

**"Does it use future data?"** No — features are as-of the scoring date; training
uses only earlier cohorts.

**"Why does it output a tiny number like 0.03, not a %?"** That *is* the predicted
edge over category (≈ +3% over 3 years). We only use its **rank**, not its exact
value, so the absolute scale doesn't matter.

**"What would break it?"** Feeding it corrupted data (see the NAV bug) or a market
regime unlike anything in training. That's why the pipeline filters bad NAVs and why
we re-validate on new years.

---

### Where to look next
- The data + fix: [prepare_features.py](../src/prepare_features.py)
- The model in 4 lines: [train_model.py](../src/train_model.py)
- Honest testing of whether it works: [run_validation.py](../validation/run_validation.py) and `FINDINGS.md`
- The plain-English, non-technical version: `EXPLAINER.md`
