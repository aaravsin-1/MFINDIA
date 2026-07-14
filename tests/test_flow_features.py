"""
tests/test_flow_features.py  (RESULTS_PROJECT / exploratory)

Does adding FUND-FLOW features legitimately grow the edge?

Flows = money investors add/withdraw, net of performance. Theory (Berk & Green;
"smart money" vs "dumb money" literature) says flows can predict future returns
(chasing hot funds -> capacity drag; or flows as an information signal).

We build two flow features from AUM (v_scheme_aum) + NAV, for each fund/cohort:
  * aum_growth_1y : trailing 1-yr change in AUM
  * flow_1y       : ORGANIC flow = AUM growth stripped of the fund's own return
                    (1+aum_growth)/(1+ret_1y) - 1   -> pure investor add/withdraw

Then we compare, on the validated category-neutral strategy:
    baseline  = the 9 features
    augmented = 9 features + flow features
on GROSS edge AND the negative control (does the augmented edge beat its own
scrambled null?). Adding features only "counts" if it survives the null.

Run from the RESULTS_PROJECT dir:  python tests/test_flow_features.py
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))  # so `import lib` works when run from parent dir

import numpy as np
import pandas as pd
import lightgbm as lgb
import warnings
from sqlalchemy import text
from lib import DATA, OUTPUTS, ASSETS, ROOT, get_engine, FEATURES, get_returns_matrix, port_from_matrix, cagr

warnings.filterwarnings('ignore')
COHORTS = [2016, 2017, 2018, 2019, 2020, 2021, 2022]
CORE = ['Large Cap Fund', 'Mid Cap Fund', 'Small Cap Fund', 'Flexi Cap Fund', 'ELSS']
FLOW_FEATS = ['aum_growth_1y', 'flow_1y']
N_SEEDS = 20


def build_flow_features(engine, df):
    """Attach aum_growth_1y and flow_1y to each (scheme_id, cohort) row."""
    ids = tuple(int(x) for x in df.scheme_id.unique())
    with engine.connect() as c:
        aum = pd.read_sql(text("SELECT scheme_id, period_end, avg_aum_lakh FROM v_scheme_aum "
                               "WHERE scheme_id IN :ids AND avg_aum_lakh > 0"),
                          c, params={'ids': ids}, parse_dates=['period_end'])
        nav = pd.read_sql(text("""SELECT sp.scheme_id, pnm.month_end, pnm.nav
            FROM plan_nav_monthly pnm JOIN scheme_plan sp ON pnm.scheme_plan_id=sp.scheme_plan_id
            WHERE sp.scheme_id IN :ids AND sp.plan_type='direct' AND sp.option_type='growth'"""),
            c, params={'ids': ids}, parse_dates=['month_end'])
    aum = aum.sort_values('period_end')
    nav = nav.groupby(['scheme_id', 'month_end'], as_index=False).nav.mean().sort_values('month_end')

    def asof_val(tbl, sid, date, col):
        sub = tbl[(tbl.scheme_id == sid) & (tbl.iloc[:, 1] <= date)]
        return sub[col].iloc[-1] if len(sub) else np.nan

    rows = []
    for t in COHORTS:
        now = pd.Timestamp(f"{t}-12-31"); prev = pd.Timestamp(f"{t-1}-12-31")
        for sid in df[df.cohort == t].scheme_id.unique():
            a_now = asof_val(aum, sid, now, 'avg_aum_lakh'); a_prev = asof_val(aum, sid, prev, 'avg_aum_lakh')
            n_now = asof_val(nav, sid, now, 'nav'); n_prev = asof_val(nav, sid, prev, 'nav')
            aum_g = (a_now / a_prev - 1) if (a_now and a_prev and a_prev > 0) else np.nan
            ret = (n_now / n_prev - 1) if (n_now and n_prev and n_prev > 0) else np.nan
            flow = ((1 + aum_g) / (1 + ret) - 1) if (pd.notna(aum_g) and pd.notna(ret)) else np.nan
            rows.append((sid, t, aum_g, flow))
    f = pd.DataFrame(rows, columns=['scheme_id', 'cohort', 'aum_growth_1y', 'flow_1y'])
    out = df.merge(f, on=['scheme_id', 'cohort'], how='left')
    # fill missing with cohort medians (same policy as the base pipeline)
    for col in FLOW_FEATS:
        out[col] = out.groupby('cohort')[col].transform(lambda s: s.fillna(s.median()))
        out[col] = out[col].fillna(out[col].median())
    return out


def cat_neutral_edge(df, feats, engine, shuffle_seed=None):
    """Mean category-neutral (top-2/cat) edge vs category benchmark over all cohorts."""
    edges = []
    rng = np.random.RandomState(shuffle_seed) if shuffle_seed is not None else None
    for t in COHORTS:
        tr = df[df.cohort < t]; te = df[df.cohort == t]
        mat = get_returns_matrix(engine, te.scheme_id.tolist(), f"{t}-12-31", f"{t+3}-12-31")
        bench = te[te.category_name.isin(CORE)].scheme_id.tolist()
        picks = []
        for ccat in CORE:
            a, b = tr[tr.category_name == ccat], te[te.category_name == ccat]
            if len(a) < 10 or b.empty:
                continue
            y = a['fwd_alpha'].values
            if rng is not None:
                y = rng.permutation(y)
            m = lgb.LGBMRegressor(random_state=42, n_estimators=50, max_depth=3, verbose=-1)
            m.fit(a[feats], y)
            b = b.assign(p=m.predict(b[feats]))
            picks += b.sort_values('p', ascending=False).head(2).scheme_id.tolist()
        edges.append(cagr(port_from_matrix(mat, picks)) - cagr(port_from_matrix(mat, bench)))
    return np.mean(edges)


def main():
    engine = get_engine()
    df = pd.read_csv(DATA / 'ml_dataset.csv')
    print("Building flow features from AUM + NAV...")
    dff = build_flow_features(engine, df)
    print(f"  flow features attached. Non-null flow_1y: {dff['flow_1y'].notna().mean()*100:.0f}%")

    base_edge = cat_neutral_edge(dff, FEATURES, engine)
    aug_edge = cat_neutral_edge(dff, FEATURES + FLOW_FEATS, engine)

    # negative control for the augmented model
    null = np.array([cat_neutral_edge(dff, FEATURES + FLOW_FEATS, engine, shuffle_seed=100 + s)
                     for s in range(N_SEEDS)])

    print("\n" + "=" * 60)
    print("DO FLOW FEATURES LEGITIMATELY GROW THE EDGE?")
    print("=" * 60)
    print(f"  Baseline (9 features)        edge: {base_edge*100:+.2f}%/yr")
    print(f"  Augmented (9 + 2 flow feats) edge: {aug_edge*100:+.2f}%/yr")
    print(f"  Change from flows                : {(aug_edge-base_edge)*100:+.2f}%/yr")
    print(f"\n  Augmented scrambled null: mean {null.mean()*100:+.2f}%  [{null.min()*100:+.1f}, {null.max()*100:+.1f}]")
    print(f"  Empirical p (null >= augmented) : {(null>=aug_edge).mean():.3f}")
    better = aug_edge > base_edge
    passes = (null >= aug_edge).mean() < 0.05
    print(f"\n  VERDICT: flows {'HELP' if better else 'do NOT help'} the edge; "
          f"augmented model {'PASSES' if passes else 'FAILS'} its negative control.")
    if better and passes:
        print("  -> Legitimate improvement.")
    elif not better:
        print("  -> No improvement; keep the simpler 9-feature model.")
    else:
        print("  -> Higher but not distinguishable from noise; not trustworthy.")


if __name__ == '__main__':
    main()
