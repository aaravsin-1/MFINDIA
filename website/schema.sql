-- =====================================================================
--  FundLens — Supabase schema
--  Retail mutual-fund selection engine (RESULTS_PROJECT deliverable).
--
--  This is a REFERENCE of the tables `push_to_supabase.py` creates. You do NOT
--  have to run it by hand — the Python ETL uses pandas `to_sql(if_exists=
--  'replace')`, which drops & recreates each table on every push, then applies
--  the indexes and RLS policies at the bottom. Keep this file as the contract
--  the website is built against, and to stand the schema up empty if needed.
--
--  Storage note: every table is small and read-only for the site (public anon
--  SELECT via RLS). Detail tables cover the LIVE snapshot only.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. funds — the rated universe (live + validation). The main list table.
--    Quality is a WITHIN-CATEGORY percentile (never compare across categories).
--    Risk is absolute volatility+drawdown math. Two independent 0–100 axes.
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS funds CASCADE;
CREATE TABLE funds (
    snapshot          text    NOT NULL,          -- 'live' (2025 buy-now) | 'validation' (2022 gradable)
    as_of             text,                       -- snapshot date, e.g. '2025-12-31'
    is_live           boolean,
    rank              integer,                    -- 1 = best (recommended first, then score)
    fund_name         text    NOT NULL,
    category          text,                       -- SEBI category, e.g. 'Small Cap Fund', 'ELSS'
    is_core_category  boolean,                    -- one of the 5 core sleeves the portfolio uses
    quality           integer,                    -- 0–100 within-category percentile
    risk              integer,                    -- 0–100 absolute risk
    risk_band         text,                       -- 'Conservative' | 'Balanced' | 'Aggressive'
    recommended       boolean,                    -- one of the 10 validated top-2/category picks
    holding_period    text,                       -- '5+ years' | '3-5 years' | '1-3 years'
    reason_1          text,                       -- plain-English "Why", prefixed [+]/[-]
    reason_2          text,
    n_positive        integer,                    -- count of [+] call-outs
    n_negative        integer,                    -- count of [-] call-outs
    why               text,                       -- raw pipe-joined reasons
    scheme_id         bigint                      -- FK-ish link to the detail tables (amfi_data scheme_id)
);

-- ---------------------------------------------------------------------
-- 2. fund_detail — one summary row per LIVE fund (the detail header card).
--    Loaded on click, not in the main list.
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS fund_detail CASCADE;
CREATE TABLE fund_detail (
    scheme_id       bigint  NOT NULL,
    fund_name       text,
    category        text,
    quality         integer,
    risk            integer,
    risk_band       text,
    recommended     boolean,
    holding_period  text,
    amc             text,                         -- fund house
    inception_date  date,
    aum_cr          numeric,                      -- latest AUM in ₹ crore
    aum_as_of       date,
    ter_pct         numeric,                      -- latest direct-plan total expense ratio
    ter_as_of       date,
    num_managers    integer,
    manager_names   text,                         -- comma-joined (also in fund_managers)
    num_holdings    integer,                      -- how many rows exist in fund_holdings
    holdings_as_of  date,
    top_holding     text,
    has_holdings    boolean,                      -- false for ~half the funds (partial data)
    nav_points      integer                       -- how many monthly NAV points exist
);

-- ---------------------------------------------------------------------
-- 3. fund_nav — ~1 year of monthly NAV per LIVE fund (direct-growth plan).
--    For a small sparkline / 1-year trend on the detail page.
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS fund_nav CASCADE;
CREATE TABLE fund_nav (
    scheme_id  bigint NOT NULL,
    date       date   NOT NULL,                   -- month-end
    nav        numeric
);

-- ---------------------------------------------------------------------
-- 4. fund_managers — current managers per LIVE fund.
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS fund_managers CASCADE;
CREATE TABLE fund_managers (
    scheme_id     bigint NOT NULL,
    manager_name  text,
    start_date    date,
    tenure_years  numeric,
    is_current    boolean
);

-- ---------------------------------------------------------------------
-- 5. fund_holdings — top-10 holdings per LIVE fund (where linkable).
--    Coverage is PARTIAL (~188/381 funds): `source` = 'amfi' (clean names) or
--    'morningstar' (ISIN-linked, ticker-resolved). Kept for later use; the
--    website currently does NOT surface this (see note in LOVABLE_PROMPT.md).
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS fund_holdings CASCADE;
CREATE TABLE fund_holdings (
    scheme_id   bigint NOT NULL,
    rank        integer,                          -- 1 = largest position
    instrument  text,                             -- company / security name
    isin        text,                             -- null for morningstar-sourced rows
    industry    text,
    pct_nav     numeric,                          -- % of NAV
    as_of       date,                             -- null for morningstar-sourced rows
    source      text                              -- 'amfi' | 'morningstar'
);

-- ---------------------------------------------------------------------
-- 6. research_log — the 12 empirical findings (F1–F12). Credibility content.
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS research_log CASCADE;
CREATE TABLE research_log (
    id         integer PRIMARY KEY,
    code       text,                              -- 'F1'..'F12'
    verdict    text,                              -- 'survived' | 'dead' | 'artifact'
    title      text,
    finding    text,
    reference  text
);

-- ---------------------------------------------------------------------
-- 7. engine_metrics — the headline validated numbers.
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS engine_metrics CASCADE;
CREATE TABLE engine_metrics (
    metric  text,                                 -- e.g. 'edge_gross_pct'
    value   text,                                 -- kept as text ('2.37', '7 / 7', 'PASS')
    unit    text,
    label   text,                                 -- human-readable caption
    "group" text                                  -- 'performance' | 'significance' | 'product'
);

-- ---------------------------------------------------------------------
-- 8. category_summary — per-category counts + where selection skill lives.
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS category_summary CASCADE;
CREATE TABLE category_summary (
    category            text,
    n_funds             integer,
    n_recommended       integer,
    avg_quality         numeric,
    avg_risk            numeric,
    is_core             boolean,
    selection_edge_pct  numeric                   -- null unless measured (Small 3.4, Large 0.6)
);

-- =====================================================================
--  Indexes
-- =====================================================================
CREATE INDEX IF NOT EXISTS idx_funds_snapshot    ON funds (snapshot);
CREATE INDEX IF NOT EXISTS idx_funds_category    ON funds (category);
CREATE INDEX IF NOT EXISTS idx_funds_recommended ON funds (recommended);
CREATE INDEX IF NOT EXISTS idx_funds_quality     ON funds (quality DESC);
CREATE INDEX IF NOT EXISTS idx_funds_riskband    ON funds (risk_band);
CREATE INDEX IF NOT EXISTS idx_funds_scheme      ON funds (scheme_id);
CREATE INDEX IF NOT EXISTS idx_detail_scheme     ON fund_detail (scheme_id);
CREATE INDEX IF NOT EXISTS idx_nav_scheme        ON fund_nav (scheme_id, date);
CREATE INDEX IF NOT EXISTS idx_mgr_scheme        ON fund_managers (scheme_id);
CREATE INDEX IF NOT EXISTS idx_hold_scheme       ON fund_holdings (scheme_id, rank);
CREATE INDEX IF NOT EXISTS idx_catsum_cat        ON category_summary (category);

-- =====================================================================
--  Row Level Security — public (anon) read-only, for the website
-- =====================================================================
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'funds','fund_detail','fund_nav','fund_managers','fund_holdings',
    'research_log','engine_metrics','category_summary'
  ] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    BEGIN
      EXECUTE format(
        'CREATE POLICY pubread_%1$s ON %1$I FOR SELECT TO anon USING (true)', t);
    EXCEPTION WHEN duplicate_object THEN NULL;
    END;
  END LOOP;
END $$;
