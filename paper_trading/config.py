"""
config.py -- paper trading system configuration and path/bootstrapping.

Importing this module also puts RESULTS_PROJECT on sys.path so the paper trader can
reuse the validated code (lib, prepare_features_live, model_live.pkl).
"""
import os
import sys
from pathlib import Path

# ---- paths ----
PT_DIR = Path(__file__).resolve().parent                 # .../RESULTS_PROJECT/paper_trading
RESULTS_DIR = PT_DIR.parent                               # .../RESULTS_PROJECT
# Ingestion tooling now lives INSIDE the project (data_pipeline/) so RESULTS_PROJECT is
# self-contained and portable — nothing points at the external KOTAK-TASK parent.
PIPELINE_DIR = RESULTS_DIR / "data_pipeline"             # scrapers/parsers/db copies
ROOT_DIR = PIPELINE_DIR / "scrapers"                     # daily_updater.py, ingest_managers.py live here
SCRAPER_DIR = PIPELINE_DIR / "scrapers" / "scraper"      # load_navall.py etc.
ENV_PATH = RESULTS_DIR / ".env"                          # DB credentials (RESULTS_PROJECT/.env)
MODEL_PATH = RESULTS_DIR / "data" / "model_live.pkl"
DATASET_PATH = RESULTS_DIR / "data" / "ml_dataset.csv"

DB_PATH = PT_DIR / "paper_trading.db"                     # SQLite paper-account state
LOG_DIR = PT_DIR / "logs"
REPORT_DIR = PT_DIR / "reports"

# make the code package importable (lib.py, prepare_features_live.py, etc.)
if str(RESULTS_DIR / "src") not in sys.path:
    sys.path.insert(0, str(RESULTS_DIR / "src"))

for d in (LOG_DIR, REPORT_DIR):
    d.mkdir(exist_ok=True)

# ---- strategy parameters (mirror the validated category-neutral construction) ----
START_CAPITAL = 1_000_000.0            # notional Rs 10 lakh
CORE_CATS = ['Large Cap Fund', 'Mid Cap Fund', 'Small Cap Fund', 'Flexi Cap Fund', 'ELSS']
STRATEGY_PER_CAT = 2                    # top-2 per core category  -> 10-fund portfolio
BUFFER_K = 4                            # hold a fund until it drops out of category top-4
MIN_HOLD_DAYS = 365                     # never sell under 12 months (LTCG / exit-load rule)
REBALANCE_INTERVAL_DAYS = 365          # annual rebalance cadence

# books tracked in the same account for a fair comparison
BOOK_STRATEGY = "strategy"             # the 10-fund category-neutral portfolio
BOOK_BENCHMARK = "benchmark"           # equal-weight basket of ALL core-category funds

# ---- DB credentials helper ----
def load_env():
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH)


def get_engine():
    """SQLAlchemy engine for the postgres market-data DB (reuses lib with abs env path)."""
    from lib import get_engine as _ge
    return _ge(env_path=str(ENV_PATH))


def get_dsn():
    """libpq DSN string for the scraper (load_navall.py)."""
    load_env()
    return (f"dbname={os.getenv('DB_NAME','amfi_data')} user={os.getenv('DB_USER','postgres')} "
            f"host={os.getenv('DB_HOST','localhost')} port={os.getenv('DB_PORT','5432')} "
            f"password={os.getenv('DB_PASSWORD')}")
