# INDEX — Start Here

**Project:** Using Machine Learning to Assist Indian Mutual-Fund Selection
**One line:** An ML engine that ranks Indian active-equity funds *within their category*; a
category-neutral top-2/category portfolio beats a like-for-like benchmark by **+2.4%/yr, 7/7
back-test years** (Newey-West p ≈ 0.001), of which **+1.7%/yr is genuine skill** after factor
adjustment. It does **not** beat the market — it is honest, within-category selection skill.

This file is the map of the folder. For how to *run* things, see **[README.md](docs/README.md)**.

---

## Folder layout

```
RESULTS_PROJECT/
├── INDEX.md                  ← you are here (start map)
├── Fund_Selection_Deck.pptx  ← presentation deck
├── docs/                     ← all write-ups (report, findings, validation catalog, …)
├── src/                      ← core code: pipeline, model, scoring, figure generators, lib.py
├── validation/               ← the QA suite that PROVES the edge (red-team, negative control, factor test, …)
├── data/                     ← ml_dataset.csv + trained models (model.pkl, model_live.pkl)
├── outputs/                  ← generated fund lists (retail list, strategy screener)
├── assets/                   ← generated figures
├── tests/                    ← exploratory experiments + strategy-property tests
├── paper_trading/            ← live forward paper-trade
├── website/                  ← public site (source only)
└── data_pipeline/            ← how the DB was built: scrapers, parsers, grabber, Morningstar,
                                 the DB schema, + ~9.6 GB raw data  (git-ignored; README kept)
```

**How to run:** from this folder, e.g. `python validation/red_team.py` or `python src/make_report_figures.py`.
All scripts resolve their own paths (`data/`, `outputs/`, `assets/`) via `src/lib.py`, so they work
regardless of the current directory. DB-backed scripts need a `.env` (copy `.env.example`).

---

## 1. Read these first (the write-up)

| File | What it is |
|---|---|
| **[PROJECT_REPORT.md](docs/PROJECT_REPORT.md)** | The main decision report (results, assurance, limits, recommendation). |
| [PROJECT_REPORT_1PAGE.md](docs/PROJECT_REPORT_1PAGE.md) | One-page version of the above. |
| [STRATEGY_AND_RESULTS.md](docs/STRATEGY_AND_RESULTS.md) | Full detail of the strategy and every result. |
| [VALIDATION_CATALOG.md](docs/VALIDATION_CATALOG.md) | Index of every validation/experiment run, with pass/fail. |
| **[Fund_Selection_Deck.pptx](Fund_Selection_Deck.pptx)** | 16-slide presentation deck (figures + speaker notes). |

## 2. Deliverables (the actual products)

| File | What it is |
|---|---|
| [retail_fund_list_2025.csv](outputs/retail_fund_list_2025.csv) | The retail product: every fund rated & tiered within its category (live on the website). |
| [fund_screener_results_2025.csv](outputs/fund_screener_results_2025.csv) | The strategy list: full 2025 universe scored, with the top-2/category picks flagged. |
| `website/` | The public site (source only; build artifacts stripped). Live URL is in the report. |
| `paper_trading/` | Live forward paper-trade of the strategy vs a category benchmark. |

## 3. How it was built (pipeline, in run order)

| Script | Role |
|---|---|
| [prepare_features.py](src/prepare_features.py) | Builds `ml_dataset.csv` from the DB (features + target, with the NAV-sanity + trimmed-benchmark fixes). |
| [train_model.py](src/train_model.py) | Trains the production model → `model.pkl`. |
| [lib.py](src/lib.py) | Shared helpers (DB access, portfolio math, the 9-feature list). |
| [manager_quality_screener.py](src/manager_quality_screener.py) | Scores a snapshot → Quality/Risk/SHAP-why. |
| [score_live.py](src/score_live.py) / [score_retail_list.py](src/score_retail_list.py) | Produce the strategy list / retail list for the live snapshot. |

## 4. How it was validated (the evidence)

| Script | What it checks |
|---|---|
| [run_validation.py](validation/run_validation.py) | Walk-forward + the seeded negative control. |
| [strengthen_edge.py](validation/strengthen_edge.py) | Out-of-sample rank IC + the category-neutral construction vs its null. |
| [red_team.py](validation/red_team.py) | The 6-way adversarial battery (size, seed, leave-one-out, jackknife, momentum, random placebo). |
| [test_benchmarks_hard.py](validation/test_benchmarks_hard.py) | Cap-weighted benchmark + factor-adjusted alpha (the +1.72% skill). |
| [test_turnover_tax.py](tests/test_turnover_tax.py) / [test_buffer_rule.py](tests/test_buffer_rule.py) | Tax/turnover and the top-4 buffer rule. |
| `tests/` | Exploratory experiments that were tried and (mostly) rejected — flows, alt targets, LambdaMART, shrinkage, de-tilting, survivorship. See [tests/README.md](tests/README.md). |

## 5. Figures

| File | Role |
|---|---|
| [make_report_figures.py](src/make_report_figures.py) | Regenerates all report figures from the real data/model. |
| [build_deck.py](src/build_deck.py) | Rebuilds `Fund_Selection_Deck.pptx` from the figures. |
| `assets/` | The 11 generated figures (input table, decision tree, importance, IC, mean-reversion, per-cohort alpha, etc.). |

## 6. Data & models

- [ml_dataset.csv](data/ml_dataset.csv) — the 1,841-row training set (2013–2022 cohorts). Self-contained.
- `model.pkl` / `model_live.pkl` — the trained models (back-test / live snapshot).
- [DATABASE.md](docs/DATABASE.md) — full data dictionary for the `amfi_data` source DB (33 tables, ~37M rows) the pipeline builds.

## 7. Supporting / background docs (optional depth)

[FINDINGS.md](docs/FINDINGS.md) (step-by-step before/after evidence) ·
[research_journey.md](docs/research_journey.md) (chronological story) ·
[model_works.md](docs/model_works.md) (how the model works, in depth) ·
[EXPLAINER.md](docs/EXPLAINER.md) / [walkthrough.md](docs/walkthrough.md) / [executive_summary.md](docs/executive_summary.md) /
[RESEARCH_FINDINGS.md](docs/RESEARCH_FINDINGS.md) (earlier/plain-English write-ups) ·
[STRATEGIES.md](docs/STRATEGIES.md) (map of the broader 12-strategy research).

---

## Notes for whoever runs this

- **Secrets:** real `.env` files are git-ignored and were **not** included. Copy `.env.example` →
  `.env` and fill in your own DB/Supabase credentials to run the DB-backed scripts.
- **Reproducibility:** the analysis (`ml_dataset.csv` + `model.pkl`) is self-contained; scripts that
  hit the live database (`prepare_features.py`, `score_live.py`, the validators) need the `amfi_data`
  Postgres DB. All figures and the deck regenerate offline from the CSV/model.
- **Requirements:** Python 3.12 — see [README.md](docs/README.md) for the package list.
