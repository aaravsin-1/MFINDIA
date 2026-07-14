"""
backfill.py -- replay daily marks from the account inception up to the latest NAV
date already stored in the DB, so you get an immediate real track record instead of
waiting for the cron to accumulate one day at a time.

Marks every business day (weekends skipped; holidays carry the prior NAV forward
because get_navs takes the latest NAV on/before the date). Triggers a rebalance
whenever one becomes due during the replay.

Usage:
    python backfill.py
"""
from datetime import datetime
import pandas as pd

import config
import state_db as db
import market_data as md
import strategy as strat
import engine


def main():
    con = db.connect()
    db.init_schema(con)
    if not db.account_exists(con):
        print("No paper account. Run: python init_account.py")
        return
    acct = db.get_account(con)
    engine_pg = config.get_engine()
    latest = pd.Timestamp(md.latest_nav_date(engine_pg))
    start = pd.Timestamp(acct['inception_date'])

    dates = pd.bdate_range(start + pd.Timedelta(days=1), latest)
    if len(dates) == 0:
        print(f"Nothing to backfill (inception {start.date()} >= latest NAV {latest.date()}).")
        return
    print(f"Backfilling {len(dates)} business days: {dates[0].date()} -> {dates[-1].date()} ...")

    model = None
    for i, d in enumerate(dates):
        ds = str(d.date())
        engine.mark_to_market(con, engine_pg, ds)
        if engine.rebalance_due(con, ds):
            if model is None:
                model = strat.load_or_train_model()
            print(f"  [{ds}] rebalance due ...")
            print("   ", engine.rebalance(con, engine_pg, model, ds))
        if (i + 1) % 20 == 0:
            print(f"  ... {i+1}/{len(dates)} marked (through {ds})")

    print(f"Backfill complete through {dates[-1].date()}. Run: python report.py")
    con.close()


if __name__ == "__main__":
    main()
