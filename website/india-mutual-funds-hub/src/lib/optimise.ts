// Holdings-based portfolio look-through + diversification optimiser.
//
// Design note: FundLens deliberately produces NO return forecasts. So this
// optimiser is NOT a mean-variance / Markowitz engine. It works purely on
// *disclosed holdings* — blending the underlying stocks of the funds you hold,
// measuring overlap and concentration, and suggesting weights that trade off
// diversification against the funds' within-category Quality scores.

export type RawHolding = {
  scheme_id: number;
  instrument: string;
  isin: string | null;
  industry: string | null;
  pct_nav: number;
  source: string | null;
};

export type FundInput = {
  scheme_id: number;
  fund_name: string;
  category: string | null;
  quality: number | null;
  risk: number | null;
  risk_band: string | null;
  amount: number; // rupees held
  holdings: RawHolding[]; // disclosed (usually top-10) holdings
};

// ---- instrument canonicalisation -------------------------------------------
// morningstar names ("HDFC Bank Limited") and amfi names ("HDFC BANK LTD") must
// resolve to the same key so overlap across sources is detected. ISIN is only
// present on amfi rows, so a normalised name is the common denominator.
const SUFFIXES = [
  "LIMITED", "LTD", "PLC", "CORPORATION", "CORP", "COMPANY", "CO",
  "PRIVATE", "PVT", "AND", "&", "THE",
];

export function canonName(raw: string): string {
  let s = (raw || "").toUpperCase();
  s = s.replace(/[.,'"()\-\/]/g, " ");
  let toks = s.split(/\s+/).filter(Boolean);
  toks = toks.filter((t) => !SUFFIXES.includes(t));
  return toks.join(" ").trim();
}

// A holding's canonical key: prefer ISIN when available, else normalised name.
// (Within a fund the source is consistent; across amfi/morningstar we fall back
// to the name key, which the normaliser makes agree.)
export function holdingKey(h: RawHolding): string {
  return canonName(h.instrument);
}

export type FundDist = {
  scheme_id: number;
  fund_name: string;
  category: string | null;
  quality: number | null;
  risk: number | null;
  risk_band: string | null;
  amount: number;
  coverage: number; // fraction of NAV the disclosed holdings sum to (0..1)
  // stock distribution normalised to sum to 1 across disclosed holdings
  dist: Map<string, number>;
  label: Map<string, string>; // key -> display name
  sector: Map<string, string>; // key -> industry/sector
};

export function toDist(f: FundInput): FundDist {
  const dist = new Map<string, number>();
  const label = new Map<string, string>();
  const sector = new Map<string, string>();
  let total = 0;
  for (const h of f.holdings) {
    const k = holdingKey(h);
    if (!k) continue;
    const pct = Number(h.pct_nav) || 0;
    dist.set(k, (dist.get(k) || 0) + pct);
    if (!label.has(k)) label.set(k, h.instrument);
    if (h.industry && !sector.has(k)) sector.set(k, h.industry);
    total += pct;
  }
  const coverage = total / 100;
  // normalise to a distribution (sums to 1) so funds are comparable regardless
  // of how much of NAV their top-10 happens to cover.
  if (total > 0) for (const [k, v] of dist) dist.set(k, v / total);
  return {
    scheme_id: f.scheme_id, fund_name: f.fund_name, category: f.category,
    quality: f.quality, risk: f.risk, risk_band: f.risk_band, amount: f.amount,
    coverage, dist, label, sector,
  };
}

// ---- blended look-through ---------------------------------------------------
export type Exposure = { key: string; name: string; sector: string; weight: number };

// weights: fund weight (sums to 1). Returns blended stock exposure (sums to ~1).
export function lookThrough(funds: FundDist[], weights: number[]): Exposure[] {
  const acc = new Map<string, number>();
  const name = new Map<string, string>();
  const sec = new Map<string, string>();
  funds.forEach((f, i) => {
    const w = weights[i] || 0;
    for (const [k, v] of f.dist) {
      acc.set(k, (acc.get(k) || 0) + w * v);
      if (!name.has(k)) name.set(k, f.label.get(k) || k);
      if (!sec.has(k) && f.sector.get(k)) sec.set(k, f.sector.get(k)!);
    }
  });
  return Array.from(acc.entries())
    .map(([key, weight]) => ({ key, name: name.get(key) || key, sector: sec.get(key) || "—", weight }))
    .sort((a, b) => b.weight - a.weight);
}

export function sectorExposure(exp: Exposure[]): { sector: string; weight: number }[] {
  const acc = new Map<string, number>();
  for (const e of exp) acc.set(e.sector, (acc.get(e.sector) || 0) + e.weight);
  return Array.from(acc.entries())
    .map(([sector, weight]) => ({ sector, weight }))
    .sort((a, b) => b.weight - a.weight);
}

// ---- overlap & concentration ------------------------------------------------
// pairwise overlap = sum over shared stocks of min(weight_a, weight_b), in %.
// 100 => identical baskets, 0 => no shared names.
export function overlap(a: FundDist, b: FundDist): number {
  let s = 0;
  for (const [k, va] of a.dist) {
    const vb = b.dist.get(k);
    if (vb != null) s += Math.min(va, vb);
  }
  return s * 100;
}

export function overlapMatrix(funds: FundDist[]): number[][] {
  return funds.map((a) => funds.map((b) => (a === b ? 100 : overlap(a, b))));
}

// Portfolio-level "how much do my funds duplicate each other" number: the
// weighted-average pairwise overlap (%). This is the headline the user cares
// about — 0 = no two funds share stocks, high = you're paying twice for one bet.
export function avgPairwiseOverlap(funds: FundDist[], weights: number[]): number {
  let num = 0, den = 0;
  for (let i = 0; i < funds.length; i++)
    for (let j = i + 1; j < funds.length; j++) {
      const wpair = (weights[i] || 0) * (weights[j] || 0);
      num += wpair * overlap(funds[i], funds[j]);
      den += wpair;
    }
  return den > 0 ? num / den : 0;
}

// Pairs of funds that substantially duplicate each other, worst first, with a
// recommendation on which to drop (the lower-Quality one).
export type RedundantPair = {
  i: number; j: number; overlap: number; dropIdx: number; keepIdx: number;
};
export function redundantPairs(funds: FundDist[], minOverlap = 30): RedundantPair[] {
  const out: RedundantPair[] = [];
  for (let i = 0; i < funds.length; i++)
    for (let j = i + 1; j < funds.length; j++) {
      const ov = overlap(funds[i], funds[j]);
      if (ov < minOverlap) continue;
      const dropIdx = (funds[i].quality ?? 0) <= (funds[j].quality ?? 0) ? i : j;
      out.push({ i, j, overlap: ov, dropIdx, keepIdx: dropIdx === i ? j : i });
    }
  return out.sort((a, b) => b.overlap - a.overlap);
}

// Herfindahl-Hirschman index of a blended exposure, and the "effective number
// of stocks" = 1/HHI (how many equally-weighted names it behaves like).
export function hhi(exp: Exposure[]): number {
  return exp.reduce((s, e) => s + e.weight * e.weight, 0);
}
export function effectiveStocks(exp: Exposure[]): number {
  const h = hhi(exp);
  return h > 0 ? 1 / h : 0;
}

// ---- weighted portfolio metrics --------------------------------------------
export function weightedQuality(funds: FundDist[], w: number[]): number {
  return funds.reduce((s, f, i) => s + (w[i] || 0) * (f.quality ?? 0), 0);
}
export function weightedRisk(funds: FundDist[], w: number[]): number {
  return funds.reduce((s, f, i) => s + (w[i] || 0) * (f.risk ?? 0), 0);
}

// ---- the optimiser ----------------------------------------------------------
// Maximise  J(w) = gamma * Quality(w)/100  -  (1-gamma) * HHI(lookThrough(w))
// over the simplex {w >= 0, sum w = 1}, with an optional per-fund cap.
//   gamma = 1 -> chase Quality only.  gamma = 0 -> pure diversification.
// Projected gradient ascent — deterministic, explainable, no forecasting.
export function optimise(
  funds: FundDist[],
  gamma: number,
  opts: { cap?: number; iters?: number; lr?: number } = {},
): number[] {
  const n = funds.length;
  if (n === 0) return [];
  if (n === 1) return [1];
  const cap = opts.cap ?? 0.6;
  const iters = opts.iters ?? 400;
  const lr = opts.lr ?? 0.4;

  let w = new Array(n).fill(1 / n);
  for (let it = 0; it < iters; it++) {
    const exp = lookThrough(funds, w);
    // gradient of HHI wrt w_i = 2 * sum_s e_s * dist_i[s]
    const eMap = new Map(exp.map((e) => [e.key, e.weight]));
    const grad = funds.map((f, i) => {
      let dHHI = 0;
      for (const [k, v] of f.dist) dHHI += 2 * (eMap.get(k) || 0) * v;
      const dQ = (f.quality ?? 0) / 100;
      return gamma * dQ - (1 - gamma) * dHHI;
    });
    for (let i = 0; i < n; i++) w[i] += lr * grad[i];
    w = projectCappedSimplex(w, cap);
  }
  // clean tiny weights
  return w.map((x) => (x < 1e-4 ? 0 : x));
}

// Project onto {0 <= w_i <= cap, sum w = 1} by simplex projection + clamp loop.
function projectCappedSimplex(v: number[], cap: number): number[] {
  const n = v.length;
  const eff = Math.max(cap, 1 / n); // cap can't be below equal weight
  let w = projectSimplex(v);
  for (let pass = 0; pass < 30; pass++) {
    const over = w.map((x) => x > eff + 1e-9);
    if (!over.some(Boolean)) break;
    let spill = 0, freeIdx: number[] = [];
    for (let i = 0; i < n; i++) {
      if (over[i]) { spill += w[i] - eff; w[i] = eff; }
      else freeIdx.push(i);
    }
    const freeSum = freeIdx.reduce((s, i) => s + w[i], 0);
    if (freeSum <= 1e-12) { freeIdx.forEach((i) => (w[i] += spill / freeIdx.length)); }
    else freeIdx.forEach((i) => (w[i] += spill * (w[i] / freeSum)));
  }
  return w;
}

// Euclidean projection onto the probability simplex (Duchi et al., 2008).
function projectSimplex(v: number[]): number[] {
  const n = v.length;
  const u = [...v].sort((a, b) => b - a);
  let css = 0, rho = 0, theta = 0;
  for (let i = 0; i < n; i++) {
    css += u[i];
    const t = (css - 1) / (i + 1);
    if (u[i] - t > 0) { rho = i + 1; theta = t; }
  }
  return v.map((x) => Math.max(0, x - theta));
}
