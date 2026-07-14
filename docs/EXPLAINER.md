# Explainer — How It Works, In Plain English

*No jargon. Read this if you want to understand what we built, what the results
mean, and how to defend them — without reading the code.*

---

## The 60-second version (say this out loud)

> "There are ~250 active equity mutual funds in India. We built a model that, for
> each category — large-cap, mid-cap, small-cap, etc. — ranks the funds from best
> to worst prospects for the next three years. We tested it honestly on 7 years of
> history it had never seen. The headline finding is careful: we **can't** predict
> which *category* will win, and we're honest that a naive 'buy the top 10 funds'
> strategy only looks good because it accidentally bets on small funds. But we
> **can** pick the better funds *within* each category — and if you buy the top 2
> in each category and rebalance once a year, you beat a fair like-for-like
> benchmark by about **2.4% a year, every single year in the test**. That edge is
> statistically real (roughly 1-in-1000 to be luck), and — unlike the first
> version of this project — it survives a 'fake data' sanity check that the
> original failed."

That's the whole story: **honest about what doesn't work, precise about what
does.**

---

## The core idea, step by step

1. **Start with a clean list.** Only real, actively-managed equity funds. We use
   the cheaper "Direct" plans and drop funds too young to measure. ~250 funds/year.

2. **Describe each fund with 9 numbers** it had on a given date: past 3-yr return,
   how bumpy that ride was (volatility), the worst drop it ever had (drawdown), how
   consistent it was, how big it is (AUM), its fee (TER), and how long/how many
   managers run it. Nothing from the future.

3. **Ask the model to rank funds** by how much they'll beat their *category
   average* over the next 3 years. We train it only on the past and test it only on
   later years it hasn't seen (a "walk-forward" test — no cheating).

4. **Turn the ranking into a portfolio.** Buy the **top 2 funds in each of the 5
   core categories** (10 funds total), hold for a year, then re-rank and rebalance.

5. **Judge it against a fair benchmark** — the average of those same categories —
   so we're comparing apples to apples, not crediting the model for just owning
   whatever category happened to boom.

---

## What the results actually say

| Question | Answer |
|---|---|
| Does it beat a fair benchmark? | Yes — **+2.37% per year**. |
| Was that consistent or one lucky year? | **All 7 of 7** test years were positive. |
| Could it be luck? | Very unlikely — about **1-in-1000** (p≈0.001) after the strict correction. |
| Does the model actually have skill, or is it a trick? | Real skill: its fund ranking lines up with reality at an "information coefficient" of ~0.09, which is genuinely good for this field. |
| How do we *know* it's not a trick? | The **negative control** (see below) — the single most important test — passes. |

---

## The two things that make this credible (and were broken before)

**1. The "fake data" sanity check (negative control).**
We take the model, feed it **scrambled, meaningless answers** during training, and
see if it still "works." If a model trained on nonsense still beats the market,
then your strategy isn't skill — it's a hidden bias. The **original project's edge
failed this test** (a nonsense model beat the benchmark about half the time). Our
category-neutral strategy **passes** it cleanly (the real result beats every single
nonsense run). This is the difference between "looks good" and "is good."

**2. A corrupted price we found and fixed.**
One fund's price history had an error making it look like it gained **+4,367%** in
three years. Because the old code averaged prices without checking for garbage,
that one bad number poisoned the "category average" for all mid-cap funds in 2021,
corrupting what the model was trying to learn. We now automatically detect and drop
impossible values. (Details in `FINDINGS.md`.)

---

## What the final list (`fund_screener_results.csv`) means

Every fund gets two independent scores plus a plain-English reason:

- **Quality (0–100)** = the model's opinion, **within the fund's own category**.
  Quality 100 = "best-ranked fund in its category." ⚠️ It is *not* comparable
  across categories — a large-cap 100 and a small-cap 100 are each "best in class,"
  not "equally good."

- **Risk (0–100)** = pure math, no model: how bumpy (volatility) and how deep its
  worst fall (drawdown) were. Split into:
  - **Conservative** (calm) → hold 5+ years
  - **Balanced** (moderate) → hold 3–5 years
  - **Aggressive** (wild) → hold 1–3 years

- **Recommended = Yes** = one of the **10 funds in the validated portfolio** (top 2
  per category). **This is the actual product** — the part backed by all the
  testing. Everything else in the file is context.

- **Why** = the top 2 reasons the model liked/disliked it, in English (e.g.
  `[+] Excellent downside protection`, `[-] Fund size acting as a drag`).

**Example row:** *JM Large Cap Fund — Quality 100, Risk 0, Conservative,
Recommended.* → "Our top-ranked large-cap fund, and also one of the calmest —
suitable for a conservative, long-horizon investor."

Notice the recommended 10 span many different fund houses and all five categories —
that's the category-neutral design working. The original version, by contrast,
piled into 5 funds from a *single* company, which was a red flag for the hidden
bias we later confirmed.

---

## Questions people will ask (and honest answers)

**"Is this an AI that predicts the stock market?"**
No — and be suspicious of anyone who says yes. It's a *ranking* tool. It sorts
funds within a category by their odds of beating their peers. Ranking is a much
easier, more honest problem than predicting exact returns.

**"2.4% doesn't sound like much."**
Compounded over a decade on a real portfolio it's substantial, and critically it's
an edge that **survived tests that killed the first version**. A small *real* edge
beats a large *imaginary* one.

**"How do you know it isn't just curve-fitting / luck?"**
Three independent guards: (1) walk-forward testing on unseen years, (2) the
negative-control "fake data" test it passes, (3) statistical tests that survive
even after we deliberately handicap them for the fact that our test windows
overlap. It clears all three.

**"Why 'category-neutral'? Why not just buy the top 10 overall?"**
Because "top 10 overall" is exactly what failed. It just loads up on small funds,
which look great in a bull market but is a bet on fund *size*, not fund *quality*.
Forcing 2-per-category strips out that bet and leaves only the genuine skill.

**"What could go wrong / what are the limits?"**
It's one market (India), ~250 funds, and the test years overlap in calendar time,
so we don't oversell the significance (that's why we report the conservative
number, not the flashy one). It needs to keep proving itself on future years. It's
a disciplined selection engine, **not** a guarantee.

**"Does past performance drive it?"**
Only *in context*. On its own, past return is a weak and even counter-productive
signal (Phase 2 of the research). The model only trusts momentum when the risk and
structural signals agree with it.

**"How often do I trade?"**
Roughly once a year, but **always hold each fund for more than 12 months.** That one
rule keeps your gains at the 12.5% long-term tax rate (instead of 20% short-term)
*and* avoids exit fees. A "top-4 buffer" — only sell a fund when it drops out of its
category's top 4 — cuts trading further without hurting returns.

**"Does tax eat the edge?"**
No, *if you follow the >12-month rule.* We modelled it: the ~2.4% gross edge becomes
about **+2.6% net** after long-term capital-gains tax at a 1–2 year hold. But if you
churn funds in under a year, the 20% short-term tax plus exit loads roughly wipes the
edge out — so the holding-period discipline is not optional. (Note: ELSS funds are
locked for 3 years by law, which actually makes them the most tax-efficient sleeve.)

**"How do we keep it running next year?"**
Keep four data feeds current (prices, manager changes, fund sizes, fees), then
re-run three scripts. See `README.md` → "Maintaining it."

---

## How the strategy is actually run (the playbook)

People get confused here because they hear "once a year," "two years," and "top-4"
and think those are competing options. **They're one policy.** Here it is:

1. **Re-rank once a year.** Run the model annually to get fresh scores.
2. **Hold every fund at least 12 months — no exceptions.** This one rule secures the
   lower 12.5% long-term tax rate *and* avoids exit fees. Break it and you pay 20%
   short-term tax that wipes out the edge.
3. **Only sell a fund when it drops out of its category's top 4** (the "buffer").
   If a fund you own is still ranked top-4, you keep it — you don't churn it just
   because something edged slightly ahead.

**Why this gives "~2 years" without a rigid 2-year rule:** because you only sell on a
top-4 exit, good funds naturally stay ~2 years instead of being swapped every year.
That drops trading from ~46% to ~33% of the portfolio per year, keeps you in the low
tax bracket, and preserves the edge.

**So the honest answer to "per year or per 2 years or top-4?":**
> Check yearly → hold ≥12 months → swap only when a fund falls out of the top-4.
> In practice funds turn over about every 2 years.

*(And no, we didn't secretly boost the edge. We found the edge is naturally biggest
in the first year and fades over three — but the number we stand behind is still the
rigorously-tested ~2.4% gross / ~2.6% after-tax.)*

---

## The one thing to remember
We didn't find a money-printing machine, and we're honest that the first version's
big claim didn't hold up. What we found and *proved* is smaller and real: **the
model picks better funds within a category, and buying the top 2 per category beats
a fair benchmark by ~2.4% a year, consistently, and for reasons that survive every
honesty check we could throw at it.**
