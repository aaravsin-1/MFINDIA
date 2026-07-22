// Builds a concrete fund portfolio from a target allocation, optimised for BOTH
// risk and return, then diversified on look-through holdings.
//
//   return proxy  = Quality  (within-category ML rank; the site makes no raw
//                   return forecasts, so Quality is the sanctioned proxy)
//   risk          = Risk score (volatility + drawdown)
//   blended score = emphasis·Quality + (1-emphasis)·(100 - Risk)   [higher better]
//
// Category weights come from the investor type (they set the risk/return TARGET).
// Within each category we pick the best fund by blended score, breaking ties to
// MINIMISE stock overlap with funds already chosen (reusing the holdings optimiser).

import { toDist, overlap, type RawHolding, type FundDist } from "./optimise";
import type { Allocation } from "./investor-profile";

export type FundRow = {
  scheme_id: number; fund_name: string; category: string;
  quality: number | null; risk: number | null; risk_band: string | null; recommended: boolean;
};

export type Pick = {
  scheme_id: number; fund_name: string; category: string;
  quality: number | null; risk: number | null; risk_band: string | null;
  weight: number;        // portfolio weight within the equity sleeve (sums to 1)
  score: number;         // blended risk/return score used to pick it
  reason: string;
};

export function blendedScore(f: FundRow, emphasis: number): number {
  const q = f.quality ?? 0;
  const r = f.risk ?? 100;
  return emphasis * q + (1 - emphasis) * (100 - r);
}

// candidate pool: top few funds per category by blended score
export function candidatesByCategory(
  funds: FundRow[], mix: Record<string, number>, emphasis: number, perCat = 4,
): Record<string, FundRow[]> {
  const out: Record<string, FundRow[]> = {};
  for (const cat of Object.keys(mix)) {
    out[cat] = funds
      .filter((f) => f.category === cat && f.quality != null)
      .sort((a, b) => blendedScore(b, emphasis) - blendedScore(a, emphasis))
      .slice(0, perCat);
  }
  return out;
}

// scheme_ids we need holdings for (all candidates) — the page fetches these
export function candidateIds(cands: Record<string, FundRow[]>): number[] {
  return Array.from(new Set(Object.values(cands).flat().map((f) => f.scheme_id)));
}

type Built = { picks: Pick[]; equityCovered: number };

export function buildPortfolio(
  funds: FundRow[],
  alloc: Allocation,
  holdingsById: Map<number, RawHolding[]>,
  emphasis: number,
): Built {
  const cands = candidatesByCategory(funds, alloc.mix, emphasis);
  const distCache = new Map<number, FundDist>();
  const dist = (f: FundRow): FundDist | null => {
    const h = holdingsById.get(f.scheme_id);
    if (!h || h.length === 0) return null;
    if (!distCache.has(f.scheme_id))
      distCache.set(f.scheme_id, toDist({ ...f, amount: 0, holdings: h } as any));
    return distCache.get(f.scheme_id)!;
  };

  // one fund per category, chosen for high score + low overlap with picks so far.
  // Bigger category weights are split across two funds (respecting perFundCap).
  const chosen: FundDist[] = [];
  const picks: Pick[] = [];
  const cats = Object.keys(alloc.mix).sort((a, b) => alloc.mix[b] - alloc.mix[a]);

  for (const cat of cats) {
    const pool = (cands[cat] ?? []).filter((f) => !picks.some((p) => p.scheme_id === f.scheme_id));
    if (pool.length === 0) continue;
    const w = alloc.mix[cat];
    const n = w > alloc.perFundCap && pool.length > 1 ? 2 : 1;

    for (let k = 0; k < n; k++) {
      const remaining = pool.filter((f) => !picks.some((p) => p.scheme_id === f.scheme_id));
      if (remaining.length === 0) break;
      // rank by score, then penalise overlap with already-chosen funds
      const best = remaining
        .map((f) => {
          const d = dist(f);
          const maxOv = d ? Math.max(0, ...chosen.map((c) => overlap(d, c))) : 0;
          return { f, s: blendedScore(f, emphasis) - 0.25 * maxOv, maxOv };
        })
        .sort((a, b) => b.s - a.s)[0];
      const f = best.f;
      const d = dist(f);
      if (d) chosen.push(d);
      picks.push({
        scheme_id: f.scheme_id, fund_name: f.fund_name, category: f.category,
        quality: f.quality, risk: f.risk, risk_band: f.risk_band,
        weight: w / n, score: Math.round(blendedScore(f, emphasis)),
        reason: reasonFor(f, emphasis, best.maxOv),
      });
    }
  }

  // renormalise weights (categories that had no candidate drop out)
  const tot = picks.reduce((s, p) => s + p.weight, 0) || 1;
  picks.forEach((p) => (p.weight = p.weight / tot));
  const equityCovered = picks.reduce((s, p) => {
    const h = holdingsById.get(p.scheme_id);
    return s + (h ? 1 : 0);
  }, 0);
  return { picks, equityCovered };
}

function reasonFor(f: FundRow, emphasis: number, maxOv: number): string {
  const bits: string[] = [];
  if ((f.quality ?? 0) >= 70) bits.push("top-tier Quality in its category");
  else if ((f.quality ?? 0) >= 55) bits.push("above-average Quality");
  if ((f.risk ?? 100) <= 40) bits.push("gentler risk profile");
  if (f.recommended) bits.push("model top-pick");
  if (maxOv < 15) bits.push("adds distinct stock exposure");
  if (bits.length === 0) bits.push(emphasis > 0.6 ? "best return proxy available" : "best risk-adjusted option");
  return bits.join(" · ");
}

// weighted portfolio stats
export function portfolioStats(picks: Pick[]) {
  const q = picks.reduce((s, p) => s + p.weight * (p.quality ?? 0), 0);
  const r = picks.reduce((s, p) => s + p.weight * (p.risk ?? 0), 0);
  return { quality: Math.round(q), risk: Math.round(r) };
}
