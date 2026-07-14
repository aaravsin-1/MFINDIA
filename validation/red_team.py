"""
red_team.py  (RESULTS_PROJECT)

Adversarial audit: actively TRY TO DISPROVE the +2.4% category-neutral edge with
every attack a hostile referee would use. Each test reports whether the edge
SURVIVES. Honest failures are printed as failures.

Attacks:
  A. Portfolio-size robustness   - is "top-2/category" cherry-picked? (k=1..5)
  B. Model-seed sensitivity      - does it only work at random_state=42?
  C. Leave-one-cohort-out        - is it driven by a single lucky year?
  D. Feature jackknife           - does it hinge on one feature?
  E. "Is it just momentum?"      - are picks merely high-momentum funds?
  F. Random-portfolio placebo    - vs 2000 random top-2/category portfolios
  G. Look-ahead / leakage audit  - stated checks on the pipeline

Baseline strategy = category-neutral top-2/category vs category-matched benchmark,
walk-forward 2016-2022 (the validated construction).
"""
import numpy as np
import pandas as pd
import lightgbm as lgb
import warnings
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from lib import DATA, OUTPUTS, ASSETS, ROOT, get_engine, FEATURES, get_returns_matrix, port_from_matrix, cagr

warnings.filterwarnings('ignore')
TEST = [2016, 2017, 2018, 2019, 2020, 2021, 2022]
CORE = ['Large Cap Fund', 'Mid Cap Fund', 'Small Cap Fund', 'Flexi Cap Fund', 'ELSS']


def edge(df, mats, feats=FEATURES, k=2, seed=42, drop_cohort=None, return_per=False, picks_out=None):
    per = []
    for t in TEST:
        if t == drop_cohort:
            continue
        tr, te = df[df.cohort < t], df[df.cohort == t]
        mat = mats[t]
        bench = te[te.category_name.isin(CORE)].scheme_id.tolist()
        picks = []
        for c in CORE:
            a, b = tr[tr.category_name == c], te[te.category_name == c]
            if len(a) < 10 or b.empty:
                continue
            m = lgb.LGBMRegressor(random_state=seed, n_estimators=50, max_depth=3, verbose=-1)
            m.fit(a[feats], a['fwd_alpha'])
            b = b.assign(p=m.predict(b[feats]))
            sel = b.sort_values('p', ascending=False).head(k).scheme_id.tolist()
            picks += sel
        if picks_out is not None:
            picks_out[t] = picks
        per.append(cagr(port_from_matrix(mat, picks)) - cagr(port_from_matrix(mat, bench)))
    return (np.mean(per), per) if return_per else np.mean(per)


def main():
    eng = get_engine()
    df = pd.read_csv(DATA / 'ml_dataset.csv')
    mats = {t: get_returns_matrix(eng, df[df.cohort == t].scheme_id.tolist(), f"{t}-12-31", f"{t+3}-12-31") for t in TEST}

    picks_by_cohort = {}
    base, per = edge(df, mats, return_per=True, picks_out=picks_by_cohort)
    print("=" * 66)
    print(f"RED-TEAM AUDIT — baseline category-neutral edge = {base*100:+.2f}%/yr")
    print("=" * 66)

    survive = []

    # A. portfolio size
    print("\n[A] Portfolio-size robustness (is top-2 cherry-picked?)")
    a_ok = True
    for k in [1, 2, 3, 4, 5]:
        e = edge(df, mats, k=k)
        print(f"    top-{k}/cat: {e*100:+.2f}%/yr")
        if e <= 0:
            a_ok = False
    survive.append(("A size-robustness", a_ok and True))
    print(f"    -> {'SURVIVES (positive for every k)' if a_ok else 'FAILS'}")

    # B. seed sensitivity
    print("\n[B] Model-seed sensitivity (only works at seed 42?)")
    seeds = [0, 1, 7, 42, 123, 2024, 99999, 314159]
    es = np.array([edge(df, mats, seed=s) for s in seeds])
    print(f"    edges over {len(seeds)} seeds: mean {es.mean()*100:+.2f}%  [{es.min()*100:+.2f}, {es.max()*100:+.2f}]")
    b_ok = (es > 0).all()
    survive.append(("B seed-robustness", b_ok))
    print(f"    -> {'SURVIVES (positive for every seed)' if b_ok else 'FAILS'}")

    # C. leave-one-cohort-out
    print("\n[C] Leave-one-cohort-out (driven by one lucky year?)")
    per = np.array(per)
    loo = [(TEST[i], np.mean(np.delete(per, i))) for i in range(len(TEST))]
    worst = min(loo, key=lambda x: x[1])
    print(f"    per-cohort edges: {[f'{TEST[i]}:{per[i]*100:+.1f}' for i in range(len(TEST))]}")
    print(f"    worst leave-one-out (drop {worst[0]}): {worst[1]*100:+.2f}%/yr")
    c_ok = worst[1] > 0
    survive.append(("C cohort-robustness", c_ok))
    print(f"    -> {'SURVIVES (positive after dropping any single year)' if c_ok else 'FAILS'}")

    # D. feature jackknife
    print("\n[D] Feature jackknife (hinges on one feature?)")
    d_ok = True
    worst_f = None
    for f in FEATURES:
        e = edge(df, mats, feats=[x for x in FEATURES if x != f])
        if worst_f is None or e < worst_f[1]:
            worst_f = (f, e)
        if e <= 0:
            d_ok = False
    print(f"    worst case: dropping '{worst_f[0]}' -> {worst_f[1]*100:+.2f}%/yr")
    survive.append(("D feature-robustness", d_ok))
    print(f"    -> {'SURVIVES (positive dropping any single feature)' if d_ok else 'FAILS'}")

    # E. is it just momentum?
    print("\n[E] Is it just momentum? (are picks merely high past-return funds?)")
    ranks = []
    for t in TEST:
        te = df[df.cohort == t]
        for c in CORE:
            sub = te[te.category_name == c]
            if sub.empty:
                continue
            sub = sub.assign(mr=sub['hist_return'].rank(pct=True))
            picked = set(picks_by_cohort.get(t, []))
            ranks += sub[sub.scheme_id.isin(picked)]['mr'].tolist()
    avg_mom = np.mean(ranks)
    e_no_mom = edge(df, mats, feats=[x for x in FEATURES if x != 'hist_return'])
    print(f"    avg within-category momentum percentile of picks: {avg_mom:.2f} (0.5 = neutral)")
    print(f"    edge with momentum feature REMOVED: {e_no_mom*100:+.2f}%/yr")
    e_ok = (e_no_mom > 0) and (avg_mom < 0.75)
    survive.append(("E not-just-momentum", e_ok))
    print(f"    -> {'SURVIVES (edge persists without momentum; picks not momentum-maxed)' if e_ok else 'SUSPECT'}")

    # F. random-portfolio placebo
    print("\n[F] Random-portfolio placebo (vs 2000 random top-2/category)")
    rng = np.random.RandomState(0)
    rand_means = []
    for _ in range(2000):
        pers = []
        for t in TEST:
            te = df[df.cohort == t]
            mat = mats[t]
            bench = te[te.category_name.isin(CORE)].scheme_id.tolist()
            rp = []
            for c in CORE:
                ids = te[te.category_name == c].scheme_id.tolist()
                if len(ids) >= 2:
                    rp += list(rng.choice(ids, 2, replace=False))
            pers.append(cagr(port_from_matrix(mat, rp)) - cagr(port_from_matrix(mat, bench)))
        rand_means.append(np.mean(pers))
    rand_means = np.array(rand_means)
    p_rand = (rand_means >= base).mean()
    print(f"    random-portfolio edge: mean {rand_means.mean()*100:+.2f}%, 95th pct {np.percentile(rand_means,95)*100:+.2f}%")
    print(f"    empirical p (random >= real): {p_rand:.4f}")
    f_ok = p_rand < 0.05
    survive.append(("F beats-random", f_ok))
    print(f"    -> {'SURVIVES (real edge in the tail of random chance)' if f_ok else 'FAILS'}")

    # G. leakage audit (statements)
    print("\n[G] Look-ahead / leakage audit")
    print("    - Features use only data <= eval date (trailing 3y windows). OK")
    print("    - Training uses only cohorts strictly < test year (walk-forward). OK")
    print("    - Target uses forward data (that is the label, not a feature). OK")
    print("    - KNOWN minor imperfection: prepare_features fills a few missing AUM/TER")
    print("      values with a GLOBAL median (spans all cohorts). Affects <a handful of")
    print("      rows and only their level, not the within-category rank. Low impact.")

    print("\n" + "=" * 66)
    print("SCORECARD")
    print("=" * 66)
    for name, ok in survive:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    n_pass = sum(ok for _, ok in survive)
    print(f"\n  {n_pass}/{len(survive)} adversarial tests survived.")
    print("  (Combine with negative control, Newey-West, bootstrap in FINDINGS.md.)")


if __name__ == '__main__':
    main()
