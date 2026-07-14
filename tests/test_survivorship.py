"""
tests/test_survivorship.py  (RESULTS_PROJECT)

The last adversarial attack: SURVIVORSHIP BIAS.

Our benchmark so far = funds that survived to t+3. Dead/merged funds (usually poor
performers) were excluded, which can flatter the benchmark and distort the edge.

Fix: rebuild the benchmark from ALL funds ALIVE AT t (from the DB, not just the
ml_dataset survivors). Dead funds contribute their real returns until they vanish,
after which their capital implicitly earns the benchmark (the standard academic
"reinvest at benchmark" convention -- exactly what an equal-weight average of the
funds-alive-each-month does). If the edge holds against this survivorship-free
benchmark, survivorship is not driving it.

Run from the RESULTS_PROJECT dir:  python tests/test_survivorship.py
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import numpy as np
import pandas as pd
import lightgbm as lgb
import warnings
from sqlalchemy import text
from lib import DATA, OUTPUTS, ASSETS, ROOT, get_engine, FEATURES, get_returns_matrix, port_from_matrix, cagr

warnings.filterwarnings('ignore')
TEST = [2016, 2017, 2018, 2019, 2020, 2021, 2022]
CORE = ['Large Cap Fund', 'Mid Cap Fund', 'Small Cap Fund', 'Flexi Cap Fund', 'ELSS']


def alive_at(engine, eval_end):
    """All direct-growth equity CORE-category scheme_ids with a NAV at eval_end (alive at t)."""
    q = text("""
        SELECT DISTINCT sp.scheme_id
        FROM plan_nav_monthly pnm
        JOIN scheme_plan sp ON pnm.scheme_plan_id=sp.scheme_plan_id
        JOIN scheme s ON sp.scheme_id=s.scheme_id
        JOIN category c ON s.category_id=c.category_id
        WHERE pnm.month_end = :ee AND sp.plan_type='direct' AND sp.option_type='growth'
          AND c.asset_class='Equity' AND c.name IN :cats
    """)
    with engine.connect() as cx:
        d = pd.read_sql(q, cx, params={'ee': eval_end, 'cats': tuple(CORE)})
    return d.scheme_id.tolist()


def main():
    eng = get_engine()
    df = pd.read_csv(DATA / 'ml_dataset.csv')

    print("=" * 70)
    print("SURVIVORSHIP STRESS TEST — benchmark rebuilt with dead/merged funds")
    print("=" * 70)
    print(f"\n{'Cohort':<8}{'AliveAtT':>9}{'Survivors':>10}{'Died':>6}"
          f"{'Bench(surv)':>12}{'Bench(all)':>11}{'Edge(surv)':>11}{'Edge(all)':>10}")

    e_surv, e_all, bias = [], [], []
    for t in TEST:
        ee, fe = f"{t}-12-31", f"{t+3}-12-31"
        alive = alive_at(eng, ee)
        # returns matrix over ALL funds alive at t (includes those that later die)
        mat = get_returns_matrix(eng, alive, ee, fe)
        # apply the SAME NAV-sanity filter as prepare_features: drop funds whose
        # cumulative forward return is corrupt (>500% or <-95%). Without this, the
        # raw-DB universe re-imports the HSBC Midcap +4,367% error we fixed upstream.
        if not mat.empty:
            cumret = (1 + mat).prod() - 1
            good = cumret[(cumret <= 5.0) & (cumret >= -0.95)].index.tolist()
            mat = mat[good]
            alive = [a for a in alive if a in good]
        surv_ids = df[(df.cohort == t) & (df.category_name.isin(CORE))].scheme_id.tolist()
        n_died = len(set(alive) - set(surv_ids))

        # model picks (unchanged: category-neutral top-2, from ml_dataset survivors)
        tr, te = df[df.cohort < t], df[df.cohort == t]
        picks = []
        for c in CORE:
            a, b = tr[tr.category_name == c], te[te.category_name == c]
            if len(a) < 10 or b.empty:
                continue
            m = lgb.LGBMRegressor(random_state=42, n_estimators=50, max_depth=3, verbose=-1)
            m.fit(a[FEATURES], a['fwd_alpha'])
            b = b.assign(p=m.predict(b[FEATURES]))
            picks += b.sort_values('p', ascending=False).head(2).scheme_id.tolist()

        pr = port_from_matrix(mat, picks)
        bench_surv = port_from_matrix(mat, surv_ids)   # survivor-only benchmark
        bench_all = port_from_matrix(mat, alive)       # survivorship-free benchmark
        es = cagr(pr) - cagr(bench_surv)
        ea = cagr(pr) - cagr(bench_all)
        e_surv.append(es); e_all.append(ea); bias.append(cagr(bench_all) - cagr(bench_surv))
        print(f"{t:<8}{len(alive):>9}{len(surv_ids):>10}{n_died:>6}"
              f"{cagr(bench_surv)*100:>11.1f}%{cagr(bench_all)*100:>10.1f}%"
              f"{es*100:>+10.2f}%{ea*100:>+9.2f}%")

    print("-" * 70)
    print(f"{'MEAN':<8}{'':>9}{'':>10}{'':>6}{'':>12}{'':>11}"
          f"{np.mean(e_surv)*100:>+10.2f}%{np.mean(e_all)*100:>+9.2f}%")
    print(f"\n  Survivorship bias in benchmark (all - survivor): {np.mean(bias)*100:+.2f}%/yr")
    print(f"  Edge vs survivor-only benchmark : {np.mean(e_surv)*100:+.2f}%/yr")
    print(f"  Edge vs survivorship-free bench : {np.mean(e_all)*100:+.2f}%/yr")
    verdict = "SURVIVES" if np.mean(e_all) > 0 else "FAILS"
    print(f"\n  -> Edge {verdict} the survivorship correction.")
    print("  Note: picks are still chosen from survivors (they need a fwd label);")
    print("  this tests the dominant (benchmark-side) survivorship effect.")


if __name__ == '__main__':
    main()
