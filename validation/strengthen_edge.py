"""
strengthen_edge.py  (RESULTS_PROJECT)

Goal (per the brief): try, LEGITIMATELY and without fabrication, to find a
construction where a genuine edge survives the correct null.

Two honest ideas, both aimed at the diagnosis from run_validation.py -- that the
raw "top-10 vs equal-weight" edge is mostly a small-cap / momentum SELECTION
tilt that a random-label model reproduces:

  A) OUT-OF-SAMPLE RANK IC.  The cleanest test of ranking skill: pooled Spearman
     correlation between predicted alpha and REALISED forward alpha across every
     test fund (~1,600 obs -> real statistical power, unlike 7 annual CAGRs).
     We test three feature encodings:
        V0 raw features
        V1 within-cohort percentile-ranked features
        V2 within-cohort x category ranked features (de-tilts absolute size)
     Each IC is checked against a permutation null (shuffle labels) and its
     analytic Spearman p-value.

  B) CATEGORY-NEUTRAL CONSTRUCTION.  Pick the top-2 per core category (removes the
     category tilt) and measure edge against a CATEGORY-MATCHED benchmark and
     against the scrambled-label null for the SAME construction.

Reports whatever is true.
"""
import numpy as np
import pandas as pd
import lightgbm as lgb
import warnings
from scipy.stats import spearmanr
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from lib import (DATA, OUTPUTS, ASSETS, ROOT, get_engine, FEATURES, get_returns_matrix, port_from_matrix, cagr, excess_monthly)

warnings.filterwarnings('ignore')
TEST_COHORTS = [2016, 2017, 2018, 2019, 2020, 2021, 2022]
CORE_CATS = ['Large Cap Fund', 'Mid Cap Fund', 'Small Cap Fund', 'Flexi Cap Fund', 'ELSS']


def rank_within(df, cols, by):
    out = df.copy()
    for c in cols:
        out[c] = df.groupby(by)[c].rank(pct=True)
    return out


def fit(train, test, feats, y):
    m = lgb.LGBMRegressor(random_state=42, n_estimators=50, max_depth=3, verbose=-1)
    m.fit(train[feats], y)
    return m.predict(test[feats])


def collect_predictions(df_all, encoding):
    """Return pooled DataFrame of (pred, fwd_alpha, category, cohort, scheme_id) out-of-sample."""
    rows = []
    for t in TEST_COHORTS:
        train = df_all[df_all['cohort'] < t].copy()
        test = df_all[df_all['cohort'] == t].copy()
        if encoding == 'V1':
            train = rank_within(train, FEATURES, 'cohort'); test = rank_within(test, FEATURES, 'cohort')
        elif encoding == 'V2':
            train = rank_within(train, FEATURES, ['cohort', 'category_name'])
            test = rank_within(test, FEATURES, ['cohort', 'category_name'])
        pred = fit(train, test, FEATURES, train['fwd_alpha'])
        te = df_all[df_all['cohort'] == t][['scheme_id', 'category_name', 'fwd_alpha']].copy()
        te['pred'] = pred; te['cohort'] = t
        rows.append(te)
    return pd.concat(rows, ignore_index=True)


def ic_report(df_all):
    print("=" * 66)
    print("A) OUT-OF-SAMPLE RANK IC  (Spearman: predicted vs realised fwd_alpha)")
    print("=" * 66)
    for enc in ['V0', 'V1', 'V2']:
        pooled = collect_predictions(df_all, enc)
        rho, p = spearmanr(pooled['pred'], pooled['fwd_alpha'])
        # within-category average IC (skill after removing category effects)
        wc = pooled.groupby('category_name').apply(
            lambda g: spearmanr(g['pred'], g['fwd_alpha'])[0] if len(g) > 15 else np.nan)
        wc_mean = np.nanmean(wc.values)
        # permutation null on the pooled IC
        rng = np.random.RandomState(0)
        null = [spearmanr(pooled['pred'], rng.permutation(pooled['fwd_alpha'].values))[0] for _ in range(300)]
        emp_p = (np.array(null) >= rho).mean()
        label = {'V0': 'raw features', 'V1': 'cohort-ranked', 'V2': 'cohort x category-ranked (de-tilted)'}[enc]
        print(f"\n  [{enc}] {label}  (N={len(pooled)})")
        print(f"     Pooled IC          : {rho:+.4f}  (analytic p={p:.4f})")
        print(f"     Within-category IC : {wc_mean:+.4f}")
        print(f"     Permutation p-value: {emp_p:.3f}  -> {'skill present' if emp_p < 0.05 else 'not distinguishable from noise'}")


def category_neutral(df_all, engine):
    print("\n" + "=" * 66)
    print("B) CATEGORY-NEUTRAL CONSTRUCTION (top-2 per core category)")
    print("=" * 66)
    cn_cagrs, catbench_cagrs, ew_cagrs = [], [], []
    excess_vs_catbench = []
    N_SEEDS = 20
    scr = {s: [] for s in range(N_SEEDS)}

    for t in TEST_COHORTS:
        eval_end, fwd_end = f"{t}-12-31", f"{t+3}-12-31"
        train = df_all[df_all['cohort'] < t].copy()
        test = df_all[df_all['cohort'] == t].copy()
        univ = test['scheme_id'].tolist()
        mat = get_returns_matrix(engine, univ, eval_end, fwd_end)

        # real: top-2 per category
        picks, catbench_ids = [], []
        preds = {}
        for cat in CORE_CATS:
            tr_c = train[train['category_name'] == cat]
            te_c = test[test['category_name'] == cat]
            if len(tr_c) < 10 or te_c.empty:
                continue
            p = fit(tr_c, te_c, FEATURES, tr_c['fwd_alpha'])
            te_c = te_c.assign(pred=p); preds[cat] = te_c
            picks += te_c.sort_values('pred', ascending=False).head(2)['scheme_id'].tolist()
            catbench_ids += te_c['scheme_id'].tolist()   # category-matched benchmark = all funds in these cats

        cn_r = port_from_matrix(mat, picks)
        cb_r = port_from_matrix(mat, catbench_ids)
        ew_r = port_from_matrix(mat, univ)
        cn_cagrs.append(cagr(cn_r)); catbench_cagrs.append(cagr(cb_r)); ew_cagrs.append(cagr(ew_r))
        excess_vs_catbench.extend(excess_monthly(cn_r, cb_r).tolist())

        # scrambled null for the SAME category-neutral machinery
        for s in range(N_SEEDS):
            rng = np.random.RandomState(500 + s)
            spk = []
            for cat in CORE_CATS:
                if cat not in preds:
                    continue
                tr_c = train[train['category_name'] == cat]
                te_c = test[test['category_name'] == cat]
                ps = fit(tr_c, te_c, FEATURES, rng.permutation(tr_c['fwd_alpha'].values))
                te_c = te_c.assign(ps=ps)
                spk += te_c.sort_values('ps', ascending=False).head(2)['scheme_id'].tolist()
            scr[s].append(cagr(port_from_matrix(mat, spk)))

    cn, cb, ew = np.mean(cn_cagrs), np.mean(catbench_cagrs), np.mean(ew_cagrs)
    scr_m = np.array([np.mean(scr[s]) for s in range(N_SEEDS)])
    from scipy.stats import ttest_1samp
    ex = np.array(excess_vs_catbench)
    tstat, pval = ttest_1samp(ex, 0.0)

    print(f"\n  Category-neutral ML CAGR      : {cn*100:.2f}%")
    print(f"  Category-matched benchmark     : {cb*100:.2f}%")
    print(f"  Equal-weight universe          : {ew*100:.2f}%")
    print(f"  Edge vs category benchmark     : {(cn-cb)*100:+.2f}%")
    print(f"  Scrambled null (same machinery): mean={scr_m.mean()*100:.2f}%  [{scr_m.min()*100:.1f}, {scr_m.max()*100:.1f}]")
    print(f"  Empirical p (scrambled>=real)  : {(scr_m>=cn).mean():.3f}")
    print(f"  Monthly alpha vs cat-benchmark : t={tstat:.2f}  p={pval:.4f}  "
          f"-> {'significant' if pval<0.05 and tstat>0 else 'not significant'}")


def main():
    engine = get_engine()
    df_all = pd.read_csv(DATA / 'ml_dataset.csv')
    ic_report(df_all)
    category_neutral(df_all, engine)


if __name__ == '__main__':
    main()
