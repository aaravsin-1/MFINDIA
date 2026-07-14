"""
run_validation.py  (RESULTS_PROJECT - honest validation harness)

Answers ONE question honestly: does the ML selection add value beyond the
selection machinery itself?

Fixes vs. the original final_validation.py:
  * The original negative control used an UNSEEDED single permutation and quoted
    the resulting 16.2% as if deterministic. Across seeds the scrambled model
    actually averages ~17.9% and beats the equal-weight baseline about half the
    time -- so a single lucky-low draw was reported. Here we run the negative
    control over N seeds and report the FULL distribution, plus an empirical
    p-value for the real model against that null.
  * The correct null for "does the model learn?" is the scrambled-label model
    (same top-k machinery, no real signal) -- NOT the equal-weight universe.
    We report the real model against BOTH.
  * All randomness is seeded; walk-forward is 2016-2022 (7 cohorts) and labelled
    as such (the original printed "2016-2022" while only testing 2018-2022).

No numbers are hard-coded; everything is computed from the fixed ml_dataset.csv.
"""
import numpy as np
import pandas as pd
import lightgbm as lgb
import warnings
from scipy.stats import ttest_1samp
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from lib import (DATA, OUTPUTS, ASSETS, ROOT, get_engine, FEATURES, get_returns_matrix, port_from_matrix,
                 cagr, excess_monthly)

warnings.filterwarnings('ignore')

TEST_COHORTS = [2016, 2017, 2018, 2019, 2020, 2021, 2022]
TOP_K = 10
N_SEEDS = 40


def fit_predict(train_df, test_df, y):
    m = lgb.LGBMRegressor(random_state=42, n_estimators=50, max_depth=3, verbose=-1)
    m.fit(train_df[FEATURES], y)
    return m, m.predict(test_df[FEATURES])


def main():
    engine = get_engine()
    df_all = pd.read_csv(DATA / 'ml_dataset.csv')

    real_ret, ew_ret = [], []            # concatenated monthly series pieces
    real_excess_all = []                 # monthly excess vs EW (for t-test)
    real_cagrs, ew_cagrs = [], []        # per-cohort CAGR
    scrambled_cagrs = {s: [] for s in range(N_SEEDS)}
    turnover, prev_funds = [], []
    feat_top3 = {}

    for t in TEST_COHORTS:
        eval_end, fwd_end = f"{t}-12-31", f"{t+3}-12-31"
        train_df = df_all[df_all['cohort'] < t].copy()
        test_df = df_all[df_all['cohort'] == t].copy()

        univ = test_df['scheme_id'].tolist()
        mat = get_returns_matrix(engine, univ, eval_end, fwd_end)  # one query per cohort

        # ---- Real model ----
        model, pred = fit_predict(train_df, test_df, train_df['fwd_alpha'])
        test_df['pred'] = pred
        ml_funds = test_df.sort_values('pred', ascending=False).head(TOP_K)['scheme_id'].tolist()

        imp = model.feature_importances_
        feat_top3[t] = [FEATURES[i] for i in np.argsort(imp)[-3:][::-1]]

        ml_r = port_from_matrix(mat, ml_funds)
        ew_r = port_from_matrix(mat, univ)
        real_cagrs.append(cagr(ml_r)); ew_cagrs.append(cagr(ew_r))
        real_excess_all.extend(excess_monthly(ml_r, ew_r).tolist())

        # turnover
        if prev_funds:
            turnover.append(TOP_K - len(set(ml_funds) & set(prev_funds)))
        prev_funds = ml_funds

        # ---- Negative control: scrambled labels, many seeds, reuse the matrix ----
        for s in range(N_SEEDS):
            rng = np.random.RandomState(1000 + s)
            y_shuf = rng.permutation(train_df['fwd_alpha'].values)
            _, pred_s = fit_predict(train_df, test_df, y_shuf)
            test_df['ps'] = pred_s
            rf = test_df.sort_values('ps', ascending=False).head(TOP_K)['scheme_id'].tolist()
            scrambled_cagrs[s].append(cagr(port_from_matrix(mat, rf)))

    real_cagr = np.mean(real_cagrs)
    ew_cagr = np.mean(ew_cagrs)
    scr = np.array([np.mean(scrambled_cagrs[s]) for s in range(N_SEEDS)])

    print("=" * 66)
    print("HONEST VALIDATION  (Walk-forward 2016-2022, Top 10, annual rebalance)")
    print("=" * 66)

    print("\n--- 1. HEADLINE PERFORMANCE ---")
    print(f"  Real ML model  CAGR : {real_cagr*100:.2f}%")
    print(f"  Equal-Weight   CAGR : {ew_cagr*100:.2f}%")
    print(f"  Raw edge vs EW      : {(real_cagr-ew_cagr)*100:+.2f}%")

    print("\n--- 2. NEGATIVE CONTROL (scrambled labels, %d seeds) ---" % N_SEEDS)
    print(f"  Scrambled CAGR: mean={scr.mean()*100:.2f}%  sd={scr.std()*100:.2f}%"
          f"  [min={scr.min()*100:.2f}%, max={scr.max()*100:.2f}%]")
    print(f"  Scrambled beats EW ({ew_cagr*100:.1f}%) in {int((scr>ew_cagr).sum())}/{N_SEEDS} seeds")
    emp_p = (scr >= real_cagr).mean()
    print(f"  Empirical p-value (P[scrambled >= real]) : {emp_p:.3f}")
    z = (real_cagr - scr.mean()) / (scr.std() + 1e-12)
    print(f"  Real model is {z:.2f} sd above the scrambled-null mean")
    verdict = "PASSES" if emp_p < 0.05 else "DOES NOT PASS"
    print(f"  -> Negative control: model {verdict} the correct null at 5%.")

    print("\n--- 3. STATISTICAL SIGNIFICANCE (monthly alpha vs EW) ---")
    ex = np.array(real_excess_all)
    tstat, pval = ttest_1samp(ex, 0.0)
    ann = (1 + ex.mean()) ** 12 - 1
    print(f"  Observations: {len(ex)} fund-months")
    print(f"  Annualised alpha: {ann*100:.2f}%   t={tstat:.3f}   p={pval:.4f}")
    print(f"  -> {'Significant' if pval<0.05 and tstat>0 else 'NOT significant'} at 5%.")

    print("\n--- 4. TURNOVER ---")
    print(f"  Avg annual replacement: {np.mean(turnover):.1f}/{TOP_K}  ({np.mean(turnover)/TOP_K*100:.0f}%)")

    print("\n--- 5. FEATURE STABILITY (top-3 importance per year) ---")
    for t in TEST_COHORTS:
        print(f"  {t}: {', '.join(feat_top3[t])}")


if __name__ == '__main__':
    main()
