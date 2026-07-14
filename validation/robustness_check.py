"""
robustness_check.py  (RESULTS_PROJECT)

Firms up the significance of the category-neutral edge under the honest objection
that the 3-year forward windows OVERLAP (so naive monthly t-stats are inflated by
autocorrelation). We report four estimators, weakest-assumption last:

  1. Naive monthly t-test           (assumes independent months -> optimistic)
  2. Newey-West HAC t-test          (Bartlett kernel, 36 lags -> corrects overlap)
  3. Non-overlapping annual t-test  (7 cohort edges, one per cohort)
  4. Cohort block bootstrap + sign test (non-parametric, no distributional/indep. assumption)

Strategy under test = category-neutral top-2 per core category vs the
category-matched benchmark (the construction that passed the negative control).
"""
import numpy as np
import pandas as pd
import lightgbm as lgb
import warnings
from scipy.stats import ttest_1samp, binomtest
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from lib import DATA, OUTPUTS, ASSETS, ROOT, get_engine, FEATURES, get_returns_matrix, port_from_matrix, cagr, excess_monthly

warnings.filterwarnings('ignore')
TEST_COHORTS = [2016, 2017, 2018, 2019, 2020, 2021, 2022]
CORE_CATS = ['Large Cap Fund', 'Mid Cap Fund', 'Small Cap Fund', 'Flexi Cap Fund', 'ELSS']


def fit(tr, te, y):
    m = lgb.LGBMRegressor(random_state=42, n_estimators=50, max_depth=3, verbose=-1)
    m.fit(tr[FEATURES], y)
    return m.predict(te[FEATURES])


def newey_west_tstat(x, lags):
    """HAC (Bartlett) t-stat for H0: mean(x)=0."""
    x = np.asarray(x, float)
    n = len(x)
    xbar = x.mean()
    e = x - xbar
    gamma0 = (e @ e) / n
    var = gamma0
    for l in range(1, lags + 1):
        w = 1 - l / (lags + 1)
        cov = (e[l:] @ e[:-l]) / n
        var += 2 * w * cov
    se = np.sqrt(var / n)
    return xbar / se, se


def main():
    engine = get_engine()
    df_all = pd.read_csv(DATA / 'ml_dataset.csv')

    annual_edges = []        # 7 non-overlapping cohort CAGR edges
    monthly_excess = []      # pooled monthly excess vs category benchmark

    for t in TEST_COHORTS:
        eval_end, fwd_end = f"{t}-12-31", f"{t+3}-12-31"
        train = df_all[df_all['cohort'] < t]
        test = df_all[df_all['cohort'] == t]
        mat = get_returns_matrix(engine, test['scheme_id'].tolist(), eval_end, fwd_end)

        picks, bench = [], []
        for cat in CORE_CATS:
            tr_c = train[train['category_name'] == cat]
            te_c = test[test['category_name'] == cat]
            if len(tr_c) < 10 or te_c.empty:
                continue
            te_c = te_c.assign(p=fit(tr_c, te_c, tr_c['fwd_alpha']))
            picks += te_c.sort_values('p', ascending=False).head(2)['scheme_id'].tolist()
            bench += te_c['scheme_id'].tolist()

        pr = port_from_matrix(mat, picks)
        br = port_from_matrix(mat, bench)
        annual_edges.append(cagr(pr) - cagr(br))
        monthly_excess.extend(excess_monthly(pr, br).tolist())

    annual_edges = np.array(annual_edges)
    mex = np.array(monthly_excess)

    print("=" * 64)
    print("ROBUSTNESS OF THE CATEGORY-NEUTRAL EDGE (vs category benchmark)")
    print("=" * 64)
    print(f"\nPer-cohort annual edge: {[f'{e*100:+.2f}%' for e in annual_edges]}")
    print(f"Mean annual edge      : {annual_edges.mean()*100:+.2f}%")

    print("\n--- 1. Naive monthly t-test (optimistic; assumes independence) ---")
    t1, p1 = ttest_1samp(mex, 0.0)
    print(f"  n={len(mex)}  t={t1:.2f}  p={p1:.4f}")

    print("\n--- 2. Newey-West HAC t-test (36 lags; corrects for 3-yr overlap) ---")
    t2, se2 = newey_west_tstat(mex, lags=36)
    # two-sided p via normal approx
    from scipy.stats import norm
    p2 = 2 * (1 - norm.cdf(abs(t2)))
    print(f"  t_HAC={t2:.2f}  p~{p2:.4f}  -> {'significant' if p2 < 0.05 else 'not significant'} at 5%")

    print("\n--- 3. Non-overlapping annual t-test (7 cohort edges) ---")
    t3, p3 = ttest_1samp(annual_edges, 0.0)
    print(f"  n=7  t={t3:.2f}  p={p3:.4f}  -> {'significant' if p3 < 0.05 else 'not significant'} at 5%")

    print("\n--- 4. Non-parametric: cohort block bootstrap + sign test ---")
    rng = np.random.RandomState(0)
    boot = [rng.choice(annual_edges, size=7, replace=True).mean() for _ in range(20000)]
    boot = np.array(boot)
    ci = np.percentile(boot, [2.5, 97.5]) * 100
    print(f"  Bootstrap mean edge 95% CI: [{ci[0]:+.2f}%, {ci[1]:+.2f}%]")
    print(f"  Bootstrap P(mean edge <= 0): {(boot <= 0).mean():.4f}")
    wins = int((annual_edges > 0).sum())
    sp = binomtest(wins, 7, 0.5, alternative='greater').pvalue
    print(f"  Sign test: {wins}/7 cohorts positive -> p={sp:.4f}")

    print("\n" + "-" * 64)
    print("READ: the naive monthly t is inflated by overlap. The HAC, the")
    print("annual, and the non-parametric tests are the trustworthy ones.")


if __name__ == '__main__':
    main()
