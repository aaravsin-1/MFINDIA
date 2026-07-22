/**
 * Pure JS Engine for calculating correlation matrices.
 */

export interface AssetReturns {
  [assetId: string]: number[];
}

function calculateMean(arr: number[]): number {
  return arr.reduce((sum, val) => sum + val, 0) / arr.length;
}

function calculateStandardDeviation(arr: number[], mean: number): number {
  const variance = arr.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / arr.length;
  return Math.sqrt(variance);
}

function calculateCovariance(arr1: number[], mean1: number, arr2: number[], mean2: number): number {
  let cov = 0;
  for (let i = 0; i < arr1.length; i++) {
    cov += (arr1[i] - mean1) * (arr2[i] - mean2);
  }
  return cov / arr1.length;
}

/**
 * Calculates a Pearson correlation matrix for a dictionary of asset returns.
 */
export function calculateCorrelationMatrix(returnsDict: AssetReturns, activeAssets: string[]): number[][] {
  const n = activeAssets.length;
  const matrix: number[][] = Array(n).fill(0).map(() => Array(n).fill(0));
  
  if (n === 0) return matrix;
  
  // Precompute means and standard deviations
  const means: number[] = new Array(n);
  const stds: number[] = new Array(n);
  const arrays: number[][] = new Array(n);
  
  for (let i = 0; i < n; i++) {
    const assetId = activeAssets[i];
    const arr = returnsDict[assetId] || [];
    arrays[i] = arr;
    
    if (arr.length > 0) {
      means[i] = calculateMean(arr);
      stds[i] = calculateStandardDeviation(arr, means[i]);
    } else {
      means[i] = 0;
      stds[i] = 0;
    }
  }
  
  // Build correlation matrix
  for (let i = 0; i < n; i++) {
    for (let j = i; j < n; j++) {
      if (i === j) {
        matrix[i][j] = 1.0;
      } else {
        const arr1 = arrays[i];
        const arr2 = arrays[j];
        
        // Ensure same length
        const minLen = Math.min(arr1.length, arr2.length);
        if (minLen === 0 || stds[i] === 0 || stds[j] === 0) {
          matrix[i][j] = 0;
          matrix[j][i] = 0;
        } else {
          const slice1 = arr1.slice(-minLen);
          const slice2 = arr2.slice(-minLen);
          const m1 = calculateMean(slice1);
          const m2 = calculateMean(slice2);
          const s1 = calculateStandardDeviation(slice1, m1);
          const s2 = calculateStandardDeviation(slice2, m2);
          
          if (s1 === 0 || s2 === 0) {
            matrix[i][j] = 0;
            matrix[j][i] = 0;
          } else {
            const cov = calculateCovariance(slice1, m1, slice2, m2);
            const corr = cov / (s1 * s2);
            matrix[i][j] = corr;
            matrix[j][i] = corr;
          }
        }
      }
    }
  }
  
  return matrix;
}
