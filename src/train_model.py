"""
train_model.py  (RESULTS_PROJECT)

Trains the production LightGBM ranking model on the corrected ml_dataset.csv.
Trained on all cohorts strictly before 2022 so that scoring the 2022 snapshot in
manager_quality_screener.py remains genuinely out-of-sample.
"""
import pandas as pd
import lightgbm as lgb
import joblib
from lib import DATA, OUTPUTS, ASSETS, ROOT, FEATURES

TRAIN_BEFORE = 2022


def main():
    df = pd.read_csv(DATA / 'ml_dataset.csv')
    train_df = df[df['cohort'] < TRAIN_BEFORE]
    print(f"Training on {len(train_df)} funds (cohorts {int(train_df['cohort'].min())}-{TRAIN_BEFORE-1})...")
    model = lgb.LGBMRegressor(random_state=42, n_estimators=50, max_depth=3, verbose=-1)
    model.fit(train_df[FEATURES], train_df['fwd_alpha'])
    joblib.dump(model, DATA / 'model.pkl')
    print("Saved model.pkl")


if __name__ == '__main__':
    main()
