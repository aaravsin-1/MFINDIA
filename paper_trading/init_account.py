"""
init_account.py -- one-time setup: create the paper account and form the initial
portfolio (10-fund strategy + category benchmark) at the latest available NAV date.

Usage:
    python init_account.py                 # inception = latest NAV date in the DB
    python init_account.py --date 2025-12-31
    python init_account.py --capital 1000000 --name "KotakStrat-Live" --force
"""
import argparse
import config
import state_db as db
import market_data as md
import strategy as strat
import engine


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="inception date YYYY-MM-DD (default: latest NAV in DB)")
    ap.add_argument("--capital", type=float, default=config.START_CAPITAL)
    ap.add_argument("--name", default="KotakCategoryNeutral")
    ap.add_argument("--force", action="store_true", help="overwrite an existing account")
    args = ap.parse_args()

    con = db.connect()
    db.init_schema(con)
    if db.account_exists(con) and not args.force:
        print("Account already exists. Use --force to reset it (this wipes paper history).")
        return
    if args.force:
        for t in ("pt_account", "pt_book", "pt_position", "pt_trade",
                  "pt_value_history", "pt_rebalance", "pt_meta"):
            con.execute(f"DELETE FROM {t}")
        con.commit()

    engine_pg = config.get_engine()
    inception = str(args.date) if args.date else str(md.latest_nav_date(engine_pg))
    print(f"Initialising paper account '{args.name}'  capital=Rs {args.capital:,.0f}  "
          f"inception={inception}")

    db.create_account(con, args.name, inception, args.capital)
    model = strat.load_or_train_model()
    engine.initialize(con, engine_pg, model, inception)

    # show what we bought
    print("\nStrategy holdings (top-2 per core category):")
    for p in db.get_positions(con, config.BOOK_STRATEGY):
        print(f"  {p['category']:<16} | {p['fund_name'][:48]:<48} | "
              f"{p['units']:.2f} units @ {p['entry_nav']:.2f}")
    nbench = len(db.get_positions(con, config.BOOK_BENCHMARK))
    print(f"\nBenchmark basket: {nbench} core-category funds (equal weight).")
    print(f"Done. State saved to {config.DB_PATH.name}. "
          f"Schedule run_paper_trading.bat to mark daily.")
    con.close()


if __name__ == "__main__":
    main()
