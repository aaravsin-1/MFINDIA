"""
validate_hold_periods.py  (RESULTS_PROJECT)

test_turnover_tax.py found the gross edge is FRONT-LOADED (biggest at a 1-year
hold, decaying by 3 years). But only the 3-year edge had passed the negative
control. This script runs the SAME honesty gauntlet on the 1- and 2-year holds:

  * Negative control: scrambled-label category-neutral picks over N seeds ->
    empirical p (is the real edge above the null?).
  * Sign test on per-cohort annual edges.

If the short-hold edge survives, the front-loaded alpha is real; if not, it was
noise and we should stick with the validated ~3-year edge.
"""
import numpy as np
import pandas as pd
import lightgbm as lgb
import warnings
from scipy.stats import binomtest
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from lib import DATA, OUTPUTS, ASSETS, ROOT, get_engine, FEATURES, get_returns_matrix, port_from_matrix, cagr

warnings.filterwarnings('ignore')
COHORTS = [2016, 2017, 2018, 2019, 2020, 2021, 2022]
CORE = ['Large Cap Fund', 'Mid Cap Fund', 'Small Cap Fund', 'Flexi Cap Fund', 'ELSS']
N_SEEDS = 20


def fit(tr, te, y):
    m = lgb.LGBMRegressor(random_state=42, n_estimators=50, max_depth=3, verbose=-1)
    m.fit(tr[FEATURES], y)
    return m.predict(te[FEATURES])


def main():
    eng = get_engine()
    df = pd.read_csv(DATA / 'ml_dataset.csv')

    print("=" * 68)
    print("VALIDATION OF SHORT-HOLD EDGES (negative control + sign test)")
    print("=" * 68)

    for H in [1, 2, 3]:
        real_edges = []
        scr_edges = {s: [] for s in range(N_SEEDS)}
        used = 0
        for t in COHORTS:
            if t + H > 2025:
                continue
            used += 1
            tr = df[df.cohort < t]
            te = df[df.cohort == t]
            mat = get_returns_matrix(eng, te['scheme_id'].tolist(), f"{t}-12-31", f"{t+H}-12-31")
            bench_ids = te[te.category_name.isin(CORE)]['scheme_id'].tolist()
            bn = cagr(port_from_matrix(mat, bench_ids))

            # real picks
            picks = []
            per_cat_train = {}
            for c in CORE:
                a, b = tr[tr.category_name == c], te[te.category_name == c]
                if len(a) < 10 or b.empty:
                    continue
                per_cat_train[c] = (a, b)
                b = b.assign(p=fit(a, b, a['fwd_alpha']))
                picks += b.sort_values('p', ascending=False).head(2)['scheme_id'].tolist()
            real_edges.append(cagr(port_from_matrix(mat, picks)) - bn)

            # scrambled null (same machinery)
            for s in range(N_SEEDS):
                rng = np.random.RandomState(300 + s)
                spk = []
                for c, (a, b) in per_cat_train.items():
                    ps = fit(a, b, rng.permutation(a['fwd_alpha'].values))
                    b2 = b.assign(ps=ps)
                    spk += b2.sort_values('ps', ascending=False).head(2)['scheme_id'].tolist()
                scr_edges[s].append(cagr(port_from_matrix(mat, spk)) - bn)

        real = np.mean(real_edges)
        scr = np.array([np.mean(scr_edges[s]) for s in range(N_SEEDS)])
        emp_p = (scr >= real).mean()
        wins = int(np.sum(np.array(real_edges) > 0))
        sign_p = binomtest(wins, used, 0.5, alternative='greater').pvalue

        verdict = "PASSES" if emp_p < 0.05 else "FAILS"
        print(f"\n--- {H}-YEAR HOLD  ({used} cohorts) ---")
        print(f"  Gross edge vs benchmark   : {real*100:+.2f}%/yr")
        print(f"  Per-cohort edges          : {[f'{e*100:+.1f}' for e in real_edges]}")
        print(f"  Scrambled null            : mean {scr.mean()*100:+.2f}%  [{scr.min()*100:+.1f}, {scr.max()*100:+.1f}]")
        print(f"  Empirical p (null>=real)  : {emp_p:.3f}   -> negative control {verdict}")
        print(f"  Sign test                 : {wins}/{used} positive, p={sign_p:.4f}")


if __name__ == '__main__':
    main()
