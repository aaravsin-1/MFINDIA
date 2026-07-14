# Lovable Prompt — "FundLens" — Indian Mutual-Fund Selection Engine

Paste the **PROMPT** block below into [Lovable](https://lovable.dev). It is a
single, self-contained build spec. The data already lives in Supabase (populated
by `push_to_supabase.py` in this folder); the prompt tells Lovable exactly which
tables/columns exist and how to query them.

> **Before building**, connect Lovable to Supabase and set:
> - `SUPABASE_URL` = `https://xhkgqnapjevtpixlykzp.supabase.co`
> - `SUPABASE_ANON_KEY` = *(Supabase dashboard → Settings → API → anon/public key)*
>
> All tables are public-read (RLS `SELECT` for `anon`). The app never writes.

---

## THE PROMPT

Build a polished, trustworthy, **mobile-first** web app called **FundLens** that
helps ordinary Indian retail investors choose an actively-managed equity mutual
fund. It is a **fund-selection engine**, not a trading app — it does not sell
funds, take money, or show live intraday prices. Tone: honest, calm, plain-English,
never hype. Think "a fee-only advisor who refuses to overclaim."

### The core concept the whole app expresses

Each fund has **two independent 0–100 scores**:
- **Quality** — a machine-learning model's rank of the fund *within its own
  category* (how it compares to peer funds of the same type). **Never comparable
  across categories** — a Small Cap 100 and a Large Cap 100 are each "best in their
  class," not equally good.
- **Risk** — pure maths (past volatility + worst drawdown), mapped into three
  bands: **Conservative**, **Balanced**, **Aggressive**.

The retail journey: pick a **category** → pick a **risk comfort band** → see funds
ranked by **Quality**, with a 2-D Quality×Risk view and sliders to fine-tune → click
a fund for its fundamentals.

### Data source — Supabase (already populated, read-only)

Use the Supabase JS client. Always default list queries to `snapshot=eq.live`.

**`funds`** — the rated universe (main list table). Columns:
`snapshot` (`"live"` = current 381-fund buy-now list — use this everywhere except
the credibility page; `"validation"` = older gradable back-test), `as_of`,
`is_live`, `rank`, `fund_name`, `category`, `is_core_category` (bool),
`quality` (0–100 within-category), `risk` (0–100), `risk_band`
(`"Conservative"|"Balanced"|"Aggressive"`), `recommended` (bool — one of 10
validated picks), `holding_period`, `reason_1`, `reason_2` (plain-English, each
prefixed `[+]` strength or `[-]` drawback), `n_positive`, `n_negative`, `why`
(raw), `scheme_id` (join key to detail tables).

**`fund_detail`** — one summary row per LIVE fund, loaded **on click**. Columns:
`scheme_id`, `fund_name`, `category`, `quality`, `risk`, `risk_band`,
`recommended`, `holding_period`, `amc` (fund house), `inception_date`, `aum_cr`
(₹ crore), `aum_as_of`, `ter_pct` (expense ratio %), `ter_as_of`, `num_managers`,
`manager_names`, `nav_points`. (It also has `num_holdings`/`has_holdings` — ignore
those, see the holdings note below.)

**`fund_nav`** — ~13 monthly NAV points per LIVE fund: `scheme_id`, `date`
(month-end), `nav`. Use for a **1-year NAV trend sparkline** on the detail page.

**`fund_managers`** — current managers per LIVE fund: `scheme_id`, `manager_name`,
`start_date`, `tenure_years`, `is_current`.

**`engine_metrics`** — headline validated numbers: `metric`, `value`, `unit`,
`label`, `group` (`"performance"|"significance"|"product"`).

**`research_log`** — the 12 findings: `id`, `code` (F1–F12), `verdict`
(`"survived"|"dead"|"artifact"`), `title`, `finding`, `reference`.

**`category_summary`** — per category: `category`, `n_funds`, `n_recommended`,
`avg_quality`, `avg_risk`, `is_core`, `selection_edge_pct` (nullable — only Small
Cap 3.4 and Large Cap 0.6 are known).

> **`fund_holdings` — DO NOT USE in the UI.** The table exists in Supabase but its
> coverage is partial (~half the funds), so surfacing it would be misleading and
> inconsistent. Leave portfolio holdings out of the website entirely for now. (The
> data is intentionally retained in the database for a future release.)

### Pages

**1. Home**
- Hero: the honest one-line pitch (verbatim, below) + a primary "Find my fund" CTA.
- A strip of 4 headline stats pulled from `engine_metrics`: `edge_gross_pct`
  ("+2.4%/yr vs a fair benchmark"), `cohorts_positive` ("7 of 7 test years"),
  `p_value` (render as "≈1-in-1000 to be luck"), `negative_control` ("Passed the
  fake-data test"). Each with its `label` as a tooltip.
- "The 10 validated picks" — a grid of `funds` where `snapshot=eq.live &
  recommended=eq.true`, rendered as fund cards.
- A short "How it works in 30 seconds" teaser linking to the explainer page.

**2. Find my fund (the wizard — this is the product)**
A 3-step guided flow, then results:
- **Step 1 — Category.** Show the 5 **core** categories first as big cards (Large
  Cap Fund, Mid Cap Fund, Small Cap Fund, Flexi Cap Fund, ELSS), each with a
  one-line description and `n_funds` from `category_summary`; below, an
  "Other categories" expander (Sectoral/Thematic, Focused, Value, Multi Cap,
  Large & Mid Cap, Dividend Yield, Contra). Note on core cards: "Our validated
  recommendations come from these 5 categories."
- **Step 2 — Risk comfort.** Three large choices → `risk_band`:
  - **Conservative** — "Calm ride, smaller dips. Best if you'll hold 5+ years."
  - **Balanced** — "Moderate swings. Hold 3–5 years."
  - **Aggressive** — "Bumpy — only if you can stay invested through sharp drops. 1–3 years+."
  Add a "Not sure? Start with Balanced" shortcut.
- **Step 3 — Results.** Query `funds` where `snapshot=eq.live & category=eq.<cat> &
  risk_band=eq.<band>`, ordered by `quality.desc`. Above the list, a **2-D
  Quality×Risk scatter/quadrant** (x = Risk 0–100, y = Quality 0–100; highlight
  `recommended`), and two **range sliders** — "Minimum Quality" and "Risk range" —
  that filter the list live (client-side). Pin any `recommended=true` matches into
  a highlighted "★ Validated pick" band at top with a tooltip: *"One of our 10
  back-tested recommendations — the part of this engine actually proven in
  testing."* If a band/category combo returns nothing, gently suggest widening the
  risk range.

**3. Browse all funds**
Full `funds` (live) table with: category dropdown, risk-band chips, "Recommended
only" toggle, a **Quality slider** and **Risk slider**, and text search on
`fund_name`. Sortable columns (Rank, Quality, Risk). Paginate ~25/page (381 rows).
Reuse the fund card or a compact row that opens the detail view.

**4. Fund detail (`/fund/:scheme_id`)** — loaded on click
Fetch in parallel by `scheme_id`:
`fund_detail?scheme_id=eq.X`, `fund_nav?scheme_id=eq.X&order=date`,
`fund_managers?scheme_id=eq.X`.
Render:
- Header: fund name, `amc`, category chip, `recommended` badge.
- The two big gauges (Quality + Risk) with the same captions/tooltips as the cards.
- **Snapshot facts** row: AUM (`aum_cr` → "₹X cr"), Expense ratio (`ter_pct` → "X%"),
  Inception (`inception_date` → "since YYYY"), Risk band + suggested holding period.
- **1-year NAV trend**: a small line/sparkline from `fund_nav` (label "Direct plan,
  last 12 months — for trend only, not a return promise").
- **Managers**: list `manager_names` / `fund_managers` with `tenure_years`
  ("Managed by … · N yrs tenure").
- **Why this rating**: the full `why` as `[+]`/`[-]` pills (green check / amber
  caution; strip the literal prefix, use the icon).
- The disclaimer block (below). **No holdings section.**
- Gracefully handle nulls (some funds lack AUM/TER/managers) — show "—" or hide the
  row, never a broken value.

**5. How it works** (plain-English explainer)
Explain, jargon-free: the 2 scores (Quality within-category vs Risk absolute),
"category-neutral" picking (top-2 per core category), and the playbook:
*"Re-check yearly → hold every fund at least 12 months → only sell when it drops out
of its category's top 4. That keeps you in the 12.5% long-term tax bracket and
avoids exit fees. In practice funds turn over about every 2 years."* Keep it warm
and concrete.

**6. How we tested it** (credibility page)
- Render `engine_metrics` grouped by `group` (performance / significance / product)
  as stat cards.
- Render `research_log` as an accordion/timeline of the 12 findings; colour the
  `verdict` chips: `survived`=green, `dead`=grey, `artifact`=amber. Lead with the
  **negative-control** story: the original engine FAILED the fake-data test; this
  category-neutral one PASSES it.
- A small bar chart of `category_summary.selection_edge_pct` where present,
  captioned "Skill concentrates where funds differ most (small-cap > large-cap)."
- Optionally note the `validation` snapshot exists (2022, gradable) — this is the
  only place it may be mentioned; never use it in the selection flow.

### Copy to use (verbatim — carefully honest, do not embellish)

- **Hero pitch:** "We can't tell you which *type* of fund will win. But within a
  category, we can rank funds better than chance — and buying the top few per
  category beat a fair benchmark by about **2.4% a year, every year we tested**,
  for reasons that survive every honesty check we ran."
- **Quality caption:** "The model's view of this fund *within its own category*.
  Not comparable across categories."
- **Risk caption:** "Pure maths — how bumpy the ride was and how deep its worst
  fall. No prediction involved."
- **Recommended tooltip:** "These 10 funds (top 2 per core category) are the actual
  validated product. Everything else is context to help you understand them."

### Mandatory disclaimer (footer on every page; also a dismissible banner on results & detail)

> "FundLens is an educational research tool, **not investment advice** and not a
> SEBI-registered advisory service. Quality is a model's relative ranking, not a
> prediction of returns. Mutual fund investments are subject to market risks; past
> performance does not guarantee future results. The tested edge is modest
> (~2.4%/yr), based on one market (India, 2013–2025) and may not persist. NAV shown
> is the direct-plan month-end series for trend context only. Consult a registered
> financial advisor before investing."

### Design

Clean, modern, high-trust fintech aesthetic. Light theme, deep-blue/teal primary,
a **green = Quality / amber = Risk** accent system used consistently. Generous
whitespace, rounded cards, soft shadows. **Mobile-first** (many Indian retail users
are on phones): the wizard and cards must feel great on a small screen. Accessible:
strong contrast, keyboard navigation, ARIA labels on gauges and sliders. Use
Recharts for the gauges, the Quality×Risk scatter, the NAV sparkline, and the
category-edge bar chart. Cache Supabase reads (data is static between yearly
refreshes) and load `fund_detail`/`fund_nav`/`fund_managers` only on click.

Deliver a working app: Supabase client wired up, the 3-step wizard with the 2-D
Quality×Risk view + sliders, the browse table, the on-click fund detail (facts +
NAV sparkline + managers + reasons, **no holdings**), and the two explainer pages.

---

## Notes for whoever runs this (not part of the prompt)

- **Read-only site.** RLS public-read policies are set by `push_to_supabase.py` /
  `schema.sql`. Re-run the ETL after each yearly re-score (`score_live.py`) to
  refresh — no redeploy needed.
- **`snapshot`:** `"live"` = the 2025 buy-now list (381 funds) — the whole retail
  flow. `"validation"` = 2022 gradable back-test (275) — credibility page only.
- **Holdings are intentionally excluded** from the UI (partial coverage), but the
  `fund_holdings` table is still populated and kept in Supabase for a future
  release once coverage improves. If you later want to show it, gate the section on
  `fund_detail.has_holdings = true`.
- **Keep the honesty.** The entire value of this project is that it *doesn't*
  overclaim. A demo promising guaranteed returns would misrepresent the research
  and the disclaimer.
