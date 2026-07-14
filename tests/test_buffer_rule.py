"""
test_buffer_rule.py  (RESULTS_PROJECT)

A "buffer" (hysteresis) rule to cut turnover WITHOUT giving up gross edge:
hold each fund until it drops OUT of the top-K in its category (K >= 2), instead
of forcing exactly the top-2 every year. This keeps good funds instead of churning
them for a marginally higher-ranked name.

We simulate a real, continuously-held portfolio year by year (2016->2025):
  * Each category keeps 2 funds.
  * Annually, re-rank (model trained only on prior data).
  * A held fund is KEPT if it's still in the category's top-K; otherwise it's
    sold and replaced by the best-ranked fund not already held.
  * Portfolio return = equal-weight 1-year forward return of held funds.

We report realised annual turnover and CAGR/edge for K = 2 (no buffer), 4, 6.
Lower turnover at the same edge = less tax churn = more kept after tax.
"""
import numpy as np
import pandas as pd
import lightgbm as lgb
import warnings
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from lib import DATA, OUTPUTS, ASSETS, ROOT, get_engine, FEATURES, get_returns_matrix, port_from_matrix, cagr

warnings.filterwarnings('ignore')
YEARS = [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024]  # rebalance dates; need t+1 returns
CORE = ['Large Cap Fund', 'Mid Cap Fund', 'Small Cap Fund', 'Flexi Cap Fund', 'ELSS']


def fit(tr, te, y):
    m = lgb.LGBMRegressor(random_state=42, n_estimators=50, max_depth=3, verbose=-1)
    m.fit(tr[FEATURES], y)
    return m.predict(te[FEATURES])


def ranked_by_category(df, t):
    """Return {category: [scheme_id ranked best->worst]} for cohort t, model trained < t."""
    tr = df[df.cohort < t]
    te = df[df.cohort == t]
    out = {}
    for c in CORE:
        a, b = tr[tr.category_name == c], te[te.category_name == c]
        if len(a) < 10 or b.empty:
            continue
        b = b.assign(p=fit(a, b, a['fwd_alpha']))
        out[c] = b.sort_values('p', ascending=False)['scheme_id'].tolist()
    return out


def simulate(df, eng, K):
    """Continuously-held portfolio with a top-K buffer. Returns (cagr, edge, turnover)."""
    held = {c: [] for c in CORE}           # current 2 funds per category
    port_rets, bench_rets, turnovers = [], [], []

    for t in YEARS:
        if t not in set(df.cohort.unique()):
            # cohort features must exist to rank; 2023/2024 not in ml_dataset -> stop ranking,
            # but we can still hold. Reuse last available ranking year.
            pass
        rank_year = t if t in df.cohort.unique() else max(y for y in df.cohort.unique() if y <= t)
        ranks = ranked_by_category(df, rank_year)

        # rebalance with hysteresis
        replaced, slots = 0, 0
        for c in CORE:
            if c not in ranks:
                continue
            order = ranks[c]
            topK = set(order[:K])
            keep = [f for f in held[c] if f in topK]
            replaced += len(held[c]) - len(keep)
            slots += 2
            # refill to 2 from best not already held
            for f in order:
                if len(keep) >= 2:
                    break
                if f not in keep:
                    keep.append(f)
            held[c] = keep
        if slots:
            turnovers.append(replaced / slots)

        # 1-year forward returns of the currently-held portfolio
        cur = [f for c in CORE for f in held[c]]
        cat_universe = df[(df.cohort == rank_year) & (df.category_name.isin(CORE))]['scheme_id'].tolist()
        mat = get_returns_matrix(eng, list(set(cur + cat_universe)), f"{t}-12-31", f"{t+1}-12-31")
        pr = port_from_matrix(mat, cur)
        br = port_from_matrix(mat, cat_universe)
        if not pr.empty:
            port_rets.append(pr)
            bench_rets.append(br)

    port = pd.concat(port_rets)
    bench = pd.concat(bench_rets)
    return cagr(port), cagr(port) - cagr(bench), np.mean(turnovers)


def main():
    eng = get_engine()
    df = pd.read_csv(DATA / 'ml_dataset.csv')
    print("=" * 60)
    print("BUFFER / HYSTERESIS RULE — turnover vs edge (annual, 1yr hold)")
    print("=" * 60)
    print(f"\n{'Rule':<22}{'CAGR':>9}{'Edge/yr':>10}{'Turnover/yr':>13}")
    print("-" * 60)
    for K in [2, 4, 6]:
        cg, edge, turn = simulate(df, eng, K)
        label = "Top-2 (no buffer)" if K == 2 else f"Hold until out of top-{K}"
        print(f"{label:<22}{cg*100:>8.1f}%{edge*100:>+9.2f}%{turn*100:>11.0f}%")
    print("\nREAD: a wider buffer (bigger K) should cut turnover while keeping most")
    print("of the edge — fewer taxable sales for the same selection quality.")


if __name__ == '__main__':
    main()
