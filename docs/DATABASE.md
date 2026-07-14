# AMFI Mutual Fund Database — Data Dictionary

**Database:** `amfi_data` (PostgreSQL)  
**Profiled:** 30 June 2026  
**Reviewed:** 14 July 2026 — counts unchanged since the 30 June 2026 profile (no ingestion since; the scheme-master snapshot is dated 15 June 2026).  
**Total:** 33 tables, 1 view, ~37 million rows

> **Where the schema lives.** The `CREATE TABLE` DDL and the feature/return builders this
> dictionary describes are in [`../data_pipeline/database/`](../data_pipeline/database/):
> `amc_schema.sql`, `funds_schema.sql`, `funds_2_schema.sql`, `portfolio_schema.sql`,
> `ter_schema.sql`, `aum_scheme.sql`, `bse_bridge_schema.sql`, plus `build_returns.sql`,
> `build_returns_clean.sql`, `build_features.sql`, `clean_features.sql`, `verify_features.sql`.
> The `feature_*` / `train_dataset*` tables (§8) are what [`../src/prepare_features.py`](../src/prepare_features.py)
> reproduces into [`../data/ml_dataset.csv`](../data/ml_dataset.csv) — the file the whole ML analysis runs on.

---

## Table of Contents

1. [How the database is organised](#1-how-the-database-is-organised)
2. [Entity & Reference Tables](#2-entity--reference-tables)
   - [amc](#21-amc--asset-management-companies)
   - [amc_alias](#22-amc_alias--name-aliases)
   - [scheme](#23-scheme--mutual-fund-schemes)
   - [scheme_plan](#24-scheme_plan--plans-share-classes)
   - [category](#25-category--sebi-categories)
3. [NAV Time-Series](#3-nav-time-series)
   - [nav](#31-nav--daily-nav)
   - [plan_nav_monthly](#32-plan_nav_monthly--month-end-nav)
   - [plan_return_monthly](#33-plan_return_monthly--monthly-returns)
4. [Assets Under Management (AUM)](#4-assets-under-management-aum)
   - [plan_aum](#41-plan_aum--quarterly-aum-per-plan)
   - [amc_aum](#42-amc_aum--aum-per-fund-house)
   - [scheme_aum & v_scheme_aum](#43-scheme_aum--v_scheme_aum)
5. [Total Expense Ratio (TER)](#5-total-expense-ratio-ter)
6. [BSE Scheme Master](#6-bse-scheme-master)
7. [Portfolio Holdings (Star Schema)](#7-portfolio-holdings-star-schema)
   - [fund_dim](#71-fund_dim--fund-dimension)
   - [portfolio_snapshot_fact](#72-portfolio_snapshot_fact--monthly-snapshots)
   - [portfolio_holding_fact](#73-portfolio_holding_fact--individual-holdings)
8. [ML / Feature & Training Tables](#8-ml--feature--training-tables)
9. [Portfolio Disclosure Crawl](#9-portfolio-disclosure-crawl)
10. [Empty Reference Tables (Future Use)](#10-empty-reference-tables-future-use)
11. [Row Counts at a Glance](#11-row-counts-at-a-glance)
12. [Data Quality & Known Issues](#12-data-quality--known-issues)

---

## 1. How the database is organised

The database tracks Indian mutual funds end-to-end. Here's the mental model:

```
AMC (fund house)
 └── Scheme (the fund itself, e.g. "HDFC Flexi Cap Fund")
      └── Scheme Plan (the investable variant, e.g. "Direct Growth" or "Regular IDCW")
           ├── NAV (daily prices)
           ├── AUM (quarterly assets)
           └── Returns (monthly performance)
```

**Seven data domains:**

| Domain | What it covers | Key tables |
|--------|---------------|------------|
| Entity & reference | Fund houses, schemes, plans, categories | `amc`, `scheme`, `scheme_plan`, `category` |
| Identity resolution | Different names for the same AMC; ISIN cross-references | `amc_alias`, `bse_scheme` |
| NAV time-series | Daily and month-end net asset values | `nav`, `plan_nav_monthly`, `plan_return_monthly` |
| AUM | Assets under management at plan and AMC level | `plan_aum`, `amc_aum`, `scheme_aum`, `v_scheme_aum` |
| TER (cost) | Total expense ratios by scheme | `ter` |
| Portfolio holdings | What each fund actually owns (star schema) | `fund_dim`, `portfolio_snapshot_fact`, `portfolio_holding_fact` |
| ML / features | Engineered features and training datasets | `feature_scheme`, `feature_plan`, `train_dataset`, `train_dataset_risk` |

**Key numbers:**

| Metric | Value |
|--------|-------|
| Fund houses (AMC) | 60 (59 active, 1 wound up) |
| Schemes | 14,745 |
| Scheme plans | 34,794 |
| Categories | 56 |
| Daily NAV observations | 33.2 million |
| Portfolio holdings | 2.49 million |
| NAV history | Apr 2006 – Jun 2026 |
| Largest table | `nav` (~33.2M rows) |

> **Performance warning:** The `nav` table is enormous. Always filter by `scheme_plan_id` and/or `nav_date` (both indexed). Never do `SELECT * FROM nav` without a WHERE clause.

---

## 2. Entity & Reference Tables

These define the core entities: who runs the fund, what the fund is, and which variant you can invest in.

### 2.1 `amc` — Asset Management Companies

**What it is:** One row per fund house (e.g. "HDFC MF", "SBI MF"). This is the top-level entity.

**Row count:** 60

| Column | Type | What it means |
|--------|------|---------------|
| `amc_id` | int8 (PK) | Auto-generated ID. Every other table references this. |
| `sebi_reg_id` | text (unique) | SEBI registration number. Uniquely identifies the AMC with the regulator. |
| `fund_house_name` | text (unique) | Display name (e.g. "HDFC MF"). This is what you'll see in reports. |
| `amc_legal_name` | text | Registered legal name — **currently empty for all rows**. |
| `status` | enum | One of: `active`, `wound_up`, `merged`, `suspended`. 59 are active; 1 (Sahara) is wound_up. |
| `mf_setup_date` | date | When the mutual fund was set up — **currently empty**. |
| `amc_incorporation_date` | date | When the AMC company was incorporated — **currently empty**. |
| `registration_valid_from` | date | SEBI registration start — **currently empty**. |
| `registration_valid_to` | date | SEBI registration end — **currently empty**. Has a CHECK: must be after valid_from. |
| `trustee_company_name` | text | Name of the trustee company — **currently empty**. |
| `rta_id` | int8 (FK→rta) | Registrar & transfer agent — **currently empty** (rta table is also empty). |
| `paid_up_capital` | numeric | Paid-up capital in INR — **currently empty**. |
| `registered_address` | text | Registered office address — **currently empty**. |
| `correspondence_address` | text | Mailing address — **currently empty**. |
| `city`, `state`, `pincode` | text | Location — **currently empty**. |
| `phone`, `fax` | text | Contact numbers — **currently empty**. |
| `website_url` | text | AMC website — **currently empty**. |
| `email`, `email_domain` | text | Contact email — **currently empty**. |
| `amfi_mf_id` | int2 | AMFI's internal fund-house ID. Used to join with TER and AUM feeds. Populated for 53 of 60 AMCs. |

**What's populated vs empty:** Only `sebi_reg_id`, `fund_house_name`, `status` and `amfi_mf_id` have data. Everything else (legal name, dates, address, contact info, RTA) is placeholder — awaiting a future enrichment feed (likely from SEBI SAI documents).

> **Note:** The Sahara AMC row was added manually with a placeholder `sebi_reg_id`. Replace it with the real registration number when available.

---

### 2.2 `amc_alias` — Name aliases

**What it is:** Maps the many spellings of each AMC to a single `amc_id`. Crucial because AMFI, BSE, and CSV feeds all use different names for the same fund house.

**Row count:** 128

| Column | Type | What it means |
|--------|------|---------------|
| `amc_id` | int8 (FK→amc) | The AMC this alias belongs to. |
| `alias` | text | An alternate name (e.g. "DSP MF", "DSP Mutual Fund", "DSP Asset Managers Private Limited" all point to the same amc_id). |
| `source` | text | Where the alias came from (e.g. `amfi_csv`). |

**Primary key:** (amc_id, alias) — one AMC can have many aliases.

**Index:** A lowercase functional index (`idx_amc_alias_lower`) supports case-insensitive lookups.

**Example:** AMC "DSP MF" (amc_id 16) has aliases: "DSP MF", "DSP Mutual Fund", "DSP Asset Managers Private Limited".

---

### 2.3 `scheme` — Mutual fund schemes

**What it is:** One row per scheme within an AMC. A scheme is the fund itself (e.g. "HDFC Flexi Cap Fund"), which then has multiple plan variants (Regular Growth, Direct Growth, Regular IDCW, etc.).

**Row count:** 14,745

| Column | Type | What it means |
|--------|------|---------------|
| `scheme_id` | int8 (PK) | Auto-generated ID. |
| `amc_id` | int8 (FK→amc) | Which fund house runs this scheme. |
| `name` | text | Scheme name (e.g. "HDFC Flexi Cap Fund"). Unique within each AMC. |
| `category_id` | int8 (FK→category) | SEBI category (e.g. "Flexi Cap Fund" under "Equity"). All 14,745 populated. |
| `structure` | text | `open_ended`, `close_ended`, or `interval`. All populated. |
| `inception_date` | date | When the scheme launched. Only 6,146 of 14,745 populated (42%). |
| `is_active` | bool | Whether the scheme is currently active. All set to true (default). |

**Unique constraint:** (amc_id, name) — no two schemes under the same AMC can have the same name.

**Coverage:** 54 of 60 AMCs have schemes. The remaining 6 AMCs are very new or were added before their schemes were ingested.

> **Data quality issue — structure casing:** The `structure` column mixes formats: `close_ended` (9,424 rows) vs `Close Ended` (436 rows), `open_ended` (4,719) vs `Open Ended` (114), `interval` (42) vs `Interval Fund` (10). Always normalise before grouping:
> ```sql
> lower(replace(structure, ' ', '_'))
> ```

---

### 2.4 `scheme_plan` — Plans (share classes)

**What it is:** The investable unit. Each scheme has multiple plans — typically Regular Growth, Regular IDCW, Direct Growth, Direct IDCW. This is what NAV and AUM data is tracked against.

**Row count:** 34,794

| Column | Type | What it means |
|--------|------|---------------|
| `scheme_plan_id` | int8 (PK) | Auto-generated ID. Most time-series tables (nav, plan_aum, etc.) reference this. |
| `scheme_id` | int8 (FK→scheme) | Parent scheme. |
| `amfi_scheme_code` | text (unique) | AMFI's scheme code (e.g. "100033"). **The primary join key** to AMFI data feeds. All 34,794 populated. |
| `raw_scheme_name` | text | Original name string from AMFI (e.g. "Aditya Birla Sun Life Large & Mid Cap Fund - Regular Growth"). |
| `plan_type` | text | `regular`, `direct`, `retail`, or `institutional`. Retail and institutional are legacy (pre-2013) classifications. 98% populated. |
| `option_type` | text | `growth`, `idcw` (income distribution), `payout`, or `bonus`. 90% populated. |
| `idcw_frequency` | text | For IDCW plans: `daily`, `weekly`, `monthly`, `quarterly`, etc. Only populated where relevant (5,159 rows). |
| `isin_growth_payout` | text | Primary ISIN for the plan. 80% populated (27,930). Indexed. |
| `isin_reinvestment` | text | Reinvestment ISIN (for IDCW plans that reinvest). 18% populated (6,173). Indexed. |
| `is_active` | bool | Whether the plan is currently open. 10,570 active. |
| `start_date` | date | Launch date. 61% populated (21,119). |
| `end_date` | date | Maturity/closure date. NULL means open-ended. 10,184 have a past end_date (closed plans). |
| `lock_in_months` | int4 | Lock-in period (e.g. 36 months for ELSS). |
| `face_value` | numeric | Face value per unit. 48% populated. |
| `isin_source` | text | How the ISIN was filled: NULL means it came from the AMFI feed directly. `bse_name` means it was back-filled from BSE data. Only 13 rows were back-filled from BSE. |

**Plan type breakdown:**

| plan_type | Count |
|-----------|-------|
| regular | 21,113 |
| direct | 10,621 |
| retail | 1,140 |
| institutional | 1,088 |
| (null) | 832 |

**Option type breakdown:**

| option_type | Count |
|-------------|-------|
| idcw | 15,477 |
| growth | 14,136 |
| (null) | 3,612 |
| payout | 1,277 |
| bonus | 292 |

---

### 2.5 `category` — SEBI categories

**What it is:** The SEBI-mandated category taxonomy. Each scheme belongs to one category. Categories are grouped by asset class.

**Row count:** 56

| Column | Type | What it means |
|--------|------|---------------|
| `category_id` | int8 (PK) | Auto-generated ID. |
| `asset_class` | text | Top-level grouping: Equity, Debt, Hybrid, Other, Solution Oriented, Fund of Funds, or NULL (legacy). |
| `name` | text | Category name (e.g. "Large Cap Fund", "Liquid Fund"). |

**Unique constraint:** (asset_class, name).

**Well-formed SEBI categories (with asset_class):**

| Asset class | Categories | Top by scheme count |
|-------------|-----------|---------------------|
| Debt | 16 | Liquid Fund (290), Overnight (149), Low Duration (148) |
| Equity | 12 | Sectoral/Thematic (406), Large Cap (77), ELSS (74) |
| Hybrid | 7 | Arbitrage (94), Aggressive Hybrid (83) |
| Other | 5 | Index Funds (506), Other ETFs (319) |
| Solution Oriented | 3 | Retirement Fund (49), Children's Fund (18) |
| Fund of Funds | 2 | Domestic (13), Overseas (7) |

**Legacy categories (NULL asset_class) — these predate SEBI's formal categorisation:**

| Name | Scheme count | Notes |
|------|-------------|-------|
| Income | 9,821 | Overwhelmingly the largest single category. These are old closed-ended FMPs and income schemes. |
| Growth | 430 | Legacy equity-oriented schemes |
| ELSS | 74 | Duplicates the Equity→ELSS category |
| Gilt | 54 | Duplicates Debt→Gilt Fund |
| Liquid | 32 | Duplicates Debt→Liquid Fund |
| Others | — | Balanced, Money Market, Floating Rate, Other ETFs, Gold ETFs, Assured Return |

> **Data quality issues:**
> - "ELSS" exists twice — once under Equity, once with NULL asset_class.
> - "Children's Fund" has an encoding issue (mojibake `â€™` instead of apostrophe) plus a duplicate "Children s Fund" with 0 schemes.
> - The 9,821 "Income" schemes under NULL asset_class should ideally be remapped to proper Debt subcategories.
>
> **Recommendation:** Treat categories with a non-NULL `asset_class` as the canonical SEBI taxonomy. Plan a cleanup pass for the legacy nulls.

---

## 3. NAV Time-Series

Net asset value (the price of one unit of a mutual fund) tracked daily and at month-end.

### 3.1 `nav` — Daily NAV

**What it is:** The largest table in the database. One row per plan per trading day. This is the raw daily price history.

**Row count:** 33,205,368

| Column | Type | What it means |
|--------|------|---------------|
| `scheme_plan_id` | int8 (PK, FK→scheme_plan) | Which plan this NAV belongs to. |
| `nav_date` | date (PK) | The date of the NAV observation. Indexed. |
| `nav` | numeric(18,8) | The NAV value. CHECK constraint ensures it's > 0. |

**Coverage:**

| Metric | Value |
|--------|-------|
| Total rows | 33,205,368 |
| Plans with NAV data | 32,756 of 34,794 (94%) |
| Earliest NAV | 2006-04-01 |
| Latest NAV | 2026-06-24 |

> **Query tip:** Always filter by `scheme_plan_id` first (clustered in the PK), then `nav_date`. Example:
> ```sql
> SELECT nav_date, nav
> FROM nav
> WHERE scheme_plan_id = 123
>   AND nav_date BETWEEN '2025-01-01' AND '2025-12-31';
> ```

---

### 3.2 `plan_nav_monthly` — Month-end NAV

**What it is:** Month-end NAV snapshots. Since markets may be closed on the last calendar day of a month, this table records both the month-end label and the actual date the NAV was taken from.

**Row count:** 642,496

| Column | Type | What it means |
|--------|------|---------------|
| `scheme_plan_id` | int8 (PK) | Plan. |
| `month_end` | date (PK) | Month-end label (e.g. 2025-06-30). Indexed. |
| `actual_nav_date` | date | The real trading day the NAV is from (e.g. 2025-06-27 if June 30 was a weekend). |
| `nav` | numeric(18,8) | The NAV on that date. |

**Coverage:** 13,761 plans, Apr 2006 – Jun 2026.

---

### 3.3 `plan_return_monthly` — Monthly returns

**What it is:** Pre-computed trailing returns at 1, 3, 6 and 12-month windows. Derived from the monthly NAV table. Use this instead of recomputing returns from daily NAV.

**Row count:** 642,496

| Column | Type | What it means |
|--------|------|---------------|
| `scheme_plan_id` | int8 (PK) | Plan. |
| `month_end` | date (PK) | Month-end date. Indexed. |
| `nav` | numeric(18,8) | Month-end NAV. |
| `ret_1m` | numeric | 1-month trailing return (as a decimal, e.g. 0.05 = 5%). |
| `ret_3m` | numeric | 3-month trailing return. |
| `ret_6m` | numeric | 6-month trailing return. |
| `ret_12m` | numeric | 12-month trailing return (1-year). |

**Also:** `return_artifacts` (203 rows) is a scratch/QA table with just `scheme_plan_id`, `month_end`, `ret_1m`. Not part of the production model — ignore it.

---

## 4. Assets Under Management (AUM)

AUM measures how much money investors have put into a fund. All AUM values in this database are in **INR lakh** (1 lakh = ₹100,000). Divide by 100 to get crore.

### 4.1 `plan_aum` — Quarterly AUM per plan

**What it is:** Average AUM per scheme plan per quarter, from the AMFI schemewise AUM feed.

**Row count:** 618,912

| Column | Type | What it means |
|--------|------|---------------|
| `plan_aum_id` | int8 (PK) | Auto-generated ID. |
| `scheme_plan_id` | int8 (FK→scheme_plan) | Which plan. Unique with period_end. |
| `period_end` | date | Quarter-end date (e.g. 2025-03-31). |
| `fy_id` | int2 | Fiscal year ID. |
| `period_id` | int2 | Period ID within the fiscal year. |
| `category_label` | text | Category label from the source feed. |
| `avg_aum_lakh` | numeric | Average AUM in INR lakh, excluding domestic FoF but including overseas FoF. CHECK ≥ 0. |
| `avg_aum_fof_dom_lakh` | numeric | Domestic fund-of-fund AAUM component, INR lakh. |
| `source` | text | Default: `amfi_average_aum_schemewise`. |

**Coverage:** 32,187 distinct plans; Apr 2006 – Mar 2026.

---

### 4.2 `amc_aum` — AUM per fund house

**What it is:** Fund-house-level AUM from the AMFI fundwise feed. Includes historical data for defunct AMCs.

**Row count:** 4,364

| Column | Type | What it means |
|--------|------|---------------|
| `amc_aum_id` | int8 (PK) | Auto-generated ID. |
| `amc_id` | int8 (FK→amc) | AMC. **Can be NULL** — 784 rows belong to defunct/renamed fund houses that don't match a current AMC. |
| `mf_name_raw` | text | Raw fund-house name from the feed. Unique with period_end. |
| `period_end` | date | Period end date. |
| `avg_aum_lakh` | numeric | Average AUM, INR lakh. |
| `avg_aum_fof_dom_lakh` | numeric | Domestic FoF AAUM, INR lakh. |
| `closing_aum_lakh` | numeric | Closing (end-of-period) AUM, INR lakh. |
| `closing_aum_fof_dom_lakh` | numeric | Closing FoF AUM, INR lakh. |
| `source` | text | Default: `amfi_average_aum_fundwise`. |

**Coverage:** 52 distinct AMCs (with amc_id); Apr 2006 – Mar 2026. The 784 NULL-amc_id rows are retained for historical industry totals.

---

### 4.3 `scheme_aum` & `v_scheme_aum`

**`scheme_aum`** (table) is currently **empty** (0 rows). It was designed for scheme-level AUM but hasn't been populated directly.

**`v_scheme_aum`** (view) derives scheme-level AUM on the fly by summing `plan_aum` up to the scheme level via `scheme_plan`. **Use the view** for scheme-level AUM queries:

```sql
SELECT scheme_id, period_end, avg_aum_lakh / 100 AS avg_aum_crore
FROM v_scheme_aum
WHERE scheme_id = 42
ORDER BY period_end;
```

---

## 5. Total Expense Ratio (TER)

**What it is:** Monthly TER snapshots per scheme, from the AMFI revised-TER feed. TER is the annual cost of running a fund, expressed as a percentage. Separate columns for Regular and Direct plans.

**Table:** `ter`  
**Row count:** 163,266

| Column | Type | What it means |
|--------|------|---------------|
| `ter_id` | int8 (PK) | Auto-generated ID. |
| `scheme_id` | int8 (FK→scheme) | Matched scheme. **NULL for 35,757 rows** (~22%) that couldn't be matched. |
| `amc_id` | int8 (FK→amc) | AMC. |
| `mf_id` | int2 | AMFI fund-house ID. Part of uniqueness constraint with raw_scheme_name and ter_month. |
| `nsdl_scheme_code` | text | NSDL scheme identifier. |
| `raw_scheme_name` | text | Scheme name from the TER feed. |
| `scheme_type` | text | Source classification (e.g. "Open Ended"). |
| `scheme_category` | text | Source category label. |
| `ter_month` | date | Month of the TER snapshot. Indexed. |
| `as_of_date` | date | The specific day the TER was sampled from. |
| `reg_base_ter` | numeric | Regular plan base TER (%). |
| `reg_addl_6a_b` | numeric | Additional TER under regulation 6A(b) (%). |
| `reg_addl_6a_c` | numeric | Additional TER under regulation 6A(c) (%). |
| `reg_gst` | numeric | GST rate on TER (e.g. 18 means 18%). Total ≈ base × (1 + gst/100). |
| `reg_total_ter` | numeric | Total Regular-plan TER (%). |
| `dir_base_ter` | numeric | Direct plan base TER (%). |
| `dir_addl_6a_b`, `dir_addl_6a_c`, `dir_gst`, `dir_total_ter` | numeric | Direct-plan TER components (same structure as Regular). |
| `source` | text | Default: `amfi_ter_revised`. |

**Coverage:** 51 AMCs; 3,648 distinct matched schemes; Apr 2018 – Mar 2026.

> **Known gap:** 35,757 rows (22%) have `scheme_id = NULL` — the TER feed scheme names haven't been fully resolved to the scheme table. For complete expense analysis, you'd need to improve matching via `raw_scheme_name` and `mf_id`.

---

## 6. BSE Scheme Master

**What it is:** A secondary scheme reference keyed by ISIN, sourced from BSE scheme master files. Useful for cross-referencing ISINs, and as a back-fill source for face values, lock-in periods, and lifecycle dates.

**Table:** `bse_scheme`  
**Row count:** 26,135

| Column | Type | What it means |
|--------|------|---------------|
| `isin` | text (PK) | Instrument ISIN. The primary key. |
| `bse_scheme_code` | text | BSE's scheme code. |
| `rta_scheme_code` | text | Registrar's scheme code. |
| `amc_scheme_code` | text | AMC's internal scheme code. |
| `amc_code` | text | AMC identifier in BSE's system. |
| `scheme_type` | text | BSE scheme type. |
| `scheme_plan` | text | BSE plan descriptor. |
| `scheme_name` | text | BSE scheme name. Indexed. |
| `face_value` | numeric | Face value per unit. |
| `start_date` | date | Scheme start date. All 26,135 populated. |
| `end_date` | date | Scheme end date. 11,359 populated. |
| `lock_in_months` | int4 | Lock-in period. 23,436 populated. |
| `source_file` | text | Which BSE file this came from. |

**Linkage:** You can join `bse_scheme.isin` to `scheme_plan.isin_growth_payout` or `scheme_plan.isin_reinvestment` to cross-reference. However, a profiling check shows that every plan matching a BSE ISIN already has a `start_date`, so BSE won't add new launch dates via this join. It's still useful for `lock_in_months`, `face_value`, and `end_date` back-fill.

---

## 7. Portfolio Holdings (Star Schema)

This is the newest data layer — instrument-level portfolio disclosures parsed from AMC monthly/half-yearly portfolio statements. Modelled as a **star schema** with three tables:

```
fund_dim (dimension)
 └── portfolio_snapshot_fact (one row per fund per statement date)
      └── portfolio_holding_fact (one row per instrument held)
```

### 7.1 `fund_dim` — Fund dimension

**What it is:** The dimension table for funds in the portfolio layer. One row per fund.

**Row count:** 7,623

| Column | Type | What it means |
|--------|------|---------------|
| `fund_id` | serial (PK) | Auto-generated ID. |
| `amc_name` | text | Fund-house name (as it appears in portfolio disclosures). |
| `fund_name` | text | Fund name. |

**Unique constraint:** (amc_name, fund_name).

**Important:** This table uses its own AMC names (35 distinct values) and is **not FK-linked to the `amc` table**. Of those 35, only 21 match `amc.fund_house_name` or an alias; 14 don't. To integrate this layer, add aliases for the unmatched 14, or add an `amc_id` column.

---

### 7.2 `portfolio_snapshot_fact` — Monthly snapshots

**What it is:** One row per fund per statement date. Contains fund-level metadata for that period.

**Row count:** 62,406

| Column | Type | What it means |
|--------|------|---------------|
| `snapshot_id` | serial (PK) | Auto-generated ID. Referenced by holdings. |
| `fund_id` | int (FK→fund_dim) | Which fund. ON DELETE CASCADE. |
| `statement_date` | date | The disclosure date (e.g. 2025-03-31). Indexed. Unique with fund_id. |
| `currency_unit` | text | Currency denomination. |
| `risk_level` | text | Risk classification. **Currently empty** (0 rows populated). |
| `portfolio_turnover_ratio` | numeric | Turnover ratio. Only 2,034 rows (3%) populated. |
| `num_holdings` | int | Number of holdings in the portfolio. 100% populated. |
| `aum` | numeric | Portfolio AUM. 50,562 rows (81%) populated. |
| `source_file` | text | Which file this was parsed from. |
| `sheet_name` | text | Which sheet/tab within the file. |

**Date range:** Nov 2005 – Apr 2065 (yes, 2065 — see data quality note below).

**Top months by snapshot count:** Apr 2026 (705), Mar 2026 (692), Dec 2025 (613).

> **Data quality issue:** The `statement_date` range extends to 2065-04-15, which is clearly a mis-parsed date. Always add `WHERE statement_date <= CURRENT_DATE` for time-series work. Consider identifying and correcting the offending rows.

---

### 7.3 `portfolio_holding_fact` — Individual holdings

**What it is:** The grain-level table — one row per instrument held in each snapshot. This tells you exactly what each fund owns.

**Row count:** 2,489,836

| Column | Type | What it means |
|--------|------|---------------|
| `holding_id` | serial (PK) | Auto-generated ID. |
| `snapshot_id` | int (FK→snapshot_fact) | Parent snapshot. ON DELETE CASCADE. Indexed. |
| `section` | text | Instrument category (e.g. "Equity & Equity related", "Certificate of Deposit"). |
| `subsection` | text | Further classification within the section. |
| `row_num` | int | Original row order in the source document. |
| `instrument` | text | Security name (e.g. "Reliance Industries Ltd", "7.26% GOI 2033"). |
| `isin` | text | Security ISIN. 100% populated. Indexed. |
| `industry` | text | Industry/sector classification. 100% populated. |
| `quantity` | numeric | Number of units/shares held. |
| `market_value` | numeric | Market value. 95% populated (2,358,676 rows). |
| `pct_nav` | numeric | Weight as percentage of NAV. 95% populated (2,377,080 rows). |

**Key statistics:**

| Metric | Value |
|--------|-------|
| Distinct ISINs held | 44,964 |
| Average holdings per snapshot | 40.8 |
| Min holdings in a snapshot | 1 |
| Max holdings in a snapshot | 757 |

**Top instrument sections:**

| Section | Holdings |
|---------|----------|
| Equity & Equity related | 955,093 |
| None | 463,866 |
| Non Convertible Debentures | 162,725 |
| EQUITY & EQUITY RELATED | 124,931 |
| Listed / awaiting listing on the stock exchanges | 109,511 |
| Certificate of Deposit | 76,415 |
| Debt Instruments | 76,221 |
| Commercial Paper | 60,554 |
| Government Securities | 50,157 |

> **Data quality issue:** The `section` column has casing inconsistencies ("Equity & Equity related" and "EQUITY & EQUITY RELATED" are counted separately — together they'd be ~1.08M). The "None" section (463K) likely represents rows where the source document didn't have a section header. Normalise before aggregating.

**Linkage to the rest of the database:**

- **Held ISINs → scheme_plan ISINs:** 342 distinct ISINs in holdings match an ISIN in `scheme_plan`. These represent funds-of-funds or cross-holdings where one tracked scheme holds units of another. Useful for look-through analysis, but it's a small fraction — most of the 44,964 held ISINs are direct equities, bonds, and money-market instruments, not MF units.
- **fund_dim → amc:** 21 of 35 portfolio AMC names match the `amc` table; 14 don't. The portfolio layer is currently standalone.

---

## 8. ML / Feature & Training Tables

Pre-computed feature matrices and model-ready training datasets built from NAV, AUM and TER. Used for fund selection, performance prediction, and risk analysis.

**What the columns mean (shared across all four tables):**

| Column group | What it measures |
|-------------|-----------------|
| `ret_1m, ret_3m, ret_6m, ret_12m` | Trailing returns over 1/3/6/12 months |
| `vol_12m_ann, vol_36m_ann` | Annualised volatility (standard deviation of returns) over 12/36 months |
| `drawdown_12m, drawdown_36m` | Maximum drawdown (worst peak-to-trough decline) over 12/36 months |
| `sharpe_12m` | Sharpe ratio over 12 months (return per unit of risk) |
| `sortino_12m` | Sortino ratio over 12 months (return per unit of downside risk) |
| `downside_dev_12m` | Downside deviation over 12 months |
| `age_months` | How long the scheme has been running |
| `avg_aum_lakh` | Average AUM in INR lakh |
| `ter_pct` | Total expense ratio in percent |
| `fwd_ret_1m/3m/6m/12m` | **Forward** returns — future performance (target variable for prediction) |
| `fwd_catrank_12m` | Forward 12-month category rank (0 = best, 1 = worst) |
| `fwd_excess_12m` | Forward 12-month excess return vs category average |
| `fwd_bottom_quintile_12m` | Binary flag: did the fund end up in the bottom 20% of its category? |

**The four tables:**

| Table | Grain | Rows | Date range | Schemes |
|-------|-------|------|-----------|---------|
| `feature_scheme` | scheme × month | 339,449 | Apr 2006 – Jun 2026 | 8,517 |
| `feature_plan` | plan × month | 642,496 | Apr 2006 – Jun 2026 | 13,761 |
| `train_dataset` | scheme × month | 48,175 | Nov 2014 – Jun 2026 | 978 |
| `train_dataset_risk` | scheme × month | 48,175 | Nov 2014 – Jun 2026 | 978 |

**What's different:**
- `feature_*` tables cover the full history and all plans/schemes.
- `train_dataset` is filtered to model-eligible schemes (enough history, proper category) — 978 schemes from Nov 2014. This is what you'd feed into a model.
- `train_dataset_risk` adds forward risk targets: `fwd_vol_12m`, `fwd_dd_12m`, `fwd_vol_excess_12m`, `fwd_vol_catrank_12m`, `fwd_dd_excess_12m`, `fwd_dd_catrank_12m`.
- `train_dataset` and `train_dataset_risk` also include net-flow and AUM-growth features: `net_flow_1m/3m/6m/12m_rate`, `aum_growth_12m`.

These are **denormalised** tables with no foreign keys — they're snapshots designed for analytics and ML pipelines, not for transactional queries.

---

## 9. Portfolio Disclosure Crawl

Operational tables that manage the process of discovering and downloading AMC portfolio disclosure documents from AMFI.

### `portfolio_source` — AMC disclosure landing pages

**Row count:** 149

| Column | Type | What it means |
|--------|------|---------------|
| `source_id` | int8 (PK) | Auto-generated ID. |
| `amc_id` | int8 (FK→amc) | Linked AMC (51 of 149 are linked). |
| `amc_name` | text | AMC name from the source. |
| `disclosure_type` | text | Type of disclosure. Unique with amc_name. |
| `disclosure_url` | text | URL of the disclosure landing page. |
| `needs_js` | bool | Whether the page requires JavaScript to render. Default true. |
| `note` | text | Free-text notes. |

### `portfolio_file` — Discovered disclosure files

**Row count:** 26,703

| Column | Type | What it means |
|--------|------|---------------|
| `file_id` | int8 (PK) | Auto-generated ID. |
| `source_id` | int8 (FK→portfolio_source) | Which source page this file was found on. |
| `amc_name` | text | AMC name. |
| `file_url` | text (unique) | URL of the file. |
| `file_name` | text | Filename. |
| `file_format` | text | File format (e.g. pdf, xlsx). |
| `detected_period` | text | Detected disclosure period (e.g. "2025-03"). Indexed. |
| `found_on_url` | text | The page where this file was linked from. |
| `download_status` | text | Status: all 26,703 are `pending`. Indexed. |
| `local_path` | text | Local path after download. |
| `http_status` | int | HTTP response code from download attempt. |
| `error` | text | Error message if download failed. |

> **Note:** All 26,703 files are in `pending` status. If the holdings data has already been ingested via a separate pipeline, this status column isn't being updated. Otherwise, the crawl queue hasn't been executed yet.

---

## 10. Empty Reference Tables (Future Use)

These tables are defined in the schema but currently have **zero rows**. They represent planned enrichment from SEBI SAI (Scheme Additional Information) documents or other regulatory filings.

| Table | What it's for |
|-------|--------------|
| `rta` | Registrar & Transfer Agents (e.g. CAMS, KFintech). Referenced by `amc.rta_id`. |
| `custodian` | Fund custodians (e.g. HDFC Bank, Deutsche Bank). |
| `amc_custodian` | Links AMCs to their custodians. |
| `auditor` | Auditing firms (e.g. Deloitte, KPMG). |
| `amc_auditor` | Links AMCs to auditors, with a scope enum (`amc` or `schemes`). |
| `sponsor` | AMC sponsors/promoters (e.g. Aditya Birla Group). |
| `amc_sponsor` | Links AMCs to sponsors. |
| `sponsor_financials` | Sponsor net worth, income, profit by fiscal year. |
| `amc_shareholding` | AMC ownership breakdown (shareholder name, percentage, date). |
| `amc_official` | Key personnel — trustees, directors, CEO, compliance officer, investor service officer. Uses the `official_role` enum. |

**Custom enums defined for these tables:**

| Enum | Values |
|------|--------|
| `amc_status` | active, wound_up, merged, suspended |
| `auditor_scope` | amc, schemes |
| `official_role` | trustee, director, ceo, compliance_officer, investor_service_officer |

The `amc_status` enum is in active use; the other two are defined but unused since their tables are empty.

---

## 11. Row Counts at a Glance

| Table | Rows | Notes |
|-------|------|-------|
| `amc` | 60 | Fund houses |
| `amc_alias` | 128 | Name aliases |
| `amc_aum` | 4,364 | AMC-level AUM |
| `bse_scheme` | 26,135 | BSE ISIN reference |
| `category` | 56 | SEBI categories |
| `feature_plan` | 642,496 | ML features per plan |
| `feature_scheme` | 339,449 | ML features per scheme |
| `fund_dim` | 7,623 | Portfolio fund dimension |
| `nav` | **33,205,368** | Daily NAV (largest table) |
| `plan_aum` | 618,912 | Plan-level quarterly AUM |
| `plan_nav_monthly` | 642,496 | Month-end NAV |
| `plan_return_monthly` | 642,496 | Monthly trailing returns |
| `portfolio_file` | 26,703 | Disclosure file crawler |
| `portfolio_holding_fact` | **2,489,836** | Instrument holdings |
| `portfolio_snapshot_fact` | 62,406 | Portfolio snapshots |
| `portfolio_source` | 149 | Disclosure landing pages |
| `return_artifacts` | 203 | QA scratch table |
| `scheme` | 14,745 | Schemes |
| `scheme_aum` | 0 | Empty (use v_scheme_aum view) |
| `scheme_plan` | 34,794 | Plans (share classes) |
| `ter` | 163,266 | Expense ratios |
| `train_dataset` | 48,175 | ML training set |
| `train_dataset_risk` | 48,175 | ML training set (risk) |
| `rta`, `custodian`, `auditor`, `sponsor`, etc. | 0 each | Awaiting enrichment |

---

## 12. Data Quality & Known Issues

### Integrity checks (all passing)

| Check | Result |
|-------|--------|
| Schemes with no parent AMC | 0 |
| Plans with no parent scheme | 0 |
| Schemes with no category | 0 |
| NAV rows with no parent plan | 0 |
| Portfolio snapshots with no parent fund | 0 |
| Holdings with no parent snapshot | 0 |

The relational structure is clean — no orphan rows anywhere.

### Issues to address

| Priority | Issue | Where | What to do |
|----------|-------|-------|-----------|
| **High** | Future date 2065-04-15 in snapshots | `portfolio_snapshot_fact.statement_date` | Find and correct the mis-parsed date(s). Filter `statement_date <= current_date` in queries until fixed. |
| **High** | Inconsistent `structure` casing | `scheme.structure` | Normalise to lowercase snake_case (`open_ended`, `close_ended`, `interval`). |
| **Medium** | TER rows unmatched to scheme (22%) | `ter` — 35,757 rows with NULL `scheme_id` | Improve matching using `raw_scheme_name` and `mf_id`. |
| **Medium** | Duplicate/legacy categories | `category` — 11 NULL-asset-class buckets, duplicate "ELSS", encoding-broken "Children's Fund" | Remap legacy categories; fix encoding; drop empty duplicate. |
| **Medium** | Mixed-case section labels | `portfolio_holding_fact.section` | Unify casing, map synonyms (e.g. merge "Equity & Equity related" with "EQUITY & EQUITY RELATED"). |
| **Medium** | Portfolio layer not linked to AMC | `fund_dim` ↔ `amc` | Add `amc_alias` entries for the 14 unmatched names, or add an `amc_id` FK to `fund_dim`. |
| **Low** | Placeholder Sahara `sebi_reg_id` | `amc` | Replace with the real SEBI registration ID. |
| **Low** | Scheme inception dates 42% populated | `scheme.inception_date` | Source additional launch dates from BSE, RTA, or AMC websites. |
| **Low** | Empty governance/reference tables | `rta`, `sponsor`, `auditor`, `amc_official`, etc. | Populate from SEBI SAI documents when the enrichment pipeline is built. |

### Coverage scorecard

| Data layer | Status |
|-----------|--------|
| Core entities (amc / scheme / scheme_plan) | ✅ **Strong** — 100% keyed, well-populated |
| NAV (daily + monthly) | ✅ **Strong** — 33.2M rows, 20 years of history |
| AUM (plan + AMC) | ✅ **Strong** — full quarterly history since 2006 |
| Portfolio holdings | 🟡 **Good** — 2.49M rows, but needs date cleanup & FK linkage |
| TER | 🟡 **Partial** — 22% of rows unmatched to scheme |
| Scheme inception dates | 🟡 **Partial** — 42% populated |
| Governance / ownership / contacts | 🔴 **Empty** — awaiting enrichment feed |