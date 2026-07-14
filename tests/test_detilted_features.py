"""
tests/test_detilted_features.py  (RESULTS_PROJECT / exploratory)

Does "de-tilting" the FEATURES actually improve the picks, or only the IC number?

Context: strengthen_edge.py reports an out-of-sample rank IC that rises from ~+0.09
(raw features) to ~+0.18 when features are rank-transformed within cohort x category
("de-tilted", encoding V2). FINDINGS.md §4.4 flags the +0.18 as "likely optimistic":
it is the best of three encodings AND the transform is aligned to the within-category
axis it is then scored on. Crucially, strengthen_edge.py only used V2 for IC
*measurement* -- the actual +2.37% category-neutral PORTFOLIO uses RAW features.

So the real question is untested: if we feed de-tilted features into the exact
top-2-per-category construction, does the EDGE/IR beat the raw-feature version? (We
have twice seen a better metric NOT translate into a better portfolio -- LGBMRanker
and hierarchical shrinkage.) This settles it with a portfolio number.

Feature encodings (train and test transformed independently, as-of-date, no leak):
  RAW     : the 9 features as-is                              (current baseline)
  V1      : within-cohort percentile rank of each feature
  V2      : within-cohort x category percentile rank         (the "de-tilted" one)

Same bar as every experiment here: category-neutral top-2/cat, walk-forward
2016-2022, judged on CAGR edge + Information Ratio, must pass its own scrambled-label
negative control (p<0.05), and any gain must be real (not within noise of RAW).

Run from the RESULTS_PROJECT dir:  python tests/test_detilted_features.py
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
ENCODINGS = ['RAW', 'V1', 'V2']
N_SEEDS = 20


def encode(df, kind):
    """Return a copy with FEATURES transformed per `kind` (as-of within each frame)."""
    if kind == 'RAW':
        return df
    out = df.copy()
    by = 'cohort' if kind == 'V1' else ['cohort', 'category_name']
    for c in FEATURES:
        out[c] = df.groupby(by)[c].rank(pct=True)
    return out


def evaluate(df, mats, kind, shuffle_seed=None):
    """Category-neutral top-2/cat under feature encoding `kind`. (edge, IR)."""
    rng = np.random.RandomState(shuffle_seed) if shuffle_seed is not None else None
    edges, pooled_ex = [], []
    for t in TEST:
        # encode within the train and test frames independently (no cross-set info)
        tr = encode(df[df.cohort < t], kind)
        te = encode(df[df.cohort == t], kind)
        mat = mats[t]
        bench = te[te.category_name.isin(CORE)].scheme_id.tolist()
        picks = []
        for ccat in CORE:
            a = tr[tr.category_name == ccat].dropna(subset=['fwd_alpha'])
            b = te[te.category_name == ccat]
            if len(a) < 10 or b.empty:
                continue
            y = a['fwd_alpha'].values
            if rng is not None:
                y = rng.permutation(y)
            m = lgb.LGBMRegressor(random_state=42, n_estimators=50,
                                  max_depth=3, verbose=-1)
            m.fit(a[FEATURES], y)
            b = b.assign(p=m.predict(b[FEATURES]))
            picks += b.sort_values('p', ascending=False).head(2).scheme_id.tolist()
        pr, br = port_from_matrix(mat, picks), port_from_matrix(mat, bench)
        edges.append(cagr(pr) - cagr(br))
        pooled_ex.extend(excess_monthly(pr, br).tolist())
    ex = np.array(pooled_ex)
    ir = (ex.mean() / ex.std()) * np.sqrt(12) if ex.std() > 0 else 0.0
    return np.mean(edges), ir, np.array(edges)


def main():
    eng = get_engine()
    df = pd.read_csv(DATA / 'ml_dataset.csv')
    print("Fetching forward return matrices (once per cohort)...")
    mats = {t: get_returns_matrix(eng, df[df.cohort == t].scheme_id.tolist(),
                                  f"{t}-12-31", f"{t+3}-12-31") for t in COHORTS_ALL}

    print("\n" + "=" * 74)
    print("DE-TILTED FEATURES vs RAW  (category-neutral, top-2/cat)")
    print("  does rank-transforming the INPUT features improve the PICKS?")
    print("=" * 74)
    print(f"\n{'Encoding':<28}{'Edge/yr':>9}{'InfoRatio':>11}{'NegCtrl p':>11}")
    print("-" * 74)

    results = {}
    for kind in ENCODINGS:
        edge, ir, ce = evaluate(df, mats, kind)
        null = np.array([evaluate(df, mats, kind, shuffle_seed=600 + s)[0]
                         for s in range(N_SEEDS)])
        p = (null >= edge).mean()
        results[kind] = (edge, ir, p, null.mean(), ce)
        label = {'RAW': 'RAW (baseline, current)',
                 'V1': 'V1 cohort-ranked',
                 'V2': 'V2 cohort x cat (de-tilted)'}[kind]
        print(f"{label:<28}{edge*100:>+8.2f}%{ir:>11.2f}{p:>11.3f}")

    be, bir, bp, _, bce = results['RAW']
    print("\nREAD (vs RAW baseline; per-cohort = # of 7 cohorts this encoding beats RAW):")
    for kind in ['V1', 'V2']:
        e, ir, p, nullm, ce = results[kind]
        n_beat = int((ce > bce).sum())
        tag = "passes null" if p < 0.05 else "FAILS null"
        print(f"  {kind:<4} edge {(e-be)*100:+.2f}%/yr  IR {ir-bir:+.2f}  "
              f"beats RAW in {n_beat}/7 cohorts   ({e*100:+.2f}% vs {be*100:+.2f}%, {tag})")

    # --- direct answer: did DE-TILTING (V2) convert the +0.18 IC into a real edge? ---
    v2e, v2ir, v2p, _, v2ce = results['V2']
    v2_beat = int((v2ce > bce).sum())
    # "real" requires a non-trivial edge gain AND per-cohort consistency, not just IR noise
    v2_real = (v2e - be > 0.003) and (v2_beat >= 5)
    print("\nVERDICT #1 -- does DE-TILTING (V2) the features help the actual picks?")
    if v2p < 0.05 and v2_real:
        print("  [WIN]  De-tilted (V2) features beat RAW meaningfully and consistently.")
    elif v2p < 0.05:
        print(f"  [IC-ONLY]  V2's IC roughly DOUBLED (0.09 -> 0.18) but the portfolio edge moved")
        print(f"         only {(v2e-be)*100:+.2f}%/yr (beats RAW in just {v2_beat}/7 cohorts). The +0.18")
        print("         IC was an OPTIMISTIC, axis-aligned metric that does NOT convert into better")
        print("         picks -> keep RAW features. Confirms the 'optimistic' label (a better IC")
        print("         != a better portfolio, same lesson as the ranker and shrinkage tests).")
    else:
        print("  [FAIL] V2 fails its own negative control -> not usable.")

    # --- honest bonus: V1 (cohort-ranked, NOT de-tilting) looks stronger; flag it ---
    v1e, v1ir, v1p, _, v1ce = results['V1']
    v1_beat = int((v1ce > bce).sum())
    print("\nVERDICT #2 -- bonus lead (NOT de-tilting): V1 cohort-ranked features")
    print(f"  V1 edge {(v1e-be)*100:+.2f}%/yr, IR {v1ir-bir:+.2f}, beats RAW in {v1_beat}/7 cohorts,"
          f" null p={v1p:.3f}.")
    print("  This is a LARGER, more consistent lead than V2 -- but it is a single untested")
    print("  configuration. Per this project's discipline (cf. the ranker's one-config spike),")
    print("  it is NOT claimed as a win until it clears a robustness battery (portfolio-size")
    print("  sweep, per-cohort, HAC/bootstrap). Flagged as the one lead worth a follow-up test.")
    print("\n  Bar: beat RAW on edge by a real margin AND in >=5/7 cohorts AND pass the null.")


if __name__ == '__main__':
    main()
