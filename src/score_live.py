"""
score_live.py  (RESULTS_PROJECT)

Produce a CURRENT, actionable fund list for an investor putting money in today and
holding ~3 years -- as opposed to manager_quality_screener.py, which scores the
2022 *validation* snapshot (the last year whose 3-yr outcome can be graded).

Pipeline:
  1. Train a PRODUCTION model on ALL labeled cohorts in ml_dataset.csv (2013-2022).
     (train_model.py deliberately trains on <2022 to keep 2022 out-of-sample for
     validation; for a live deployment we want every labeled year, so we retrain.)
  2. Build a feature-only snapshot for the chosen as-of year (default: latest
     complete Dec year-end available in the DB) via prepare_features_live.
  3. Apply the exact screener logic (within-category Quality, top-2/category
     Recommended set, Risk band, SHAP "Why", tie-free Rank).
  4. Write fund_screener_results_<year>.csv.

Usage:
    python score_live.py            # auto-detect latest complete year-end
    python score_live.py 2025       # force a specific as-of year
"""
import sys
import numpy as np
import pandas as pd
import lightgbm as lgb
import joblib
import shap
import warnings
from lib import DATA, OUTPUTS, ASSETS, ROOT, FEATURES, get_engine
from prepare_features_live import build_features
from manager_quality_screener import (
    translate_shap, risk_category, holding_period, CORE_CATS,
)

warnings.filterwarnings('ignore')


def latest_complete_year(engine):
    """Newest year Y for which a {Y}-12-31 monthly NAV exists in the DB."""
    mx = pd.read_sql("SELECT MAX(month_end) AS mx FROM plan_nav_monthly", engine).iloc[0, 0]
    mx = pd.to_datetime(mx)
    # if we're past year-end use this year, else the prior year-end is the last complete one
    return mx.year if (mx.month == 12 and mx.day >= 31) else mx.year - 1


def train_live_model():
    df = pd.read_csv(DATA / 'ml_dataset.csv')
    print(f"Training live model on ALL {len(df)} labeled fund-cohorts "
          f"({int(df['cohort'].min())}-{int(df['cohort'].max())})...")
    model = lgb.LGBMRegressor(random_state=42, n_estimators=50, max_depth=3, verbose=-1)
    model.fit(df[FEATURES], df['fwd_alpha'])
    joblib.dump(model, DATA / 'model_live.pkl')
    return model


def main():
    engine = get_engine()
    eval_year = int(sys.argv[1]) if len(sys.argv) > 1 else latest_complete_year(engine)

    model = train_live_model()

    print(f"Building live feature snapshot as-of {eval_year}-12-31 "
          f"(trailing 3Y from {eval_year-3}-12-31)...")
    df = build_features(engine, eval_year)
    if df.empty:
        print(f"No funds with sufficient history at {eval_year}-12-31. Aborting.")
        return

    # ---- QUALITY: within-category percentile of the model score ----
    df['ml_score'] = model.predict(df[FEATURES])
    df['Quality'] = (df.groupby('category_name')['ml_score'].rank(pct=True) * 100).round(0).astype(int)

    # ---- Recommended = validated strategy (top-2 per core category by raw score) ----
    df['Recommended'] = 'No'
    for cat in CORE_CATS:
        idx = df[df['category_name'] == cat].sort_values('ml_score', ascending=False).head(2).index
        df.loc[idx, 'Recommended'] = 'Yes'

    # ---- RISK: normalised trailing volatility + max drawdown ----
    z_vol = (df['hist_volatility'] - df['hist_volatility'].mean()) / df['hist_volatility'].std()
    z_dd = (-df['max_drawdown'] - (-df['max_drawdown']).mean()) / (-df['max_drawdown']).std()
    raw_risk = (z_vol + z_dd) / 2
    clipped = np.clip(raw_risk, -2.0, 3.0)
    df['Risk'] = ((clipped + 2.0) / 5.0 * 100).round(0).astype(int)
    df['RiskBand'] = df['Risk'].apply(risk_category)
    df['Expected Holding Period'] = df['RiskBand'].apply(holding_period)

    # ---- SHAP "Why" ----
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(df[FEATURES])
    reasons = []
    for i in range(len(df)):
        sv = shap_values[i]
        impacts = sorted([(FEATURES[j], sv[j]) for j in range(len(FEATURES))], key=lambda x: abs(x[1]), reverse=True)
        r = []
        for feat, val in impacts:
            msg = translate_shap(feat, val)
            if msg:
                r.append(msg)
            if len(r) >= 2:
                break
        reasons.append(" | ".join(r))
    df['Why'] = reasons
    df['Fund'] = df['scheme_name']

    # ---- RANK: stable, no ties (recommended first, then score) ----
    df = df.sort_values(['Recommended', 'ml_score'], ascending=[False, False]).reset_index(drop=True)
    df['Rank'] = np.arange(1, len(df) + 1)

    out_cols = ['Rank', 'Fund', 'Category', 'Quality', 'Risk', 'RiskBand',
                'Recommended', 'Expected Holding Period', 'Why']
    out = df.rename(columns={'category_name': 'Category'})[out_cols]
    fname = f'fund_screener_results_{eval_year}.csv'
    out.to_csv(OUTPUTS / fname, index=False)

    print("=" * 68)
    print(f"LIVE SCREENER - as-of {eval_year}-12-31  (for investors buying now, ~3yr hold)")
    print("Quality = within-category percentile | Recommended = validated top-2/category")
    print("=" * 68)
    rec = out[out['Recommended'] == 'Yes']
    print(f"\nRECOMMENDED PORTFOLIO (category-neutral, {len(rec)} funds):")
    for _, r in rec.iterrows():
        print(f"  {r['Category']:<16} | Q:{r['Quality']:>3} R:{r['Risk']:>3} ({r['RiskBand']:<12}) | {r['Fund']}")
    print(f"\nFull universe ({len(out)} funds) saved to {fname}")


if __name__ == '__main__':
    main()
