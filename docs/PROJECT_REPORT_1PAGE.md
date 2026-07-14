# Project Report (1-Page) — ML Fund-Selection Engine

**For:** Reporting Manager  **Status:** Complete — validated; deliverables shipped; live forward test running
**Basis:** ~250 Indian active-equity funds/yr, 2016–2022 walk-forward; all figures reproduced against the `amfi_data` DB

---

### Bottom line
We built and honestly validated an ML engine that ranks funds **within their category**. As a
category-neutral portfolio (top-2 funds per category), it beats a like-for-like benchmark by
**+2.4%/yr, positive in all 7 test years** (Newey-West p ≈ 0.001), of which **+1.7%/yr is genuine
skill** after adjusting for size/momentum. The prototype's original "beats the market" claim
**failed** validation and was corrected. The surviving edge is real but **modest, relative, and
concentrated in small/mid-cap** — a decision-support tool, not market-beating alpha.

### Key results
| Metric | Result |
|---|---|
| Edge vs category-matched benchmark | **+2.37% / yr**, **7/7 cohorts** |
| Significance (overlap-corrected) | Newey-West t = 3.30, p = 0.001; bootstrap CI [+1.37%, +3.36%] |
| Factor-adjusted alpha (skill after size/momentum) | **+1.72% / yr (t = 4.26)** |
| Negative control | Original claim **fails** (p = 0.125); category-neutral **passes** (p = 0.000) |
| Where skill lives | Small-cap +3.4%, large-cap +0.6% |
| After tax (hold > 12 months) | ~**+2.6% net** |

*Context: the ~20% headline CAGR is mostly the bull market (benchmark ~17.8%); our contribution is the ~2.4% on top.*

### Assurance
Validated adversarially: passes a scrambled-data negative control, a 6/6 red-team battery, harder
(cap-weighted + factor-adjusted) benchmarks, and a survivorship check. Five attempts to enlarge the
edge were tested and rejected — evidence the simple model is near-optimal on available data.

### Deliverables
Strategy list (10-fund portfolio) · retail tiered fund list · Quality×Risk screener · live
paper-trading control · one-command annual maintenance.

### Top risks
1. **Relative, not absolute** — does not protect against a falling market.
2. **One market / one bull era** — needs forward + external confirmation (paper trade is running).
3. **Modest & tax-sensitive** — the >12-month hold rule is mandatory.

### Recommendation
Adopt as a **within-category, category-neutral decision-support screener**. Do not market as
market-beating. Next: continue the live paper trade (review quarterly), and close the holdings
data-linkage gap (highest-potential unexplored signal).

*Full detail: `PROJECT_REPORT.md` · results: `STRATEGY_AND_RESULTS.md` · all tests: `VALIDATION_CATALOG.md`.*
