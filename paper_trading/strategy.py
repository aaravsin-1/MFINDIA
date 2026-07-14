"""
strategy.py -- turns an as-of date into a target portfolio using the validated,
category-neutral model. This is the same scoring logic as ../score_live.py, exposed
as a function the paper-trade engine calls at each rebalance.

Returns:
  * `ranked`  : per-core-category funds scored & sorted (used for top-2 + top-4 buffer)
  * `benchmark_ids` : every scored core-category fund (the category-matched benchmark)
"""
import joblib
import lightgbm as lgb
import pandas as pd
import config
from lib import FEATURES
from prepare_features_live import build_features


def load_or_train_model():
    """Load model_live.pkl; if absent, train it on all labeled cohorts (2013-2022)."""
    if config.MODEL_PATH.exists():
        return joblib.load(config.MODEL_PATH)
    df = pd.read_csv(config.DATASET_PATH)
    model = lgb.LGBMRegressor(random_state=42, n_estimators=50, max_depth=3, verbose=-1)
    model.fit(df[FEATURES], df['fwd_alpha'])
    joblib.dump(model, config.MODEL_PATH)
    return model


def score_asof(engine, model, as_of):
    """Score the live universe as-of `as_of`. Returns (ranked_df, benchmark_ids).

    ranked_df has one row per fund in a core category with columns:
        scheme_id, scheme_name, category_name, score
    sorted by score descending within category.
    """
    feats = build_features(engine, as_of=as_of)
    feats = feats[feats['category_name'].isin(config.CORE_CATS)].copy()
    if feats.empty:
        return feats, []
    feats['score'] = model.predict(feats[FEATURES])
    feats = feats.sort_values(['category_name', 'score'], ascending=[True, False]).reset_index(drop=True)
    benchmark_ids = feats['scheme_id'].astype(int).tolist()
    return feats, benchmark_ids


def target_top2(ranked_df):
    """The clean target (ignoring buffer/holdings): top-2 per core category."""
    picks = []
    for cat in config.CORE_CATS:
        sub = ranked_df[ranked_df['category_name'] == cat].head(config.STRATEGY_PER_CAT)
        picks += sub['scheme_id'].astype(int).tolist()
    return picks
