// Investor profiling engine.
//
// There is no single "Harvard" paper enumerating 35-40 investor types. This is a
// composite taxonomy built from established, citable behavioral-finance frameworks:
//   • Risk CAPACITY vs risk TOLERANCE (CFA / industry standard; Grable & Lytton) —
//     capacity = objective ability to take risk; tolerance = psychological willingness.
//   • Pompian's Behavioral Investor Types — Preserver / Follower / Independent /
//     Accumulator, classified on the active↔passive × risk-tolerance grid.
//   • BB&K five-way model (confidence↔anxiety, careful↔impetuous) — informs the copy.
//
// 3 capacity levels × 3 tolerance levels × 4 behavioral types = 36 investor types.
// The (capacity × tolerance) pair sets the risk/return TARGET (equity % + category
// mix); the behavioral type sets TILTS, guardrails and coaching.

export type Level = "Low" | "Medium" | "High";
export type Tol = "Cautious" | "Balanced" | "Bold";
export type Behavioral = "Preserver" | "Follower" | "Independent" | "Accumulator";

// ---- the 10 questions -------------------------------------------------------
// Each option contributes to axis raw scores (0..1 scale per option weight).
export type Effect = Partial<{ capacity: number; tolerance: number; active: number }>;
export type Question = {
  id: string;
  axis: "Capacity" | "Tolerance" | "Style";
  prompt: string;
  help?: string;
  options: { label: string; effect: Effect }[];
};

export const QUESTIONS: Question[] = [
  {
    id: "horizon", axis: "Capacity",
    prompt: "When will you likely need most of this money?",
    help: "Longer horizons can ride out market falls, so they carry more risk capacity.",
    options: [
      { label: "Within 3 years", effect: { capacity: 0.0 } },
      { label: "3–7 years", effect: { capacity: 0.4 } },
      { label: "7–15 years", effect: { capacity: 0.8 } },
      { label: "15+ years", effect: { capacity: 1.0 } },
    ],
  },
  {
    id: "income", axis: "Capacity",
    prompt: "How stable and secure is your income?",
    options: [
      { label: "Irregular / uncertain", effect: { capacity: 0.0 } },
      { label: "Mostly steady", effect: { capacity: 0.5 } },
      { label: "Very stable, growing", effect: { capacity: 1.0 } },
    ],
  },
  {
    id: "buffer", axis: "Capacity",
    prompt: "Emergency fund — months of expenses in cash you could fall back on?",
    help: "A cash buffer means you won't be forced to sell investments in a crash.",
    options: [
      { label: "Less than 1 month", effect: { capacity: 0.0 } },
      { label: "1–3 months", effect: { capacity: 0.4 } },
      { label: "3–6 months", effect: { capacity: 0.8 } },
      { label: "6+ months", effect: { capacity: 1.0 } },
    ],
  },
  {
    id: "dependents", axis: "Capacity",
    prompt: "Big financial commitments in the next few years (loan, home, family, education)?",
    options: [
      { label: "Several major ones", effect: { capacity: 0.0 } },
      { label: "One or two", effect: { capacity: 0.5 } },
      { label: "None significant", effect: { capacity: 1.0 } },
    ],
  },
  {
    id: "share", axis: "Capacity",
    prompt: "Roughly what share of your total savings is this money?",
    options: [
      { label: "Almost all of it", effect: { capacity: 0.1 } },
      { label: "About half", effect: { capacity: 0.5 } },
      { label: "A small slice", effect: { capacity: 1.0 } },
    ],
  },
  {
    id: "drawdown", axis: "Tolerance",
    prompt: "Your portfolio drops 30% in a few months. You…",
    help: "This is the single most revealing risk-tolerance question.",
    options: [
      { label: "Sell to stop the bleeding", effect: { tolerance: 0.0, active: 0.3 } },
      { label: "Feel sick but hold on", effect: { tolerance: 0.4 } },
      { label: "Shrug — it happens", effect: { tolerance: 0.75 } },
      { label: "Invest more — it's on sale", effect: { tolerance: 1.0, active: 0.7 } },
    ],
  },
  {
    id: "tradeoff", axis: "Tolerance",
    prompt: "Which matters more to you?",
    options: [
      { label: "Protecting what I have", effect: { tolerance: 0.1 } },
      { label: "A balance of both", effect: { tolerance: 0.5 } },
      { label: "Maximising long-run growth", effect: { tolerance: 1.0 } },
    ],
  },
  {
    id: "swings", axis: "Tolerance",
    prompt: "Which return pattern would you rather own over a year?",
    options: [
      { label: "+6% steady, barely moves", effect: { tolerance: 0.1 } },
      { label: "+12%, with a 15% dip on the way", effect: { tolerance: 0.55 } },
      { label: "+25%, with a 35% dip on the way", effect: { tolerance: 1.0 } },
    ],
  },
  {
    id: "involvement", axis: "Style",
    prompt: "How hands-on do you want to be?",
    help: "Active vs passive is the first axis of the behavioral-type model.",
    options: [
      { label: "Set it and forget it", effect: { active: 0.0 } },
      { label: "Check in occasionally", effect: { active: 0.45 } },
      { label: "I like researching and adjusting", effect: { active: 1.0 } },
    ],
  },
  {
    id: "driver", axis: "Style",
    prompt: "What most drives your money decisions?",
    options: [
      { label: "Tips from friends / news / social media", effect: { active: 0.2, tolerance: 0.1 } },
      { label: "Gut feeling and how I feel that day", effect: { active: 0.1 } },
      { label: "My own research and a written plan", effect: { active: 1.0 } },
      { label: "Whatever most people seem to be doing", effect: { active: 0.3 } },
    ],
  },
];

// ---- scoring & classification ----------------------------------------------
export type Profile = {
  capacity: Level;
  tolerance: Tol;
  behavioral: Behavioral;
  tier: 1 | 2 | 3 | 4 | 5;
  scores: { capacity: number; tolerance: number; active: number };
  code: string;      // e.g. "H-Bold-Accumulator"
  name: string;      // display name
  tagline: string;
  coaching: string[]; // behavioral guardrails
  biases: string[];   // biases to watch (BB&K / Pompian flavour)
};

function avg(xs: number[]): number {
  return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0;
}

// answers: index chosen per question, aligned to QUESTIONS order
export function scoreAnswers(answers: (number | null)[]): Profile["scores"] {
  const cap: number[] = [], tol: number[] = [], act: number[] = [];
  QUESTIONS.forEach((q, i) => {
    const a = answers[i];
    if (a == null || !q.options[a]) return;
    const e = q.options[a].effect;
    if (e.capacity != null) cap.push(e.capacity);
    if (e.tolerance != null) tol.push(e.tolerance);
    if (e.active != null) act.push(e.active);
  });
  return { capacity: avg(cap), tolerance: avg(tol), active: avg(act) };
}

const capLevel = (s: number): Level => (s < 0.4 ? "Low" : s < 0.7 ? "Medium" : "High");
const tolLevel = (s: number): Tol => (s < 0.4 ? "Cautious" : s < 0.7 ? "Balanced" : "Bold");

// Pompian: active/passive × risk tolerance → behavioral type.
function behavioralType(active: number, tol: Tol): Behavioral {
  const isActive = active >= 0.5;
  if (isActive) return tol === "Bold" ? "Accumulator" : "Independent";
  return tol === "Cautious" ? "Preserver" : "Follower";
}

// Risk tier from the capacity × tolerance grid. Guardrail logic: you should not
// take more risk than EITHER your ability or willingness allows, so bold-but-
// low-capacity is capped, and high-capacity-but-cautious is nudged up only mildly.
const TIER_GRID: Record<Level, Record<Tol, 1 | 2 | 3 | 4 | 5>> = {
  Low:    { Cautious: 1, Balanced: 1, Bold: 2 },
  Medium: { Cautious: 2, Balanced: 3, Bold: 4 },
  High:   { Cautious: 3, Balanced: 4, Bold: 5 },
};

const BEHAVIORAL_NOUN: Record<Behavioral, string> = {
  Preserver: "Guardian",
  Follower: "Navigator",
  Independent: "Individualist",
  Accumulator: "Accumulator",
};
const TIER_ADJ: Record<number, string> = {
  1: "Cautious", 2: "Steady", 3: "Balanced", 4: "Growth-Seeking", 5: "Bold",
};

const COACHING: Record<Behavioral, string[]> = {
  Preserver: [
    "Your instinct is to protect capital — the real risk for you is being *too* safe and letting inflation erode returns over long horizons.",
    "Decide your plan when markets are calm and write it down, so fear doesn't drive selling in a downturn.",
  ],
  Follower: [
    "You're prone to herding — chasing what's popular or last year's winner. Beware buying funds *after* they've run up.",
    "Automate contributions (SIP) and avoid reacting to tips, news cycles or social media.",
  ],
  Independent: [
    "You do your own research — watch for confirmation bias (seeking only views that agree with you) and over-trading.",
    "A written thesis per holding, reviewed yearly, keeps conviction honest.",
  ],
  Accumulator: [
    "Confidence is your edge and your risk — overconfidence leads to over-concentration. Hard-cap any single fund and stock.",
    "Rebalance on a schedule, not on excitement; resist the urge to keep adding to what's already winning.",
  ],
};
const BIASES: Record<Behavioral, string[]> = {
  Preserver: ["Loss aversion", "Status-quo bias", "Anchoring"],
  Follower: ["Herding", "Recency bias", "Regret aversion"],
  Independent: ["Confirmation bias", "Overconfidence (in research)", "Availability bias"],
  Accumulator: ["Overconfidence", "Illusion of control", "Self-attribution"],
};

export function classify(answers: (number | null)[]): Profile {
  const scores = scoreAnswers(answers);
  const capacity = capLevel(scores.capacity);
  const tolerance = tolLevel(scores.tolerance);
  const behavioral = behavioralType(scores.active, tolerance);
  const tier = TIER_GRID[capacity][tolerance];
  const name = `${TIER_ADJ[tier]} ${BEHAVIORAL_NOUN[behavioral]}`;
  return {
    capacity, tolerance, behavioral, tier, scores,
    code: `${capacity[0]}-${tolerance}-${behavioral}`,
    name,
    tagline: TAGLINES[behavioral],
    coaching: COACHING[behavioral],
    biases: BIASES[behavioral],
  };
}

const TAGLINES: Record<Behavioral, string> = {
  Preserver: "Safety-first, emotionally driven. Values stability over upside.",
  Follower: "Goes with the flow; wants to do the sensible thing others do.",
  Independent: "Thinks for themselves; comfortable going against the crowd.",
  Accumulator: "Confident, growth-hungry, hands-on wealth builder.",
};

// ---- target allocation ------------------------------------------------------
// Equity-only universe: `equityPct` is guidance for the overall equity vs
// debt/emergency split (shown as text); `mix` allocates WITHIN the equity sleeve
// across the fund categories we actually rate.
export const CATS = {
  LARGE: "Large Cap Fund",
  LARGEMID: "Large & Mid Cap Fund",
  FLEXI: "Flexi Cap Fund",
  MULTI: "Multi Cap Fund",
  MID: "Mid Cap Fund",
  SMALL: "Small Cap Fund",
  ELSS: "ELSS",
  FOCUSED: "Focused Fund",
  VALUE: "Value Fund",
  THEMATIC: "Sectoral/ Thematic",
} as const;

export type Allocation = {
  equityPct: number;            // guidance: % of investable money in equity
  safeLabel: string;            // what the rest should be
  mix: Record<string, number>;  // category -> weight within equity (sums to 1)
  perFundCap: number;           // max weight for any single fund
  targetFunds: number;          // how many funds to hold
  riskEmphasisDefault: number;  // 0=risk-first .. 1=return-first
};

const TIER_BASE: Record<number, { equityPct: number; mix: Record<string, number> }> = {
  1: { equityPct: 40, mix: { [CATS.LARGE]: 0.55, [CATS.FLEXI]: 0.25, [CATS.LARGEMID]: 0.20 } },
  2: { equityPct: 55, mix: { [CATS.LARGE]: 0.40, [CATS.FLEXI]: 0.30, [CATS.LARGEMID]: 0.15, [CATS.MID]: 0.15 } },
  3: { equityPct: 68, mix: { [CATS.LARGE]: 0.25, [CATS.FLEXI]: 0.30, [CATS.LARGEMID]: 0.15, [CATS.MID]: 0.18, [CATS.SMALL]: 0.12 } },
  4: { equityPct: 80, mix: { [CATS.FLEXI]: 0.28, [CATS.LARGE]: 0.17, [CATS.LARGEMID]: 0.12, [CATS.MID]: 0.25, [CATS.SMALL]: 0.18 } },
  5: { equityPct: 92, mix: { [CATS.MID]: 0.30, [CATS.SMALL]: 0.30, [CATS.FLEXI]: 0.20, [CATS.LARGE]: 0.10, [CATS.THEMATIC]: 0.10 } },
};

function shift(mix: Record<string, number>, from: string, to: string, amt: number) {
  const take = Math.min(amt, mix[from] ?? 0);
  if (take <= 0) return;
  mix[from] = (mix[from] ?? 0) - take;
  mix[to] = (mix[to] ?? 0) + take;
  if (mix[from] <= 1e-9) delete mix[from];
}

export function targetAllocation(p: Profile): Allocation {
  const base = TIER_BASE[p.tier];
  const mix: Record<string, number> = { ...base.mix };
  let perFundCap = 0.4, targetFunds = 4, riskEmphasisDefault = 0.5;

  switch (p.behavioral) {
    case "Preserver":
      // de-risk one notch: pull weight out of Small/Mid into Large & Large-Mid
      shift(mix, CATS.SMALL, CATS.LARGE, 0.10);
      shift(mix, CATS.MID, CATS.LARGEMID, 0.06);
      perFundCap = 0.35; targetFunds = 4; riskEmphasisDefault = 0.3; // risk-first
      break;
    case "Follower":
      // keep it simple: fold the smallest sleeves into Flexi, prefer fewer funds
      shift(mix, CATS.THEMATIC, CATS.FLEXI, 1);
      shift(mix, CATS.LARGEMID, CATS.FLEXI, 0.06);
      perFundCap = 0.45; targetFunds = 3; riskEmphasisDefault = 0.45;
      break;
    case "Independent":
      // room for a conviction Value satellite; can hold more funds
      shift(mix, CATS.FLEXI, CATS.VALUE, 0.10);
      perFundCap = 0.4; targetFunds = 5; riskEmphasisDefault = 0.6; // return-tilt
      break;
    case "Accumulator":
      // growth-hungry but force diversification via a tighter cap + more funds
      shift(mix, CATS.LARGE, CATS.MID, 0.04);
      perFundCap = 0.3; targetFunds = 5; riskEmphasisDefault = 0.7; // return-first, capped
      break;
  }
  // renormalise
  const tot = Object.values(mix).reduce((a, b) => a + b, 0) || 1;
  for (const k of Object.keys(mix)) mix[k] = mix[k] / tot;

  return {
    equityPct: base.equityPct,
    safeLabel: "debt funds, PPF/EPF, FDs & emergency cash",
    mix, perFundCap, targetFunds, riskEmphasisDefault,
  };
}
