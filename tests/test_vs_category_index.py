"""
test_vs_category_index.py  (RESULTS_PROJECT)

The fairer absolute test: each category's picks vs (a) all funds in that category
[= our validated benchmark] and (b) that category's OWN passive index.

Two honest limits, handled explicitly:
  * Mid/Small/500 index funds only launched in 2020-2024, so category-index
    history is short -- we test only the cohorts each index actually covers.
  * We also check whether the all-funds-in-category benchmark tracks the category
    index (if so, our +2.4% "vs category funds" is effectively "vs category index").
"""
import numpy as np
import pandas as pd
import lightgbm as lgb
import warnings
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from lib import DATA, OUTPUTS, ASSETS, ROOT, get_engine, FEATURES, get_returns_matrix, port_from_matrix, get_monthly_returns, cagr

warnings.filterwarnings('ignore')
TEST_COHORTS = [2016, 2017, 2018, 2019, 2020, 2021, 2022]

# category -> (its own index fund scheme_id)
CAT_INDEX = {
    'Large Cap Fund': 6364,    # UTI Nifty 50 (full history)
    'Mid Cap Fund': 2617,      # Nippon Nifty Midcap 150 (from 2021)
    'Small Cap Fund': 2622,    # Nippon Nifty Smallcap 250 (from 2020-10)
}


def fit(tr, te, y):
    m = lgb.LGBMRegressor(random_state=42, n_estimators=50, max_depth=3, verbose=-1)
    m.fit(tr[FEATURES], y)
    return m.predict(te[FEATURES])


def main():
    engine = get_engine()
    df_all = pd.read_csv(DATA / 'ml_dataset.csv')

    for cat, idx_id in CAT_INDEX.items():
        print("=" * 70)
        print(f"{cat}   (index fund id {idx_id})")
        print("=" * 70)
        print(f"{'Cohort':<8}{'Picks(top2)':>12}{'AllFunds':>11}{'Index':>9}"
              f"{'picks-funds':>13}{'picks-index':>13}{'funds-index':>13}")
        rows = []
        for t in TEST_COHORTS:
            eval_end, fwd_end = f"{t}-12-31", f"{t+3}-12-31"
            train = df_all[(df_all['cohort'] < t) & (df_all['category_name'] == cat)]
            test = df_all[(df_all['cohort'] == t) & (df_all['category_name'] == cat)]
            if len(train) < 10 or test.empty:
                continue
            idx_r = get_monthly_returns(engine, [idx_id], eval_end, fwd_end)
            # require the index to cover (most of) the 3-year window
            if idx_r.empty or len(idx_r) < 30:
                continue
            mat = get_returns_matrix(engine, test['scheme_id'].tolist(), eval_end, fwd_end)
            test = test.assign(p=fit(train, test, train['fwd_alpha']))
            picks = test.sort_values('p', ascending=False).head(2)['scheme_id'].tolist()
            pk, fu, ix = cagr(port_from_matrix(mat, picks)), cagr(port_from_matrix(mat, test['scheme_id'].tolist())), cagr(idx_r)
            rows.append((t, pk, fu, ix))
            print(f"{t:<8}{pk*100:>11.1f}%{fu*100:>10.1f}%{ix*100:>8.1f}%"
                  f"{(pk-fu)*100:>+12.1f}%{(pk-ix)*100:>+12.1f}%{(fu-ix)*100:>+12.1f}%")
        if rows:
            d = pd.DataFrame(rows, columns=['t', 'pk', 'fu', 'ix']).mean(numeric_only=True)
            print("-" * 70)
            print(f"{'MEAN':<8}{d.pk*100:>11.1f}%{d.fu*100:>10.1f}%{d.ix*100:>8.1f}%"
                  f"{(d.pk-d.fu)*100:>+12.1f}%{(d.pk-d.ix)*100:>+12.1f}%{(d.fu-d.ix)*100:>+12.1f}%")
            print(f"  n={len(rows)} cohort(s). 'funds-index' ~0 => our category-fund benchmark tracks the index.")
        else:
            print("  (no cohorts with sufficient index history)")
        print()


if __name__ == '__main__':
    main()
