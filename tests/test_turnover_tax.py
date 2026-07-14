"""
test_turnover_tax.py  (RESULTS_PROJECT)

Question: our validated edge is +2.4%/yr GROSS, but the strategy churns ~80%/yr,
which triggers tax. What if we DON'T rebalance so much? Does a lower-turnover
version keep more of the edge after tax?

We test holding periods H = 1, 2, 3 years and compute, for each:
  - GROSS edge vs the category benchmark (empirical, from the DB)
  - turnover per rebalance and annualised (empirical)
  - AFTER-TAX net edge, using an explicit, transparent tax model

Tax / friction assumptions (see DATABASE.md check: exit load absent, lock-in
column empty, so these are domain rules, stated openly):
  * LTCG 12.5% on realised gains IF held > 12 months. All H >= 1 qualify.
  * Exit load ~= 0 because equity exit loads apply only to redemptions < 12 months.
  * The category buy-and-hold benchmark defers tax (pays once, at the end).
  * ELSS is force-locked 3 years anyway -> naturally low-turnover, LTCG, no load.
  * ₹1.25 lakh/yr exemption ignored -> conservative (assumes a sizeable portfolio;
    small portfolios pay even less).
The model treats the portfolio as churning a fraction (turnover) each rebalance,
realising proportional embedded gains and stepping up basis. It is illustrative,
not a tax return, but the ranking across H is robust.
"""
import numpy as np
import pandas as pd
import lightgbm as lgb
import warnings
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from lib import DATA, OUTPUTS, ASSETS, ROOT, get_engine, FEATURES, get_returns_matrix, port_from_matrix, cagr

warnings.filterwarnings('ignore')
COHORTS = [2016, 2017, 2018, 2019, 2020, 2021, 2022]
CORE = ['Large Cap Fund', 'Mid Cap Fund', 'Small Cap Fund', 'Flexi Cap Fund', 'ELSS']
LTCG = 0.125


def fit(tr, te, y):
    m = lgb.LGBMRegressor(random_state=42, n_estimators=50, max_depth=3, verbose=-1)
    m.fit(tr[FEATURES], y)
    return m.predict(te[FEATURES])


def picks_for(df_all, t):
    tr = df_all[df_all['cohort'] < t]
    te = df_all[df_all['cohort'] == t]
    out = []
    for c in CORE:
        a, b = tr[tr['category_name'] == c], te[te['category_name'] == c]
        if len(a) < 10 or b.empty:
            continue
        b = b.assign(p=fit(a, b, a['fwd_alpha']))
        out += b.sort_values('p', ascending=False).head(2)['scheme_id'].tolist()
    return out


def after_tax_cagr(g, turnover, H, years=9, tax=LTCG):
    """Simulate a portfolio growing at g/yr, churning `turnover` every H years."""
    V, basis = 1.0, 1.0
    for yr in range(1, years + 1):
        V *= (1 + g)
        if yr % H == 0:                       # rebalance year
            gain = max(V - basis, 0.0)
            realised = gain * turnover        # portion sold
            V -= realised * tax               # pay LTCG on realised gains
            basis += realised                 # step up basis on churned slice
    return V ** (1 / years) - 1


def bench_after_tax_cagr(g, years=9, tax=LTCG):
    """Buy-and-hold: grow untaxed, pay LTCG once at the very end."""
    V = (1 + g) ** years
    V -= max(V - 1.0, 0.0) * tax
    return V ** (1 / years) - 1


def main():
    eng = get_engine()
    df = pd.read_csv(DATA / 'ml_dataset.csv')

    # cache picks per cohort (for turnover) and returns per (cohort,H)
    picks = {t: picks_for(df, t) for t in COHORTS}

    print("=" * 74)
    print("TURNOVER vs TAX — does holding longer keep more of the +2.4% edge?")
    print("=" * 74)
    rows = []
    for H in [1, 2, 3]:
        gross_edges, bench_cagrs, pick_cagrs, turns = [], [], [], []
        for t in COHORTS:
            if t + H > 2025:
                continue
            mat = get_returns_matrix(eng, df[df.cohort == t]['scheme_id'].tolist(),
                                     f"{t}-12-31", f"{t+H}-12-31")
            bench_ids = df[(df.cohort == t) & (df.category_name.isin(CORE))]['scheme_id'].tolist()
            pk = cagr(port_from_matrix(mat, picks[t]))
            bn = cagr(port_from_matrix(mat, bench_ids))
            pick_cagrs.append(pk); bench_cagrs.append(bn); gross_edges.append(pk - bn)
            # turnover vs the next rebalance H years later
            if (t + H) in picks:
                prev, nxt = set(picks[t]), set(picks[t + H])
                turns.append(1 - len(prev & nxt) / len(prev))

        g_edge = np.mean(gross_edges)
        g_pick = np.mean(pick_cagrs)
        g_bench = np.mean(bench_cagrs)
        turnover = np.mean(turns) if turns else 0.8
        ann_turn = turnover / H

        pick_at = after_tax_cagr(g_pick, turnover, H)
        bench_at = bench_after_tax_cagr(g_bench)
        net_edge = pick_at - bench_at
        rows.append((H, g_edge, turnover, ann_turn, g_pick, pick_at, bench_at, net_edge))

    print(f"\n{'Hold':<6}{'GrossEdge':>10}{'Turn/reb':>10}{'Turn/yr':>9}"
          f"{'Picks(AT)':>11}{'Bench(AT)':>11}{'NetEdge(AT)':>13}")
    print("-" * 74)
    for H, ge, tr_, at_, gp, pat, bat, ne in rows:
        print(f"{H}yr{'':<3}{ge*100:>+9.2f}%{tr_*100:>9.0f}%{at_*100:>8.0f}%"
              f"{pat*100:>10.1f}%{bat*100:>10.1f}%{ne*100:>+12.2f}%")

    print("\nREAD:")
    print("  GrossEdge  = picks - category benchmark, before tax (what we validated).")
    print("  Turn/yr    = annualised turnover (per-rebalance / H). Lower = less tax churn.")
    print("  NetEdge(AT)= after-tax edge an investor keeps vs buying & holding the category.")
    print("\n  Key: holding >12 months keeps us in LTCG (12.5%) and avoids exit loads.")
    print("  ELSS is locked 3 years regardless, so its sleeve is naturally H=3.")


if __name__ == '__main__':
    main()
