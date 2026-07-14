"""
test_vs_index.py  (RESULTS_PROJECT)

Tests the honesty claim: our +2.4% edge is RELATIVE (vs other funds). This script
adds an ABSOLUTE market benchmark -- a Nifty 50 index fund -- so we can see:

  (a) Do the picks beat the market index? (absolute "beat the market")
  (b) Do active funds as a group even beat the index? (active vs passive)
  (c) Is our fund-selection edge separate from whatever the index does?

Same 3-year forward windows and category-neutral construction as the validated
strategy. Nifty 50 index fund = UTI Nifty 50 (scheme_id 6364, full history).
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
CORE_CATS = ['Large Cap Fund', 'Mid Cap Fund', 'Small Cap Fund', 'Flexi Cap Fund', 'ELSS']
NIFTY50_ID = 6364  # UTI Nifty 50 Index Fund (direct-growth), NAVs from 2013


def fit(tr, te, y):
    m = lgb.LGBMRegressor(random_state=42, n_estimators=50, max_depth=3, verbose=-1)
    m.fit(tr[FEATURES], y)
    return m.predict(te[FEATURES])


def main():
    engine = get_engine()
    df_all = pd.read_csv(DATA / 'ml_dataset.csv')

    rows = []
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

        picks_cagr = cagr(port_from_matrix(mat, picks))
        bench_cagr = cagr(port_from_matrix(mat, bench))
        nifty_cagr = cagr(get_monthly_returns(engine, [NIFTY50_ID], eval_end, fwd_end))
        rows.append((t, picks_cagr, bench_cagr, nifty_cagr))

    df = pd.DataFrame(rows, columns=['cohort', 'picks', 'bench', 'nifty'])

    print("=" * 72)
    print("STRATEGY vs FUND BENCHMARK vs MARKET INDEX (Nifty 50)  — 3yr fwd, annualised")
    print("=" * 72)
    print(f"\n{'Cohort':<8}{'ML picks':>10}{'Cat-bench':>11}{'Nifty50':>10}"
          f"{'picks-bench':>13}{'picks-Nifty':>13}{'bench-Nifty':>13}")
    for _, r in df.iterrows():
        print(f"{int(r.cohort):<8}{r.picks*100:>9.1f}%{r.bench*100:>10.1f}%{r.nifty*100:>9.1f}%"
              f"{(r.picks-r.bench)*100:>+12.1f}%{(r.picks-r.nifty)*100:>+12.1f}%{(r.bench-r.nifty)*100:>+12.1f}%")

    m = df.mean(numeric_only=True)
    print("-" * 72)
    print(f"{'MEAN':<8}{m.picks*100:>9.1f}%{m.bench*100:>10.1f}%{m.nifty*100:>9.1f}%"
          f"{(m.picks-m.bench)*100:>+12.1f}%{(m.picks-m.nifty)*100:>+12.1f}%{(m.bench-m.nifty)*100:>+12.1f}%")

    print("\nREAD:")
    print(f"  picks - bench  = fund SELECTION skill (validated)      : {(m.picks-m.bench)*100:+.2f}%/yr")
    print(f"  bench - Nifty  = active funds vs the market (a tilt)    : {(m.bench-m.nifty)*100:+.2f}%/yr")
    print(f"  picks - Nifty  = total gap vs the index (mix of both)   : {(m.picks-m.nifty)*100:+.2f}%/yr")
    wins_idx = int((df.picks > df.nifty).sum())
    wins_sel = int((df.picks > df.bench).sum())
    print(f"\n  Picks beat the fund benchmark in {wins_sel}/7 cohorts (SELECTION skill).")
    print(f"  Picks beat the Nifty 50 index  in {wins_idx}/7 cohorts (market-relative).")
    print("\n  NOTE: Nifty 50 is a LARGE-CAP index; our portfolio includes mid/small/flexi/ELSS,")
    print("  so 'picks - Nifty' also contains a size/style tilt, not pure skill. The clean")
    print("  skill number is 'picks - bench' (same categories on both sides).")


if __name__ == '__main__':
    main()
