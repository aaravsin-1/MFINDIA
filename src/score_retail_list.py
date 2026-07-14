"""
score_retail_list.py  (RESULTS_PROJECT)

The RETAIL deliverable -- a full "rate every fund" within-category list, as opposed to
score_live.py which produces the concentrated top-2/category STRATEGY portfolio.

Why a separate product & model (see tests/test_list_quality.py, tests/README.md §9):
  * The STRATEGY list consumes only the TOP-2 of each category, so it is best served by
    the validated RAW-feature model (+2.37%/yr, survives every null).
  * A RETAIL list uses the WHOLE within-category ranking, so overall ranking quality
    matters. There, DE-TILTED features (V2 = rank each feature within cohort x category)
    give a materially wider, monotone, bucket-count-robust quintile spread
    (~+13pp top-vs-bottom vs ~+8pp for RAW), positive in all 7 cohorts. So the retail
    list is scored with the V2 model.

Honest framing baked into the output:
  * Funds are grouped into within-category TIERS (Top / Above avg / Average / Below avg
    / Bottom), NOT presented as a precise 1-N ranking -- the fund-level ordering is
    noisy (Spearman ~0.15); only the tier-level tilt is reliable.
  * The Risk band + expected holding period overlay is kept (suitability, not just alpha).
  * A StrategyPick flag cross-references the validated top-2/category portfolio (scored
    by the RAW model) so the two products stay connected.

Usage:
    python score_retail_list.py            # auto-detect latest complete year-end
    python score_retail_list.py 2025       # force a specific as-of year
"""
import sys
import numpy as np
import pandas as pd
import lightgbm as lgb
import shap
import warnings
from lib import DATA, OUTPUTS, ASSETS, ROOT, FEATURES, get_engine
from prepare_features_live import build_features
from manager_quality_screener import translate_shap, risk_category, holding_period, CORE_CATS
from score_live import latest_complete_year

warnings.filterwarnings('ignore')

ENCODING = 'V2'   # 'V2' = within cohort x category (retail default); 'V1' = within cohort


def encode(df):
    """De-tilt: replace each feature by its percentile rank within cohort x category.
    Works for training (many cohorts) and a single live snapshot (one cohort) alike."""
    if ENCODING == 'RAW':
        return df
    out = df.copy()
    by = ['cohort', 'category_name'] if ENCODING == 'V2' else 'cohort'
    for c in FEATURES:
        out[c] = df.groupby(by)[c].rank(pct=True)
    return out


def tier(pct):
    """Within-category percentile (0-100) -> honest tier band (not a precise rank)."""
    if pct >= 80: return '1. Top Tier'
    if pct >= 60: return '2. Above Average'
    if pct >= 40: return '3. Average'
    if pct >= 20: return '4. Below Average'
    return '5. Bottom Tier'


def train(df, encoded):
    """Train an all-cohorts production model; `encoded`=True applies the V2 de-tilt."""
    d = encode(df) if encoded else df
    m = lgb.LGBMRegressor(random_state=42, n_estimators=50, max_depth=3, verbose=-1)
    m.fit(d[FEATURES], d['fwd_alpha'])
    return m


def main():
    engine = get_engine()
    eval_year = int(sys.argv[1]) if len(sys.argv) > 1 else latest_complete_year(engine)

    train_df = pd.read_csv(DATA / 'ml_dataset.csv')
    print(f"Training retail (de-tilted {ENCODING}) + strategy (RAW) models on "
          f"{len(train_df)} labeled fund-cohorts ({int(train_df.cohort.min())}-"
          f"{int(train_df.cohort.max())})...")
    retail_model = train(train_df, encoded=True)   # V2 -> retail ranking
    raw_model = train(train_df, encoded=False)     # RAW -> strategy top-2 cross-reference

    print(f"Building live snapshot as-of {eval_year}-12-31 (trailing 3Y)...")
    df = build_features(engine, eval_year)
    if df.empty:
        print(f"No funds with sufficient history at {eval_year}-12-31. Aborting.")
        return
    df['cohort'] = eval_year  # single-cohort snapshot; enables the within-cat encode

    # ---- RETAIL QUALITY: within-category percentile + tier from the de-tilted model ----
    df_enc = encode(df)
    df['retail_score'] = retail_model.predict(df_enc[FEATURES])
    df['Quality'] = (df.groupby('category_name')['retail_score'].rank(pct=True) * 100).round(0).astype(int)
    df['Tier'] = df['Quality'].apply(tier)

    # ---- STRATEGY cross-reference: RAW model's validated top-2 per core category ----
    df['raw_score'] = raw_model.predict(df[FEATURES])
    df['StrategyPick'] = 'No'
    for cat in CORE_CATS:
        idx = df[df.category_name == cat].sort_values('raw_score', ascending=False).head(2).index
        df.loc[idx, 'StrategyPick'] = 'Yes'

    # ---- RISK overlay (same engine as the screener): trailing vol + max drawdown ----
    z_vol = (df['hist_volatility'] - df['hist_volatility'].mean()) / df['hist_volatility'].std()
    z_dd = (-df['max_drawdown'] - (-df['max_drawdown']).mean()) / (-df['max_drawdown']).std()
    clipped = np.clip((z_vol + z_dd) / 2, -2.0, 3.0)
    df['Risk'] = ((clipped + 2.0) / 5.0 * 100).round(0).astype(int)
    df['RiskBand'] = df['Risk'].apply(risk_category)
    df['Expected Holding Period'] = df['RiskBand'].apply(holding_period)

    # ---- SHAP "Why" from the retail model (attribution on the ranked features) ----
    explainer = shap.TreeExplainer(retail_model)
    shap_values = explainer.shap_values(df_enc[FEATURES])
    reasons = []
    for i in range(len(df)):
        sv = shap_values[i]
        impacts = sorted([(FEATURES[j], sv[j]) for j in range(len(FEATURES))],
                         key=lambda x: abs(x[1]), reverse=True)
        r = [m for m in (translate_shap(f, v) for f, v in impacts) if m][:2]
        reasons.append(" | ".join(r))
    df['Why'] = reasons
    df['Fund'] = df['scheme_name']

    # ---- within-category rank (retail is a within-category product) ----
    df = df.sort_values(['category_name', 'Quality'], ascending=[True, False]).reset_index(drop=True)
    df['CategoryRank'] = df.groupby('category_name').cumcount() + 1

    out_cols = ['category_name', 'CategoryRank', 'Fund', 'Tier', 'Quality', 'Risk',
                'RiskBand', 'Expected Holding Period', 'StrategyPick', 'Why']
    out = df[out_cols].rename(columns={'category_name': 'Category'})
    fname = f'retail_fund_list_{eval_year}.csv'
    out.to_csv(OUTPUTS / fname, index=False)

    # ---- console summary ----
    print("=" * 74)
    print(f"RETAIL FUND LIST - as-of {eval_year}-12-31  (rate-every-fund, within category)")
    print(f"Model: de-tilted ({ENCODING}) within-category | Tiers, not precise ranks")
    print("=" * 74)
    print(f"\n{len(out)} funds across {out['Category'].nunique()} categories.")
    print("\nTier distribution (within-category):")
    for tname, n in out['Tier'].value_counts().sort_index().items():
        print(f"  {tname:<18} {n:>4}")
    # show the Top Tier of each core category
    print("\nTop-Tier funds in core categories (also flagged if in the strategy top-2):")
    for cat in CORE_CATS:
        top = out[(out.Category == cat) & (out.Tier == '1. Top Tier')].head(3)
        if top.empty:
            continue
        print(f"\n  {cat}:")
        for _, r in top.iterrows():
            star = " *STRATEGY PICK*" if r['StrategyPick'] == 'Yes' else ""
            print(f"    Q:{r['Quality']:>3} R:{r['Risk']:>3} ({r['RiskBand']:<12}) {r['Fund']}{star}")
    print(f"\nFull list ({len(out)} funds) saved to {fname}")
    print("\nNOTE: tiers reflect a modest statistical tilt (quintile spread ~+13pp/3y);")
    print("fund-level ordering within a tier is noisy -- use tiers + Risk band, not the")
    print("exact CategoryRank, for decisions.")


if __name__ == '__main__':
    main()
