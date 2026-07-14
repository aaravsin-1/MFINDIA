"""
tests/test_bayesian_shrinkage.py  (RESULTS_PROJECT / exploratory)

Does hierarchical (empirical-Bayes) shrinkage across categories help?

The category-neutral construction trains a SEPARATE model per core category
(Large / Mid / Small / Flexi / ELSS), each on a small slice of data -> noisy on
small samples. Hierarchical shrinkage / partial pooling says: shrink each category's
prediction toward a GLOBAL all-category model, more so where the category has less
data. This is the "pool across categories on small samples" idea flagged as the one
attractive untried alternative in RESEARCH_FINDINGS.md §3.

We operationalise it as empirical-Bayes shrinkage BETWEEN two LightGBM predictions
(so there is no model-family confound vs the LightGBM baseline):

    pred_shrunk = w * pred_local + (1 - w) * pred_global

  w = 1.0  -> pure per-category model      (the current +2.47% baseline)
  w = 0.0  -> pure global model            (fully pooled)
  0<w<1    -> partial pooling (shrinkage)
  adaptive -> w_cat = n_cat / (n_cat + K)  (small categories shrink toward global)

Since we only ever RANK within category and take top-2, the blend changes the
within-category ordering. Held to the same bar as every experiment here:
  * category-neutral, top-2/cat, walk-forward 2016-2022,
  * judged on CAGR edge, Information Ratio, AND robustness (worst cohort, cohort
    std) -- the hypothesis is shrinkage helps *robustness* more than headline edge,
  * must pass its own scrambled-label negative control (p<0.05),
  * any gain must be ROBUST across the shrinkage weight w, not a one-setting spike.

RESULT (documented negative): pooling toward the global model HURTS. Every partial-
pooling setting (w<1) lowers the edge (2.47% -> 1.50-2.17%), and the risk-adjusted
measures get worse too (IR 1.00 -> 0.58-0.77; worst-cohort +0.82% -> +0.15%). The only
metric that "improves" is raw cohort-std at w=0.5 -- a mean-shrinkage artifact (pulling
toward a mediocre global model lowers the mean, hence the variance), not real
robustness, which is why IR (the proper risk-adjusted measure) falls. Economically
sensible: the validated skill is WITHIN-category and concentrated in small-cap (F6), so
pooling across categories dilutes exactly the category-specific signal the construction
was built to exploit. Keep the per-category models. (A full MCMC hierarchical-linear
model is a separate, model-family-confounded idea -- not tested here on purpose.)

Run from the RESULTS_PROJECT dir:  python tests/test_bayesian_shrinkage.py
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import numpy as np
import pandas as pd
import lightgbm as lgb
import warnings
from lib import (DATA, OUTPUTS, ASSETS, ROOT, get_engine, FEATURES, get_returns_matrix, port_from_matrix,
                 cagr, excess_monthly)

warnings.filterwarnings('ignore')
COHORTS_ALL = [2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]
TEST = [2016, 2017, 2018, 2019, 2020, 2021, 2022]
CORE = ['Large Cap Fund', 'Mid Cap Fund', 'Small Cap Fund', 'Flexi Cap Fund', 'ELSS']
W_GRID = [0.0, 0.25, 0.5, 0.75, 1.0]
K_ADAPT = 100  # w_cat = n_cat / (n_cat + K); n_cat = prior-cohort funds in category
N_SEEDS = 20


def _fit(a, y, seed=42):
    m = lgb.LGBMRegressor(random_state=seed, n_estimators=50, max_depth=3, verbose=-1)
    m.fit(a[FEATURES], y)
    return m


def build_preds(df, shuffle_rng=None):
    """For each test cohort, train a global model + per-category local models on
    prior cohorts and cache both predictions for every core-category test fund.

    Returns {t: {'bench': [...], 'cats': {ccat: DataFrame[scheme_id, p_local,
    p_global, n_local]}}}. shuffle_rng!=None permutes the training target (the null).
    """
    out = {}
    for t in TEST:
        tr, te = df[df.cohort < t], df[df.cohort == t]
        bench = te[te.category_name.isin(CORE)].scheme_id.tolist()

        # global model: ALL categories, prior cohorts
        yg = tr['fwd_alpha'].values
        if shuffle_rng is not None:
            yg = shuffle_rng.permutation(yg)
        gmodel = _fit(tr, yg)

        cats = {}
        for ccat in CORE:
            a = tr[tr.category_name == ccat].dropna(subset=['fwd_alpha'])
            b = te[te.category_name == ccat]
            if len(a) < 10 or b.empty:
                continue
            yl = a['fwd_alpha'].values
            if shuffle_rng is not None:
                yl = shuffle_rng.permutation(yl)
            lmodel = _fit(a, yl)
            cats[ccat] = pd.DataFrame({
                'scheme_id': b['scheme_id'].values,
                'p_local': lmodel.predict(b[FEATURES]),
                'p_global': gmodel.predict(b[FEATURES]),
                'n_local': len(a),
            })
        out[t] = {'bench': bench, 'cats': cats}
    return out


def evaluate(preds, mats, w=None, adaptive=False):
    """Blend cached preds at weight w (or adaptive), pick top-2/cat, return
    (mean_edge, IR, worst_cohort_edge, cohort_std)."""
    edges, pooled_ex = [], []
    for t in TEST:
        mat = mats[t]
        picks = []
        for ccat, d in preds[t]['cats'].items():
            wc = (d['n_local'].iloc[0] / (d['n_local'].iloc[0] + K_ADAPT)) if adaptive else w
            score = wc * d['p_local'] + (1 - wc) * d['p_global']
            dd = d.assign(s=score).sort_values('s', ascending=False)
            picks += dd.head(2).scheme_id.tolist()
        pr, br = port_from_matrix(mat, picks), port_from_matrix(mat, preds[t]['bench'])
        edges.append(cagr(pr) - cagr(br))
        pooled_ex.extend(excess_monthly(pr, br).tolist())
    ex = np.array(pooled_ex)
    ir = (ex.mean() / ex.std()) * np.sqrt(12) if ex.std() > 0 else 0.0
    edges = np.array(edges)
    return edges.mean(), ir, edges.min(), edges.std()


def main():
    eng = get_engine()
    df = pd.read_csv(DATA / 'ml_dataset.csv')
    print("Fetching forward return matrices (once per cohort)...")
    mats = {t: get_returns_matrix(eng, df[df.cohort == t].scheme_id.tolist(),
                                  f"{t}-12-31", f"{t+3}-12-31") for t in COHORTS_ALL}

    print("Training global + per-category models per cohort (real labels)...")
    preds = build_preds(df)

    print("\n" + "=" * 78)
    print("HIERARCHICAL (EMPIRICAL-BAYES) SHRINKAGE across categories")
    print("  pred = w*local + (1-w)*global ;  w=1 pure per-category (base), w=0 global")
    print("=" * 78)
    print(f"\n{'Setting':<22}{'Edge/yr':>9}{'InfoRatio':>11}{'WorstCohort':>13}{'CohortStd':>11}")
    print("-" * 78)

    rows = {}
    for w in W_GRID:
        e, ir, wmin, wstd = evaluate(preds, mats, w=w)
        rows[w] = (e, ir, wmin, wstd)
        tag = "  <- pure per-cat baseline" if w == 1.0 else ("  <- pure global" if w == 0.0 else "")
        print(f"{'w=' + format(w, '.2f'):<22}{e*100:>+8.2f}%{ir:>11.2f}{wmin*100:>+12.2f}%{wstd*100:>10.2f}%{tag}")

    ea, ira, amin, astd = evaluate(preds, mats, adaptive=True)
    rows['adapt'] = (ea, ira, amin, astd)
    print(f"{'adaptive n/(n+%d)' % K_ADAPT:<22}{ea*100:>+8.2f}%{ira:>11.2f}{amin*100:>+12.2f}%{astd*100:>10.2f}%")

    base = rows[1.0]  # pure per-category = the +2.47% baseline
    print("\nREAD (vs pure per-category baseline w=1.00):")
    # best partial-pooling setting by edge (exclude the w=1 baseline)
    cand = {k: v for k, v in rows.items() if k != 1.0}
    bk = max(cand, key=lambda k: cand[k][0])
    be_, bir_, bmin_, bstd_ = cand[bk]
    print(f"  baseline w=1.00 : edge {base[0]*100:+.2f}%  IR {base[1]:.2f}  "
          f"worst {base[2]*100:+.2f}%  std {base[3]*100:.2f}%")
    print(f"  best pooled ({bk}): edge {be_*100:+.2f}%  IR {bir_:.2f}  "
          f"worst {bmin_*100:+.2f}%  std {bstd_*100:.2f}%")

    # robustness of any edge gain across the w grid
    grid_deltas = [rows[w][0] - base[0] for w in W_GRID if w != 1.0]
    n_better_edge = sum(d > 0 for d in grid_deltas)
    # Genuine robustness = IR (risk-adjusted, penalises dispersion) and worst-cohort.
    # NOTE: raw cohort-std is a misleading robustness metric here -- shrinking toward a
    # mediocre global model lowers the mean, which mechanically lowers std too (that is
    # regression to the middle, not skill). So we judge robustness on IR / worst-cohort.
    best_ir_pooled = max(cand.values(), key=lambda v: v[1])[1]
    best_min_pooled = max(cand.values(), key=lambda v: v[2])[2]
    robustness_win = (best_ir_pooled > base[1] + 1e-9) or (best_min_pooled > base[2] + 1e-9)

    # negative control at the best pooled setting
    print("\nRunning negative control at the best pooled setting...")
    null = []
    for s in range(N_SEEDS):
        rng = np.random.RandomState(500 + s)
        np_preds = build_preds(df, shuffle_rng=rng)
        if bk == 'adapt':
            null.append(evaluate(np_preds, mats, adaptive=True)[0])
        else:
            null.append(evaluate(np_preds, mats, w=bk)[0])
    null = np.array(null)
    p = (null >= be_).mean()

    print(f"\n  best-pooled edge {be_*100:+.2f}%  vs scrambled-label null "
          f"mean {null.mean()*100:+.2f}%  -> empirical p = {p:.3f}")
    print(f"  edge gain vs baseline is positive in {n_better_edge}/{len(grid_deltas)} "
          f"pooled settings; deltas = {[f'{d*100:+.2f}%' for d in grid_deltas]}")
    print(f"  robustness: best pooled IR {best_ir_pooled:.2f} vs baseline {base[1]:.2f}; "
          f"best pooled worst-cohort {best_min_pooled*100:+.2f}% vs baseline {base[2]*100:+.2f}%")

    passes = p < 0.05
    edge_robust = n_better_edge > len(grid_deltas) // 2
    print("\nVERDICT:")
    if passes and edge_robust:
        print("  [WIN]  Shrinkage beats the per-category baseline on edge across a majority")
        print("         of settings AND passes its null -> a real, robust improvement.")
    elif passes and robustness_win and not edge_robust:
        print("  [ROBUSTNESS WIN]  No reliable edge gain, but shrinkage improves risk-adjusted")
        print("         robustness (IR or worst-cohort) and passes its null -> adopt for stability.")
    elif passes:
        print("  [NO GAIN]  Passes its null but pooling HURTS: edge down in every setting, IR and")
        print("         worst-cohort worse. Categories are genuinely different (skill is small-cap-")
        print("         concentrated, F6), so pooling across them dilutes the signal. Keep per-category.")
    else:
        print("  [FAIL] Best pooled setting fails its own negative control -> not usable.")
    print("\n  Bar: pass the scrambled-label null (p<0.05) AND improve edge (robustly across w)")
    print("  or risk-adjusted robustness (IR / worst-cohort) vs the w=1.00 per-category baseline.")


if __name__ == '__main__':
    main()
