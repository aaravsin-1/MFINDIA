"""
manager_quality_screener.py  (RESULTS_PROJECT)

Scores the latest (2022) fund snapshot with the corrected, out-of-sample model.

Fixes / changes vs. the original:
  * QUALITY is now a WITHIN-CATEGORY percentile of the model score. The validation
    (strengthen_edge.py) showed the model's skill is within-category ranking, not
    cross-category return prediction -- so quality is only meaningful relative to
    peers in the same category. A global 0-100 normalisation (as in the original)
    invited apples-to-oranges comparisons.
  * Adds a 'Recommended' flag = the validated strategy (top-2 per core category),
    the construction that actually passed the negative control.
  * RANK no longer ties: it is a stable dense rank on the continuous score, not on
    the rounded integer Quality (the original produced duplicate "Rank 5"s).
  * Uses the retrained model.pkl and the de-poisoned ml_dataset.csv.
"""
import numpy as np
import pandas as pd
import joblib
import shap
import warnings
from lib import DATA, OUTPUTS, ASSETS, ROOT, FEATURES

warnings.filterwarnings('ignore')

SNAPSHOT_COHORT = 2022
CORE_CATS = ['Large Cap Fund', 'Mid Cap Fund', 'Small Cap Fund', 'Flexi Cap Fund', 'ELSS']


def translate_shap(feature, v):
    if v > 0.001:
        return {
            'max_tenure_years': "[+] Veteran manager with exceptional tenure",
            'hist_return': "[+] Strong past momentum",
            'hist_volatility': "[+] Stable risk profile",
            'aum_percentile': "[+] Favourable AUM / capacity",
            'hist_hit_rate': "[+] Strong long-term consistency",
            'num_managers': "[+] Supported by a management team",
            'ter': "[+] Cost efficient structure",
            'max_drawdown': "[+] Excellent downside protection",
        }.get(feature, f"[+] Favourable {feature}")
    if v < -0.001:
        return {
            'max_tenure_years': "[-] Relatively inexperienced manager",
            'hist_return': "[-] Lagging past returns",
            'hist_volatility': "[-] Elevated trailing volatility",
            'aum_percentile': "[-] Fund size acting as a drag",
            'hist_hit_rate': "[-] Inconsistent hit rate",
            'num_managers': "[-] Solo management risk",
            'ter': "[-] Expensive TER",
            'max_drawdown': "[-] Severe historical drawdown",
        }.get(feature, f"[-] Unfavourable {feature}")
    return None


def risk_category(score):
    return "Conservative" if score <= 30 else ("Balanced" if score <= 60 else "Aggressive")


def holding_period(cat):
    return {"Conservative": "5+ years", "Balanced": "3-5 years", "Aggressive": "1-3 years"}[cat]


def main():
    df_all = pd.read_csv(DATA / 'ml_dataset.csv')
    df = df_all[df_all['cohort'] == SNAPSHOT_COHORT].copy()
    model = joblib.load(DATA / 'model.pkl')

    # ---- QUALITY ENGINE: within-category percentile of the model score ----
    df['ml_score'] = model.predict(df[FEATURES])
    df['Quality'] = (df.groupby('category_name')['ml_score'].rank(pct=True) * 100).round(0).astype(int)

    # Recommended = validated strategy (top-2 per core category by raw score)
    df['Recommended'] = 'No'
    for cat in CORE_CATS:
        idx = df[df['category_name'] == cat].sort_values('ml_score', ascending=False).head(2).index
        df.loc[idx, 'Recommended'] = 'Yes'

    # ---- RISK ENGINE: normalised trailing volatility + max drawdown ----
    z_vol = (df['hist_volatility'] - df['hist_volatility'].mean()) / df['hist_volatility'].std()
    z_dd = (-df['max_drawdown'] - (-df['max_drawdown']).mean()) / (-df['max_drawdown']).std()
    raw_risk = (z_vol + z_dd) / 2
    clipped = np.clip(raw_risk, -2.0, 3.0)
    df['Risk'] = ((clipped + 2.0) / 5.0 * 100).round(0).astype(int)
    df['RiskBand'] = df['Risk'].apply(risk_category)
    df['Expected Holding Period'] = df['RiskBand'].apply(holding_period)

    # ---- SHAP explanations ----
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

    # ---- RANK: stable, no ties (continuous score, recommended first) ----
    df = df.sort_values(['Recommended', 'ml_score'], ascending=[False, False]).reset_index(drop=True)
    df['Rank'] = np.arange(1, len(df) + 1)

    out_cols = ['Rank', 'Fund', 'Category', 'Quality', 'Risk', 'RiskBand',
                'Recommended', 'Expected Holding Period', 'Why']
    out = df.rename(columns={'category_name': 'Category'})[out_cols]
    out.to_csv(OUTPUTS / 'fund_screener_results.csv', index=False)

    print("=" * 64)
    print(f"MANAGER QUALITY SCREENER — {SNAPSHOT_COHORT} snapshot (out-of-sample)")
    print("Quality = within-category percentile | Recommended = validated top-2/category")
    print("=" * 64)
    rec = out[out['Recommended'] == 'Yes']
    print(f"\nRECOMMENDED PORTFOLIO (category-neutral, {len(rec)} funds):")
    for _, r in rec.iterrows():
        print(f"  {r['Category']:<16} | Q:{r['Quality']:>3} R:{r['Risk']:>3} ({r['RiskBand']:<12}) | {r['Fund']}")
        print(f"       Why: {r['Why']}")
    print(f"\nFull universe ({len(out)} funds) saved to fund_screener_results.csv")


if __name__ == '__main__':
    main()
