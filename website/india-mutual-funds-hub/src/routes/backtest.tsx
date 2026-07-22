import { createFileRoute } from '@tanstack/react-router';
import { useMultiAssetData } from '@/hooks/useMultiAssetData';
import { useMemo, useState } from 'react';
import { simulatePortfolio, PortfolioWeights, RebalanceFrequency } from '@/engine/portfolio';
import { calculateCAGR, calculateVolatility, calculateMaxDrawdown, calculateSharpeRatio, calculateDrawdownCurve, calculateBestWorstYear } from '@/engine/statistics';
import { calculateSuccessProbabilities } from '@/engine/success_probability';
import { Slider } from '@/components/ui/slider';
import { Area, AreaChart, CartesianGrid, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, LineChart, Line, Cell } from 'recharts';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';

type BacktestSearch = {
  startYear?: number;
  endYear?: number;
  rebalance?: RebalanceFrequency;
  sip?: number;
} & Record<string, unknown>;

export const Route = createFileRoute('/backtest')({
  validateSearch: (search: Record<string, unknown>): BacktestSearch => {
    return {
      startYear: search.startYear ? Number(search.startYear) : 2008,
      endYear: search.endYear ? Number(search.endYear) : 2024,
      rebalance: (search.rebalance as RebalanceFrequency) || 'monthly',
      sip: search.sip ? Number(search.sip) : 10000,
      ...search
    };
  },
  component: BacktestPage,
});

const PORTFOLIO_COLORS: Record<string, string> = {
  a: '#2563eb', // Blue
  b: '#f97316', // Orange
  c: '#10b981', // Green
  d: '#8b5cf6', // Purple
};

function extractWeights(search: Record<string, unknown>, prefix: string): PortfolioWeights {
  const weights: PortfolioWeights = {};
  for (const key in search) {
    if (key.startsWith(`${prefix}_`)) {
      const assetId = key.substring(prefix.length + 1);
      weights[assetId] = Number(search[key]);
    }
  }
  return weights;
}

function BacktestPage() {
  const { data, isLoading, error } = useMultiAssetData();
  const search = Route.useSearch();
  const navigate = Route.useNavigate();

  // Determine active portfolios from URL (must have a_ or b_ etc)
  const activePortfolios = useMemo(() => {
    const ports = ['a', 'b', 'c', 'd'].filter(p => 
      Object.keys(search).some(k => k.startsWith(`${p}_`))
    );
    if (ports.length === 0) return ['a']; // Default to at least 'a'
    return ports;
  }, [search]);

  // Default to the first available portfolio if the active tab is removed
  const [activeTab, setActiveTab] = useState<string>(activePortfolios[0]);
  if (!activePortfolios.includes(activeTab)) {
    setActiveTab(activePortfolios[0]);
  }

  const startYear = search.startYear || 2008;
  const endYear = search.endYear || 2024;
  const rebalance = search.rebalance || 'monthly';
  const sip = search.sip || 10000;

  // Handle URL updates
  const updateWeights = (prefix: string, assetId: string, newValue: number) => {
    const currentWeights = extractWeights(search, prefix);
    if (Object.keys(currentWeights).length === 0) currentWeights['large_cap'] = 100;

    const oldVal = currentWeights[assetId] || 0;
    const diff = newValue - oldVal;
    let sumOthers = 0;
    
    Object.keys(currentWeights).forEach(k => {
      if (k !== assetId) sumOthers += currentWeights[k];
    });

    currentWeights[assetId] = newValue;

    if (sumOthers > 0) {
      Object.keys(currentWeights).forEach(k => {
        if (k !== assetId) {
          currentWeights[k] = Math.max(0, currentWeights[k] - diff * (currentWeights[k] / sumOthers));
        }
      });
    }

    // Normalize
    const currentSum = Object.values(currentWeights).reduce((val1, val2) => val1 + val2, 0);
    if (currentSum > 0 && currentSum !== 100) {
      Object.keys(currentWeights).forEach(k => currentWeights[k] = (currentWeights[k] / currentSum) * 100);
    }

    // Reconstruct search object by keeping all other prefixes intact
    const newSearch: Record<string, unknown> = { startYear, endYear, rebalance, sip };
    Object.keys(search).forEach(k => {
      if (!k.startsWith(`${prefix}_`) && !['startYear', 'endYear', 'rebalance', 'sip'].includes(k)) {
        newSearch[k] = search[k];
      }
    });
    
    // Add NEW weights
    Object.keys(currentWeights).forEach(k => {
      newSearch[`${prefix}_${k}`] = currentWeights[k];
    });

    navigate({ search: newSearch, replace: true });
  };

  const addAsset = (prefix: string, assetId: string) => {
    const currentWeights = extractWeights(search, prefix);
    if (!currentWeights[assetId]) {
      currentWeights[assetId] = 0;
      updateWeights(prefix, assetId, 10);
    }
  };

  const removeAsset = (prefix: string, assetId: string) => {
    const currentWeights = extractWeights(search, prefix);
    if (Object.keys(currentWeights).length <= 1) return; // Must have at least 1
    
    delete currentWeights[assetId];
    
    // Normalize remaining to 100
    const sum = Object.values(currentWeights).reduce((val1, val2) => val1 + val2, 0);
    if (sum > 0) {
      Object.keys(currentWeights).forEach(k => currentWeights[k] = (currentWeights[k] / sum) * 100);
    }

    const newSearch: Record<string, unknown> = { startYear, endYear, rebalance, sip };
    Object.keys(search).forEach(k => {
      if (!k.startsWith(`${prefix}_`) && !['startYear', 'endYear', 'rebalance', 'sip'].includes(k)) {
        newSearch[k] = search[k];
      }
    });
    Object.keys(currentWeights).forEach(k => newSearch[`${prefix}_${k}`] = currentWeights[k]);
    navigate({ search: newSearch, replace: true });
  };

  const addPortfolio = () => {
    const available = ['a', 'b', 'c', 'd'].find(p => !activePortfolios.includes(p));
    if (available) {
      updateWeights(available, 'large_cap', 100);
      setActiveTab(available);
    }
  };

  const removePortfolio = (prefix: string) => {
    if (activePortfolios.length <= 1) return;
    const newSearch: Record<string, unknown> = { startYear, endYear, rebalance, sip };
    Object.keys(search).forEach(k => {
      if (!k.startsWith(`${prefix}_`) && !['startYear', 'endYear', 'rebalance', 'sip'].includes(k)) {
        newSearch[k] = search[k];
      }
    });
    navigate({ search: newSearch, replace: true });
  };

  const updateParam = (key: string, val: string | number) => {
    navigate({ search: (prev: any) => ({ ...prev, [key]: val }), replace: true });
  };

  // The Engine
  const engineResults = useMemo(() => {
    if (!data || !data.returnsDict) return null;

    // Filter by Time Horizon
    const startIndex = data.dates.findIndex(d => d.startsWith(startYear.toString()));
    const rawEndIndex = data.dates.findIndex(d => d.startsWith(endYear.toString()));
    
    let endIndex = data.dates.length - 1;
    if (rawEndIndex !== -1) {
       for(let i = rawEndIndex; i < data.dates.length; i++) {
           if(data.dates[i].startsWith(endYear.toString())) {
               endIndex = i;
           } else {
               break;
           }
       }
    }
    
    const actualStart = startIndex !== -1 ? startIndex : 0;
    const actualEnd = endIndex !== -1 ? endIndex : data.dates.length - 1;
    const slicedDates = data.dates.slice(actualStart, actualEnd + 1);
    const numMonths = slicedDates.length;

    const slicedDict: Record<string, number[]> = {};
    Object.keys(data.returnsDict).forEach(k => {
      slicedDict[k] = data.returnsDict[k].slice(actualStart, actualEnd + 1);
    });

    const formatAttribution = (contributions: Record<string, number>, finalValue: number) => {
      const totalGrowth = finalValue - 10000 - (sip * numMonths); // simple proxy
      return Object.keys(contributions).map(k => ({
        asset: data.assetInfo[k]?.display_name || k,
        growth: contributions[k],
        pct: totalGrowth === 0 ? 0 : (contributions[k] / totalGrowth) * 100
      })).sort((val1,val2) => val2.growth - val1.growth);
    };

    // Run Engine dynamically for all active portfolios
    const resultsMap: Record<string, any> = {};
    const chartData = slicedDates.map(d => ({ date: d.substring(0, 7) })) as any[];

    activePortfolios.forEach(p => {
      let w = extractWeights(search, p);
      if (Object.keys(w).length === 0) w = { large_cap: 100 };
      
      const port = simulatePortfolio(slicedDict, w, numMonths, rebalance, 10000, sip);
      const dd = calculateDrawdownCurve(port.equityCurve);
      
      resultsMap[p] = {
        weights: w,
        port,
        stats: {
          cagr: calculateCAGR(port.blendedReturns),
          vol: calculateVolatility(port.blendedReturns),
          mdd: calculateMaxDrawdown(port.equityCurve),
          sharpe: calculateSharpeRatio(port.blendedReturns),
          bw: calculateBestWorstYear(port.blendedReturns)
        },
        attrib: formatAttribution(port.contributions, port.equityCurve[numMonths - 1]),
        successProbs: calculateSuccessProbabilities(port.blendedReturns)
      };

      // Populate chart data
      for (let i = 0; i < numMonths; i++) {
        chartData[i][`portfolio_${p}`] = port.equityCurve[i];
        chartData[i][`drawdown_${p}`] = dd[i] * 100;
      }
    });

    return {
      slicedDates,
      chartData,
      resultsMap
    };
  }, [data, search, startYear, endYear, rebalance, sip, activePortfolios]);

  if (isLoading) return <div className="p-10 text-center">Loading Quant Engine...</div>;
  if (error || !data) return <div className="p-10 text-center text-red-500">Error loading data.</div>;

  const currentWeights = engineResults?.resultsMap[activeTab]?.weights || { large_cap: 100 };
  const availableAssets = Object.keys(data.assetInfo).filter(id => !currentWeights[id]);
  const activeStats = engineResults?.resultsMap[activeTab];

  return (
    <div className="mx-auto max-w-[1400px] px-6 py-10">
      <div className="mb-8 flex justify-between items-end">
        <div>
          <h1 className="font-display text-3xl tracking-tight mb-2">Multi-Asset Backtester</h1>
          <p className="text-muted-foreground">Compare custom allocations across actual historical regimes.</p>
        </div>
        
        {/* Global Controls */}
        <div className="flex gap-4 items-center bg-surface-2 p-3 rounded-md border hairline">
          <div className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-widest text-muted-foreground">Horizon</span>
            <div className="flex gap-2">
              <input type="number" value={startYear} onChange={e => updateParam('startYear', e.target.value)} className="w-16 bg-background border px-2 py-1 text-xs rounded" />
              <span className="text-muted-foreground">-</span>
              <input type="number" value={endYear} onChange={e => updateParam('endYear', e.target.value)} className="w-16 bg-background border px-2 py-1 text-xs rounded" />
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-widest text-muted-foreground">Rebalance</span>
            <Select value={rebalance} onValueChange={(val) => updateParam('rebalance', val)}>
              <SelectTrigger className="w-[120px] h-7 text-xs bg-background"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="never">Never</SelectItem>
                <SelectItem value="annual">Annual</SelectItem>
                <SelectItem value="quarterly">Quarterly</SelectItem>
                <SelectItem value="monthly">Monthly</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-widest text-muted-foreground">Monthly SIP</span>
            <input type="number" value={sip} onChange={e => updateParam('sip', e.target.value)} className="w-24 bg-background border px-2 py-1 text-xs rounded" />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Sidebar: Builder */}
        <div className="lg:col-span-3 space-y-6">
          <Tabs value={activeTab} onValueChange={(v: any) => setActiveTab(v)}>
            <div className="flex gap-2 mb-2">
              <TabsList className="w-full flex">
                {activePortfolios.map(p => (
                  <TabsTrigger key={p} value={p} className="flex-1 uppercase font-mono text-xs">
                    <span style={{color: PORTFOLIO_COLORS[p]}}>●</span> {p}
                  </TabsTrigger>
                ))}
              </TabsList>
              {activePortfolios.length < 4 && (
                <button onClick={addPortfolio} className="px-3 bg-surface-2 border hairline rounded-sm text-xs text-muted-foreground hover:text-foreground">
                  +
                </button>
              )}
            </div>
            
            <div className="mt-6 bg-surface-2 border hairline p-4 rounded-sm">
              <div className="flex justify-between items-center mb-4">
                <h3 className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Allocation (Port {activeTab.toUpperCase()})</h3>
                {activePortfolios.length > 1 && (
                  <button onClick={() => removePortfolio(activeTab)} className="text-[10px] text-red-500 hover:underline">Remove Portfolio</button>
                )}
              </div>
              
              {Object.keys(currentWeights).map(asset => (
                <div key={asset} className="mb-4">
                  <div className="flex justify-between text-sm mb-2 items-center">
                    <span className="truncate pr-2">{data.assetInfo[asset]?.display_name || asset}</span>
                    <div className="flex gap-2 items-center shrink-0">
                      <span className="font-mono">{currentWeights[asset]?.toFixed(1)}%</span>
                      <button onClick={() => removeAsset(activeTab, asset)} className="text-muted-foreground hover:text-red-500 text-xs">✕</button>
                    </div>
                  </div>
                  <Slider 
                    value={[currentWeights[asset] || 0]} 
                    min={0} max={100} step={1}
                    onValueChange={(val) => updateWeights(activeTab, asset, val[0])}
                  />
                </div>
              ))}

              {availableAssets.length > 0 && (
                <div className="mt-4 pt-4 border-t hairline">
                  <Select key={availableAssets.join(',')} onValueChange={(val) => addAsset(activeTab, val)}>
                    <SelectTrigger className="w-full text-xs text-muted-foreground bg-surface-2"><SelectValue placeholder="+ Add Asset Class" /></SelectTrigger>
                    <SelectContent>
                      {availableAssets.map(a => <SelectItem key={a} value={a}>{data.assetInfo[a].display_name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          </Tabs>

          <div className="p-4 bg-surface-2 rounded-sm border hairline">
            <h3 className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground mb-4">Statistics Comparison</h3>
            {engineResults && (
              <div className="space-y-4 font-mono text-sm tabular-nums">
                <div className="flex justify-between items-center border-b border-hairline pb-2">
                  <span className="text-muted-foreground text-xs uppercase">Metric</span>
                  <div className="flex gap-4">
                    {activePortfolios.map(p => (
                      <span key={p} className="w-12 text-right" style={{color: PORTFOLIO_COLORS[p]}}>P{p.toUpperCase()}</span>
                    ))}
                  </div>
                </div>
                {[
                  { label: 'CAGR', key: 'cagr', fmt: (val: number) => (val * 100).toFixed(1)+'%' },
                  { label: 'Vol', key: 'vol', fmt: (val: number) => (val * 100).toFixed(1)+'%' },
                  { label: 'Max DD', key: 'mdd', fmt: (val: number) => (val * 100).toFixed(1)+'%' },
                  { label: 'Sharpe', key: 'sharpe', fmt: (val: number) => val.toFixed(2) },
                ].map(stat => (
                  <div key={stat.label} className="flex justify-between">
                    <span>{stat.label}</span>
                    <div className="flex gap-4">
                      {activePortfolios.map(p => {
                        const val = engineResults.resultsMap[p]?.stats[stat.key];
                        return <span key={p} className="w-12 text-right">{val !== undefined ? stat.fmt(val) : '—'}</span>;
                      })}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Main Content: Charts */}
        <div className="lg:col-span-9 space-y-8">
          {engineResults && (
            <>
              {/* Growth Curve */}
              <div className="h-[400px]">
                <h3 className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground mb-4">Portfolio Value (₹)</h3>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={engineResults.chartData} margin={{ top: 10, right: 0, left: 0, bottom: 0 }}>
                    <defs>
                      {activePortfolios.map(p => (
                        <linearGradient key={`grad_${p}`} id={`color_${p}`} x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={PORTFOLIO_COLORS[p]} stopOpacity={0.3}/>
                          <stop offset="95%" stopColor={PORTFOLIO_COLORS[p]} stopOpacity={0}/>
                        </linearGradient>
                      ))}
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#333" opacity={0.2} />
                    <XAxis dataKey="date" tick={{fontSize: 10}} tickMargin={10} minTickGap={30} />
                    <YAxis tick={{fontSize: 10}} domain={['auto', 'auto']} tickFormatter={(val) => '₹'+(val/1000).toFixed(0)+'k'} />
                    <Tooltip contentStyle={{ fontSize: '12px', fontFamily: 'monospace' }} formatter={(val: number) => '₹'+val.toLocaleString(undefined, {maximumFractionDigits:0})} />
                    
                    {activePortfolios.map(p => (
                      <Area key={`area_${p}`} type="monotone" dataKey={`portfolio_${p}`} name={`Port ${p.toUpperCase()}`} stroke={PORTFOLIO_COLORS[p]} fillOpacity={1} fill={`url(#color_${p})`} />
                    ))}
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Drawdown Curve */}
                <div className="h-[200px]">
                  <h3 className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground mb-4">Historical Drawdown</h3>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={engineResults.chartData} margin={{ top: 10, right: 0, left: 0, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#333" opacity={0.2} />
                      <XAxis dataKey="date" tick={{fontSize: 10}} hide />
                      <YAxis tick={{fontSize: 10}} domain={['auto', 0]} tickFormatter={(val) => val.toFixed(0)+'%'} />
                      <Tooltip contentStyle={{ fontSize: '12px', fontFamily: 'monospace' }} />
                      
                      {activePortfolios.map((p, i) => (
                        <Line key={`dd_${p}`} type="monotone" dataKey={`drawdown_${p}`} name={`Port ${p.toUpperCase()} DD`} stroke={PORTFOLIO_COLORS[p]} dot={false} strokeWidth={i === 0 ? 2 : 1} strokeDasharray={i === 0 ? undefined : "5 5"} />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                
                {/* Attribution (Active Tab Only) */}
                <div className="h-[200px]">
                  <h3 className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground mb-4">Asset Contribution (Port {activeTab.toUpperCase()})</h3>
                  {activeStats && (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={activeStats.attrib} layout="vertical" margin={{ top: 0, right: 0, left: 50, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#333" opacity={0.2} />
                        <XAxis type="number" tick={{fontSize: 10}} tickFormatter={(val) => '₹'+(val/1000).toFixed(0)+'k'} />
                        <YAxis dataKey="asset" type="category" tick={{fontSize: 10}} width={120} />
                        <Tooltip contentStyle={{ fontSize: '12px', fontFamily: 'monospace' }} formatter={(val: number) => '₹'+val.toLocaleString(undefined, {maximumFractionDigits:0})} />
                        <Bar dataKey="growth" radius={[0, 4, 4, 0]}>
                          {activeStats.attrib.map((entry: any, index: number) => (
                            <Cell key={`cell-${index}`} fill={entry.growth > 0 ? PORTFOLIO_COLORS[activeTab] : "#ef4444"} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>

              {/* Success Probability (Active Tab Only) */}
              <div>
                <h3 className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground mb-4">Historical Success Probability (Port {activeTab.toUpperCase()})</h3>
                {activeStats && (
                  <div className="grid grid-cols-4 gap-4">
                    {activeStats.successProbs.map((sp: any) => (
                      <div key={sp.horizon} className="p-4 bg-surface-2 rounded-sm border hairline text-center">
                        <div className="text-muted-foreground text-xs mb-1">{sp.horizon} Horizon</div>
                        <div className="text-2xl font-mono tabular-nums" style={{color: PORTFOLIO_COLORS[activeTab]}}>
                          {sp.probability !== null ? `${sp.probability.toFixed(0)}%` : 'N/A'}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              
            </>
          )}
        </div>
      </div>
    </div>
  );
}
