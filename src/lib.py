"""
lib.py - shared helpers for the RESULTS_PROJECT validation & screening scripts.

Centralises DB access and portfolio math so every script uses identical logic
(the original z_FINAL_train copy-pasted these into 8 files, which drifts).
"""
import os
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

FEATURES = ['hist_return', 'hist_volatility', 'hist_hit_rate', 'aum_percentile',
            'ter', 'max_tenure_years', 'num_managers', 'is_team', 'max_drawdown']

# Project layout (this file lives in RESULTS_PROJECT/src/). All paths are resolved
# absolutely from here so scripts work regardless of the current working directory.
ROOT = Path(__file__).resolve().parent.parent      # RESULTS_PROJECT/
DATA = ROOT / 'data'                                # datasets + trained models
OUTPUTS = ROOT / 'outputs'                          # generated fund lists (deliverables)
ASSETS = ROOT / 'assets'                            # generated figures

# Single source of DB credentials for the whole project: RESULTS_PROJECT/.env
DEFAULT_ENV = ROOT / '.env'


def get_engine(env_path=None):
    load_dotenv(env_path or DEFAULT_ENV)
    return create_engine(
        f'postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASSWORD")}'
        f'@{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/{os.getenv("DB_NAME")}'
    )


def get_monthly_returns(engine, scheme_ids, start_date, end_date):
    """Equal-weighted monthly return series for a set of scheme_ids over (start,end]."""
    if not scheme_ids:
        return pd.Series(dtype=float)
    funds_str = ",".join(map(str, scheme_ids))
    q = f"""
    WITH monthly_prices AS (
        SELECT sp.scheme_id, pnm.month_end, pnm.nav,
               LAG(pnm.nav) OVER (PARTITION BY sp.scheme_id ORDER BY pnm.month_end) as prev_nav
        FROM plan_nav_monthly pnm JOIN scheme_plan sp ON pnm.scheme_plan_id=sp.scheme_plan_id
        WHERE pnm.month_end > '{start_date}' AND pnm.month_end <= '{end_date}'
          AND sp.scheme_id IN ({funds_str}) AND sp.plan_type='direct' AND sp.option_type='growth'
    ),
    monthly_returns AS ( SELECT scheme_id, month_end, (nav/prev_nav)-1 AS m_ret FROM monthly_prices WHERE prev_nav IS NOT NULL )
    SELECT month_end, AVG(m_ret) as port_m_ret FROM monthly_returns GROUP BY month_end ORDER BY month_end
    """
    df = pd.read_sql(q, engine)
    if df.empty:
        return pd.Series(dtype=float)
    df.set_index('month_end', inplace=True)
    return df['port_m_ret']


def get_returns_matrix(engine, scheme_ids, start_date, end_date):
    """month_end x scheme_id matrix of monthly returns (one query, reused for many portfolios)."""
    if not scheme_ids:
        return pd.DataFrame()
    funds_str = ",".join(map(str, scheme_ids))
    q = f"""
    WITH monthly_prices AS (
        SELECT sp.scheme_id, pnm.month_end, pnm.nav,
               LAG(pnm.nav) OVER (PARTITION BY sp.scheme_id ORDER BY pnm.month_end) as prev_nav
        FROM plan_nav_monthly pnm JOIN scheme_plan sp ON pnm.scheme_plan_id=sp.scheme_plan_id
        WHERE pnm.month_end > '{start_date}' AND pnm.month_end <= '{end_date}'
          AND sp.scheme_id IN ({funds_str}) AND sp.plan_type='direct' AND sp.option_type='growth'
    )
    SELECT scheme_id, month_end, (nav/prev_nav)-1 AS m_ret FROM monthly_prices WHERE prev_nav IS NOT NULL
    """
    df = pd.read_sql(q, engine)
    if df.empty:
        return pd.DataFrame()
    return df.pivot_table(index='month_end', columns='scheme_id', values='m_ret')


def port_from_matrix(mat, scheme_ids):
    """Equal-weighted monthly return series from a returns matrix for the given ids."""
    if mat.empty:
        return pd.Series(dtype=float)
    cols = [c for c in scheme_ids if c in mat.columns]
    if not cols:
        return pd.Series(dtype=float)
    return mat[cols].mean(axis=1).dropna()


def cagr(port_rets):
    if port_rets is None or port_rets.empty:
        return 0.0
    total = np.prod(1 + port_rets) - 1
    years = len(port_rets) / 12
    return (1 + total) ** (1 / years) - 1


def excess_monthly(port_rets, bench_rets):
    """Aligned monthly excess-return series (port - bench)."""
    if port_rets.empty or bench_rets.empty:
        return pd.Series(dtype=float)
    aligned = pd.concat([port_rets, bench_rets], axis=1).dropna()
    if aligned.empty:
        return pd.Series(dtype=float)
    return aligned.iloc[:, 0] - aligned.iloc[:, 1]


def info_ratio(port_rets, bench_rets):
    ex = excess_monthly(port_rets, bench_rets)
    if ex.empty or ex.std() == 0:
        return 0.0
    return (ex.mean() / ex.std()) * np.sqrt(12)
