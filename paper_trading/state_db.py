"""
state_db.py -- the paper-trading account state (SQLite, isolated from the postgres
market-data DB). Holds the ledger, current positions, per-book cash, the daily
mark-to-market value history, and rebalance log.

One SQLite file = one portable, auditable record of the paper trade.
"""
import sqlite3
from datetime import datetime
import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS pt_account (
    account_id     INTEGER PRIMARY KEY,
    name           TEXT,
    inception_date TEXT,
    start_capital  REAL,
    created_at     TEXT
);
CREATE TABLE IF NOT EXISTS pt_book (
    account_id INTEGER,
    book       TEXT,
    cash       REAL,
    PRIMARY KEY (account_id, book)
);
-- one row per currently-held fund per book (units aggregated)
CREATE TABLE IF NOT EXISTS pt_position (
    account_id INTEGER,
    book       TEXT,
    scheme_id  INTEGER,
    fund_name  TEXT,
    category   TEXT,
    units      REAL,
    entry_nav  REAL,      -- cost-basis NAV (weighted avg over buys)
    entry_date TEXT,      -- date of first buy of the current lot
    last_nav   REAL,
    last_date  TEXT,
    PRIMARY KEY (account_id, book, scheme_id)
);
-- full immutable trade ledger
CREATE TABLE IF NOT EXISTS pt_trade (
    trade_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,
    book       TEXT,
    trade_date TEXT,
    scheme_id  INTEGER,
    fund_name  TEXT,
    category   TEXT,
    action     TEXT,      -- BUY / SELL
    units      REAL,
    nav        REAL,
    amount     REAL,      -- units * nav
    realized_pnl REAL,    -- for SELLs
    reason     TEXT
);
-- daily mark-to-market value per book
CREATE TABLE IF NOT EXISTS pt_value_history (
    account_id INTEGER,
    book       TEXT,
    date       TEXT,
    value      REAL,      -- holdings marked at NAV
    cash       REAL,
    total      REAL,      -- value + cash
    PRIMARY KEY (account_id, book, date)
);
CREATE TABLE IF NOT EXISTS pt_rebalance (
    rebalance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER,
    date         TEXT,
    summary      TEXT
);
CREATE TABLE IF NOT EXISTS pt_meta (
    account_id           INTEGER PRIMARY KEY,
    last_rebalance_date  TEXT,
    last_mark_date       TEXT
);
"""


def connect():
    con = sqlite3.connect(str(config.DB_PATH))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_schema(con):
    con.executescript(SCHEMA)
    con.commit()


# ---------- account ----------
def create_account(con, name, inception_date, start_capital):
    con.execute(
        "INSERT OR REPLACE INTO pt_account(account_id,name,inception_date,start_capital,created_at)"
        " VALUES (1,?,?,?,?)",
        (name, inception_date, start_capital, datetime.now().isoformat(timespec='seconds')))
    for book, cash in ((config.BOOK_STRATEGY, start_capital), (config.BOOK_BENCHMARK, start_capital)):
        con.execute("INSERT OR REPLACE INTO pt_book(account_id,book,cash) VALUES (1,?,?)", (book, cash))
    con.execute("INSERT OR REPLACE INTO pt_meta(account_id,last_rebalance_date,last_mark_date)"
                " VALUES (1,NULL,NULL)")
    con.commit()


def account_exists(con):
    return con.execute("SELECT 1 FROM pt_account WHERE account_id=1").fetchone() is not None


def get_account(con):
    return con.execute("SELECT * FROM pt_account WHERE account_id=1").fetchone()


# ---------- cash / positions ----------
def get_cash(con, book):
    r = con.execute("SELECT cash FROM pt_book WHERE account_id=1 AND book=?", (book,)).fetchone()
    return r['cash'] if r else 0.0


def set_cash(con, book, cash):
    con.execute("UPDATE pt_book SET cash=? WHERE account_id=1 AND book=?", (cash, book))


def get_positions(con, book):
    return con.execute("SELECT * FROM pt_position WHERE account_id=1 AND book=?", (book,)).fetchall()


def get_position(con, book, scheme_id):
    return con.execute(
        "SELECT * FROM pt_position WHERE account_id=1 AND book=? AND scheme_id=?",
        (book, scheme_id)).fetchone()


def upsert_position(con, book, scheme_id, fund_name, category, units, entry_nav, entry_date,
                    last_nav, last_date):
    con.execute(
        "INSERT OR REPLACE INTO pt_position"
        "(account_id,book,scheme_id,fund_name,category,units,entry_nav,entry_date,last_nav,last_date)"
        " VALUES (1,?,?,?,?,?,?,?,?,?)",
        (book, scheme_id, fund_name, category, units, entry_nav, entry_date, last_nav, last_date))


def delete_position(con, book, scheme_id):
    con.execute("DELETE FROM pt_position WHERE account_id=1 AND book=? AND scheme_id=?",
                (book, scheme_id))


def record_trade(con, book, trade_date, scheme_id, fund_name, category, action, units, nav,
                 realized_pnl, reason):
    con.execute(
        "INSERT INTO pt_trade"
        "(account_id,book,trade_date,scheme_id,fund_name,category,action,units,nav,amount,realized_pnl,reason)"
        " VALUES (1,?,?,?,?,?,?,?,?,?,?,?)",
        (book, trade_date, scheme_id, fund_name, category, action, units, nav, units * nav,
         realized_pnl, reason))


def record_value(con, book, date, value, cash):
    con.execute(
        "INSERT OR REPLACE INTO pt_value_history(account_id,book,date,value,cash,total)"
        " VALUES (1,?,?,?,?,?)", (book, date, value, cash, value + cash))


def record_rebalance(con, date, summary):
    con.execute("INSERT INTO pt_rebalance(account_id,date,summary) VALUES (1,?,?)", (date, summary))


def set_meta(con, last_rebalance_date=None, last_mark_date=None):
    if last_rebalance_date is not None:
        con.execute("UPDATE pt_meta SET last_rebalance_date=? WHERE account_id=1", (last_rebalance_date,))
    if last_mark_date is not None:
        con.execute("UPDATE pt_meta SET last_mark_date=? WHERE account_id=1", (last_mark_date,))


def get_meta(con):
    return con.execute("SELECT * FROM pt_meta WHERE account_id=1").fetchone()
