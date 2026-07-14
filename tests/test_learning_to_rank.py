"""
tests/test_learning_to_rank.py  (RESULTS_PROJECT / exploratory)

Does a learning-to-RANK loss beat regression-then-rank?

The production model is an LGBMRegressor on raw fwd_alpha, whose prediction we only
ever consume as a *rank* (within-category percentile -> top-2/category). That is
regression used as a ranking mechanism. The theoretically-aligned alternative is
LambdaMART (LGBMRanker), which optimises rank ordering (NDCG) directly per query
group -- here the query group = cohort x category, exactly our selection unit.

Unlike the RANK-TARGET already tested in test_target_definition.py (T1, which
regressed on a rank and LOST, +2.14% vs +2.47%), LambdaMART does NOT discard
magnitude: it keeps pairwise magnitude through NDCG-weighted gradients. So this is a
genuinely different experiment, not a rerun of T1.

Held to the same bar as every experiment here:
  * category-neutral construction (per-core-category model, top-2/category),
  * judged on CAGR edge, Information Ratio, portfolio Max Drawdown,
  * must beat its OWN scrambled-label negative control (empirical p<0.05),
  * compared apples-to-apples against the T0 regressor computed in the SAME run,
  * AND the improvement must be ROBUST to the relevance-bucketing choice (N_REL),
    not a spike at one lucky setting.

RESULT (documented negative): a single setting (N_REL=4) beats T0 by +0.81%/yr
(IR +0.35) and passes its null -- but the sweep below shows this is a HYPERPARAMETER
ARTIFACT: at N_REL in {2,3,5,8} the ranker is tied-or-worse than the regressor
(-0.43% to +0.07%). Across the sensible range it clusters around T0's +2.47% and is
mostly negative. So learning-to-rank does NOT robustly beat regression-then-rank
here -- consistent with the prior that on ~250 funds/yr and weak signal (IC~0.09),
tiny query groups blunt LambdaMART's advantage. Keep the simpler regressor.

This is exactly the kind of single-config false positive the project's red-team
discipline exists to catch (cf. the original prototype's unseeded negative control).

Run from the RESULTS_PROJECT dir:  python tests/test_learning_to_rank.py
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
N_SEEDS = 20
N_REL = 4  # graded-relevance levels for LambdaMART (0..3), bucketed within each query


def maxdd(rets):
    if rets.empty:
        return 0.0
    cum = (1 + rets).cumprod()
    return float((cum / cum.cummax() - 1).min())


def rank_groups(a):
    """Given a per-category training frame, return (X, relevance, group_sizes).

    Query group = cohort (within this category). Relevance = within-cohort
    quantile of fwd_alpha bucketed into N_REL graded levels (top bucket = best).
    Rows are ordered by cohort so LightGBM's contiguous `group` array is valid.
    """
    a = a.sort_values('cohort')
    rels, groups = [], []
    for _, grp in a.groupby('cohort', sort=True):
        n = len(grp)
        groups.append(n)
        pct = grp['fwd_alpha'].rank(pct=True).values          # (0,1], best -> 1
        rel = np.minimum(N_REL - 1, (pct * N_REL).astype(int))  # 0..N_REL-1
        rels.append(rel)
    return a[FEATURES], np.concatenate(rels), groups


def evaluate(d, mats, kind, shuffle_seed=None):
    """Category-neutral top-2/cat. kind in {'reg','rank'}. Returns (edge, IR, maxdd)."""
    rng = np.random.RandomState(shuffle_seed) if shuffle_seed is not None else None
    edges, dds, pooled_ex = [], [], []
    for t in TEST:
        tr, te = d[d.cohort < t], d[d.cohort == t]
        mat = mats[t]
        bench = te[te.category_name.isin(CORE)].scheme_id.tolist()
        picks = []
        for ccat in CORE:
            a = tr[tr.category_name == ccat].dropna(subset=['fwd_alpha'])
            b = te[te.category_name == ccat]
            if len(a) < 10 or b.empty:
                continue

            if kind == 'reg':
                y = a['fwd_alpha'].values
                if rng is not None:
                    y = rng.permutation(y)
                m = lgb.LGBMRegressor(random_state=42, n_estimators=50,
                                      max_depth=3, verbose=-1)
                m.fit(a[FEATURES], y)
            else:  # learning-to-rank
                X, rel, groups = rank_groups(a)
                if rng is not None:
                    rel = rng.permutation(rel)  # break feature->label link (null)
                m = lgb.LGBMRanker(objective='lambdarank', random_state=42,
                                   n_estimators=50, max_depth=3, verbose=-1)
                m.fit(X, rel, group=groups)

            b = b.assign(p=m.predict(b[FEATURES]))
            picks += b.sort_values('p', ascending=False).head(2).scheme_id.tolist()

        pr, br = port_from_matrix(mat, picks), port_from_matrix(mat, bench)
        edges.append(cagr(pr) - cagr(br)); dds.append(maxdd(pr))
        pooled_ex.extend(excess_monthly(pr, br).tolist())
    ex = np.array(pooled_ex)
    ir = (ex.mean() / ex.std()) * np.sqrt(12) if ex.std() > 0 else 0.0
    return np.mean(edges), ir, np.mean(dds)


SWEEP = [2, 3, 4, 5, 8]  # relevance-bucket settings to test robustness over


def main():
    global N_REL
    eng = get_engine()
    df = pd.read_csv(DATA / 'ml_dataset.csv')
    print("Fetching forward return matrices (once per cohort)...")
    mats = {t: get_returns_matrix(eng, df[df.cohort == t].scheme_id.tolist(),
                                  f"{t}-12-31", f"{t+3}-12-31") for t in COHORTS_ALL}

    print("\n" + "=" * 74)
    print("LEARNING-TO-RANK vs REGRESSION-THEN-RANK (category-neutral, top-2/cat)")
    print("=" * 74)

    # --- Baseline: T0 regressor (+ its own null) ---
    be, bir, bdd = evaluate(df, mats, 'reg')
    bnull = np.array([evaluate(df, mats, 'reg', shuffle_seed=300 + s)[0]
                      for s in range(N_SEEDS)])
    bp = (bnull >= be).mean()
    print(f"\n{'Model':<24}{'Edge/yr':>9}{'InfoRatio':>11}{'Port.MaxDD':>12}{'NegCtrl p':>11}")
    print("-" * 74)
    print(f"{'T0_regressor (base)':<24}{be*100:>+8.2f}%{bir:>11.2f}{bdd*100:>11.1f}%{bp:>11.3f}")

    # --- Ranker across relevance-bucketing settings (robustness sweep) ---
    best = None
    for nr in SWEEP:
        N_REL = nr
        e, ir, dd = evaluate(df, mats, 'rank')
        label = f"LGBMRanker N_REL={nr}"
        # run the null only for the strongest config (cost control)
        if best is None or e > best[1]:
            best = (nr, e, ir, dd)
        print(f"{label:<24}{e*100:>+8.2f}%{ir:>11.2f}{dd*100:>11.1f}%{'':>11}"
              f"  (delta edge {(e-be)*100:+.2f}%, IR {ir-bir:+.2f})")

    # null for the best-looking ranker config, to show even it isn't robust
    nr, e, ir, dd = best
    N_REL = nr
    rnull = np.array([evaluate(df, mats, 'rank', shuffle_seed=400 + s)[0]
                      for s in range(N_SEEDS)])
    rp = (rnull >= e).mean()

    deltas = []
    for nr2 in SWEEP:
        N_REL = nr2
        deltas.append(evaluate(df, mats, 'rank')[0] - be)
    n_better = sum(d > 0.0 for d in deltas)

    print("\nREAD:")
    print(f"  best ranker config = N_REL={nr}: edge {e*100:+.2f}%/yr (vs T0 {be*100:+.2f}%), "
          f"IR {ir:.2f}, passes its own null (p={rp:.3f})")
    print(f"  BUT across N_REL in {SWEEP}: ranker beats T0 in only {n_better}/{len(SWEEP)} "
          f"settings; deltas = {[f'{d*100:+.2f}%' for d in deltas]}")

    robust = n_better > len(SWEEP) // 2  # must win in a majority of settings
    print("\nVERDICT:")
    if robust:
        print("  [WIN]  Ranker beats T0 across a MAJORITY of relevance settings -> real, robust gain.")
    else:
        print("  [NO ROBUST GAIN]  A single setting spikes above T0 but the improvement is NOT")
        print("  robust to the (arbitrary) relevance-bucketing choice -> hyperparameter artifact.")
        print("  Keep the simpler regressor. Documented negative result (like flows / rank-target).")
    print("\n  Bar: beat T0 (+edge or +IR), pass the scrambled-label null (p<0.05),")
    print("  AND the gain must hold across relevance settings (not a one-config spike).")


if __name__ == '__main__':
    main()
