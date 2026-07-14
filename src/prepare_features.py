"""
prepare_features.py  (RESULTS_PROJECT - corrected pipeline)

Fixes vs. the original z_FINAL_train/prepare_features.py:

  1. NAV-OUTLIER SANITY FILTER (critical bug fix).
     The original computed the per-category forward-return benchmark as a plain
     AVG(fwd_return) with no outlier handling. A single corrupted NAV series
     (HSBC Midcap Fund: NAV 10.26 -> 458.50, a +4,367% "3-year return") inflated
     the Mid Cap 2021 benchmark to +273%, poisoning the `fwd_alpha` training
     target for all 19 mid-cap funds in that cohort (alphas of -170% to -220%).

     A 3-year total return outside [-95%, +500%] is a data error for an Indian
     active-equity fund (the true historical max is ~155%). Such rows are dropped
     BEFORE the category benchmark is computed, so they can neither poison the
     benchmark nor enter the training set. The same band is applied to the
     trailing (historical) return.

  2. Robust benchmark. The category average is additionally computed as a
     TRIMMED mean (drop the top/bottom 5% of each cohort x category) so that any
     future undetected NAV glitch cannot dominate the benchmark.

Everything else (feature definitions, filters, merge logic) is unchanged so the
comparison to the original is apples-to-apples.
"""
import os
from pathlib import Path
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from dotenv import load_dotenv
from lib import DATA

# A 3-year total return must fall inside this band to be considered real data.
# -0.95 => lost 95%; 5.0 => +500% over 3 years (~81%/yr). Anything outside is a
# NAV data error (split/rebase/merged-series stitch).
RET_LOWER, RET_UPPER = -0.95, 5.0
TRIM_FRAC = 0.05  # trim 5% tails when computing the category benchmark


def get_data(engine, cohorts):
    print("Extracting features from database (with NAV-outlier sanity filter)...")
    all_data = []
    dropped_total = 0

    for t in cohorts:
        eval_end = f"{t}-12-31"
        hist_start = f"{t-3}-12-31"
        fwd_end = f"{t+3}-12-31"

        # 1. Forward 3Y Target  (benchmark computed on SANITISED, TRIMMED returns)
        fwd_query = f"""
        WITH fwd_prices AS (
            SELECT sp.scheme_id, s.name as scheme_name, c.name as category_name,
                   MAX(CASE WHEN month_end = '{eval_end}' THEN pnm.nav END) as nav_start,
                   MAX(CASE WHEN month_end = '{fwd_end}' THEN pnm.nav END) as nav_end
            FROM plan_nav_monthly pnm
            JOIN scheme_plan sp ON pnm.scheme_plan_id=sp.scheme_plan_id
            JOIN scheme s ON sp.scheme_id=s.scheme_id
            JOIN category c ON s.category_id=c.category_id
            WHERE pnm.month_end IN ('{eval_end}', '{fwd_end}')
              AND sp.plan_type='direct' AND sp.option_type='growth' AND c.asset_class='Equity'
            GROUP BY sp.scheme_id, s.name, c.name
        ),
        fwd_returns AS (
            SELECT scheme_id, scheme_name, category_name, (nav_end / nav_start) - 1 AS fwd_return
            FROM fwd_prices
            WHERE nav_start IS NOT NULL AND nav_end IS NOT NULL
        )
        SELECT scheme_id, scheme_name, category_name, fwd_return FROM fwd_returns
        """
        fr = pd.read_sql(fwd_query, engine)
        if fr.empty:
            continue

        # --- FIX 1: drop NAV-error rows entirely (before they can poison anything)
        n_before = len(fr)
        fr = fr[(fr['fwd_return'] >= RET_LOWER) & (fr['fwd_return'] <= RET_UPPER)].copy()
        dropped = n_before - len(fr)
        dropped_total += dropped
        if dropped:
            print(f"  cohort {t}: dropped {dropped} fund(s) with corrupted forward NAV returns")

        # --- FIX 2: robust (trimmed) category benchmark
        def trimmed_mean(x):
            if len(x) < 5:
                return x.mean()
            lo, hi = x.quantile(TRIM_FRAC), x.quantile(1 - TRIM_FRAC)
            core = x[(x >= lo) & (x <= hi)]
            return core.mean() if len(core) else x.mean()

        cat_avg = fr.groupby('category_name')['fwd_return'].apply(trimmed_mean).rename('cat_avg_return')
        fr = fr.merge(cat_avg, on='category_name', how='left')
        fr['fwd_alpha'] = fr['fwd_return'] - fr['cat_avg_return']
        df_target = fr[['scheme_id', 'scheme_name', 'category_name', 'fwd_return', 'fwd_alpha']]

        # 2. Historical 3Y Features (unchanged, plus hist_return sanity band)
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
        # sanity band on trailing return (same corruption can appear on the history side)
        df_hist = df_hist[(df_hist['hist_return'] >= RET_LOWER) & (df_hist['hist_return'] <= RET_UPPER)].copy()

        # 3. Manager Features (unchanged)
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

        # 4. AUM and TER Features (unchanged)
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

        # Merge all
        df = df_target.merge(df_hist, on='scheme_id', how='inner')
        df = df.merge(df_mgr, on='scheme_id', how='left')
        df = df.merge(df_aum, on='scheme_id', how='left')
        df = df.merge(df_ter, on='scheme_id', how='left')
        df['cohort'] = t

        df['max_tenure_years'] = df['max_tenure_years'].fillna(0)
        df['num_managers'] = df['num_managers'].fillna(0)
        df['is_team'] = (df['num_managers'] > 1).astype(int)

        all_data.append(df)

    print(f"Total corrupted forward-NAV rows dropped across all cohorts: {dropped_total}")
    final_df = pd.concat(all_data, ignore_index=True)
    return final_df


if __name__ == '__main__':
    load_dotenv(Path(__file__).resolve().parent.parent / '.env')  # RESULTS_PROJECT/.env
    engine = create_engine(
        f'postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASSWORD")}@{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/{os.getenv("DB_NAME")}'
    )

    cohorts = [2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]
    df = get_data(engine, cohorts)

    features = ['hist_return', 'hist_volatility', 'hist_hit_rate', 'aum_percentile', 'ter',
                'max_tenure_years', 'num_managers', 'is_team', 'max_drawdown']
    df['ter'] = pd.to_numeric(df['ter'], errors='coerce')
    df[features] = df[features].fillna(df[features].median())

    df.to_csv(DATA / 'ml_dataset.csv', index=False)
    print(f"Saved {len(df)} rows to ml_dataset.csv.")
    # Quick integrity readout: worst |mean alpha| by cohort x category should now be sane.
    g = df.groupby(['cohort', 'category_name'])['fwd_alpha'].mean().abs()
    print(f"Max |mean fwd_alpha| within cohort x category after fix: {g.max():.4f} (was 1.85 before)")
