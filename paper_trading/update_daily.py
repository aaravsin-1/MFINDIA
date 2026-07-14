"""
update_daily.py -- the daily cron entrypoint (called by run_paper_trading.bat ~9pm).

Steps:
  1. Fetch the day's NAVs into postgres via scraper/load_navall.py (skippable, non-fatal
     if the AMFI download/DB write fails -- we still mark on the latest stored NAV).
  2. Mark both books to market at the latest NAV date.
  3. If a rebalance is due (>= REBALANCE_INTERVAL_DAYS since the last one), rebalance
     the strategy (top-4 buffer, 12-month min-hold) and re-equalise the benchmark.

All output is echoed and appended to logs/paper_YYYY-MM-DD.log by the .bat.

Usage:
    python update_daily.py                 # normal daily run
    python update_daily.py --no-fetch      # skip the AMFI download (mark on stored data)
    python update_daily.py --force-rebalance
"""
import argparse
import subprocess
import sys
from datetime import datetime

import config
import state_db as db
import market_data as md
import strategy as strat
import engine
import maintenance


def fetch_navs():
    """Pull the latest NAVAll.txt into postgres (reuses the project's own loader)."""
    script = config.SCRAPER_DIR / "load_navall.py"
    if not script.exists():
        print(f"[warn] {script} not found; skipping NAV fetch.")
        return
    print(f"[{datetime.now():%H:%M:%S}] Fetching NAVs via {script.name} ...")
    try:
        r = subprocess.run([sys.executable, str(script), "--dsn", config.get_dsn()],
                           cwd=str(config.SCRAPER_DIR), timeout=1800)
        print(f"[info] load_navall exit code {r.returncode}")
    except Exception as e:                              # noqa: BLE001 -- must stay non-fatal
        print(f"[warn] NAV fetch failed ({e}); marking on stored NAVs instead.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true", help="don't download NAVs, mark on stored data")
    ap.add_argument("--force-rebalance", action="store_true")
    args = ap.parse_args()

    print("=" * 68)
    print(f"PAPER-TRADE DAILY RUN  {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("=" * 68)

    con = db.connect()
    db.init_schema(con)
    if not db.account_exists(con):
        print("[error] No paper account. Run:  python init_account.py")
        return

    if not args.no_fetch:
        fetch_navs()

    engine_pg = config.get_engine()
    mark_date = str(md.latest_nav_date(engine_pg))
    meta = db.get_meta(con)

    if meta['last_mark_date'] == mark_date and not args.force_rebalance:
        print(f"[info] Already marked for {mark_date}. Nothing new to do.")
    else:
        print(f"[{datetime.now():%H:%M:%S}] Marking to market @ {mark_date} ...")
        engine.mark_to_market(con, engine_pg, mark_date)

    # rebalance if due
    if args.force_rebalance or engine.rebalance_due(con, mark_date):
        print(f"[{datetime.now():%H:%M:%S}] Rebalance due -> scoring live universe ...")
        model = strat.load_or_train_model()
        summary = engine.rebalance(con, engine_pg, model, mark_date)
        print(f"[rebalance] {summary}")
    else:
        nxt = config.REBALANCE_INTERVAL_DAYS - engine._days_between(meta['last_rebalance_date'], mark_date)
        print(f"[info] No rebalance (next due in ~{nxt} days).")

    # concise status line
    s = db.get_account(con)
    for book in (config.BOOK_STRATEGY, config.BOOK_BENCHMARK):
        row = con.execute(
            "SELECT total FROM pt_value_history WHERE account_id=1 AND book=? ORDER BY date DESC LIMIT 1",
            (book,)).fetchone()
        if row:
            ret = (row['total'] / s['start_capital'] - 1) * 100
            print(f"  {book:<9} total = Rs {row['total']:,.0f}  ({ret:+.2f}% since {s['inception_date']})")

    # data-freshness / retrain reminder
    print()
    maintenance.panel(engine_pg)
    print("Daily run complete.")
    con.close()


if __name__ == "__main__":
    main()
