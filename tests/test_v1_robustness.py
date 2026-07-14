"""
tests/test_v1_robustness.py  (RESULTS_PROJECT / exploratory)

Is the V1 (cohort-ranked features) lead real, or the next mirage?

test_detilted_features.py surfaced V1 -- rank-transforming the 9 features WITHIN each
cohort (across all categories) -- beating RAW features by +0.73%/yr (IR +0.23) in a
single walk-forward run, but in only 4/7 cohorts. Per this folder's discipline (the
LGBMRanker win was a one-config spike; de-tilting was IC-only), a single-config lead is
NOT believed until it clears the same battery the headline edge cleared.

This runs that battery on the V1-vs-RAW question. The decisive object is the PAIRED
IMPROVEMENT (V1 picks minus RAW picks), because "does V1 beat RAW" is the claim -- not
merely "does V1 beat the benchmark" (it does, but so does RAW).

Battery:
  1. Portfolio-size sweep k=1..5/category -- does V1>RAW hold at every k, or only k=2?
  2. Per-cohort paired deltas + sign test -- is V1>RAW in a majority of cohorts?
  3. V1's own edge vs benchmark under Newey-West HAC (does V1 itself survive overlap?)
  4. The IMPROVEMENT (V1-RAW) monthly series: naive t, HAC t, cohort bootstrap CI.

Verdict logic: V1 is a real improvement only if the V1-RAW delta is positive across
the size sweep AND significant under HAC/bootstrap AND positive in >=5/7 cohorts.
Anything less -> "within noise of RAW", keep RAW (documented).

Run from the RESULTS_PROJECT dir:  python tests/test_v1_robustness.py
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import numpy as np
import pandas as pd
import lightgbm as lgb
import warnings
from scipy.stats import ttest_1samp, binomtest, norm
from lib import (DATA, OUTPUTS, ASSETS, ROOT, get_engine, FEATURES, get_returns_matrix, port_from_matrix,
                 cagr, excess_monthly)

warnings.filterwarnings('ignore')
COHORTS_ALL = [2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]
TEST = [2016, 2017, 2018, 2019, 2020, 2021, 2022]
CORE = ['Large Cap Fund', 'Mid Cap Fund', 'Small Cap Fund', 'Flexi Cap Fund', 'ELSS']
K_SWEEP = [1, 2, 3, 4, 5]


def encode(df, kind):
    if kind == 'RAW':
        return df
    out = df.copy()  # V1 = within-cohort percentile rank of each feature
    for c in FEATURES:
        out[c] = df.groupby('cohort')[c].rank(pct=True)
    return out


def fit_predict(tr, te, y):
    m = lgb.LGBMRegressor(random_state=42, n_estimators=50, max_depth=3, verbose=-1)
    m.fit(tr[FEATURES], y)
    return m.predict(te[FEATURES])


def picks_for(df, t, kind, k):
    """Return (picks_ids, bench_ids) for cohort t under encoding `kind`, top-k/cat."""
    tr = encode(df[df.cohort < t], kind)
    te = encode(df[df.cohort == t], kind)
    picks, bench = [], []
    for ccat in CORE:
        a = tr[tr.category_name == ccat].dropna(subset=['fwd_alpha'])
        b = te[te.category_name == ccat]
        if len(a) < 10 or b.empty:
            continue
        b = b.assign(p=fit_predict(a, b, a['fwd_alpha']))
        picks += b.sort_values('p', ascending=False).head(k).scheme_id.tolist()
        bench += b.scheme_id.tolist()
    return picks, bench


def newey_west_t(x, lags=36):
    x = np.asarray(x, float); n = len(x)
    e = x - x.mean()
    var = (e @ e) / n
    for l in range(1, lags + 1):
        var += 2 * (1 - l / (lags + 1)) * (e[l:] @ e[:-l]) / n
    se = np.sqrt(var / n)
    return x.mean() / se


def main():
    eng = get_engine()
    df = pd.read_csv(DATA / 'ml_dataset.csv')
    print("Fetching forward return matrices (once per cohort)...")
    mats = {t: get_returns_matrix(eng, df[df.cohort == t].scheme_id.tolist(),
                                  f"{t}-12-31", f"{t+3}-12-31") for t in TEST}

    print("\n" + "=" * 76)
    print("V1 (cohort-ranked features) ROBUSTNESS BATTERY  vs RAW  (category-neutral)")
    print("=" * 76)

    # -------- 1. Portfolio-size sweep --------
    print("\n--- 1. Portfolio-size sweep (mean edge/yr vs category benchmark) ---")
    print(f"    {'k/cat':<7}{'RAW':>9}{'V1':>9}{'V1-RAW':>10}")
    sweep_deltas = []
    for k in K_SWEEP:
        raw_edges, v1_edges = [], []
        for t in TEST:
            mat = mats[t]
            rp, rb = picks_for(df, t, 'RAW', k)
            vp, vb = picks_for(df, t, 'V1', k)
            raw_edges.append(cagr(port_from_matrix(mat, rp)) - cagr(port_from_matrix(mat, rb)))
            v1_edges.append(cagr(port_from_matrix(mat, vp)) - cagr(port_from_matrix(mat, vb)))
        rm, vm = np.mean(raw_edges), np.mean(v1_edges)
        sweep_deltas.append(vm - rm)
        print(f"    {k:<7}{rm*100:>+8.2f}%{vm*100:>+8.2f}%{(vm-rm)*100:>+9.2f}%")
    n_k_better = sum(d > 0 for d in sweep_deltas)

    # -------- 2/3/4 at the headline k=2 --------
    k = 2
    per_cohort_delta = []
    v1_excess_bench, delta_monthly = [], []
    for t in TEST:
        mat = mats[t]
        rp, rb = picks_for(df, t, 'RAW', k)
        vp, vb = picks_for(df, t, 'V1', k)
        r_ret = port_from_matrix(mat, rp)
        v_ret = port_from_matrix(mat, vp)
        b_ret = port_from_matrix(mat, vb)  # same category benchmark
        per_cohort_delta.append(cagr(v_ret) - cagr(r_ret))
        v1_excess_bench.extend(excess_monthly(v_ret, b_ret).tolist())
        # paired monthly V1-minus-RAW (aligned months)
        aligned = pd.concat([v_ret, r_ret], axis=1).dropna()
        delta_monthly.extend((aligned.iloc[:, 0] - aligned.iloc[:, 1]).tolist())

    per_cohort_delta = np.array(per_cohort_delta)
    v1_excess_bench = np.array(v1_excess_bench)
    delta_monthly = np.array(delta_monthly)

    print("\n--- 2. Per-cohort V1-minus-RAW edge (k=2) ---")
    print("    " + "  ".join(f"{t}:{d*100:+.2f}%" for t, d in zip(TEST, per_cohort_delta)))
    wins = int((per_cohort_delta > 0).sum())
    sp = binomtest(wins, len(TEST), 0.5, alternative='greater').pvalue
    print(f"    V1 beats RAW in {wins}/{len(TEST)} cohorts;  sign test p={sp:.3f}")

    print("\n--- 3. V1's OWN edge vs benchmark under overlap correction ---")
    tn, pn = ttest_1samp(v1_excess_bench, 0.0)
    th = newey_west_t(v1_excess_bench, 36)
    ph = 2 * (1 - norm.cdf(abs(th)))
    print(f"    naive monthly t={tn:.2f} (p={pn:.4f});  Newey-West HAC t={th:.2f} (p~{ph:.4f})")
    print(f"    -> V1's own edge is {'significant' if ph < 0.05 else 'NOT significant'} after HAC")

    print("\n--- 4. Is the IMPROVEMENT (V1 - RAW) significant? [the decisive test] ---")
    if delta_monthly.std() == 0:
        td = th_d = 0.0; pd_ = ph_d = 1.0
    else:
        td, pd_ = ttest_1samp(delta_monthly, 0.0)
        th_d = newey_west_t(delta_monthly, 36)
        ph_d = 2 * (1 - norm.cdf(abs(th_d)))
    print(f"    paired monthly V1-RAW: mean={delta_monthly.mean()*100:+.3f}%/mo  "
          f"naive t={td:.2f} (p={pd_:.4f})  HAC t={th_d:.2f} (p~{ph_d:.4f})")
    rng = np.random.RandomState(0)
    boot = np.array([rng.choice(per_cohort_delta, size=len(TEST), replace=True).mean()
                     for _ in range(20000)])
    ci = np.percentile(boot, [2.5, 97.5]) * 100
    print(f"    cohort bootstrap of V1-RAW edge: 95% CI [{ci[0]:+.2f}%, {ci[1]:+.2f}%];  "
          f"P(delta<=0)={ (boot <= 0).mean():.3f}")

    # -------- verdict --------
    sweep_ok = n_k_better >= 4          # V1 > RAW at >=4/5 portfolio sizes
    cohort_ok = wins >= 5               # V1 > RAW in >=5/7 cohorts
    sig_ok = ph_d < 0.05 and ci[0] > 0  # improvement significant under HAC AND bootstrap CI>0
    print("\n" + "=" * 76)
    print("VERDICT -- is V1's +0.73%/yr over RAW real?")
    print(f"  size sweep: V1>RAW in {n_k_better}/5 k-settings  ({'ok' if sweep_ok else 'FAIL'})")
    print(f"  per-cohort: V1>RAW in {wins}/7 cohorts           ({'ok' if cohort_ok else 'FAIL'})")
    print(f"  significance of improvement (HAC & bootstrap)    ({'ok' if sig_ok else 'FAIL'})")
    if sweep_ok and cohort_ok and sig_ok:
        print("\n  [REAL]  V1 beats RAW robustly and significantly -> a genuine improvement")
        print("          worth promoting (retest live before deploying).")
    else:
        print("\n  [MIRAGE / WITHIN NOISE]  The +0.73% does NOT clear the battery: the")
        print("          improvement over RAW is not robust across portfolio size and/or not")
        print("          statistically distinguishable from noise. Keep RAW. Documented negative.")
    print("=" * 76)


if __name__ == '__main__':
    main()
