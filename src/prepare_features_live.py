"""
prepare_features_live.py  (RESULTS_PROJECT)

LIVE scoring feature builder.

`prepare_features.py` builds features AND the 3-year forward `fwd_alpha` label in
one pass, joined with an INNER join on the forward return. That is correct for
backtesting/validation, but it means a fund cannot enter the table until its
3-year future has already happened -- so it can never produce a snapshot for the
*current* year (the future isn't known yet).

This module builds the SAME feature block (identical SQL for the trailing-return,
manager, AUM and TER features) but WITHOUT the forward label, so we can score a
live, as-of-today snapshot and hand an investor a current recommendation. The
forward window is only needed to *grade* a pick, not to *make* one.

Feature definitions are copied verbatim from prepare_features.py so the live
snapshot is on the exact same distribution the model was trained on.
"""
import pandas as pd
import numpy as np
from lib import DATA, OUTPUTS, ASSETS, ROOT, FEATURES

# Same NAV-sanity band as prepare_features.py (a 3-yr trailing return outside this
# is a data error: split / rebase / merged-series stitch).
RET_LOWER, RET_UPPER = -0.95, 5.0


def build_features(engine, eval_year=None, as_of=None):
    """Return a feature table (no forward label) as-of a given date.

    Provide either `eval_year` (uses {eval_year}-12-31, the year-end convention the
    model was trained on) or `as_of` (an explicit 'YYYY-MM-DD' / date for a mid-year
    live rebalance). Trailing features look back exactly 3 years; only funds alive at
    the as-of date with >=30 months of history are returned (same filter as training).
    """
    if as_of is not None:
        eval_end = str(pd.Timestamp(as_of).date())
        hist_start = str((pd.Timestamp(as_of) - pd.DateOffset(years=3)).date())
        eval_year = pd.Timestamp(as_of).year
    else:
        eval_end = f"{eval_year}-12-31"
        hist_start = f"{eval_year-3}-12-31"

    # 0. Base universe: names + category for every direct-growth equity plan.
    #    (In prepare_features these came from the forward-target query; here we
    #    source them independently since there is no forward query.)
    base_query = f"""
        SELECT DISTINCT sp.scheme_id, s.name AS scheme_name, c.name AS category_name
        FROM scheme_plan sp
        JOIN scheme s ON sp.scheme_id = s.scheme_id
        JOIN category c ON s.category_id = c.category_id
        WHERE sp.plan_type='direct' AND sp.option_type='growth' AND c.asset_class='Equity'
    """
    df_base = pd.read_sql(base_query, engine)

    # 1. Historical 3Y features (VERBATIM from prepare_features.py)
    hist_query = f"""
    WITH monthly_prices AS (
        SELECT sp.scheme_id, pnm.month_end, pnm.nav,
               LAG(pnm.nav) OVER (PARTITION BY sp.scheme_id ORDER BY pnm.month_end) as prev_nav,
               c.name as category_name
        FROM plan_nav_monthly pnm
        JOIN scheme_plan sp ON pnm.scheme_plan_id=sp.scheme_plan_id
        JOIN scheme s ON sp.scheme_id=s.scheme_id
        JOIN category c ON s.category_id=c.category_id
        WHERE pnm.month_end >= '{hist_start}' AND pnm.month_end <= '{eval_end}'
          AND sp.plan_type='direct' AND sp.option_type='growth' AND c.asset_class='Equity'
    ),
    monthly_returns AS ( SELECT scheme_id, category_name, month_end, (nav/prev_nav)-1 AS m_ret FROM monthly_prices WHERE prev_nav IS NOT NULL ),
    category_monthly_avg AS ( SELECT category_name, month_end, AVG(m_ret) as cat_m_ret FROM monthly_returns GROUP BY category_name, month_end ),
    cum_max AS ( SELECT scheme_id, (nav / MAX(nav) OVER (PARTITION BY scheme_id ORDER BY month_end)) - 1 as dd FROM monthly_prices ),
    dd_metrics AS ( SELECT scheme_id, MIN(dd) as max_drawdown FROM cum_max GROUP BY scheme_id ),
    fund_metrics AS (
        SELECT mr.scheme_id,
               EXP(SUM(LN(1 + mr.m_ret))) - 1 as hist_return,
               STDDEV(mr.m_ret) * SQRT(12) as hist_volatility,
               AVG(CASE WHEN mr.m_ret > cma.cat_m_ret THEN 1.0 ELSE 0.0 END) as hist_hit_rate
        FROM monthly_returns mr
        JOIN category_monthly_avg cma ON mr.category_name=cma.category_name AND mr.month_end=cma.month_end
        GROUP BY mr.scheme_id HAVING COUNT(mr.m_ret) >= 30
    )
    SELECT fm.*, dm.max_drawdown FROM fund_metrics fm JOIN dd_metrics dm ON fm.scheme_id = dm.scheme_id
    """
    df_hist = pd.read_sql(hist_query, engine)
    df_hist = df_hist[(df_hist['hist_return'] >= RET_LOWER) & (df_hist['hist_return'] <= RET_UPPER)].copy()

    # 2. Manager features (VERBATIM)
    mgr_query = f"""
    WITH cur_managers AS (
        SELECT scheme_id, manager_id, start_date FROM scheme_manager WHERE start_date <= '{eval_end}' AND (end_date >= '{eval_end}' OR is_current=True)
    ),
    mgr_tenure AS (
        SELECT scheme_id, MAX((DATE '{eval_end}' - start_date) / 365.25) as max_tenure_years, COUNT(manager_id) as num_managers
        FROM cur_managers GROUP BY scheme_id
    )
    SELECT * FROM mgr_tenure
    """
    df_mgr = pd.read_sql(mgr_query, engine)

    # 3. AUM and TER features (VERBATIM)
    aum_period = pd.read_sql(f"SELECT MAX(period_end) FROM v_scheme_aum WHERE period_end <= '{eval_end}'", engine).iloc[0, 0]
    df_aum = pd.DataFrame(columns=['scheme_id', 'aum_percentile'])
    if aum_period:
        df_aum_raw = pd.read_sql(f"SELECT scheme_id, avg_aum_lakh FROM v_scheme_aum WHERE period_end='{aum_period}'", engine)
        if not df_aum_raw.empty:
            df_aum_raw['aum_percentile'] = df_aum_raw['avg_aum_lakh'].rank(pct=True)
            df_aum = df_aum_raw[['scheme_id', 'aum_percentile']]

    ter_period = pd.read_sql(f"SELECT MAX(as_of_date) FROM ter WHERE as_of_date <= '{eval_end}'", engine).iloc[0, 0]
    df_ter = pd.DataFrame(columns=['scheme_id', 'ter'])
    if ter_period:
        df_ter_raw = pd.read_sql(f"SELECT scheme_id, dir_total_ter as ter FROM ter WHERE as_of_date='{ter_period}'", engine)
        df_ter = df_ter_raw.groupby('scheme_id').first().reset_index()

    # Merge: base universe -> hist (inner: must have trailing history) -> the rest
    df = df_base.merge(df_hist.drop(columns=['category_name'], errors='ignore'), on='scheme_id', how='inner')
    df = df.merge(df_mgr, on='scheme_id', how='left')
    df = df.merge(df_aum, on='scheme_id', how='left')
    df = df.merge(df_ter, on='scheme_id', how='left')
    df['cohort'] = eval_year

    df['max_tenure_years'] = df['max_tenure_years'].fillna(0)
    df['num_managers'] = df['num_managers'].fillna(0)
    df['is_team'] = (df['num_managers'] > 1).astype(int)
    df['ter'] = pd.to_numeric(df['ter'], errors='coerce')
    df[FEATURES] = df[FEATURES].fillna(df[FEATURES].median())

    return df
