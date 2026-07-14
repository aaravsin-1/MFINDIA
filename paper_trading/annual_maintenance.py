"""
annual_maintenance.py -- the once-a-year data refresh + model retrain.

The daily cron only needs NAVs. The MODEL additionally needs monthly-NAV rollup, AUM,
TER and manager data, and gains a new labelable cohort at most once a year. Run this
each January (or whenever `--check` reports a retrain is due).

Modes (combine as needed):
    python annual_maintenance.py                     # --check (default, non-destructive)
    python annual_maintenance.py --refresh-data      # pull fresh source data into postgres
    python annual_maintenance.py --retrain           # rebuild ml_dataset + model_live.pkl
    python annual_maintenance.py --refresh-data --retrain

--refresh-data runs, in order:
    1. ../../daily_updater.py         -> daily NAV + TER + AUM (+ tracking)
    2. rebuild plan_nav_monthly       -> the month-end rollup the model reads (from `nav`)
    3. ../../ingest_managers.py       -> manager tenure from the Morningstar CSVs

NOTE ON MORNINGSTAR: manager data is NOT auto-scraped here. ingest_managers.py rebuilds
`scheme_manager` from morningstar_clean/*.csv, which are produced by the `m_h.ts`
harvester. To capture manager *changes* you must re-run m_h.ts first (it needs live
Morningstar auth headers); tenure of unchanged managers advances automatically with the
as-of date, so a yearly re-harvest is plenty.
"""
import argparse
import subprocess
import sys
import pandas as pd

import config
import maintenance

# rollup that materializes plan_nav_monthly from daily `nav` (mirrors amfi-database/
# build_returns.sql, stage 1). Growth-only, month-end snapshot, survivorship-safe.
REBUILD_MONTHLY_SQL = """
DROP TABLE IF EXISTS plan_nav_monthly CASCADE;
CREATE TABLE plan_nav_monthly AS
SELECT DISTINCT ON (n.scheme_plan_id, date_trunc('month', n.nav_date))
       n.scheme_plan_id,
       (date_trunc('month', n.nav_date) + INTERVAL '1 month - 1 day')::date AS month_end,
       n.nav_date AS actual_nav_date,
       n.nav
FROM   nav n
JOIN   scheme_plan sp ON sp.scheme_plan_id = n.scheme_plan_id
WHERE  sp.option_type = 'growth' AND n.nav > 0
ORDER BY n.scheme_plan_id, date_trunc('month', n.nav_date), n.nav_date DESC;
ALTER TABLE plan_nav_monthly ADD PRIMARY KEY (scheme_plan_id, month_end);
CREATE INDEX idx_pnm_month ON plan_nav_monthly (month_end);
"""


def _run(script, args=None, cwd=None):
    cmd = [sys.executable, str(script)] + (args or [])
    print(f"\n>>> {script} {' '.join(args or [])}")
    r = subprocess.run(cmd, cwd=str(cwd) if cwd else None)
    if r.returncode != 0:
        print(f"[warn] {getattr(script,'name',script)} exited {r.returncode}")
    return r.returncode


def refresh_data():
    print("\n### REFRESH DATA ###")
    # 1. NAV + TER + AUM via the project's own daily orchestrator
    _run(config.ROOT_DIR / "daily_updater.py", cwd=config.ROOT_DIR)
    # 2. rebuild the monthly-NAV rollup the model reads
    print("\n>>> rebuilding plan_nav_monthly (month-end rollup from daily nav) ...")
    from sqlalchemy import text
    eng = config.get_engine()
    with eng.begin() as con:
        for stmt in filter(str.strip, REBUILD_MONTHLY_SQL.split(";")):
            con.execute(text(stmt))
    print("    plan_nav_monthly rebuilt.")
    # 3. managers from the Morningstar CSVs
    _run(config.ROOT_DIR / "ingest_managers.py", cwd=config.ROOT_DIR)
    print("\n[note] scheme_manager reflects the current morningstar_clean CSVs. Re-run "
          "m_h.ts first if you need to catch manager CHANGES.")


def retrain():
    print("\n### RETRAIN ###")
    import prepare_features as pf
    from lib import FEATURES
    import lightgbm as lgb
    import joblib

    eng = config.get_engine()
    st = maintenance.retrain_status(eng)
    max_lab = st['max_labelable']
    if max_lab is None:
        print("[error] cannot determine labelable cohort; aborting retrain.")
        return
    cohorts = list(range(2013, max_lab + 1))
    print(f"Rebuilding ml_dataset.csv for cohorts {cohorts[0]}-{cohorts[-1]} ...")
    df = pf.get_data(eng, cohorts)
    df['ter'] = pd.to_numeric(df['ter'], errors='coerce')
    df[FEATURES] = df[FEATURES].fillna(df[FEATURES].median())
    df.to_csv(config.DATASET_PATH, index=False)
    print(f"  wrote {config.DATASET_PATH.name}: {len(df)} rows, "
          f"cohorts {int(df['cohort'].min())}-{int(df['cohort'].max())}")

    print("Retraining model_live.pkl on ALL labeled cohorts ...")
    model = lgb.LGBMRegressor(random_state=42, n_estimators=50, max_depth=3, verbose=-1)
    model.fit(df[FEATURES], df['fwd_alpha'])
    joblib.dump(model, config.MODEL_PATH)
    print(f"  saved {config.MODEL_PATH.name}. Next rebalance will score on the refreshed model.")


def refresh_lists():
    """Regenerate BOTH investor deliverables from the refreshed dataset/model:
       the STRATEGY list (score_live.py, top-2/category, RAW model) and the RETAIL
       list (score_retail_list.py, within-category tiers, de-tilted model). Run after
       --retrain so the published lists reflect the newest labelable cohort."""
    print("\n### REFRESH LISTS ###")
    _run(config.RESULTS_DIR / "src" / "score_live.py", cwd=config.RESULTS_DIR)
    _run(config.RESULTS_DIR / "src" / "score_retail_list.py", cwd=config.RESULTS_DIR)
    verify_retail_premise()


def verify_retail_premise():
    """Re-validate the RETAIL product's premise on the refreshed data: does the
       de-tilted model still give a wider, bucket-robust within-category spread than
       RAW? test_list_quality.py exits 0 if yes, 1 if the premise no longer holds."""
    print("\n>>> re-validating retail-list premise (tests/test_list_quality.py) ...")
    rc = subprocess.run([sys.executable, str(config.RESULTS_DIR / "tests" / "test_list_quality.py")],
                        cwd=str(config.RESULTS_DIR)).returncode
    if rc == 0:
        print("[ok] retail premise re-validated: de-tilted list still beats RAW & is bucket-robust.")
    else:
        print("[WARN] retail premise NOT re-validated on refreshed data. The de-tilted retail "
              "list no longer clearly beats RAW -- review before publishing it; the RAW strategy "
              "list is unaffected.")
    return rc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh-data", action="store_true", help="pull fresh NAV/TER/AUM/monthly/managers")
    ap.add_argument("--retrain", action="store_true", help="rebuild ml_dataset + model_live.pkl")
    ap.add_argument("--refresh-lists", action="store_true",
                    help="regenerate strategy + retail deliverables (auto-runs after --retrain)")
    args = ap.parse_args()

    eng = config.get_engine()
    print("Current status:")
    maintenance.panel(eng)

    if not (args.refresh_data or args.retrain or args.refresh_lists):
        print("\n(--check only; nothing changed.) Use --refresh-data, --retrain and/or "
              "--refresh-lists to act.")
        return
    if args.refresh_data:
        refresh_data()
    if args.retrain:
        retrain()
    # regenerate the published lists whenever the model/dataset changed, or on request
    if args.retrain or args.refresh_lists:
        refresh_lists()

    print("\nStatus after maintenance:")
    maintenance.panel(config.get_engine())


if __name__ == "__main__":
    main()
