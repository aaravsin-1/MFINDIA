"""
engine.py -- the paper-trading engine.

Two books share one account for a fair, live comparison:
  * strategy : the validated 10-fund category-neutral portfolio (top-2/core category),
               rebalanced annually with a top-4 buffer and a 12-month min-hold.
  * benchmark: an equal-weight basket of ALL core-category funds (the category-matched
               benchmark the +2.4% edge was measured against), re-equalised each rebalance.

Everything is marked at the direct/growth NAV. Returns reported are GROSS; a simple
LTCG-aware net figure is derived in report.py.
"""
from datetime import datetime
import pandas as pd

import config
import state_db as db
import market_data as md
import strategy as strat


def _days_between(d1, d2):
    return (pd.Timestamp(d2) - pd.Timestamp(d1)).days


# --------------------------------------------------------------------------- trades
def buy(con, book, date, scheme_id, fund_name, category, amount, nav, reason):
    """Buy `amount` worth of a fund at `nav`. Merges into an existing lot (weighted-avg
    cost, keeps the original entry_date so the min-hold clock isn't reset)."""
    if amount <= 0 or nav <= 0:
        return
    units = amount / nav
    pos = db.get_position(con, book, scheme_id)
    if pos:
        tot_units = pos['units'] + units
        avg_nav = (pos['units'] * pos['entry_nav'] + units * nav) / tot_units
        db.upsert_position(con, book, scheme_id, fund_name, category, tot_units, avg_nav,
                           pos['entry_date'], nav, date)
    else:
        db.upsert_position(con, book, scheme_id, fund_name, category, units, nav, date, nav, date)
    db.set_cash(con, book, db.get_cash(con, book) - amount)
    db.record_trade(con, book, date, scheme_id, fund_name, category, 'BUY', units, nav, None, reason)


def sell(con, book, date, scheme_id, nav, reason):
    """Fully liquidate a fund position at `nav`."""
    pos = db.get_position(con, book, scheme_id)
    if not pos:
        return
    units = pos['units']
    proceeds = units * nav
    realized = units * (nav - pos['entry_nav'])
    db.set_cash(con, book, db.get_cash(con, book) + proceeds)
    db.record_trade(con, book, date, scheme_id, pos['fund_name'], pos['category'], 'SELL',
                    units, nav, realized, reason)
    db.delete_position(con, book, scheme_id)


# --------------------------------------------------------------------------- marking
def mark_to_market(con, engine, mark_date):
    """Value every book at the given date's NAVs and append to pt_value_history."""
    mark_date = str(mark_date)
    for book in (config.BOOK_STRATEGY, config.BOOK_BENCHMARK):
        positions = db.get_positions(con, book)
        ids = [p['scheme_id'] for p in positions]
        navs = md.get_navs(engine, ids, mark_date)
        value = 0.0
        for p in positions:
            info = navs.get(p['scheme_id'])
            nav = info[2] if info else p['last_nav']          # fall back to last known
            if info:
                db.upsert_position(con, book, p['scheme_id'], p['fund_name'], p['category'],
                                   p['units'], p['entry_nav'], p['entry_date'], nav, mark_date)
            value += p['units'] * nav
        db.record_value(con, book, mark_date, value, db.get_cash(con, book))
    db.set_meta(con, last_mark_date=mark_date)
    con.commit()


# --------------------------------------------------------------------------- rebalance
def _equal_weight_deploy(con, engine, book, date, id_to_meta, target_ids, cash_pool, reason):
    """Deploy `cash_pool` equally across target_ids (that aren't already held)."""
    to_buy = [i for i in target_ids if not db.get_position(con, book, i)]
    if not to_buy:
        return cash_pool
    navs = md.get_navs(engine, to_buy, date)
    alloc = cash_pool / len(to_buy)
    spent = 0.0
    for sid in to_buy:
        info = navs.get(sid)
        if not info:
            continue
        name, cat = id_to_meta.get(sid, ("?", "?"))
        buy(con, book, date, sid, name, cat, alloc, info[2], reason)
        spent += alloc
    return cash_pool - spent


def initialize(con, engine, model, date):
    """First formation: buy the 10-fund strategy and the full category benchmark."""
    date = str(date)
    ranked, benchmark_ids = strat.score_asof(engine, model, date)
    if ranked.empty:
        raise RuntimeError(f"No scorable core-category funds as-of {date}.")
    id_to_meta = {int(r.scheme_id): (r.scheme_name, r.category_name) for r in ranked.itertuples()}

    # strategy: equal weight across top-2 per category
    picks = strat.target_top2(ranked)
    cash = db.get_cash(con, config.BOOK_STRATEGY)
    left = _equal_weight_deploy(con, engine, config.BOOK_STRATEGY, date, id_to_meta, picks, cash,
                                "INIT top-2/category")
    db.set_cash(con, config.BOOK_STRATEGY, left)

    # benchmark: equal weight across all core-category funds
    cash_b = db.get_cash(con, config.BOOK_BENCHMARK)
    left_b = _equal_weight_deploy(con, engine, config.BOOK_BENCHMARK, date, id_to_meta,
                                  benchmark_ids, cash_b, "INIT category basket")
    db.set_cash(con, config.BOOK_BENCHMARK, left_b)

    db.record_rebalance(con, date, f"INIT: {len(picks)} strategy funds, "
                                   f"{len(benchmark_ids)} benchmark funds")
    db.set_meta(con, last_rebalance_date=date)
    con.commit()
    mark_to_market(con, engine, date)


def rebalance(con, engine, model, date):
    """Annual rebalance with a top-4 buffer and 12-month min-hold on the strategy book;
    the benchmark book is re-equalised across the current core universe."""
    date = str(date)
    ranked, benchmark_ids = strat.score_asof(engine, model, date)
    if ranked.empty:
        return "skip: no scorable funds"
    id_to_meta = {int(r.scheme_id): (r.scheme_name, r.category_name) for r in ranked.itertuples()}
    changes = []

    # ---- STRATEGY: buffer logic per category ----
    for cat in config.CORE_CATS:
        sub = ranked[ranked['category_name'] == cat]
        if sub.empty:
            continue
        ordered = sub['scheme_id'].astype(int).tolist()
        top_buffer = set(ordered[:config.BUFFER_K])       # still-good set
        held = [p for p in db.get_positions(con, config.BOOK_STRATEGY) if p['category'] == cat]
        held_ids = {p['scheme_id'] for p in held}

        # sells: dropped out of top-4 AND held >= 12 months
        survivors = set()
        navs_held = md.get_navs(engine, list(held_ids), date)
        for p in held:
            sid = p['scheme_id']
            age = _days_between(p['entry_date'], date)
            if sid in top_buffer or age < config.MIN_HOLD_DAYS:
                survivors.add(sid)                        # keep (still good, or tax-locked)
            else:
                info = navs_held.get(sid)
                if info:
                    sell(con, config.BOOK_STRATEGY, date, sid, info[2],
                         f"REBAL dropped out of {cat} top-{config.BUFFER_K}")
                    changes.append(f"-{p['fund_name']}")

        # buys: fill up to STRATEGY_PER_CAT with best not-yet-held
        need = config.STRATEGY_PER_CAT - len(survivors)
        if need > 0:
            candidates = [i for i in ordered if i not in survivors][:need]
            # fund the buys from the strategy cash pool, split equally
            cash = db.get_cash(con, config.BOOK_STRATEGY)
            per = cash / max(1, len(candidates)) if candidates else 0
            navs_new = md.get_navs(engine, candidates, date)
            for sid in candidates:
                info = navs_new.get(sid)
                if not info:
                    continue
                name, c = id_to_meta.get(sid, ("?", cat))
                buy(con, config.BOOK_STRATEGY, date, sid, name, c, per, info[2],
                    f"REBAL new top-{config.STRATEGY_PER_CAT} {cat}")
                changes.append(f"+{name}")

    # ---- BENCHMARK: re-equalise across the current core universe ----
    for p in db.get_positions(con, config.BOOK_BENCHMARK):
        info = md.get_navs(engine, [p['scheme_id']], date).get(p['scheme_id'])
        if info:
            sell(con, config.BOOK_BENCHMARK, date, p['scheme_id'], info[2], "REBAL benchmark re-equalise")
    cash_b = db.get_cash(con, config.BOOK_BENCHMARK)
    left_b = _equal_weight_deploy(con, engine, config.BOOK_BENCHMARK, date, id_to_meta,
                                  benchmark_ids, cash_b, "REBAL category basket")
    db.set_cash(con, config.BOOK_BENCHMARK, left_b)

    summary = f"REBAL {date}: " + (", ".join(changes) if changes else "no strategy changes (buffer held)")
    db.record_rebalance(con, date, summary)
    db.set_meta(con, last_rebalance_date=date)
    con.commit()
    mark_to_market(con, engine, date)
    return summary


def rebalance_due(con, mark_date):
    meta = db.get_meta(con)
    if not meta or not meta['last_rebalance_date']:
        return True
    return _days_between(meta['last_rebalance_date'], mark_date) >= config.REBALANCE_INTERVAL_DAYS
