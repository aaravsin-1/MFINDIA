# data_pipeline/

The data-engineering stack that built the `amfi_data` database behind this project.
Kept here so RESULTS_PROJECT is a self-contained record of **how the data was produced** —
but the contents are **git-ignored** (heavy tooling + ~9.6 GB of raw data). The ML analysis
itself does not need any of this; it runs off `../data/ml_dataset.csv`.

## Layout

| Folder | What it is |
|---|---|
| `scrapers/` | AMFI ingestion — daily NAV, TER, AUM, tracking data (`scraper/`, `amfi_scrapers/`), plus the scheme/manager loaders (`daily_updater.py`, `ingest_managers.py`, `ingest_schemes_data.py`, `insert_unmatched_schemes.py`, `backfill.py`). Also `rupeevest/` — the RupeeVest portfolio scraper (**proprietary core tech, not open-sourced**). |
| `parsers/` | Portfolio-document extraction — PDF/Excel parsers (`pdf_excel_parser/`), `universal_parser.py`, `aggregate_portfolios.py`, `convert_xls.py`, `batch_extract.py`, `run_pipeline.py`. |
| `omnimodel/` | The ML model used to **optimise the parsers** — classifies/audits parser rule disagreements (`ml_classifier.py`, `ml_audit_js_rules.py`, `openrouter_labeler.py`). |
| `grabber/` | The custom Playwright portfolio-disclosure grabber (`grabber/`, `grabber_latest/`, `grabber_exports/`, `m_h.ts` — the Morningstar harvester, the actual scraper). |
| `morningstar/` | Morningstar holdings/ratings ingestion (`ingest_morningstar.py`) and its data (`morningstar_clean/`, `morningstar_out/`, `morningstar_profile/`). |
| `raw_data/` | The raw scraped corpus: `z_files_list/` (4.2 GB), `parsed_portfolios/` (2.4 GB), `historical_portfolios/` (957 MB), `downloads/`. |

## Flow (roughly)

```
scrapers/ + grabber/  ──►  raw_data/  ──►  parsers/  ──►  amfi_data DB  ──►  ../src/prepare_features.py  ──►  ../data/ml_dataset.csv
morningstar/          ──►  amfi_data DB (holdings, ratings) ──┘
```

The annual refresh (`../paper_trading/annual_maintenance.py`) historically called
`daily_updater.py` and `ingest_managers.py` from here to top up the database before retraining.

> Everything under this folder except this README is git-ignored (see `../.gitignore`).
> These are copies; the originals still live in the root `KOTAK-TASK/` monorepo.
