"""
market_data.py -- read-only accessors over the postgres `amfi_data` market DB.

Everything here answers "what was the direct/growth NAV of fund X on/before date D?"
and "which funds populate each core category?" -- the only market facts the paper
trader needs. All prices are the direct-plan / growth-option NAV, matching the
universe the model was trained and validated on.
"""
import pandas as pd
import config


def latest_nav_date(engine):
    """Newest NAV date available in the DB (the mark date for a daily run)."""
    return pd.read_sql("SELECT MAX(nav_date) AS d FROM nav", engine).iloc[0, 0]


def get_navs(engine, scheme_ids, as_of):
    """{scheme_id: (scheme_plan_id, nav_date, nav)} -- latest direct/growth NAV on/before as_of.

    One query for the whole list via DISTINCT ON, picking the most recent NAV per
    scheme (deterministic tie-break on plan id)."""
    if not scheme_ids:
        return {}
    ids = ",".join(str(int(s)) for s in scheme_ids)
    q = f"""
        SELECT DISTINCT ON (sp.scheme_id)
               sp.scheme_id, sp.scheme_plan_id, n.nav_date, n.nav
        FROM nav n
        JOIN scheme_plan sp ON n.scheme_plan_id = sp.scheme_plan_id
        WHERE sp.scheme_id IN ({ids})
          AND sp.plan_type='direct' AND sp.option_type='growth'
          AND n.nav_date <= '{as_of}'
        ORDER BY sp.scheme_id, n.nav_date DESC, sp.scheme_plan_id
    """
    df = pd.read_sql(q, engine)
    return {int(r.scheme_id): (int(r.scheme_plan_id), r.nav_date, float(r.nav))
            for r in df.itertuples()}


def core_universe(engine, as_of):
    """All direct/growth equity funds in the core categories that have a NAV on/before
    as_of. Returns DataFrame[scheme_id, scheme_name, category_name]."""
    cats = ",".join("'" + c.replace("'", "''") + "'" for c in config.CORE_CATS)
    q = f"""
        SELECT DISTINCT s.scheme_id, s.name AS scheme_name, c.name AS category_name
        FROM scheme_plan sp
        JOIN scheme s ON sp.scheme_id = s.scheme_id
        JOIN category c ON s.category_id = c.category_id
        JOIN nav n ON n.scheme_plan_id = sp.scheme_plan_id
        WHERE sp.plan_type='direct' AND sp.option_type='growth'
          AND c.asset_class='Equity' AND c.name IN ({cats})
          AND n.nav_date <= '{as_of}'
    """
    return pd.read_sql(q, engine)
