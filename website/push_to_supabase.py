#!/usr/bin/env python3
"""
ETL: RESULTS_PROJECT screener CSVs (+ amfi_data detail)  →  Supabase

The headline deliverable is a set of pre-computed CSVs (produced by
`score_live.py`), so this script reads the finished screener output and shapes it
into clean, website-ready tables. On top of that it enriches the LIVE list with a
small amount of per-fund detail pulled straight from the source `amfi_data`
Postgres DB — 1 year of NAV, latest AUM, current managers, and top holdings — so
the website can show a fund's fundamentals when a retail investor clicks into it.

Detail is deliberately shallow (Supabase storage is limited): only LIVE funds,
only ~13 monthly NAV points, only the top-10 holdings. It is loaded on click, not
in the main list.

Source CSVs (in ../ = RESULTS_PROJECT/):
  retail_fund_list_2025.csv        LIVE RETAIL list (381 funds, as-of 2025-12-31) ← the product
                                   (within-category Tier + Quality/Risk; StrategyPick flags
                                    the funds that are also in the concentrated strategy)
  fund_screener_results.csv        VALIDATION snapshot (275 funds, 2022, gradable strategy)

Source DB (../.env = RESULTS_PROJECT/.env → amfi_data):  NAV / AUM / managers / holdings

Tables created on Supabase:
  funds            every rated fund (live retail + validation): 2D Quality×Risk, Tier, reasons, holding period, scheme_id
  fund_detail      one summary row per LIVE fund: AMC, inception, AUM, TER, #managers, #holdings
  fund_nav         ~13 monthly NAV points per LIVE fund (for a 1-year sparkline)
  fund_managers    current managers per LIVE fund (name, tenure)
  fund_holdings    top-10 equity holdings per LIVE fund (where the holdings data links)
  research_log     the 12 empirical findings (F1–F12) with verdicts — the "why trust this" story
  engine_metrics   the headline validated numbers (edge, IC, significance, universe sizes)
  category_summary per-category counts + where selection skill actually lives (F6)

Usage:
  python push_to_supabase.py                 # full push (needs SUPABASE_* env + source DB)
  python push_to_supabase.py --dry-run       # build tables, print summary, don't push
  python push_to_supabase.py --dry-run --out # also dump the tables to ./preview/*.json
  python push_to_supabase.py --no-detail     # skip the DB enrichment (CSV tables only)
"""

import os
import sys
import re
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()

# Make console output safe on Windows terminals (cp1252) that can't render → ←
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ── Paths ────────────────────────────────────────────────────────────
# This script lives in RESULTS_PROJECT/website/ ; generated lists sit in ../outputs/.
HERE = Path(__file__).resolve().parent
BASE = HERE.parent
LIVE_CSV = BASE / "outputs" / "retail_fund_list_2025.csv"   # the RETAIL recommendations list (live product)
VALIDATION_CSV = BASE / "outputs" / "fund_screener_results.csv"
SOURCE_ENV = BASE / ".env"   # RESULTS_PROJECT/.env — holds both DB_* and SUPABASE_*

# Live snapshot metadata (from README / score_live.py)
LIVE_AS_OF = "2025-12-31"
VALIDATION_AS_OF = "2022-12-31"

# The 5 core categories the validated top-2/category portfolio is built from.
CORE_CATEGORIES = ["Large Cap Fund", "Mid Cap Fund", "Small Cap Fund",
                   "Flexi Cap Fund", "ELSS"]

# Per-category out-of-sample selection edge (F6). Only measured for core sleeves.
CATEGORY_EDGE = {"Small Cap Fund": 3.4, "Large Cap Fund": 0.6}

# Detail depth knobs (keep Supabase storage small).
NAV_MONTHS = 13          # ~1 year of monthly NAV points
TOP_HOLDINGS = 10        # top-N equity holdings per fund

SUPABASE_PROJECT_URL = "https://xhkgqnapjevtpixlykzp.supabase.co"

# Load credentials from RESULTS_PROJECT/.env (SUPABASE_* and DB_* live here),
# regardless of the directory the script is launched from.
load_dotenv(BASE / ".env")


# ── Destination DB (Supabase) ────────────────────────────────────────

def get_supabase():
    url = os.getenv("SUPABASE_URL")
    if not url:
        host = os.getenv("SUPABASE_HOST", "db.xhkgqnapjevtpixlykzp.supabase.co")
        port = os.getenv("SUPABASE_PORT", "5432")
        name = os.getenv("SUPABASE_DB", "postgres")
        user = os.getenv("SUPABASE_USER", "postgres")
        pw = os.getenv("SUPABASE_PASSWORD", "")
        url = f"postgresql://{user}:{quote_plus(pw)}@{host}:{port}/{name}"
    return create_engine(url, pool_pre_ping=True)


# ── Source DB (amfi_data) ────────────────────────────────────────────

def get_source():
    """Engine for the amfi_data DB (same creds the rest of RESULTS_PROJECT uses)."""
    load_dotenv(SOURCE_ENV)
    url = os.getenv("DATABASE_URL")
    if not url:
        user = os.getenv("DB_USER"); pw = os.getenv("DB_PASSWORD")
        host = os.getenv("DB_HOST"); port = os.getenv("DB_PORT"); name = os.getenv("DB_NAME")
        url = f"postgresql://{user}:{quote_plus(pw or '')}@{host}:{port}/{name}"
    return create_engine(url, pool_pre_ping=True)


def _norm(s):
    """Loose fund-name normaliser for cross-source matching."""
    s = str(s).lower()
    s = re.sub(r"\(formerly.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    for w in ["fund", "the", "mutual", "plan", "direct", "growth", "scheme",
              "tax saver", "elss"]:
        s = s.replace(w, " ")
    return re.sub(r"\s+", " ", s).strip()


# ── Build the funds table from a screener CSV ────────────────────────

def _split_reasons(why):
    """'[+] A | [-] B' → (['[+] A','[-] B'], reason_1, reason_2)."""
    if not isinstance(why, str) or not why.strip():
        return [], None, None
    parts = [p.strip() for p in why.split("|") if p.strip()]
    r1 = parts[0] if len(parts) > 0 else None
    r2 = parts[1] if len(parts) > 1 else None
    return parts, r1, r2


def load_funds(csv_path, snapshot, as_of):
    """Load a screener CSV, tolerating BOTH schemas:
      retail (retail_fund_list_*.csv):   Category, CategoryRank, Fund, Tier, Quality,
                                         Risk, RiskBand, ..., StrategyPick, Why
      strategy/validation (fund_screener_results*.csv): Rank, ..., Recommended, Why
    Common analytics columns are normalised; `tier` is populated for the retail list
    and left blank for the strategy/validation snapshot.
    """
    print(f"  Loading {csv_path.name} ...")
    df = pd.read_csv(csv_path)
    # shared columns + the two rank variants (Rank / CategoryRank)
    ren = {"Fund": "fund_name", "Category": "category", "Quality": "quality",
           "Risk": "risk", "RiskBand": "risk_band",
           "Expected Holding Period": "holding_period", "Why": "why",
           "Rank": "rank", "CategoryRank": "rank"}
    df = df.rename(columns={k: v for k, v in ren.items() if k in df.columns})

    # "recommended" = the concentrated strategy pick: 'Recommended' (strategy/validation)
    # or 'StrategyPick' (retail list). Both use "Yes"/"No".
    rec_col = ("Recommended" if "Recommended" in df.columns
               else "StrategyPick" if "StrategyPick" in df.columns else None)
    df["recommended"] = (df[rec_col].astype(str).str.strip().str.lower().eq("yes")
                         if rec_col else False)

    # tier (retail only): "1. Top Tier" -> tier="Top Tier", tier_rank=1
    if "Tier" in df.columns:
        df["tier"] = df["Tier"].astype(str).str.replace(r"^\s*\d+\.\s*", "", regex=True)
        df["tier_rank"] = pd.to_numeric(
            df["Tier"].astype(str).str.extract(r"^\s*(\d+)")[0], errors="coerce")
    else:
        df["tier"] = None
        df["tier_rank"] = pd.NA
    if "rank" not in df.columns:
        df["rank"] = range(1, len(df) + 1)

    parsed = df["why"].apply(_split_reasons)
    df["reason_1"] = parsed.apply(lambda t: t[1])
    df["reason_2"] = parsed.apply(lambda t: t[2])
    df["n_positive"] = df["why"].fillna("").str.count(r"\[\+\]")
    df["n_negative"] = df["why"].fillna("").str.count(r"\[-\]")
    df["is_core_category"] = df["category"].isin(CORE_CATEGORIES)
    df["snapshot"] = snapshot
    df["as_of"] = as_of
    df["is_live"] = snapshot == "live"

    cols = ["snapshot", "as_of", "is_live", "rank", "fund_name", "category",
            "is_core_category", "quality", "risk", "risk_band", "recommended",
            "tier", "tier_rank", "holding_period", "reason_1", "reason_2",
            "n_positive", "n_negative", "why"]
    out = df[cols].copy()
    tiered = int(out["tier"].notna().sum())
    print(f"    {len(out)} funds  ({int(out['recommended'].sum())} strategy picks, "
          f"{int(out['is_core_category'].sum())} core-category, {tiered} tiered)")
    return out


def attach_scheme_ids(funds, src):
    """Add a scheme_id column (exact name match against the scheme table)."""
    sch = pd.read_sql(text("SELECT scheme_id, name FROM scheme"), src)
    name2sid = dict(zip(sch["name"], sch["scheme_id"]))
    funds["scheme_id"] = funds["fund_name"].map(name2sid).astype("Int64")
    matched = funds["scheme_id"].notna().sum()
    print(f"  scheme_id matched: {matched}/{len(funds)}")
    return funds


def build_funds(src=None):
    frames = []
    if LIVE_CSV.exists():
        frames.append(load_funds(LIVE_CSV, "live", LIVE_AS_OF))
    else:
        print(f"  ! missing {LIVE_CSV}")
    if VALIDATION_CSV.exists():
        frames.append(load_funds(VALIDATION_CSV, "validation", VALIDATION_AS_OF))
    else:
        print(f"  ! missing {VALIDATION_CSV}")
    if not frames:
        raise FileNotFoundError("No screener CSVs found next to the website/ folder.")
    funds = pd.concat(frames, ignore_index=True)
    if src is not None:
        funds = attach_scheme_ids(funds, src)
    else:
        funds["scheme_id"] = pd.NA
    return funds


# ── Per-fund detail (LIVE funds only, from amfi_data) ────────────────

def _idlist(ids):
    return ",".join(str(int(i)) for i in ids)


def build_fund_nav(src, sids):
    """~1 year of monthly NAV per scheme, preferring the direct-growth plan."""
    mx = pd.read_sql(text("SELECT MAX(month_end) m FROM plan_nav_monthly"), src).iloc[0, 0]
    cutoff = (pd.Timestamp(mx) - pd.DateOffset(months=NAV_MONTHS - 1)).date()
    q = f"""
    SELECT DISTINCT ON (sp.scheme_id, pnm.month_end)
           sp.scheme_id, pnm.month_end AS date, pnm.nav
    FROM plan_nav_monthly pnm
    JOIN scheme_plan sp ON sp.scheme_plan_id = pnm.scheme_plan_id
    WHERE sp.scheme_id IN ({_idlist(sids)})
      AND sp.option_type = 'growth'
      AND pnm.month_end >= '{cutoff}'
    ORDER BY sp.scheme_id, pnm.month_end,
             CASE WHEN sp.plan_type = 'direct' THEN 0 ELSE 1 END
    """
    df = pd.read_sql(text(q), src, parse_dates=["date"])
    df["nav"] = df["nav"].round(4)
    print(f"    fund_nav: {len(df)} points / {df['scheme_id'].nunique()} funds")
    return df


def build_fund_managers(src, sids):
    q = f"""
    SELECT scheme_id, given_name, family_name, start_date, is_current
    FROM scheme_manager
    WHERE scheme_id IN ({_idlist(sids)})
      AND (is_current = TRUE OR end_date IS NULL OR end_date >= CURRENT_DATE)
    """
    df = pd.read_sql(text(q), src, parse_dates=["start_date"])
    df["manager_name"] = (df["given_name"].fillna("") + " " +
                          df["family_name"].fillna("")).str.strip()
    today = pd.Timestamp.today()
    df["tenure_years"] = ((today - df["start_date"]).dt.days / 365.25).round(1)
    df = df[df["manager_name"] != ""].copy()
    out = df[["scheme_id", "manager_name", "start_date", "tenure_years", "is_current"]]
    print(f"    fund_managers: {len(out)} / {out['scheme_id'].nunique()} funds")
    return out


def build_fund_aum_ter(src, sids):
    """Latest AUM (→ crore) and latest direct TER per scheme."""
    aum = pd.read_sql(text(f"""
        SELECT DISTINCT ON (scheme_id) scheme_id, period_end, avg_aum_lakh
        FROM v_scheme_aum WHERE scheme_id IN ({_idlist(sids)})
        ORDER BY scheme_id, period_end DESC
    """), src, parse_dates=["period_end"])
    aum["aum_cr"] = (pd.to_numeric(aum["avg_aum_lakh"], errors="coerce") / 100).round(1)
    aum = aum.rename(columns={"period_end": "aum_as_of"})[["scheme_id", "aum_cr", "aum_as_of"]]

    ter = pd.read_sql(text(f"""
        SELECT DISTINCT ON (scheme_id) scheme_id, dir_total_ter, as_of_date
        FROM ter WHERE scheme_id IN ({_idlist(sids)}) AND dir_total_ter > 0
        ORDER BY scheme_id, as_of_date DESC
    """), src, parse_dates=["as_of_date"])
    ter["ter_pct"] = pd.to_numeric(ter["dir_total_ter"], errors="coerce").round(2)
    ter = ter.rename(columns={"as_of_date": "ter_as_of"})[["scheme_id", "ter_pct", "ter_as_of"]]
    return aum, ter


HOLDINGS_COLS = ["scheme_id", "instrument", "isin", "industry", "pct_nav", "as_of", "source"]


def _holdings_from_amfi(src, live):
    """Source A — portfolio_holding_fact (clean instrument names, ISINs).

    Keyed via fund_dim's own fund_id, bridged by a normalised name match
    (the documented ~30% linkage gap). Good names where it hits.
    """
    fd = pd.read_sql(text("SELECT fund_id, fund_name FROM fund_dim"), src)
    fd["n"] = fd["fund_name"].map(_norm)
    norm2fid = {}
    for _, r in fd.iterrows():
        norm2fid.setdefault(r["n"], r["fund_id"])
    live = live.copy()
    live["fid"] = live["fund_name"].map(lambda x: norm2fid.get(_norm(x)))
    linked = live.dropna(subset=["fid"])
    if linked.empty:
        return pd.DataFrame(columns=HOLDINGS_COLS)
    fid2sid = dict(zip(linked["fid"].astype(int), linked["scheme_id"]))
    q = f"""
    WITH latest AS (
        SELECT DISTINCT ON (fund_id) fund_id, snapshot_id, statement_date
        FROM portfolio_snapshot_fact
        WHERE fund_id IN ({_idlist(linked['fid'].astype(int))})
        ORDER BY fund_id, statement_date DESC
    )
    SELECT l.fund_id, l.statement_date AS as_of, h.instrument, h.isin, h.industry, h.pct_nav
    FROM latest l
    JOIN portfolio_holding_fact h ON h.snapshot_id = l.snapshot_id
    WHERE LOWER(h.section) LIKE '%%equity%%'
      AND h.isin IS NOT NULL                 -- drop most sub-headers
      AND h.pct_nav > 0 AND h.pct_nav < 0.5  -- drop section-total rows (~0.95 of NAV)
    """
    df = pd.read_sql(text(q), src, parse_dates=["as_of"])
    if df.empty:
        return pd.DataFrame(columns=HOLDINGS_COLS)
    df["scheme_id"] = df["fund_id"].map(fid2sid)
    df["pct_nav"] = (pd.to_numeric(df["pct_nav"], errors="coerce") * 100).round(2)
    df["instrument"] = df["instrument"].astype(str).str[:60]
    df["source"] = "amfi"
    return df[HOLDINGS_COLS]


def _holdings_from_morningstar(src, live):
    """Source B — morningstar_holding, linked by exact growth-ISIN (much better
    coverage). Holding names are absent, so resolve tickers → company names via
    stock_prices; unresolved tickers fall back to the raw ticker. No statement
    date in this table, so as_of is null for these rows.
    """
    if live.empty:
        return pd.DataFrame(columns=HOLDINGS_COLS)
    isin = pd.read_sql(text(f"""
        SELECT DISTINCT scheme_id, isin_growth_payout AS isin
        FROM scheme_plan
        WHERE scheme_id IN ({_idlist(live['scheme_id'])})
          AND plan_type='direct' AND option_type='growth'
          AND isin_growth_payout IS NOT NULL
    """), src)
    mq = pd.read_sql(text("""
        SELECT DISTINCT ON (isin) sec_id, isin FROM morningstar_quote
        WHERE isin IS NOT NULL ORDER BY isin, sec_id
    """), src)
    link = isin.merge(mq, on="isin")
    if link.empty:
        return pd.DataFrame(columns=HOLDINGS_COLS)
    sec2sid = dict(zip(link["sec_id"], link["scheme_id"]))
    seclist = ",".join("'" + s.replace("'", "''") + "'" for s in link["sec_id"].unique())
    mh = pd.read_sql(text(f"""
        SELECT sec_id, ticker, sector, weighting FROM morningstar_holding
        WHERE sec_id IN ({seclist}) AND weighting > 0 AND sector IS NOT NULL
    """), src)
    if mh.empty:
        return pd.DataFrame(columns=HOLDINGS_COLS)
    sp = pd.read_sql(text("""
        SELECT DISTINCT ON (symbol) symbol, company_name FROM stock_prices
        WHERE symbol IS NOT NULL ORDER BY symbol, company_name
    """), src)
    sym2name = {str(s).upper(): n for s, n in zip(sp["symbol"], sp["company_name"])}
    mh["instrument"] = mh["ticker"].map(lambda t: sym2name.get(str(t).upper(), str(t)))
    mh["scheme_id"] = mh["sec_id"].map(sec2sid)
    mh["isin"] = None
    mh["industry"] = mh["sector"]
    mh["pct_nav"] = pd.to_numeric(mh["weighting"], errors="coerce").round(2)
    mh["as_of"] = pd.NaT
    mh["source"] = "morningstar"
    return mh[HOLDINGS_COLS]


def build_fund_holdings(src, funds_live):
    """Top-N holdings per live fund, combining two sources for best coverage:
    amfi (clean names) preferred; Morningstar (exact ISIN link) fills the gaps.
    """
    live = funds_live.dropna(subset=["scheme_id"]).copy()
    live["scheme_id"] = live["scheme_id"].astype(int)

    a = _holdings_from_amfi(src, live)
    covered = set(a["scheme_id"].unique())
    need = live[~live["scheme_id"].isin(covered)]
    b = _holdings_from_morningstar(src, need)

    df = pd.concat([a, b], ignore_index=True)
    if df.empty:
        print("    fund_holdings: 0 (no linkable funds)")
        return pd.DataFrame(columns=["scheme_id", "rank"] + HOLDINGS_COLS[1:])

    # top-N per fund, highest weight first
    df = df.sort_values(["scheme_id", "pct_nav"], ascending=[True, False])
    df["rank"] = df.groupby("scheme_id").cumcount() + 1
    df = df[df["rank"] <= TOP_HOLDINGS].copy()
    out = df[["scheme_id", "rank"] + HOLDINGS_COLS[1:]]
    n_amfi = out[out["source"] == "amfi"]["scheme_id"].nunique()
    n_ms = out[out["source"] == "morningstar"]["scheme_id"].nunique()
    print(f"    fund_holdings: {len(out)} rows / {out['scheme_id'].nunique()} funds "
          f"(amfi {n_amfi} + morningstar {n_ms}, of {len(funds_live)} live)")
    return out


def build_fund_detail(src, funds_live, nav, managers, aum, ter, holdings):
    """One summary row per live fund for the detail header card."""
    sids = funds_live["scheme_id"].dropna().astype(int).tolist()
    meta = pd.read_sql(text(f"""
        SELECT s.scheme_id, a.fund_house_name AS amc, s.inception_date
        FROM scheme s JOIN amc a ON a.amc_id = s.amc_id
        WHERE s.scheme_id IN ({_idlist(sids)})
    """), src, parse_dates=["inception_date"])

    base = funds_live[["scheme_id", "fund_name", "category", "quality", "risk",
                       "risk_band", "recommended", "holding_period"]].dropna(subset=["scheme_id"]).copy()
    base["scheme_id"] = base["scheme_id"].astype(int)

    d = base.merge(meta, on="scheme_id", how="left")
    d = d.merge(aum, on="scheme_id", how="left")
    d = d.merge(ter, on="scheme_id", how="left")

    mgr_agg = (managers.groupby("scheme_id")
               .agg(num_managers=("manager_name", "nunique"),
                    manager_names=("manager_name", lambda s: ", ".join(sorted(set(s)))))
               .reset_index())
    d = d.merge(mgr_agg, on="scheme_id", how="left")
    d["num_managers"] = d["num_managers"].fillna(0).astype(int)

    hold_agg = (holdings.groupby("scheme_id")
                .agg(num_holdings=("instrument", "count"),
                     holdings_as_of=("as_of", "max"),
                     top_holding=("instrument", "first")).reset_index())
    d = d.merge(hold_agg, on="scheme_id", how="left")
    d["num_holdings"] = d["num_holdings"].fillna(0).astype(int)
    d["has_holdings"] = d["num_holdings"] > 0
    d["nav_points"] = d["scheme_id"].map(nav.groupby("scheme_id").size()).fillna(0).astype(int)

    print(f"  fund_detail: {len(d)} live funds "
          f"({d['has_holdings'].sum()} with holdings, "
          f"{(d['num_managers']>0).sum()} with managers)")
    return d


def build_detail_tables(src, funds):
    live = funds[funds["snapshot"] == "live"].dropna(subset=["scheme_id"]).copy()
    sids = live["scheme_id"].astype(int).tolist()
    print(f"  Enriching {len(sids)} live funds from amfi_data...")
    nav = build_fund_nav(src, sids)
    managers = build_fund_managers(src, sids)
    aum, ter = build_fund_aum_ter(src, sids)
    holdings = build_fund_holdings(src, live)
    detail = build_fund_detail(src, live, nav, managers, aum, ter, holdings)
    return {"fund_detail": detail, "fund_nav": nav,
            "fund_managers": managers, "fund_holdings": holdings}


# ── Category summary (from the live list + F6 edges) ─────────────────

def build_category_summary(funds):
    live = funds[funds["snapshot"] == "live"]
    g = live.groupby("category")
    summary = pd.DataFrame({"category": g.size().index, "n_funds": g.size().values})
    summary["n_recommended"] = g["recommended"].sum().reindex(summary["category"]).values
    summary["avg_quality"] = g["quality"].mean().round(0).reindex(summary["category"]).values
    summary["avg_risk"] = g["risk"].mean().round(0).reindex(summary["category"]).values
    summary["is_core"] = summary["category"].isin(CORE_CATEGORIES)
    summary["selection_edge_pct"] = summary["category"].map(CATEGORY_EDGE)
    summary = summary.sort_values(["is_core", "n_funds"],
                                  ascending=[False, False]).reset_index(drop=True)
    print(f"  {len(summary)} categories summarised")
    return summary


# ── Research log — the 12 findings (F1–F12) ──────────────────────────

def research_log():
    findings = pd.DataFrame([
        {"id": 1, "code": "F1", "verdict": "dead",
         "title": "Single factors don't predict fund returns",
         "finding": "Twelve single-signal strategies (momentum, TER, flows, Sharpe, category rotation) all failed realistic out-of-sample testing.",
         "reference": "Carhart (1997)"},
        {"id": 2, "code": "F2", "verdict": "dead",
         "title": "Buying past winners underperforms",
         "finding": "Top-10 by trailing return lost to the equal-weight universe — mean reversion dominates.",
         "reference": "—"},
        {"id": 3, "code": "F3", "verdict": "artifact",
         "title": "The naive ML 'edge' is mostly a style tilt",
         "finding": "A universal top-10 ML portfolio beat equal-weight by +1.6%/yr but FAILED its negative control (scrambled-label models won ~29/40 seeds; p=0.125). It was a small-cap/momentum tilt, not skill.",
         "reference": "Harvey, Liu & Zhu (2016)"},
        {"id": 4, "code": "F4", "verdict": "survived",
         "title": "Genuine within-category ranking skill exists",
         "finding": "Out-of-sample rank IC between predicted and realised forward alpha = +0.096 (p<0.001) pooled, +0.09 to +0.18 within category — exploitable in equity selection.",
         "reference": "Gu, Kelly & Xiu (2020)"},
        {"id": 5, "code": "F5", "verdict": "survived",
         "title": "Category-neutral construction converts skill into a robust edge",
         "finding": "Top-2 per core category vs a category-matched benchmark yields +2.37%/yr, positive in 7/7 cohorts, PASSES the negative control (p=0.000), Newey-West t=3.30 (p=0.001).",
         "reference": "—"},
        {"id": 6, "code": "F6", "verdict": "survived",
         "title": "Skill lives where funds differ most",
         "finding": "Per-category selection edge: small-cap +3.4%, large-cap only +0.6%. Large-caps hug the index; small-cap dispersion leaves room for skill.",
         "reference": "SPIVA India; Cremers & Petajisto (2009)"},
        {"id": 7, "code": "F7", "verdict": "survived",
         "title": "Fund size (AUM/capacity) is the most robust feature",
         "finding": "Removing AUM causes the largest performance drop across ablations; size proxies capacity constraints, biting small-caps hardest.",
         "reference": "Chen, Hong, Huang & Kubik (2004); Berk & Green (2004)"},
        {"id": 8, "code": "F8", "verdict": "dead",
         "title": "'Dumb-money' flows add no incremental value",
         "finding": "Trailing organic flow has a real negative IC (-0.063, p=0.007) but points the same way as, and weaker than, the AUM feature already in the model — no portfolio improvement.",
         "reference": "Frazzini & Lamont (2008)"},
        {"id": 9, "code": "F9", "verdict": "survived",
         "title": "The alpha is front-loaded",
         "finding": "Gross edge is largest at a 1-year hold (+3.70%/yr), decaying to +2.47% by 3 years; all three horizons pass the negative control (p=0.000).",
         "reference": "—"},
        {"id": 10, "code": "F10", "verdict": "survived",
         "title": "The edge survives tax if held >12 months",
         "finding": "After 12.5% LTCG the net edge is ~+2.6% at a 1–2 year hold. A top-4 buffer cuts turnover ~46%→33%. Holding <12 months triggers 20% STCG + exit loads and erases the edge.",
         "reference": "—"},
        {"id": 11, "code": "F11", "verdict": "dead",
         "title": "The raw-alpha target is already optimal",
         "finding": "Risk-adjusted / downside training targets (Sharpe, Calmar, rank) pass the null but don't improve information ratio or drawdown.",
         "reference": "—"},
        {"id": 12, "code": "F12", "verdict": "survived",
         "title": "Data quality can silently bias fund research",
         "finding": "A single corrupted NAV (+4,367% '3-yr return') inflated a category benchmark to +273% and poisoned a whole cohort. Fixed with an outlier filter + trimmed benchmark.",
         "reference": "Elton, Gruber & Blake (1996)"},
    ])
    print(f"  {len(findings)} research findings")
    return findings


# ── Engine metrics — the headline validated numbers ──────────────────

def engine_metrics(funds):
    live_n = int((funds["snapshot"] == "live").sum())
    val_n = int((funds["snapshot"] == "validation").sum())
    rows = [
        {"metric": "edge_gross_pct", "value": "2.37", "unit": "% / yr",
         "label": "Gross edge vs a category-matched benchmark", "group": "performance"},
        {"metric": "edge_net_pct", "value": "2.6", "unit": "% / yr",
         "label": "After-tax edge (12.5% LTCG, 1–2 yr hold)", "group": "performance"},
        {"metric": "cohorts_positive", "value": "7 / 7", "unit": "",
         "label": "Back-test years the strategy beat its benchmark (2016–2022)", "group": "performance"},
        {"metric": "rank_ic", "value": "0.096", "unit": "",
         "label": "Out-of-sample information coefficient (ranking skill)", "group": "significance"},
        {"metric": "newey_west_t", "value": "3.30", "unit": "",
         "label": "Alpha t-stat after overlapping-window correction", "group": "significance"},
        {"metric": "p_value", "value": "0.001", "unit": "",
         "label": "Probability the edge is luck (≈1-in-1000)", "group": "significance"},
        {"metric": "negative_control", "value": "PASS", "unit": "",
         "label": "Fake-data sanity check (the original version FAILED this)", "group": "significance"},
        {"metric": "portfolio_size", "value": "10", "unit": "funds",
         "label": "Top-2 per core category (Large, Mid, Small, Flexi, ELSS)", "group": "product"},
        {"metric": "live_universe", "value": str(live_n), "unit": "funds",
         "label": f"Funds rated in the current live list (as-of {LIVE_AS_OF})", "group": "product"},
        {"metric": "validation_universe", "value": str(val_n), "unit": "funds",
         "label": f"Funds in the gradable validation snapshot ({VALIDATION_AS_OF})", "group": "product"},
        {"metric": "min_hold_months", "value": "12", "unit": "months",
         "label": "Minimum hold — secures 12.5% LTCG, avoids exit loads", "group": "product"},
    ]
    df = pd.DataFrame(rows)
    print(f"  {len(df)} headline metrics")
    return df


# ── Push helpers ─────────────────────────────────────────────────────

def push(dest, table_name, df):
    print(f"  Pushing {table_name}: {len(df)} rows...", end=" ")
    df.to_sql(table_name, dest, if_exists="replace", index=False,
              method="multi", chunksize=500)
    print("done")


def post_push_sql(dest, has_detail):
    """Indexes + public-read RLS so the anon website key can query these tables."""
    print("\n  Creating indexes and public-read policies...")
    stmts = [
        "CREATE INDEX IF NOT EXISTS idx_funds_snapshot ON funds (snapshot)",
        "CREATE INDEX IF NOT EXISTS idx_funds_category ON funds (category)",
        "CREATE INDEX IF NOT EXISTS idx_funds_recommended ON funds (recommended)",
        "CREATE INDEX IF NOT EXISTS idx_funds_quality ON funds (quality DESC)",
        "CREATE INDEX IF NOT EXISTS idx_funds_riskband ON funds (risk_band)",
        "CREATE INDEX IF NOT EXISTS idx_funds_scheme ON funds (scheme_id)",
        "CREATE INDEX IF NOT EXISTS idx_catsum_cat ON category_summary (category)",
    ]
    tables = ["funds", "research_log", "engine_metrics", "category_summary"]
    if has_detail:
        stmts += [
            "CREATE INDEX IF NOT EXISTS idx_detail_scheme ON fund_detail (scheme_id)",
            "CREATE INDEX IF NOT EXISTS idx_nav_scheme ON fund_nav (scheme_id, date)",
            "CREATE INDEX IF NOT EXISTS idx_mgr_scheme ON fund_managers (scheme_id)",
            "CREATE INDEX IF NOT EXISTS idx_hold_scheme ON fund_holdings (scheme_id, rank)",
        ]
        tables += ["fund_detail", "fund_nav", "fund_managers", "fund_holdings"]
    for t in tables:
        stmts.append(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        stmts.append(
            f"DO $$ BEGIN "
            f"CREATE POLICY pubread_{t} ON {t} FOR SELECT TO anon USING (true); "
            f"EXCEPTION WHEN duplicate_object THEN NULL; END $$"
        )
    with dest.connect() as conn:
        for s in stmts:
            try:
                conn.execute(text(s))
            except Exception as e:
                print(f"    note: {e}")
        conn.commit()
    print("  Done")


def dump_preview(tables):
    out_dir = HERE / "preview"
    out_dir.mkdir(exist_ok=True)
    for name, df in tables.items():
        path = out_dir / f"{name}.json"
        df.to_json(path, orient="records", indent=2, date_format="iso")
        print(f"    wrote {path.relative_to(HERE)}  ({len(df)} rows)")


# ── Main ─────────────────────────────────────────────────────────────

def main():
    dry_run = "--dry-run" in sys.argv
    want_out = "--out" in sys.argv
    want_detail = "--no-detail" not in sys.argv

    print("\n" + "=" * 62)
    print("  ETL: RESULTS_PROJECT screener CSVs (+ detail) → Supabase")
    print("=" * 62)

    # Try to open the source DB (for scheme_id mapping + detail enrichment).
    src = None
    if want_detail:
        try:
            src = get_source()
            with src.connect() as c:
                c.execute(text("SELECT 1"))
            print("  Source amfi_data: connected")
        except Exception as e:
            print(f"  ! Source DB unreachable — building CSV tables only. ({e})")
            src = None

    print("\n[1/5] Building funds table...")
    funds = build_funds(src)

    print("\n[2/5] Building category summary...")
    category_summary = build_category_summary(funds)

    print("\n[3/5] Building research log + metrics...")
    research = research_log()
    metrics = engine_metrics(funds)

    tables = {
        "funds": funds.drop(columns=["scheme_id"]).assign(
            scheme_id=funds["scheme_id"]),  # keep scheme_id last
        "research_log": research,
        "engine_metrics": metrics,
        "category_summary": category_summary,
    }

    has_detail = False
    if src is not None:
        print("\n[4/5] Building per-fund detail (live funds)...")
        detail = build_detail_tables(src, funds)
        tables.update(detail)
        has_detail = True
    else:
        print("\n[4/5] Skipping per-fund detail (no source DB).")

    print("\n[5/5] Finalising...")
    if want_out:
        print("  Writing local preview JSON...")
        dump_preview(tables)

    if dry_run:
        print("\n  DRY RUN — not pushing. Summary:")
        for name, df in tables.items():
            print(f"    {name:18s} {len(df):>5d} rows")
        return

    print("\n  Connecting to Supabase...")
    dest = get_supabase()
    with dest.connect() as c:
        c.execute(text("SELECT 1"))
    print("  Supabase: connected")

    print("\n  Pushing tables...")
    for name, df in tables.items():
        push(dest, name, df)

    post_push_sql(dest, has_detail)

    print("\n" + "=" * 62)
    print(f"  DONE — {len(tables)} tables pushed to Supabase")
    print("=" * 62)
    print(f"""
  The website queries these via Supabase's REST API, e.g.:

    # the live list, best-in-category first
    GET {SUPABASE_PROJECT_URL}/rest/v1/funds?snapshot=eq.live&order=quality.desc

    # filter by risk band + quality (the 2D retail flow)
    GET {SUPABASE_PROJECT_URL}/rest/v1/funds?snapshot=eq.live&risk_band=eq.Conservative&quality=gte.70

    # on click → the fund's detail (join everything on scheme_id)
    GET {SUPABASE_PROJECT_URL}/rest/v1/fund_detail?scheme_id=eq.1234
    GET {SUPABASE_PROJECT_URL}/rest/v1/fund_nav?scheme_id=eq.1234&order=date
    GET {SUPABASE_PROJECT_URL}/rest/v1/fund_managers?scheme_id=eq.1234
    GET {SUPABASE_PROJECT_URL}/rest/v1/fund_holdings?scheme_id=eq.1234&order=rank

  Headers: apikey: <anon-key>   (Supabase dashboard → Settings → API)

  Re-run after each yearly re-score (score_live.py) to refresh the site.
""")


if __name__ == "__main__":
    main()
