/**
 * Pure JS Engine for calculating financial statistics.
 */

export function calculateCAGR(returns: number[]): number {
  if (returns.length === 0) return 0;
  
  // Calculate total compound return
  let totalReturn = 1.0;
  for (let i = 0; i < returns.length; i++) {
    totalReturn *= (1 + returns[i]);
  }
  
  // Annualize (assuming monthly data)
  const years = returns.length / 12.0;
  return Math.pow(totalReturn, 1 / years) - 1;
}

export function calculateVolatility(returns: number[]): number {
  if (returns.length < 2) return 0;
  
  const mean = returns.reduce((sum, r) => sum + r, 0) / returns.length;
  const variance = returns.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / (returns.length - 1);
  return Math.sqrt(variance) * Math.sqrt(12);
}

export function calculateMaxDrawdown(curve: number[]): number {
  if (curve.length === 0) return 0;
  
  let maxDrawdown = 0;
  let peak = curve[0];
  
  for (let i = 1; i < curve.length; i++) {
    if (curve[i] > peak) {
      peak = curve[i];
    }
    const drawdown = (curve[i] - peak) / peak;
    if (drawdown < maxDrawdown) {
      maxDrawdown = drawdown;
    }
  }
  
  return maxDrawdown; // will be negative
}

export function calculateDrawdownCurve(curve: number[]): number[] {
  if (curve.length === 0) return [];
  
  const drawdowns = new Array(curve.length);
  let peak = curve[0];
  drawdowns[0] = 0;
  
  for (let i = 1; i < curve.length; i++) {
    if (curve[i] > peak) {
      peak = curve[i];
    }
    drawdowns[i] = (curve[i] - peak) / peak;
  }
  
  return drawdowns;
}

export function calculateSharpeRatio(returns: number[], riskFreeRateAnnual = 0.05): number {
  const cagr = calculateCAGR(returns);
  const vol = calculateVolatility(returns);
  if (vol === 0) return 0;
  return (cagr - riskFreeRateAnnual) / vol;
}

export function calculateSortinoRatio(returns: number[], riskFreeRateAnnual = 0.05): number {
  const cagr = calculateCAGR(returns);
  
  const rfMonthly = Math.pow(1 + riskFreeRateAnnual, 1/12) - 1;
  let downsideVariance = 0;
  for (let i = 0; i < returns.length; i++) {
    if (returns[i] < rfMonthly) {
      downsideVariance += Math.pow(returns[i] - rfMonthly, 2);
    }
  }
  downsideVariance = downsideVariance / returns.length;
  const downsideDev = Math.sqrt(downsideVariance) * Math.sqrt(12);
  
  if (downsideDev === 0) return 0;
  return (cagr - riskFreeRateAnnual) / downsideDev;
}

export function calculateBestWorstYear(returns: number[]): { best: number, worst: number } {
  if (returns.length < 12) return { best: 0, worst: 0 };
  
  let best = -Infinity;
  let worst = Infinity;
  
  for (let i = 11; i < returns.length; i++) {
    let yearReturn = 1.0;
    for (let j = 0; j < 12; j++) {
      yearReturn *= (1 + returns[i - j]);
    }
    yearReturn -= 1;
    
    if (yearReturn > best) best = yearReturn;
    if (yearReturn < worst) worst = yearReturn;
  }
  
  return { best: best === -Infinity ? 0 : best, worst: worst === Infinity ? 0 : worst };
}

// Basic XIRR implementation using Newton-Raphson
export function calculateXIRR(cashflows: number[], dates: Date[], guess = 0.1): number {
  if (cashflows.length !== dates.length || cashflows.length === 0) return 0;
  
  const xnpv = (rate: number) => {
    let result = 0;
    const d0 = dates[0].getTime();
    for (let i = 0; i < cashflows.length; i++) {
      const diffDays = (dates[i].getTime() - d0) / (1000 * 60 * 60 * 24);
      result += cashflows[i] / Math.pow(1 + rate, diffDays / 365.0);
    }
    return result;
  };

  const xnpvDerivative = (rate: number) => {
    let result = 0;
    const d0 = dates[0].getTime();
    for (let i = 0; i < cashflows.length; i++) {
      const diffDays = (dates[i].getTime() - d0) / (1000 * 60 * 60 * 24);
      const frac = diffDays / 365.0;
      result -= (frac * cashflows[i]) / Math.pow(1 + rate, frac + 1);
    }
    return result;
  };

  let rate = guess;
  for (let iter = 0; iter < 100; iter++) {
    const val = xnpv(rate);
    if (Math.abs(val) < 0.00001) return rate;
    const deriv = xnpvDerivative(rate);
    if (deriv === 0) break;
    rate = rate - (val / deriv);
  }
  
  return rate;
}
