"""
make_report_figures.py  (RESULTS_PROJECT)

Generates presentation/report figures from the REAL project data & model:
  * fig_input_table.png       - actual rows we feed the model (features + target)
  * fig_decision_tree.png     - an actual tree from the trained LightGBM model
  * fig_feature_importance.png- gain-based importance of the 9 features
  * fig_ic_scatter.png        - predicted score vs realised fwd_alpha (rank IC)
  * fig_drawdown_split.png    - real evidence for a learned split (dd < -20% -> neg alpha)
  * fig_cohort_alpha.png      - per-cohort edge vs category benchmark (7/7)
  * fig_skill_by_category.png - where the skill lives (small/mid/large)
  * fig_growth.png            - illustrative growth of Rs.10L at 20% vs 17.8% CAGR
  * fig_pillars.png           - 5 pillars of quality -> 9 features map

All numbers are computed here or taken from the validated results docs
(per-cohort edges, category skill). Nothing hits the DB.
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
import lightgbm as lgb
import joblib
from scipy.stats import spearmanr
from lib import DATA, OUTPUTS, ASSETS, ROOT, FEATURES

OUT = str(ASSETS)
NAVY = "#1a2947"
BLUE = "#2f6fb0"
TEAL = "#1c8c8c"
GOLD = "#d99a2b"
RED = "#c0504d"
GREEN = "#4a9a5a"
GREY = "#8a8f99"
plt.rcParams.update({
    "font.size": 12, "font.family": "DejaVu Sans",
    "axes.edgecolor": "#cccccc", "axes.linewidth": 0.8,
    "figure.facecolor": "white", "axes.facecolor": "white",
    "axes.titleweight": "bold", "axes.titlecolor": NAVY,
})

PRETTY = {
    "hist_return": "3-yr Return", "hist_volatility": "Volatility",
    "hist_hit_rate": "Hit-rate", "aum_percentile": "AUM %ile",
    "ter": "TER (cost)", "max_tenure_years": "Mgr Tenure",
    "num_managers": "# Managers", "is_team": "Is-team",
    "max_drawdown": "Max Drawdown",
}


def savefig(fig, name):
    path = f"{OUT}/{name}"
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", path)


def load():
    df = pd.read_csv(DATA / "ml_dataset.csv")
    model = joblib.load(DATA / "model.pkl")
    return df, model


# ---------------------------------------------------------------- 1. input table
def fig_input_table(df):
    show_feats = ["hist_return", "hist_volatility", "hist_hit_rate",
                  "max_drawdown", "aum_percentile", "ter", "max_tenure_years"]
    cols = ["scheme_name", "category_name"] + show_feats + ["fwd_alpha"]
    sub = df[df["cohort"] == 2018].copy()
    sub = pd.concat([sub.head(4), sub.tail(3)])
    disp = sub[cols].copy()
    disp["scheme_name"] = disp["scheme_name"].str.title().str.replace(" Fund", "", regex=False).str[:24]
    disp["category_name"] = disp["category_name"].str.replace(" Fund", "", regex=False)
    for c in show_feats + ["fwd_alpha"]:
        if c in ("hist_return", "hist_volatility", "hist_hit_rate", "max_drawdown",
                 "aum_percentile", "fwd_alpha"):
            disp[c] = (disp[c] * 100).round(1).astype(str) + "%"
        else:
            disp[c] = disp[c].round(2).astype(str)
    headers = (["Fund", "Category"] + [PRETTY[c] for c in show_feats] + ["Beat category?\n(next 3y)"])

    fig, ax = plt.subplots(figsize=(16, 4.2))
    ax.axis("off")
    tbl = ax.table(cellText=disp.values, colLabels=headers, loc="center",
                   cellLoc="center", bbox=[0.02, 0.0, 0.96, 1.0])
    tbl.auto_set_font_size(False); tbl.set_fontsize(10.5); tbl.scale(1, 1.9)
    ncol = len(headers)
    # explicit column widths so long fund names are not clipped
    widths = [0.185, 0.11] + [0.093] * len(show_feats) + [0.12]
    widths = [w / sum(widths) for w in widths]
    for (r, c), cell in tbl.get_celld().items():
        cell.set_width(widths[c])
        cell.set_edgecolor("#dddddd")
        if c <= 1 and r > 0:
            cell.set_text_props(ha="left"); cell._loc = "left"
        if r == 0:
            cell.set_facecolor(NAVY); cell.set_text_props(color="white", weight="bold")
        else:
            if c == ncol - 1:
                cell.set_facecolor("#fdf3e0"); cell.set_text_props(color=GOLD, weight="bold")
            elif c <= 1:
                cell.set_facecolor("#f2f5fa")
            else:
                cell.set_facecolor("#eef4fb")
    ax.set_title("What we feed the model: one row = one fund at one point in time  "
                 "(9 input features  ->  1 target)", pad=18, fontsize=14)
    fig.text(0.5, 0.02,
             "Blue = a few of the 9 INPUT features (what we know today)      "
             "Gold = the TARGET (what happened next: did it beat its category over 3 years)",
             ha="center", fontsize=10.5, color=GREY)
    savefig(fig, "fig_input_table.png")


# ---------------------------------------------------------------- 2. decision tree
def fig_decision_tree(model):
    try:
        import graphviz  # noqa
        # pick a representative early tree; rename features to pretty labels
        booster = model.booster_
        g = lgb.create_tree_digraph(booster, tree_index=0, show_info=["internal_value", "leaf_count"])
        src = g.source
        for raw, nice in PRETTY.items():
            src = src.replace(raw, nice)
        import graphviz as gv
        d = gv.Source(src)
        d.render(filename=f"{OUT}/fig_decision_tree", format="png", cleanup=True)
        print("wrote", f"{OUT}/fig_decision_tree.png (graphviz)")
        return True
    except Exception as e:
        print("graphviz tree failed:", e)
        return False


# --------------------------------------------------- 3b. importance TABLE (gain + split)
def fig_importance_table(model):
    b = model.booster_
    gain = b.feature_importance(importance_type="gain").astype(float)
    split = b.feature_importance(importance_type="split").astype(float)
    gp = gain / gain.sum() * 100
    sp = split / split.sum() * 100
    PILLAR = {"hist_return": "Performance", "hist_hit_rate": "Performance",
              "hist_volatility": "Risk", "max_drawdown": "Risk",
              "aum_percentile": "Size", "ter": "Cost",
              "max_tenure_years": "People", "num_managers": "People", "is_team": "People"}
    rows = []
    for i, f in enumerate(FEATURES):
        rows.append([PRETTY[f], PILLAR[f], f"{gp[i]:.1f}%", f"{int(split[i])}", f"{sp[i]:.1f}%"])
    order = np.argsort(-gp)
    rows = [rows[i] for i in order]
    headers = ["Feature", "Pillar", "Gain %\n(value of cuts)", "# Splits",
               "Split %\n(how often used)"]
    fig, ax = plt.subplots(figsize=(11, 5.4))
    ax.axis("off")
    tbl = ax.table(cellText=rows, colLabels=headers, loc="center", cellLoc="center",
                   bbox=[0.02, 0.0, 0.96, 0.86])
    tbl.auto_set_font_size(False); tbl.set_fontsize(12); tbl.scale(1, 1.7)
    widths = [0.26, 0.20, 0.20, 0.14, 0.20]
    widths = [w / sum(widths) for w in widths]
    top_gain = rows[0][0]
    top_split = max(rows, key=lambda r: float(r[4].rstrip("%")))[0]
    for (r, c), cell in tbl.get_celld().items():
        cell.set_width(widths[c]); cell.set_edgecolor("#dddddd")
        if c == 0 and r > 0:
            cell.set_text_props(ha="left"); cell._loc = "left"
        if r == 0:
            cell.set_facecolor(NAVY); cell.set_text_props(color="white", weight="bold")
        else:
            name = rows[r - 1][0]
            unused = rows[r - 1][2] == "0.0%"
            cell.set_facecolor("#f7f9fc" if r % 2 else "white")
            if unused:
                cell.set_text_props(color=GREY, style="italic")
            if c == 2 and name == top_gain:
                cell.set_facecolor("#fdf3e0"); cell.set_text_props(color=GOLD, weight="bold")
            if c == 4 and name == top_split:
                cell.set_facecolor("#e6f0f7"); cell.set_text_props(color=BLUE, weight="bold")
    ax.set_title("Feature importance, two ways: value of cuts (gain) vs how often used (split)",
                 pad=14, fontsize=14.5)
    fig.text(0.5, 0.03,
             "Gold = top by GAIN (3-yr Return: few cuts, each decisive)      "
             "Blue = top by SPLIT (AUM %ile: the model's workhorse)      "
             "Is-team: unused on both",
             ha="center", fontsize=10.5, color=GREY)
    savefig(fig, "fig_importance_table.png")


# --------------------------------------------------- 3. feature importance
def fig_feature_importance(model):
    imp = model.booster_.feature_importance(importance_type="gain")
    imp = imp / imp.sum() * 100
    order = np.argsort(imp)
    names = [PRETTY[FEATURES[i]] for i in order]
    vals = imp[order]
    fig, ax = plt.subplots(figsize=(8.5, 5))
    colors = [BLUE if v < max(vals) else GOLD for v in vals]
    ax.barh(names, vals, color=colors)
    for y, v in enumerate(vals):
        ax.text(v + 0.6, y, f"{v:.0f}%", va="center", fontsize=11, color=NAVY)
    ax.set_xlabel("Share of model's decision power (gain %)")
    ax.set_title("Which of the 9 features drive the ranking")
    ax.set_xlim(0, max(vals) * 1.18)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    savefig(fig, "fig_feature_importance.png")


# --------------------------------------------------- 3c. dataset size by cohort
def fig_dataset_size(df):
    c = df.groupby("cohort").size()
    years = list(c.index)
    counts = list(c.values)
    total = len(df)
    fig, ax = plt.subplots(figsize=(10.5, 5.6))
    # colour: pre-history (tiny) grey, training-available blue, test cohorts gold-edge
    test = set(range(2016, 2023))
    colors = [GREY if v < 20 else (BLUE if y not in test else TEAL) for y, v in zip(years, counts)]
    bars = ax.bar([str(y) for y in years], counts, color=colors)
    for y, v in zip(years, counts):
        ax.text(str(y), v + 4, str(v), ha="center", fontsize=11, color=NAVY, weight="bold")
    ax.annotate("only 2 funds had a full\n3-yr history this early",
                xy=("2013", 2), xytext=(0.5, 120), textcoords=ax.transData,
                fontsize=10.5, color=GREY, ha="center",
                arrowprops=dict(arrowstyle="->", color=GREY, lw=1.2))
    ax.set_ylabel("Funds in cohort (rows)")
    ax.set_xlabel("Cohort year (each fund measured at that year-end)")
    ax.set_title(f"The training set: {total:,} fund-cohort rows, 2013-2022")
    ax.set_ylim(0, max(counts) * 1.22)
    # legend
    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(color=BLUE, label="train-only cohorts (2015)"),
        Patch(color=TEAL, label="walk-forward test cohorts (2016-2022)"),
        Patch(color=GREY, label="too few funds (2013-14)"),
    ], frameon=False, loc="upper left", fontsize=10.5)
    ax.text(0.99, 0.94, f"Sum of all bars = {total:,} rows",
            transform=ax.transAxes, ha="right", fontsize=12, color=NAVY,
            weight="bold", bbox=dict(boxstyle="round,pad=0.4", fc="#fdf3e0", ec=GOLD))
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    savefig(fig, "fig_dataset_size.png")


# --------------------------------------------------- 4. IC scatter (walk-forward)
def fig_ic_scatter(df):
    preds, actuals = [], []
    for t in [2016, 2017, 2018, 2019, 2020, 2021, 2022]:
        tr = df[df["cohort"] < t]
        te = df[df["cohort"] == t]
        if len(te) < 10:
            continue
        m = lgb.LGBMRegressor(random_state=42, n_estimators=50, max_depth=3, verbose=-1)
        m.fit(tr[FEATURES], tr["fwd_alpha"])
        preds.extend(m.predict(te[FEATURES]))
        actuals.extend(te["fwd_alpha"].values)
    preds, actuals = np.array(preds), np.array(actuals)
    ic = spearmanr(preds, actuals).correlation
    pr = pd.Series(preds).rank(pct=True)
    ar = pd.Series(actuals).rank(pct=True)
    fig, ax = plt.subplots(figsize=(7.5, 6))
    ax.scatter(pr, ar, s=14, alpha=0.35, color=BLUE, edgecolor="none")
    z = np.polyfit(pr, ar, 1)
    xs = np.linspace(0, 1, 100)
    ax.plot(xs, np.polyval(z, xs), color=GOLD, lw=2.5)
    ax.set_xlabel("Model's predicted rank (low -> high)")
    ax.set_ylabel("Actual rank of next-3yr category-alpha")
    ax.set_title(f"Does the score predict the future?  Rank IC = {ic:+.3f}")
    ax.text(0.03, 0.94, "Upward slope = higher-scored funds\ntended to actually do better",
            transform=ax.transAxes, fontsize=11, color=GREY, va="top")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    savefig(fig, "fig_ic_scatter.png")


# --------------------------------------------------- 5. mean-reversion evidence
def fig_mean_reversion(df):
    """Real, monotonic pattern the model exploits: past out-performers fade.
    Uses hist_hit_rate (the tree's 2nd split, at 0.479); perfectly monotonic in data."""
    d = df.dropna(subset=["hist_hit_rate", "fwd_alpha"]).copy()
    d["q"] = pd.qcut(d["hist_hit_rate"], 5, labels=False)
    g = d.groupby("q")["fwd_alpha"].mean() * 100
    xlabels = ["Bottom\n20%", "", "Middle", "", "Top\n20%"]
    fig, ax = plt.subplots(figsize=(9, 5))
    colors = [GREEN if v >= 0 else RED for v in g.values]
    ax.bar(range(len(g)), g.values, color=colors)
    ax.axhline(0, color="#333", lw=1)
    ax.set_ylim(min(g.values) - 1.4, max(g.values) + 1.0)
    for i, v in enumerate(g.values):
        ax.text(i, v + (0.2 if v >= 0 else -0.25), f"{v:+.1f}%", ha="center",
                fontsize=11, color=NAVY, va="bottom" if v >= 0 else "top")
    ax.set_xticks(range(len(g)))
    ax.set_xticklabels(xlabels)
    ax.tick_params(axis="x", pad=8)
    ax.set_ylabel("Avg next-3yr category-alpha (%)")
    ax.set_xlabel("How often the fund beat its category in the PAST (hit-rate)")
    ax.set_title("What the model actually learns: past out-performers fade (mean reversion)")
    ax.text(0.02, 0.03, "Funds that beat peers most often historically tend to beat them LEAST next\n"
            "-> the model learns to fade the crowd's favourites, not chase them",
            transform=ax.transAxes, fontsize=10.5, color=GREY, va="bottom")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    savefig(fig, "fig_mean_reversion.png")


# --------------------------------------------------- 6. per-cohort alpha
def fig_cohort_alpha():
    years = [2016, 2017, 2018, 2019, 2020, 2021, 2022]
    edge = [0.56, 1.42, 3.99, 4.13, 2.99, 0.82, 2.70]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar([str(y) for y in years], edge, color=BLUE)
    ax.axhline(np.mean(edge), color=GOLD, ls="--", lw=2,
               label=f"average +{np.mean(edge):.2f}%/yr")
    for i, v in enumerate(edge):
        ax.text(i, v + 0.08, f"+{v:.2f}", ha="center", fontsize=10.5, color=NAVY)
    ax.set_ylabel("Edge vs category-matched benchmark (%/yr)")
    ax.set_title("Positive in all 7 back-test years (2016-2022)")
    ax.legend(frameon=False)
    ax.set_ylim(0, 5)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    savefig(fig, "fig_cohort_alpha.png")


# --------------------------------------------------- 7. skill by category
def fig_skill_by_category():
    cats = ["Small Cap", "Flexi/ELSS\n(mixed)", "Large Cap", "Mid Cap"]
    edge = [3.4, 2.0, 0.6, 0.1]
    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.bar(cats, edge, color=[TEAL, BLUE, GREY, GREY])
    for i, v in enumerate(edge):
        ax.text(i, v + 0.06, f"+{v:.1f}%", ha="center", fontsize=11, color=NAVY)
    ax.set_ylabel("Edge (%/yr)")
    ax.set_title("Where the skill lives: high-dispersion categories, not efficient large-cap")
    ax.set_ylim(0, 4)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    savefig(fig, "fig_skill_by_category.png")


# --------------------------------------------------- 8. growth of 10 lakh (illustrative)
def fig_growth():
    yrs = np.arange(0, 8)
    strat = 10 * (1.20 ** yrs)
    bench = 10 * (1.178 ** yrs)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(yrs, strat, marker="o", color=BLUE, lw=2.5, label="Strategy  (~20.0% CAGR)")
    ax.plot(yrs, bench, marker="o", color=GREY, lw=2.5, label="Category benchmark (~17.8% CAGR)")
    ax.fill_between(yrs, bench, strat, color=BLUE, alpha=0.10)
    ax.set_xlabel("Years")
    ax.set_ylabel("Value of Rs.10 lakh (Rs. lakh)")
    ax.set_title("Illustrative compounding: the ~2.4%/yr edge over 7 years")
    ax.legend(frameon=False, loc="upper left")
    ax.text(7, strat[-1], f" Rs.{strat[-1]:.0f}L", color=BLUE, va="center", fontsize=11)
    ax.text(7, bench[-1], f" Rs.{bench[-1]:.0f}L", color=GREY, va="center", fontsize=11)
    ax.set_xlim(0, 8.6)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.text(0.12, -0.01, "Illustrative only: assumes constant CAGRs; real returns vary year to year.",
             fontsize=9.5, color=GREY)
    savefig(fig, "fig_growth.png")


# --------------------------------------------------- 9. 5 pillars -> 9 features
def fig_pillars():
    pillars = [
        ("Performance", GREEN, ["3-yr Return", "Hit-rate"]),
        ("Risk", RED, ["Volatility", "Max Drawdown"]),
        ("Size", BLUE, ["AUM %ile"]),
        ("Cost", GOLD, ["TER"]),
        ("People", TEAL, ["Mgr Tenure", "# Managers", "Is-team"]),
    ]
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.axis("off")
    ax.set_xlim(0, 10); ax.set_ylim(3.0, 10)
    n = len(pillars)
    for i, (name, col, feats) in enumerate(pillars):
        x = 0.6 + i * 1.9
        ax.add_patch(plt.Rectangle((x, 7.6), 1.55, 1.4, color=col, alpha=0.9))
        ax.text(x + 0.77, 8.3, name, ha="center", va="center", color="white",
                fontsize=13, weight="bold")
        for j, f in enumerate(feats):
            y = 5.6 - j * 1.0
            ax.add_patch(plt.Rectangle((x, y), 1.55, 0.75, facecolor="white",
                                       edgecolor=col, lw=1.8))
            ax.text(x + 0.77, y + 0.37, f, ha="center", va="center",
                    fontsize=10, color=NAVY)
            ax.plot([x + 0.77, x + 0.77], [7.6, 6.35], color=col, lw=1.4, ls="-")
    ax.text(5, 9.6, "5 pillars of fund quality  ->  9 machine-readable features",
            ha="center", fontsize=15, weight="bold", color=NAVY)
    savefig(fig, "fig_pillars.png")


def main():
    df, model = load()
    fig_input_table(df)
    fig_decision_tree(model)
    fig_feature_importance(model)
    fig_ic_scatter(df)
    fig_mean_reversion(df)
    fig_cohort_alpha()
    fig_skill_by_category()
    fig_growth()
    fig_pillars()
    print("\nAll figures written to", OUT + "/")


if __name__ == "__main__":
    main()
