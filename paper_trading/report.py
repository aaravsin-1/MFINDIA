"""
report.py -- human-readable status of the paper trade.

Shows current holdings, gross return of the strategy vs the category benchmark, the
live edge, a rough after-LTCG net figure, recent trades, and rebalance history. Also
writes reports/paper_report.csv (the daily value series) for charting.

Usage:
    python report.py
"""
import pandas as pd
import config
import state_db as db

LTCG_RATE = 0.125   # 12.5% long-term capital gains (holds are >12 months by design)


def _series(con, book):
    df = pd.read_sql_query(
        "SELECT date, total FROM pt_value_history WHERE account_id=1 AND book=? ORDER BY date",
        con, params=(book,))
    return df


def main():
    con = db.connect()
    if not db.account_exists(con):
        print("No paper account yet. Run: python init_account.py")
        return
    acct = db.get_account(con)
    start = acct['start_capital']

    strat_s = _series(con, config.BOOK_STRATEGY)
    bench_s = _series(con, config.BOOK_BENCHMARK)
    if strat_s.empty:
        print("No marks yet. Run: python update_daily.py")
        return

    s_now = strat_s['total'].iloc[-1]
    b_now = bench_s['total'].iloc[-1]
    last_date = strat_s['date'].iloc[-1]
    days = (pd.Timestamp(last_date) - pd.Timestamp(acct['inception_date'])).days or 1
    yrs = days / 365.25

    s_ret = s_now / start - 1
    b_ret = b_now / start - 1
    s_cagr = (1 + s_ret) ** (1 / yrs) - 1 if yrs > 0 else s_ret
    b_cagr = (1 + b_ret) ** (1 / yrs) - 1 if yrs > 0 else b_ret

    # realized gains to date (from the ledger) -> rough LTCG drag on the strategy
    realized = con.execute(
        "SELECT COALESCE(SUM(realized_pnl),0) FROM pt_trade WHERE book=? AND action='SELL'",
        (config.BOOK_STRATEGY,)).fetchone()[0]
    unrealized = s_now - db.get_cash(con, config.BOOK_STRATEGY) - sum(
        p['units'] * p['entry_nav'] for p in db.get_positions(con, config.BOOK_STRATEGY))
    tax_est = LTCG_RATE * max(0.0, realized + unrealized)
    s_net = s_now - tax_est

    print("=" * 70)
    print(f" PAPER TRADE: {acct['name']}   inception {acct['inception_date']} -> {last_date} "
          f"({days}d / {yrs:.2f}y)")
    print("=" * 70)
    print(f"  Start capital           : Rs {start:,.0f}  per book")
    print(f"  Strategy  total (gross) : Rs {s_now:,.0f}   ({s_ret*100:+.2f}%, CAGR {s_cagr*100:+.2f}%)")
    print(f"  Benchmark total         : Rs {b_now:,.0f}   ({b_ret*100:+.2f}%, CAGR {b_cagr*100:+.2f}%)")
    print(f"  LIVE EDGE (strat-bench) : {(s_ret-b_ret)*100:+.2f}%   (CAGR {(s_cagr-b_cagr)*100:+.2f}%/yr)")
    print(f"  Strategy after est. LTCG: Rs {s_net:,.0f}   "
          f"(tax est Rs {tax_est:,.0f} on realized+unrealized gains @ {LTCG_RATE*100:.1f}%)")

    print("\n  Current strategy holdings:")
    rows = db.get_positions(con, config.BOOK_STRATEGY)
    for p in sorted(rows, key=lambda r: r['category']):
        mv = p['units'] * p['last_nav']
        pnl = (p['last_nav'] / p['entry_nav'] - 1) * 100
        print(f"    {p['category']:<16} | {p['fund_name'][:44]:<44} | "
              f"MV Rs {mv:>10,.0f} | {pnl:+6.1f}% | since {p['entry_date']}")
    cash = db.get_cash(con, config.BOOK_STRATEGY)
    if cash > 1:
        print(f"    {'(cash)':<16} | {'':44} | MV Rs {cash:>10,.0f}")

    print("\n  Recent trades:")
    tr = con.execute(
        "SELECT trade_date,book,action,fund_name,amount,reason FROM pt_trade "
        "ORDER BY trade_id DESC LIMIT 8").fetchall()
    for t in tr:
        print(f"    {t['trade_date']} {t['book']:<9} {t['action']:<4} "
              f"Rs {t['amount']:>9,.0f}  {t['fund_name'][:34]:<34} [{t['reason']}]")

    print("\n  Rebalance log:")
    for rb in con.execute("SELECT date,summary FROM pt_rebalance ORDER BY rebalance_id").fetchall():
        print(f"    {rb['date']}: {rb['summary'][:90]}")

    # export the value series for charting
    out = strat_s.rename(columns={'total': 'strategy'}).merge(
        bench_s.rename(columns={'total': 'benchmark'}), on='date', how='outer').sort_values('date')
    out.to_csv(config.REPORT_DIR / "paper_report.csv", index=False)
    print(f"\n  Value series written to reports/paper_report.csv ({len(out)} marks).")

    # data-freshness / retrain reminder
    print()
    import maintenance
    maintenance.panel(config.get_engine())
    con.close()


if __name__ == "__main__":
    main()
