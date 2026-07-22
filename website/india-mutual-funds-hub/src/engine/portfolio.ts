/**
 * Pure JS Engine for calculating custom portfolio returns with real drift and rebalancing.
 */

export interface AssetReturns {
  [assetId: string]: number[];
}

export interface PortfolioWeights {
  [assetId: string]: number; // 0 to 100
}

export type RebalanceFrequency = 'monthly' | 'quarterly' | 'annual' | 'never';

export interface PortfolioResult {
  blendedReturns: number[]; // The overall % return per month
  equityCurve: number[];    // The absolute ₹ value curve
  contributions: Record<string, number>; // Absolute ₹ contribution of each asset
}

export function simulatePortfolio(
  returnsDict: AssetReturns,
  weights: PortfolioWeights,
  numMonths: number,
  rebalanceFreq: RebalanceFrequency = 'monthly',
  initialCapital: number = 10000,
  monthlySip: number = 0
): PortfolioResult {
  const activeAssets = Object.keys(weights).filter(a => weights[a] > 0);
  const targetDecimals: Record<string, number> = {};
  for (const a of activeAssets) {
    targetDecimals[a] = weights[a] / 100.0;
  }

  // Initialize absolute ₹ buckets
  const buckets: Record<string, number> = {};
  const initialInvestments: Record<string, number> = {};
  
  for (const a of activeAssets) {
    buckets[a] = initialCapital * targetDecimals[a];
    initialInvestments[a] = buckets[a];
  }

  const equityCurve: number[] = new Array(numMonths);
  const blendedReturns: number[] = new Array(numMonths);

  let prevTotal = initialCapital;

  for (let i = 0; i < numMonths; i++) {
    let currentTotal = 0;

    // 1. Grow buckets by this month's return
    for (const a of activeAssets) {
      const ret = returnsDict[a] ? (returnsDict[a][i] || 0) : 0;
      buckets[a] = buckets[a] * (1 + ret);
      currentTotal += buckets[a];
    }

    // Calculate the pure portfolio return for this month (before SIP)
    blendedReturns[i] = (currentTotal / prevTotal) - 1;

    // 2. Add SIP Cashflows (allocated according to target weights)
    if (monthlySip > 0) {
      for (const a of activeAssets) {
        const sipAmount = monthlySip * targetDecimals[a];
        buckets[a] += sipAmount;
        initialInvestments[a] += sipAmount;
        currentTotal += sipAmount;
      }
    }

    equityCurve[i] = currentTotal;
    prevTotal = currentTotal;

    // 3. Rebalance if needed (End of month)
    const isQuarterly = rebalanceFreq === 'quarterly' && (i + 1) % 3 === 0;
    const isAnnual = rebalanceFreq === 'annual' && (i + 1) % 12 === 0;
    const isMonthly = rebalanceFreq === 'monthly';

    if (isMonthly || isQuarterly || isAnnual) {
      for (const a of activeAssets) {
        buckets[a] = currentTotal * targetDecimals[a];
      }
    }
  }

  // Calculate Contributions
  const contributions: Record<string, number> = {};
  let totalGrowth = 0;
  for (const a of activeAssets) {
    const growth = buckets[a] - initialInvestments[a];
    contributions[a] = growth;
    totalGrowth += growth;
  }
  
  // Normalize contributions into percentages of total portfolio return
  // If absolute ₹ growth is what we want, we keep it as growth. But user wants "+8.2%". 
  // Let's store the absolute growth, UI can convert it to %.
  
  return {
    blendedReturns,
    equityCurve,
    contributions
  };
}

export function calculateEquityCurve(returns: number[], base: number = 100): number[] {
  const curve = new Array(returns.length);
  let current = base;
  for (let i = 0; i < returns.length; i++) {
    current = current * (1 + returns[i]);
    curve[i] = current;
  }
  return curve;
}
