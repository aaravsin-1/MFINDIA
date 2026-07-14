"""
experiment_min_history.py  (RESULTS_PROJECT)

ONE experiment, requested explicitly: does the validated category-neutral edge
(+2.37% vs a category-matched benchmark, 7/7 cohorts) survive if we forbid the
strategy from picking funds with a short track record?

Motivation: the live 2025 snapshot's recommended set leans on young funds that
only just clear the 30-month history filter. Young survivors are the most
survivorship-prone picks. If a >=5-year-history constraint keeps the edge, we can
disclose+de-risk for free; if it collapses, the young-fund tilt is load-bearing
and we leave it in with a disclosure instead.

This ONLY adds a seasoning constraint to the pick universe (and to the scrambled
null, so the comparison stays apples-to-apples). Everything else -- model, features,
benchmark, cohorts -- is identical to strengthen_edge.category_neutral. Fund age is
dated from the earliest NAV across ALL plans (true inception), not direct-only.
"""
import numpy as np
import pandas as pd
import warnings
from scipy.stats import ttest_1samp
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from lib import DATA, OUTPUTS, ASSETS, ROOT, get_engine, FEATURES, get_returns_matrix, port_from_matrix, cagr, excess_monthly
from strengthen_edge import fit, TEST_COHORTS, CORE_CATS

warnings.filterwarnings('ignore')
N_SEEDS = 20


def get_inception(engine):
    """scheme_id -> earliest NAV date across ALL plans (true fund inception)."""
    q = "SELECT sp.scheme_id, MIN(pnm.month_end) AS first_nav " \
        "FROM plan_nav_monthly pnm JOIN scheme_plan sp ON pnm.scheme_plan_id=sp.scheme_plan_id " \
        "GROUP BY sp.scheme_id"
    d = pd.read_sql(q, engine)
    return dict(zip(d['scheme_id'], pd.to_datetime(d['first_nav'])))


def run(df_all, engine, inception, min_years):
    """Category-neutral backtest; pick universe restricted to funds with >= min_years
    of history at each eval date (min_years=0 reproduces the validated baseline)."""
    cn_cagrs, cb_cagrs = [], []
    per_cohort_edge = []
    excess = []
    scr = {s: [] for s in range(N_SEEDS)}
    univ_sizes, seasoned_sizes = [], []

    for t in TEST_COHORTS:
        eval_end, fwd_end = f"{t}-12-31", f"{t+3}-12-31"
        cutoff = pd.Timestamp(f"{t - min_years}-12-31")   # inception must be on/before this
        train = df_all[df_all['cohort'] < t].copy()
        test = df_all[df_all['cohort'] == t].copy()

        def seasoned(sid):
            inc = inception.get(sid)
            return inc is not None and inc <= cutoff

        univ = test['scheme_id'].tolist()
        mat = get_returns_matrix(engine, univ, eval_end, fwd_end)

        picks, catbench_ids = [], []
        preds_ok = {}
        n_univ_core, n_seasoned_core = 0, 0
        for cat in CORE_CATS:
            tr_c = train[train['category_name'] == cat]
            te_c_all = test[test['category_name'] == cat]
            if len(tr_c) < 10 or te_c_all.empty:
                continue
            # benchmark = ALL funds in the core category (the investor's opportunity cost)
            catbench_ids += te_c_all['scheme_id'].tolist()
            n_univ_core += len(te_c_all)
            # pick universe = seasoned funds only
            te_c = te_c_all[te_c_all['scheme_id'].apply(seasoned)]
            n_seasoned_core += len(te_c)
            if te_c.empty:
                continue
            p = fit(tr_c, te_c, FEATURES, tr_c['fwd_alpha'])
            te_c = te_c.assign(pred=p)
            preds_ok[cat] = (tr_c, te_c)
            picks += te_c.sort_values('pred', ascending=False).head(2)['scheme_id'].tolist()

        univ_sizes.append(n_univ_core); seasoned_sizes.append(n_seasoned_core)

        cn_r = port_from_matrix(mat, picks)
        cb_r = port_from_matrix(mat, catbench_ids)
        cn_c, cb_c = cagr(cn_r), cagr(cb_r)
        cn_cagrs.append(cn_c); cb_cagrs.append(cb_c)
        per_cohort_edge.append((t, (cn_c - cb_c) * 100))
        excess.extend(excess_monthly(cn_r, cb_r).tolist())

        # scrambled null: same seasoned universe, random labels
        for s in range(N_SEEDS):
            rng = np.random.RandomState(500 + s)
            spk = []
            for cat, (tr_c, te_c) in preds_ok.items():
                ps = fit(tr_c, te_c, FEATURES, rng.permutation(tr_c['fwd_alpha'].values))
                te_c2 = te_c.assign(ps=ps)
                spk += te_c2.sort_values('ps', ascending=False).head(2)['scheme_id'].tolist()
            scr[s].append(cagr(port_from_matrix(mat, spk)))

    cn, cb = np.mean(cn_cagrs), np.mean(cb_cagrs)
    scr_m = np.array([np.mean(scr[s]) for s in range(N_SEEDS)])
    ex = np.array(excess)
    tstat, pval = ttest_1samp(ex, 0.0)
    wins = sum(1 for _, e in per_cohort_edge if e > 0)

    tag = "BASELINE (no filter)" if min_years == 0 else f"MIN-HISTORY >= {min_years}yr"
    print("\n" + "=" * 68)
    print(f"  {tag}")
    print("=" * 68)
    print(f"  Core-category universe / seasoned per cohort: "
          f"{list(zip([t for t in TEST_COHORTS], univ_sizes, seasoned_sizes))}")
    print(f"  Category-neutral ML CAGR       : {cn*100:.2f}%")
    print(f"  Category-matched benchmark      : {cb*100:.2f}%")
    print(f"  Edge vs category benchmark      : {(cn-cb)*100:+.2f}%")
    print(f"  Per-cohort edge (won {wins}/{len(per_cohort_edge)}):")
    for yr, e in per_cohort_edge:
        print(f"      {yr}: {e:+.2f}%")
    print(f"  Scrambled null (same universe)  : mean={scr_m.mean()*100:.2f}%  "
          f"[{scr_m.min()*100:.1f}, {scr_m.max()*100:.1f}]")
    print(f"  Empirical p (scrambled >= real) : {(scr_m>=cn).mean():.3f}")
    print(f"  Monthly alpha t-test            : t={tstat:.2f}  p={pval:.4f}  "
          f"-> {'significant' if pval<0.05 and tstat>0 else 'NOT significant'}")
    return {'edge': (cn-cb)*100, 'wins': wins, 'n': len(per_cohort_edge),
            'emp_p': (scr_m>=cn).mean(), 't': tstat, 'p': pval}


def main():
    engine = get_engine()
    df_all = pd.read_csv(DATA / 'ml_dataset.csv')
    inception = get_inception(engine)
    print("Experiment: does the category-neutral edge survive a >=5yr track-record filter?")
    base = run(df_all, engine, inception, 0)
    filt = run(df_all, engine, inception, 5)

    print("\n" + "#" * 68)
    print("  VERDICT")
    print("#" * 68)
    print(f"  Baseline edge        : {base['edge']:+.2f}%  ({base['wins']}/{base['n']} cohorts, "
          f"emp_p={base['emp_p']:.3f}, monthly p={base['p']:.4f})")
    print(f"  >=5yr-history edge    : {filt['edge']:+.2f}%  ({filt['wins']}/{filt['n']} cohorts, "
          f"emp_p={filt['emp_p']:.3f}, monthly p={filt['p']:.4f})")
    survives = filt['edge'] > 0 and filt['emp_p'] < 0.05 and filt['wins'] >= filt['n'] - 1
    print(f"  --> Edge {'SURVIVES' if survives else 'DOES NOT clearly survive'} the >=5yr filter.")


if __name__ == '__main__':
    main()
