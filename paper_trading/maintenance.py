"""
maintenance.py -- data-freshness & retrain-due logic, shared by update_daily.py and
report.py so every run reminds you when the model needs new data / a retrain.

Key idea: the daily job only needs NAVs. The MODEL (used at each annual rebalance and
when retraining) additionally needs monthly-NAV rollup, AUM, TER and manager data.
A *retrain* only adds value when a new cohort's 3-year forward label has closed, which
happens at most once a year -- so we compute exactly when that unlocks.
"""
import pandas as pd
import config

# a scoring input is "stale" if it lags the latest daily NAV by more than this
STALE_DAYS = 130


def _maxdate(engine, sql):
    try:
        v = pd.read_sql(sql, engine).iloc[0, 0]
        return pd.Timestamp(v) if v is not None else None
    except Exception:
        return None


def data_freshness(engine):
    return {
        'nav_daily':        _maxdate(engine, "SELECT MAX(nav_date) FROM nav"),
        'plan_nav_monthly': _maxdate(engine, "SELECT MAX(month_end) FROM plan_nav_monthly"),
        'ter':              _maxdate(engine, "SELECT MAX(as_of_date) FROM ter"),
        'aum':              _maxdate(engine, "SELECT MAX(period_end) FROM v_scheme_aum"),
        'managers':         _maxdate(engine, "SELECT MAX(start_date) FROM scheme_manager"),
    }


def retrain_status(engine):
    """Compute whether a retrain is due and when the next cohort unlocks."""
    fresh = data_freshness(engine)
    pnm = fresh['plan_nav_monthly']
    try:
        trained = int(pd.read_csv(config.DATASET_PATH)['cohort'].max())
    except Exception:
        trained = None

    # a cohort Y is labelable once monthly NAVs reach (Y+3)-12-31
    max_labelable = None
    if pnm is not None:
        y = pnm.year
        while y >= 2013:
            if pd.Timestamp(f"{y+3}-12-31") <= pnm:
                max_labelable = y
                break
            y -= 1

    due = (trained is not None and max_labelable is not None and max_labelable > trained)
    next_cohort = (trained + 1) if trained is not None else None
    unlock_date = pd.Timestamp(f"{next_cohort+3}-12-31") if next_cohort else None
    return {
        'fresh': fresh, 'trained_through': trained, 'max_labelable': max_labelable,
        'retrain_due': due, 'next_cohort': next_cohort, 'next_unlock': unlock_date,
    }


def panel(engine, verbose=True):
    """Return a short multi-line maintenance panel (and print it if verbose)."""
    st = retrain_status(engine)
    f = st['fresh']
    nav = f['nav_daily']
    lines = ["-- DATA / RETRAIN STATUS " + "-" * 43]

    def stale_tag(d):
        if d is None or nav is None:
            return "?"
        lag = (nav - d).days
        return f"{d.date()}  ({lag}d behind NAV){'  <-- STALE' if lag > STALE_DAYS else ''}"

    lines.append(f"  daily NAV (marking)   : {nav.date() if nav is not None else '?'}")
    lines.append(f"  monthly NAV (model)   : {stale_tag(f['plan_nav_monthly'])}")
    lines.append(f"  AUM (model)           : {stale_tag(f['aum'])}")
    lines.append(f"  TER (model)           : {stale_tag(f['ter'])}")
    lines.append(f"  managers (model)      : {stale_tag(f['managers'])}")
    if st['trained_through'] is not None:
        if st['retrain_due']:
            lines.append(f"  >> RETRAIN DUE: cohort {st['max_labelable']} is now labelable "
                         f"(model trained through {st['trained_through']}).")
            lines.append(f"     Run:  python annual_maintenance.py --refresh-data --retrain")
        else:
            lines.append(f"  model trained through cohort {st['trained_through']}; "
                         f"next cohort {st['next_cohort']} unlocks after "
                         f"{st['next_unlock'].date()} -> retrain NOT due.")
    lines.append("-" * 68)
    text = "\n".join(lines)
    if verbose:
        print(text)
    return text
