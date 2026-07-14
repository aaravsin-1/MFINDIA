"""
tests/test_target_definition.py  (RESULTS_PROJECT / exploratory)

Does changing WHAT the model predicts improve the product?

The current model predicts raw 3-yr category-relative alpha (T0). A risk-adjusted
or downside-focused target might pick funds with better risk-adjusted returns /
shallower drawdowns -- valuable for the "Conservative" bucket -- even if the raw
CAGR edge is similar.

Targets compared (all trained the same category-neutral way, top-2/category):
  T0  raw fwd_alpha                              (current baseline)
  T1  within-cat RANK of fwd_alpha              (pure ordering, outlier-robust)
  T2  within-cat rank of forward SHARPE          (return / forward volatility)
  T3  within-cat rank of forward CALMAR          (return / forward max drawdown; downside)

Each target is judged on: CAGR edge, Information Ratio, portfolio Max Drawdown,
and its own negative control (empirical p). A target only "wins" if it improves a
metric AND passes the null.

Run from the RESULTS_PROJECT dir:  python tests/test_target_definition.py
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import numpy as np
import pandas as pd
import lightgbm as lgb
import warnings
from scipy.stats import rankdata
from lib import (DATA, OUTPUTS, ASSETS, ROOT, get_engine, FEATURES, get_returns_matrix, port_from_matrix,
                 cagr, excess_monthly)

warnings.filterwarnings('ignore')
COHORTS_ALL = [2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]
TEST = [2016, 2017, 2018, 2019, 2020, 2021, 2022]
CORE = ['Large Cap Fund', 'Mid Cap Fund', 'Small Cap Fund', 'Flexi Cap Fund', 'ELSS']
TARGETS = ['T0_raw', 'T1_rank', 'T2_sharpe', 'T3_calmar']
N_SEEDS = 15


def maxdd(rets):
    if rets.empty:
        return 0.0
    cum = (1 + rets).cumprod()
    return float((cum / cum.cummax() - 1).min())


def build_targets(df, mats):
    """Add forward risk metrics + the alternative targets to df."""
    rec = []
    for t in COHORTS_ALL:
        mat = mats.get(t)
        if mat is None or mat.empty:
            continue
        for sid in df[df.cohort == t].scheme_id.unique():
            if sid not in mat.columns:
                rec.append((sid, t, np.nan, np.nan)); continue
            r = mat[sid].dropna()
            if len(r) < 12:
                rec.append((sid, t, np.nan, np.nan)); continue
            vol = r.std() * np.sqrt(12)
            dd = abs(maxdd(r))
            rec.append((sid, t, vol, dd))
    fm = pd.DataFrame(rec, columns=['scheme_id', 'cohort', 'fwd_vol', 'fwd_dd'])
    d = df.merge(fm, on=['scheme_id', 'cohort'], how='left')

    ann = (1 + d['fwd_return']).clip(lower=1e-6) ** (1/3) - 1
    d['fwd_sharpe'] = ann / d['fwd_vol'].replace(0, np.nan)
    d['fwd_calmar'] = ann / d['fwd_dd'].clip(lower=0.05)

    # category-relative RANK targets (within cohort x category)
    g = d.groupby(['cohort', 'category_name'])
    d['T0_raw'] = d['fwd_alpha']
    d['T1_rank'] = g['fwd_alpha'].transform(lambda s: rankdata(s) / len(s))
    d['T2_sharpe'] = g['fwd_sharpe'].transform(lambda s: rankdata(s.fillna(s.median())) / len(s))
    d['T3_calmar'] = g['fwd_calmar'].transform(lambda s: rankdata(s.fillna(s.median())) / len(s))
    return d


def evaluate(d, mats, target, shuffle_seed=None):
    """Category-neutral top-2/cat under `target`. Returns (edge, IR, avg_maxdd)."""
    rng = np.random.RandomState(shuffle_seed) if shuffle_seed is not None else None
    edges, dds, pooled_ex = [], [], []
    for t in TEST:
        tr, te = d[d.cohort < t], d[d.cohort == t]
        mat = mats[t]
        bench = te[te.category_name.isin(CORE)].scheme_id.tolist()
        picks = []
        for ccat in CORE:
            a, b = tr[tr.category_name == ccat], te[te.category_name == ccat]
            a = a.dropna(subset=[target])
            if len(a) < 10 or b.empty:
                continue
            y = a[target].values
            if rng is not None:
                y = rng.permutation(y)
            m = lgb.LGBMRegressor(random_state=42, n_estimators=50, max_depth=3, verbose=-1)
            m.fit(a[FEATURES], y)
            b = b.assign(p=m.predict(b[FEATURES]))
            picks += b.sort_values('p', ascending=False).head(2).scheme_id.tolist()
        pr, br = port_from_matrix(mat, picks), port_from_matrix(mat, bench)
        edges.append(cagr(pr) - cagr(br)); dds.append(maxdd(pr))
        pooled_ex.extend(excess_monthly(pr, br).tolist())
    ex = np.array(pooled_ex)
    ir = (ex.mean() / ex.std()) * np.sqrt(12) if ex.std() > 0 else 0.0
    return np.mean(edges), ir, np.mean(dds)


def main():
    eng = get_engine()
    df = pd.read_csv(DATA / 'ml_dataset.csv')
    print("Fetching forward return matrices (once per cohort)...")
    mats = {t: get_returns_matrix(eng, df[df.cohort == t].scheme_id.tolist(),
                                  f"{t}-12-31", f"{t+3}-12-31") for t in COHORTS_ALL}
    d = build_targets(df, mats)

    print("\n" + "=" * 72)
    print("TARGET DEFINITION — does predicting a different quantity help?")
    print("=" * 72)
    print(f"\n{'Target':<12}{'Edge/yr':>9}{'InfoRatio':>11}{'Port.MaxDD':>12}{'NegCtrl p':>11}")
    print("-" * 72)
    results = {}
    for tg in TARGETS:
        edge, ir, dd = evaluate(d, mats, tg)
        null = np.array([evaluate(d, mats, tg, shuffle_seed=200 + s)[0] for s in range(N_SEEDS)])
        p = (null >= edge).mean()
        results[tg] = (edge, ir, dd, p)
        print(f"{tg:<12}{edge*100:>+8.2f}%{ir:>11.2f}{dd*100:>11.1f}%{p:>11.3f}")

    base = results['T0_raw']
    print("\nREAD (vs T0 baseline):")
    for tg in TARGETS[1:]:
        e, ir, dd, p = results[tg]
        tag = "passes" if p < 0.05 else "FAILS null"
        print(f"  {tg:<10} edge {(e-base[0])*100:+.2f}%  IR {ir-base[1]:+.2f}  "
              f"MaxDD {(dd-base[2])*100:+.1f}%  ({tag})")
    print("\n  A risk-adjusted target 'wins' only if it lifts IR or shrinks MaxDD")
    print("  while still passing its negative control.")


if __name__ == '__main__':
    main()
