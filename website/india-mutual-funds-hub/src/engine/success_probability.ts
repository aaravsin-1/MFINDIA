/**
 * Pure JS Engine for calculating historical success probabilities.
 */

export interface SuccessProbability {
  horizon: string;
  horizonMonths: number;
  probability: number | null;
  totalPeriods: number;
}

/**
 * Calculates the historical probability of achieving a >0% return 
 * over various rolling time horizons.
 */
export function calculateSuccessProbabilities(returns: number[]): SuccessProbability[] {
  const horizons = [
    { label: '1Y', months: 12 },
    { label: '3Y', months: 36 },
    { label: '5Y', months: 60 },
    { label: '10Y', months: 120 }
  ];
  
  const results: SuccessProbability[] = [];
  
  for (const h of horizons) {
    if (returns.length < h.months) {
      results.push({
        horizon: h.label,
        horizonMonths: h.months,
        probability: null,
        totalPeriods: 0
      });
      continue;
    }
    
    let positivePeriods = 0;
    const totalPeriods = returns.length - h.months + 1;
    
    for (let i = 0; i < totalPeriods; i++) {
      let periodReturn = 1.0;
      for (let j = 0; j < h.months; j++) {
        periodReturn *= (1 + returns[i + j]);
      }
      if (periodReturn > 1.0) {
        positivePeriods++;
      }
    }
    
    results.push({
      horizon: h.label,
      horizonMonths: h.months,
      probability: totalPeriods > 0 ? (positivePeriods / totalPeriods) * 100 : null,
      totalPeriods
    });
  }
  
  return results;
}
