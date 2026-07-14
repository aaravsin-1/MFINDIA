"""
test_benchmarks_hard.py  (RESULTS_PROJECT)

Two HARDER benchmarks than the equal-weight category peer, to confirm the +2.4%
selection edge is real and not (a) an equal-weight small-tilt artifact or (b) a
disguised size/momentum factor exposure. Same walk-forward 2016-2022, same
category-neutral top-2/category construction.

  PART A -- CAP-WEIGHTED category benchmark.
     The validated benchmark equal-weights every category fund, which tilts toward
     small funds. Here we also weight peers by AUM (how the category's money is
     actually allocated). If the edge survives vs a cap-weighted peer, it is not a
     weighting artifact.

  PART B -- FACTOR-ADJUSTED ALPHA (the academic gold standard).
     Regress the strategy's monthly EXCESS return (picks - category benchmark) on
     market + size (SMB) + momentum (WML) factors built from our own core universe,
     with Newey-West (36-lag) HAC standard errors. If the intercept (alpha) is still
     positive and significant AFTER removing factor exposure, the edge is skill, not
     a tilt. (Category-neutral already removes BETWEEN-category size tilt; this tests
     the residual WITHIN-category size/momentum tilt of the picks vs their benchmark.)

Run from the RESULTS_PROJECT dir:  python test_benchmarks_hard.py
"""
import numpy as np
import pandas as pd
import lightgbm as lgb
import warnings
from scipy.stats import norm
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from lib import (DATA, OUTPUTS, ASSETS, ROOT, get_engine, FEATURES, get_returns_matrix, port_from_matrix,
                 get_monthly_returns, cagr)

warnings.filterwarnings('ignore')
TEST = [2016, 2017, 2018, 2019, 2020, 2021, 2022]
CORE = ['Large Cap Fund', 'Mid Cap Fund', 'Small Cap Fund', 'Flexi Cap Fund', 'ELSS']
NIFTY50_ID = 6364
HAC_LAGS = 36


def fit(tr, te, y):
    m = lgb.LGBMRegressor(random_state=42, n_estimators=50, max_depth=3, verbose=-1)
    m.fit(tr[FEATURES], y)
    return m.predict(te[FEATURES])


def get_aum(engine, eval_end):
    per = pd.read_sql(f"SELECT MAX(period_end) AS p FROM v_scheme_aum WHERE period_end<='{eval_end}'",
                      engine).iloc[0, 0]
    if per is None:
        return {}
    d = pd.read_sql(f"SELECT scheme_id, avg_aum_lakh FROM v_scheme_aum WHERE period_end='{per}'", engine)
    return dict(zip(d.scheme_id, d.avg_aum_lakh))


def cap_weighted(mat, ids, aum):
    """AUM-weighted monthly return series (weights fixed as-of eval date)."""
    cols = [c for c in ids if c in mat.columns and aum.get(c, 0) and aum[c] > 0]
    if not cols:
        return pd.Series(dtype=float)
    w = np.array([float(aum[c]) for c in cols])
    sub = mat[cols]
    W = pd.DataFrame(np.tile(w, (len(sub), 1)), index=sub.index, columns=cols).where(sub.notna())
    return (sub * W).sum(axis=1) / W.sum(axis=1)


def picks_and_bench(df, t):
    """Return (picks_ids, core_ids) for cohort t under the validated construction."""
    tr, te = df[df.cohort < t], df[df.cohort == t]
    core = te[te.category_name.isin(CORE)]
    picks = []
    for cat in CORE:
        a, b = tr[tr.category_name == cat], te[te.category_name == cat]
        if len(a) < 10 or b.empty:
            continue
        b = b.assign(p=fit(a, b, a['fwd_alpha']))
        picks += b.sort_values('p', ascending=False).head(2).scheme_id.tolist()
    return picks, core['scheme_id'].tolist()


def ols_hac(y, X, L):
    """OLS with Newey-West HAC (Bartlett) covariance. Returns beta, se, t."""
    n, k = X.shape
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    e = y - X @ beta
    u = X * e[:, None]                       # X_t * e_t
    S = u.T @ u
    for l in range(1, L + 1):
        w = 1 - l / (L + 1)
        G = u[l:].T @ u[:-l]
        S += w * (G + G.T)
    V = XtX_inv @ S @ XtX_inv
    se = np.sqrt(np.diag(V))
    return beta, se, beta / se


# ---------------------------------------------------------------- PART A
def part_a(engine, df):
    print("=" * 78)
    print("PART A -- CAP-WEIGHTED (AUM) category benchmark vs equal-weight")
    print("=" * 78)
    rows = []
    for t in TEST:
        eval_end, fwd_end = f"{t}-12-31", f"{t+3}-12-31"
        picks, core_ids = picks_and_bench(df, t)
        mat = get_returns_matrix(engine, list(set(picks + core_ids)), eval_end, fwd_end)
        aum = get_aum(engine, eval_end)
        s = cagr(port_from_matrix(mat, picks))
        ew = cagr(port_from_matrix(mat, core_ids))
        cw = cagr(cap_weighted(mat, core_ids, aum))
        rows.append((t, s, ew, cw))
    d = pd.DataFrame(rows, columns=['cohort', 'strat', 'ew', 'cw'])
    print(f"\n{'Cohort':<8}{'Strategy':>10}{'EW bench':>10}{'CW bench':>10}"
          f"{'vs EW':>9}{'vs CW':>9}")
    for _, r in d.iterrows():
        print(f"{int(r.cohort):<8}{r.strat*100:>9.1f}%{r.ew*100:>9.1f}%{r.cw*100:>9.1f}%"
              f"{(r.strat-r.ew)*100:>+8.1f}%{(r.strat-r.cw)*100:>+8.1f}%")
    m = d.mean(numeric_only=True)
    ew_edge, cw_edge = m.strat - m.ew, m.strat - m.cw
    win_ew = int((d.strat > d.ew).sum()); win_cw = int((d.strat > d.cw).sum())
    print("-" * 78)
    print(f"{'MEAN':<8}{m.strat*100:>9.1f}%{m.ew*100:>9.1f}%{m.cw*100:>9.1f}%"
          f"{ew_edge*100:>+8.1f}%{cw_edge*100:>+8.1f}%")
    print(f"\n  Edge vs EQUAL-WEIGHT peer : {ew_edge*100:+.2f}%/yr  ({win_ew}/7 cohorts)  [validated benchmark]")
    print(f"  Edge vs CAP-WEIGHT  peer : {cw_edge*100:+.2f}%/yr  ({win_cw}/7 cohorts)  [harder benchmark]")
    verdict = cw_edge > 0 and win_cw >= 5
    print(f"  -> {'SURVIVES cap-weighting (not an equal-weight/small-tilt artifact).' if verdict else 'WEAKENS vs cap-weight -- some edge is a weighting effect.'}")
    return cw_edge, win_cw


# ---------------------------------------------------------------- PART B
def part_b(engine, df):
    print("\n" + "=" * 78)
    print("PART B -- FACTOR-ADJUSTED ALPHA  (excess ~ market + size + momentum, HAC)")
    print("=" * 78)
    frames = []
    for t in TEST:
        eval_end, fwd_end = f"{t}-12-31", f"{t+3}-12-31"
        te = df[df.cohort == t]
        core = te[te.category_name.isin(CORE)]
        picks, core_ids = picks_and_bench(df, t)
        mat = get_returns_matrix(engine, core_ids, eval_end, fwd_end)
        if mat.empty:
            continue
        excess = port_from_matrix(mat, picks) - port_from_matrix(mat, core_ids)
        # SMB (small-minus-big) and WML (winners-minus-losers) from the core universe as-of t
        aum_q = core['aum_percentile']
        small = core[core.aum_percentile <= aum_q.quantile(0.33)].scheme_id.tolist()
        big = core[core.aum_percentile >= aum_q.quantile(0.67)].scheme_id.tolist()
        smb = port_from_matrix(mat, small) - port_from_matrix(mat, big)
        hr = core['hist_return']
        win = core[core.hist_return >= hr.quantile(0.67)].scheme_id.tolist()
        los = core[core.hist_return <= hr.quantile(0.33)].scheme_id.tolist()
        wml = port_from_matrix(mat, win) - port_from_matrix(mat, los)
        mkt = get_monthly_returns(engine, [NIFTY50_ID], eval_end, fwd_end)
        fr = pd.concat({'excess': excess, 'mkt': mkt, 'smb': smb, 'wml': wml}, axis=1).dropna()
        frames.append(fr)
    data = pd.concat(frames, ignore_index=True)
    y = data['excess'].values
    X = np.column_stack([np.ones(len(data)), data['mkt'], data['smb'], data['wml']])
    beta, se, tstat = ols_hac(y, X, HAC_LAGS)
    names = ['alpha', 'mkt_beta', 'smb_beta', 'wml_beta']
    print(f"\n  n = {len(data)} pooled fund-months; HAC lags = {HAC_LAGS}")
    print(f"\n  {'term':<10}{'coef(mo)':>10}{'t (HAC)':>10}{'ann. (~x12)':>13}")
    for i, nm in enumerate(names):
        ann = f"{beta[i]*12*100:+.2f}%" if i == 0 else ""
        print(f"  {nm:<10}{beta[i]*100:>+9.3f}%{tstat[i]:>10.2f}{ann:>13}")
    p_alpha = 2 * (1 - norm.cdf(abs(tstat[0])))
    ann_alpha = beta[0] * 12 * 100
    print(f"\n  Factor-adjusted ALPHA = {ann_alpha:+.2f}%/yr, HAC t = {tstat[0]:.2f}, p ~ {p_alpha:.4f}")
    sig = p_alpha < 0.05 and beta[0] > 0
    print(f"  size tilt (smb_beta {beta[2]:+.2f}) and momentum tilt (wml_beta {beta[3]:+.2f}) "
          f"of picks vs their benchmark")
    print(f"  -> {'ALPHA SURVIVES factor adjustment -> genuine selection skill, not a size/momentum tilt.' if sig else 'Alpha NOT significant after factors -> edge may be factor exposure.'}")
    return ann_alpha, tstat[0], p_alpha


def main():
    engine = get_engine()
    df = pd.read_csv(DATA / 'ml_dataset.csv')
    cw_edge, win_cw = part_a(engine, df)
    ann_alpha, t_alpha, p_alpha = part_b(engine, df)

    print("\n" + "=" * 78)
    print("SUMMARY -- does the +2.4% survive harder benchmarks?")
    print("=" * 78)
    print(f"  A. vs CAP-WEIGHTED peer : {cw_edge*100:+.2f}%/yr ({win_cw}/7) "
          f"-> {'survives' if cw_edge>0 and win_cw>=5 else 'weakens'}")
    print(f"  B. factor-adjusted alpha: {ann_alpha:+.2f}%/yr (HAC t={t_alpha:.2f}, p={p_alpha:.4f}) "
          f"-> {'real skill' if p_alpha<0.05 and ann_alpha>0 else 'not distinguishable from factors'}")
    print("\n  These are the two most definitive confirmations this data allows. The remaining")
    print("  external benchmark (full-cycle passive index TRI) is blocked by index-fund history.")


if __name__ == '__main__':
    main()
