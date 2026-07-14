"""
tests/test_list_quality.py  (RESULTS_PROJECT / exploratory)

Which model should power a RETAIL "rate every fund" list -- raw or de-tilted features?

Two different products:
  * STRATEGY list  = top-2 per category (validated, raw features, +2.37%/yr).
  * RETAIL list    = rank EVERY fund within its category so an investor can see where
                     any fund stands. This uses the WHOLE ranking, not just the top-2,
                     so overall ranking quality (the thing IC measures) matters here in
                     a way it did NOT for the top-2 strategy (test_detilted_features.py).

De-tilting (V2 = rank features within cohort x category) raised within-category IC from
+0.09 to +0.18. But IC is a summary proxy. The metric a retail list actually lives or
dies on is the out-of-sample WITHIN-CATEGORY QUINTILE SPREAD:

    "do funds this model rates in the TOP 20% of their category actually realise higher
     forward alpha than the funds it rates in the BOTTOM 20%?"

We compute that directly from realised fwd_alpha (already category-relative, in the
dataset -- no portfolio, no DB), for a GLOBAL model (as the live screener uses) under
each feature encoding, and check spread size, monotonicity, per-cohort consistency, and
a permutation null. A model only makes a better retail list if its spread is wider AND
consistent AND monotone -- not merely higher IC.

Run from the RESULTS_PROJECT dir:  python tests/test_list_quality.py
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import numpy as np
import pandas as pd
import lightgbm as lgb
import warnings
from scipy.stats import binomtest, spearmanr
from lib import DATA, OUTPUTS, ASSETS, ROOT, FEATURES

warnings.filterwarnings('ignore')
TEST = [2016, 2017, 2018, 2019, 2020, 2021, 2022]
CORE = ['Large Cap Fund', 'Mid Cap Fund', 'Small Cap Fund', 'Flexi Cap Fund', 'ELSS']
ENCODINGS = ['RAW', 'V1', 'V2']
NQ = 5          # quintiles
MIN_N = 10      # min funds in a cohort x category to form quintiles


def encode(df, kind):
    if kind == 'RAW':
        return df
    out = df.copy()
    by = 'cohort' if kind == 'V1' else ['cohort', 'category_name']
    for c in FEATURES:
        out[c] = df.groupby(by)[c].rank(pct=True)
    return out


def collect(df, kind, shuffle_rng=None):
    """Global model per cohort (train on cohort<t), predict test cohort. Pooled OOS."""
    rows = []
    for t in TEST:
        tr = encode(df[df.cohort < t], kind)
        te = df[df.cohort == t].copy()
        te_enc = encode(te, kind)
        y = tr['fwd_alpha'].values
        if shuffle_rng is not None:
            y = shuffle_rng.permutation(y)
        m = lgb.LGBMRegressor(random_state=42, n_estimators=50, max_depth=3, verbose=-1)
        m.fit(tr[FEATURES], y)
        te['pred'] = m.predict(te_enc[FEATURES])
        rows.append(te[['scheme_id', 'category_name', 'cohort', 'fwd_alpha', 'pred']])
    return pd.concat(rows, ignore_index=True)


def assign_quintiles(pooled):
    """Quintile (0..NQ-1) of predicted score WITHIN each cohort x category (>=MIN_N)."""
    p = pooled.copy()
    p['q'] = np.nan
    for _, idx in p.groupby(['cohort', 'category_name']).groups.items():
        g = p.loc[idx]
        if len(g) < MIN_N:
            continue
        p.loc[idx, 'q'] = pd.qcut(g['pred'].rank(method='first'), NQ, labels=False)
    return p.dropna(subset=['q'])


def spread_stats(pooled):
    """Return (Q-means array, top-bottom spread, #monotone steps, spearman q vs alpha)."""
    p = assign_quintiles(pooled)
    qmean = p.groupby('q')['fwd_alpha'].mean().reindex(range(NQ))
    spread = qmean.iloc[-1] - qmean.iloc[0]
    steps = int((np.diff(qmean.values) > 0).sum())
    rho = spearmanr(p['q'], p['fwd_alpha'])[0]
    return qmean.values, spread, steps, rho


def per_cohort_spread(pooled):
    out = []
    for t in TEST:
        _, sp, _, _ = spread_stats(pooled[pooled.cohort == t])
        out.append(sp)
    return np.array(out)


def main():
    df = pd.read_csv(DATA / 'ml_dataset.csv')

    print("=" * 80)
    print("RETAIL LIST QUALITY -- within-category quintile spread of realised fwd_alpha")
    print("  (top-20%-rated minus bottom-20%-rated; bigger + monotone = better list)")
    print("=" * 80)

    res = {}
    for kind in ENCODINGS:
        pooled = collect(df, kind)
        qmean, spread, steps, rho = spread_stats(pooled)
        cohort_sp = per_cohort_spread(pooled)
        pos = int((cohort_sp > 0).sum())
        # permutation null on the pooled spread
        nulls = []
        for s in range(20):
            npooled = collect(df, kind, shuffle_rng=np.random.RandomState(700 + s))
            nulls.append(spread_stats(npooled)[1])
        pval = (np.array(nulls) >= spread).mean()
        res[kind] = dict(qmean=qmean, spread=spread, steps=steps, rho=rho,
                         cohort_sp=cohort_sp, pos=pos, p=pval)

        label = {'RAW': 'RAW (current retail list)', 'V1': 'V1 cohort-ranked',
                 'V2': 'V2 de-tilted (cohort x cat)'}[kind]
        print(f"\n[{kind}] {label}")
        print("   quintile realised alpha (Q1..Q5): " +
              "  ".join(f"{q*100:+.1f}%" for q in qmean))
        print(f"   TOP-minus-BOTTOM spread : {spread*100:+.2f} pp over 3y   "
              f"(monotone steps {steps}/4, Spearman q-vs-alpha {rho:+.3f})")
        print(f"   per-cohort spread positive in {pos}/7 cohorts; permutation p={pval:.3f}")

    # --- robustness: does the wider spread hold across bucket counts (not just quintiles)? ---
    global NQ
    print("\n" + "-" * 80)
    print("ROBUSTNESS: top-vs-bottom-bucket spread across bucket counts (pp over 3y)")
    print(f"    {'buckets':<9}{'RAW':>9}{'V1':>9}{'V2':>9}{'V1-RAW':>9}{'V2-RAW':>9}")
    pooled_cache = {k: collect(df, k) for k in ENCODINGS}
    saved_nq = NQ
    sweep_ok = {'V1': 0, 'V2': 0}
    n_bins = [3, 4, 5, 10]
    for nb in n_bins:
        NQ = nb
        sp = {}
        for k in ENCODINGS:
            sp[k] = spread_stats(pooled_cache[k])[1]
        for k in ('V1', 'V2'):
            if sp[k] > sp['RAW']:
                sweep_ok[k] += 1
        print(f"    {nb:<9}{sp['RAW']*100:>+8.2f}{sp['V1']*100:>+8.2f}{sp['V2']*100:>+8.2f}"
              f"{(sp['V1']-sp['RAW'])*100:>+8.2f}{(sp['V2']-sp['RAW'])*100:>+8.2f}")
    NQ = saved_nq

    base = res['RAW']
    print("\n" + "-" * 80)
    print("READ (retail list: does a de-tilted / alt encoding give a BETTER list than RAW?)")
    for kind in ['V1', 'V2']:
        r = res[kind]
        d_cohort = r['cohort_sp'] - base['cohort_sp']
        beat = int((d_cohort > 0).sum())
        sp_p = binomtest(beat, 7, 0.5, alternative='greater').pvalue
        print(f"  {kind}: spread {r['spread']*100:+.2f}pp vs RAW {base['spread']*100:+.2f}pp "
              f"(delta {(r['spread']-base['spread'])*100:+.2f}pp), wider in {beat}/7 cohorts "
              f"(sign p={sp_p:.3f}), monotone {r['steps']}/4 vs {base['steps']}/4")

    # pick the better alt encoding by spread for the headline verdict
    alt = 'V1' if res['V1']['spread'] >= res['V2']['spread'] else 'V2'
    a = res[alt]
    a_delta = a['spread'] - base['spread']
    a_beat = int(((a['cohort_sp'] - base['cohort_sp']) > 0).sum())
    # a real, adoptable list win: wider spread, holds across bucket counts, mostly-consistent
    robust_sweep = sweep_ok[alt] >= 3           # wider than RAW in >=3/4 bucket counts
    consistent = a_beat >= 6                     # wider than RAW in >=6/7 cohorts
    print(f"\nVERDICT -- should the RETAIL list use an alt encoding? (best = {alt})")
    if a['p'] < 0.05 and a_delta > 0.005 and robust_sweep and consistent:
        print(f"  [ADOPT for retail]  {alt} gives a wider ({a['spread']*100:+.1f}pp vs"
              f" {base['spread']*100:+.1f}pp), monotone spread that holds across bucket counts")
        print(f"  ({sweep_ok[alt]}/4) and cohorts ({a_beat}/7) -> serve {alt} as the RETAIL list;")
        print("  keep RAW top-2 as the STRATEGY list. Two products, each on its best-measured model.")
    elif a['p'] < 0.05 and a_delta > 0.005 and robust_sweep:
        print(f"  [PROMISING, CONFIRM FIRST]  {alt}'s spread is wider ({a['spread']*100:+.1f}pp vs"
              f" {base['spread']*100:+.1f}pp) and holds across bucket counts ({sweep_ok[alt]}/4),")
        print(f"  but the per-cohort improvement over RAW is only {a_beat}/7 (under-powered on 7")
        print("  points). Aggregate signal is real and theory-consistent (a list uses the whole")
        print("  ranking, unlike top-2) -> worth adopting for the retail list, but confirm on")
        print("  live/next cohorts before committing. Frame modestly regardless.")
    else:
        print(f"  [KEEP RAW]  {alt} is not a robust improvement on RAW's list spread.")
    print("\n  NOTE: even the widest spread here is a QUINTILE-level tilt; fund-level ordering is")
    print("  still noisy (Spearman ~0.15). A retail list must be framed as a 'modest statistical")
    print("  tilt', WITH the Risk band / horizon overlay -- never as a precise #1>#7 ordering.")

    # Exit code so annual_maintenance can re-validate the retail product's premise on
    # refreshed data: 0 = alt encoding still gives a wider, bucket-robust, null-passing
    # spread than RAW (retail list justified); 1 = premise no longer holds (review).
    premise_holds = bool(a['p'] < 0.05 and a_delta > 0.005 and robust_sweep)
    print(f"\n[premise] de-tilted retail list still beats RAW & robust across buckets: "
          f"{premise_holds}  ->  exit {0 if premise_holds else 1}")
    return 0 if premise_holds else 1


if __name__ == '__main__':
    sys.exit(main())
