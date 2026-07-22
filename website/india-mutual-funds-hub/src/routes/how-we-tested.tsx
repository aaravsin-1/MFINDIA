import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import { Section, Card } from "@/components/ui-bits";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

const sb = supabase as any;

export const Route = createFileRoute("/how-we-tested")({
  head: () => ({
    meta: [
      { title: "How we tested it — FundLens" },
      { name: "description", content: "The 12 findings, the negative-control test, and where selection skill lives." },
    ],
  }),
  component: HowTested,
});

type Metric = { metric: string; value: string; unit: string | null; label: string | null; group: string | null };
type Research = { id: number; code: string; verdict: string; title: string; finding: string; reference: string };
type CatSum = { category: string; selection_edge_pct: number | null };

const evidenceData = [
  { year: "2016", lumpPort: 35.7, lumpBench: 32.7, sipPort: 10.6, sipBench: 9.0, funds: { Large: "Nippon India, SBI", Mid: "Axis, DSP", Small: "Aditya Birla, Axis", Flexi: "BANDHAN, HSBC", ELSS: "DSP, ICICI Pru" } },
  { year: "2017", lumpPort: 24.2, lumpBench: 22.4, sipPort: 30.4, sipBench: 28.4, funds: { Large: "Axis, DSP", Mid: "Invesco India, Kotak", Small: "Kotak, Sundaram", Flexi: "DSP, Motilal Oswal", ELSS: "DSP, UTI" } },
  { year: "2018", lumpPort: 90.3, lumpBench: 84.2, sipPort: 59.2, sipBench: 56.7, funds: { Large: "JM, Kotak", Mid: "Aditya Birla, Tata", Small: "Axis, Union", Flexi: "DSP, HSBC", ELSS: "ICICI Pru, SBI" } },
  { year: "2019", lumpPort: 107.7, lumpBench: 67.5, sipPort: 49.4, sipBench: 35.8, funds: { Large: "JM, Union", Mid: "PGIM India, quant", Small: "Axis, quant", Flexi: "LIC MF, quant", ELSS: "Edelweiss, quant" } },
  { year: "2020", lumpPort: 100.4, lumpBench: 88.7, sipPort: 39.4, sipBench: 38.4, funds: { Large: "Groww, LIC MF", Mid: "Axis, PGIM India", Small: "Aditya Birla, quant", Flexi: "CANARA ROBECO, quant", ELSS: "Groww, quant" } },
  { year: "2021", lumpPort: 70.8, lumpBench: 66.7, sipPort: 42.0, sipBench: 41.7, funds: { Large: "Groww, Nippon India", Mid: "HDFC, SBI", Small: "Aditya Birla, Franklin India", Flexi: "CANARA ROBECO, quant", ELSS: "Nippon India, Shriram" } },
  { year: "2022", lumpPort: 80.8, lumpBench: 72.4, sipPort: 26.1, sipBench: 23.9, funds: { Large: "Franklin India, HDFC", Mid: "HDFC, Kotak", Small: "Franklin India, HDFC", Flexi: "HDFC, HSBC", ELSS: "ITI, JM" } },
  { year: "2023*", lumpPort: 18.7, lumpBench: 21.3, sipPort: 4.6, sipBench: 4.6, funds: { Large: "JM, Union", Mid: "Union, ICICI Prudential", Small: "UTI, SBI", Flexi: "JM, quant", ELSS: "Groww, Shriram" } },
  { year: "2024*", lumpPort: 7.7, lumpBench: 7.3, sipPort: 4.1, sipBench: 2.7, funds: { Large: "PGIM India, HSBC", Mid: "Mahindra Manulife, BARODA BNP PARIBAS", Small: "PGIM India, Union", Flexi: "Samco, JM", ELSS: "Shriram, PGIM India" } },
  { year: "2025*", lumpPort: 1.8, lumpBench: 1.0, sipPort: 3.2, sipBench: 2.7, funds: { Large: "WhiteOak Capital, Mahindra Manulife", Mid: "JM, BANDHAN", Small: "PGIM India, Mahindra Manulife", Flexi: "Samco, Sundaram", ELSS: "Groww, Shriram" } },
];

const benchmarkSummaryData = [
  { name: "Nifty 50", cagr: 16.07, alpha: "+7.53%" },
  { name: "Sensex", cagr: 16.32, alpha: "+7.28%" },
  { name: "Nifty 500", cagr: 17.30, alpha: "+6.31%" },
  { name: "Top-Picks", cagr: 23.60, alpha: "—" },
];

const benchmarkComparisonData = [
  { year: 2016, port: 35.7, nifty50: 42.1, sensex: 49.2, nifty500: 33.8 },
  { year: 2017, port: 24.2, nifty50: 26.8, sensex: 32.8, nifty500: 18.8 },
  { year: 2018, port: 90.3, nifty50: 60.2, sensex: 60.7, nifty500: 66.6 },
  { year: 2019, port: 107.7, nifty50: 51.4, sensex: 49.4, nifty500: 56.7 },
  { year: 2020, port: 100.4, nifty50: 59.4, sensex: 56.1, nifty500: 71.9 },
  { year: 2021, port: 70.8, nifty50: 36.4, sensex: 34.7, nifty500: 50.0 },
  { year: 2022, port: 80.8, nifty50: 47.9, sensex: 43.1, nifty500: 59.8 },
];

const alphaFadeData = [
  { year: 2016, y1: -0.14, y2: 0.18, y3: 3.84, y4: 0.10, y5: 0.68, y6: -1.89, y7: -6.30 },
  { year: 2017, y1: -1.94, y2: 2.18, y3: 2.32, y4: 1.43, y5: -1.80, y6: -3.27, y7: 4.87 },
  { year: 2018, y1: 2.80, y2: 2.36, y3: 5.52, y4: 4.35, y5: 13.19, y6: 13.35, y7: 17.66 },
  { year: 2019, y1: 12.83, y2: 33.57, y3: 38.64, y4: 62.46, y5: 55.47, y6: 49.56, y7: null },
  { year: 2020, y1: 9.45, y2: 9.37, y3: 14.78, y4: 7.28, y5: 5.62, y6: null, y7: null },
  { year: 2021, y1: 1.85, y2: 7.05, y3: 2.83, y4: 3.18, y5: null, y6: null, y7: null },
  { year: 2022, y1: 4.78, y2: 6.60, y3: 8.46, y4: null, y5: null, y6: null, y7: null },
];

function Evidence() {
  return (
    <Card className="p-6 mb-10">
      <div className="section-marker mb-3">◆ Evidence: 3-Year Holding Period</div>
      <p className="text-sm text-muted-foreground mb-6">
        What happens if you bought the model's top 2 picks in each category and held them for exactly 3 years without rebalancing? Here is the actual outperformance (alpha) against an equal-weight category benchmark.
      </p>
      
      <div className="overflow-x-auto mb-8">
        <table className="w-full text-left text-[13px] whitespace-nowrap">
          <thead>
            <tr className="border-b border-hairline text-muted-foreground">
              <th className="pb-3 font-medium">Cohort</th>
              <th className="pb-3 font-medium text-right">Lumpsum (Port)</th>
              <th className="pb-3 font-medium text-right">Lumpsum (Bench)</th>
              <th className="pb-3 font-medium text-right text-foreground">Alpha</th>
              <th className="pb-3 font-medium text-right pl-6">SIP (Port)</th>
              <th className="pb-3 font-medium text-right">SIP (Bench)</th>
              <th className="pb-3 font-medium text-right text-foreground">Alpha</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-hairline">
            {evidenceData.filter((row) => !String(row.year).includes('*')).map((row) => (
              <tr key={row.year} className="hover:bg-surface-2/50 transition-colors">
                <td className="py-3 font-mono">{row.year}</td>
                <td className="py-3 text-right">{row.lumpPort.toFixed(1)}%</td>
                <td className="py-3 text-right text-muted-foreground">{row.lumpBench.toFixed(1)}%</td>
                <td className="py-3 text-right text-good font-medium">+{((row.lumpPort - row.lumpBench)).toFixed(1)}%</td>
                <td className="py-3 text-right pl-6">{row.sipPort.toFixed(1)}%</td>
                <td className="py-3 text-right text-muted-foreground">{row.sipBench.toFixed(1)}%</td>
                <td className="py-3 text-right text-good font-medium">+{((row.sipPort - row.sipBench)).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="section-marker mb-3 mt-8">◆ Historical Cohort Portfolios</div>
      <p className="text-xs text-muted-foreground mb-4">Click to expand and see the exact top 2 funds per category recommended in January of each year.</p>
      <div className="space-y-2 mb-10">
        {evidenceData.map((row) => (
          <details key={row.year} className="hairline rounded-md bg-card group [&_summary::-webkit-details-marker]:hidden">
            <summary className="cursor-pointer p-4 flex items-center gap-3 list-none font-mono text-sm">
              <span className="text-muted-foreground text-xs transition-transform group-open:rotate-90">▶</span> <span className="text-foreground">{row.year} Cohort</span>
            </summary>
            <div className="p-4 pt-0 text-xs text-muted-foreground leading-relaxed grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-3">
              <div><strong className="text-foreground font-medium uppercase tracking-widest text-[10px]">Large Cap:</strong> {row.funds.Large}</div>
              <div><strong className="text-foreground font-medium uppercase tracking-widest text-[10px]">Mid Cap:</strong> {row.funds.Mid}</div>
              <div><strong className="text-foreground font-medium uppercase tracking-widest text-[10px]">Small Cap:</strong> {row.funds.Small}</div>
              <div><strong className="text-foreground font-medium uppercase tracking-widest text-[10px]">Flexi Cap:</strong> {row.funds.Flexi}</div>
              <div className="md:col-span-2"><strong className="text-foreground font-medium uppercase tracking-widest text-[10px]">ELSS:</strong> {row.funds.ELSS}</div>
            </div>
          </details>
        ))}
      </div>

      <div className="section-marker mb-3 mt-12">◆ Broader Benchmarks (Nifty 50, Sensex & Nifty 500)</div>
      <p className="text-sm text-muted-foreground mb-4">
        Because our model's picks are equally weighted across 5 categories, the portfolio intrinsically has ~40% exposure to Mid & Small Caps. Nifty 50 and Sensex are purely large-cap indices, making the broad-market <strong>Nifty 500</strong> the most accurate benchmark. Here is how the Top-Picks performed against all three major indices over strict 3-year holding periods (without rebalancing).
      </p>

      <div className="overflow-x-auto mb-8">
        <table className="w-full text-left text-[13px] whitespace-nowrap">
          <thead>
            <tr className="border-b border-hairline text-muted-foreground">
              <th className="pb-3 font-medium">Cohort</th>
              <th className="pb-3 font-medium text-right text-foreground">Top-Picks (3-Yr Hold)</th>
              <th className="pb-3 font-medium text-right">Nifty 50</th>
              <th className="pb-3 font-medium text-right">Sensex</th>
              <th className="pb-3 font-medium text-right">Nifty 500</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-hairline">
            {benchmarkComparisonData.map((row) => (
              <tr key={row.year} className="hover:bg-surface-2/50 transition-colors">
                <td className="py-2 font-mono">{row.year}</td>
                <td className="py-2 text-right text-good font-medium">{row.port.toFixed(1)}%</td>
                <td className="py-2 text-right text-muted-foreground">{row.nifty50.toFixed(1)}%</td>
                <td className="py-2 text-right text-muted-foreground">{row.sensex.toFixed(1)}%</td>
                <td className="py-2 text-right text-muted-foreground">{row.nifty500.toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="section-marker mb-3 mt-8">◆ Holding Beyond 3 Years (Alpha Fade)</div>
      <p className="text-sm text-muted-foreground mb-4">
        If you buy the top funds and hold them indefinitely without rebalancing, does the outperformance continue compounding? Our extended holding simulations (up to 7 years) reveal that the model's alpha tends to peak around Year 3 or Year 4, after which mean reversion kicks in and the edge begins to fade.
      </p>

      <div className="overflow-x-auto mb-6">
        <table className="w-full text-left text-[13px] whitespace-nowrap">
          <thead>
            <tr className="border-b border-hairline text-muted-foreground">
              <th className="pb-3 font-medium">Cohort</th>
              <th className="pb-3 font-medium text-right">Yr 1</th>
              <th className="pb-3 font-medium text-right">Yr 2</th>
              <th className="pb-3 font-medium text-right text-foreground">Yr 3</th>
              <th className="pb-3 font-medium text-right">Yr 4</th>
              <th className="pb-3 font-medium text-right">Yr 5</th>
              <th className="pb-3 font-medium text-right">Yr 6</th>
              <th className="pb-3 font-medium text-right">Yr 7</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-hairline">
            {alphaFadeData.map((row) => (
              <tr key={row.year} className="hover:bg-surface-2/50 transition-colors">
                <td className="py-2 font-mono">{row.year}</td>
                <td className={`py-2 text-right ${row.y1 !== null && row.y1 > 0 ? "text-good" : row.y1 !== null ? "text-caution" : "text-muted-foreground"}`}>{row.y1 !== null ? `${row.y1 > 0 ? '+' : ''}${row.y1.toFixed(2)}%` : '—'}</td>
                <td className={`py-2 text-right ${row.y2 !== null && row.y2 > 0 ? "text-good" : row.y2 !== null ? "text-caution" : "text-muted-foreground"}`}>{row.y2 !== null ? `${row.y2 > 0 ? '+' : ''}${row.y2.toFixed(2)}%` : '—'}</td>
                <td className="py-2 text-right text-foreground font-medium bg-surface-2/30">{row.y3 !== null ? `${row.y3 > 0 ? '+' : ''}${row.y3.toFixed(2)}%` : '—'}</td>
                <td className={`py-2 text-right ${row.y4 !== null && row.y4 > 0 ? "text-good" : row.y4 !== null ? "text-caution" : "text-muted-foreground"}`}>{row.y4 !== null ? `${row.y4 > 0 ? '+' : ''}${row.y4.toFixed(2)}%` : '—'}</td>
                <td className={`py-2 text-right ${row.y5 !== null && row.y5 > 0 ? "text-good" : row.y5 !== null ? "text-caution" : "text-muted-foreground"}`}>{row.y5 !== null ? `${row.y5 > 0 ? '+' : ''}${row.y5.toFixed(2)}%` : '—'}</td>
                <td className={`py-2 text-right ${row.y6 !== null && row.y6 > 0 ? "text-good" : row.y6 !== null ? "text-caution" : "text-muted-foreground"}`}>{row.y6 !== null ? `${row.y6 > 0 ? '+' : ''}${row.y6.toFixed(2)}%` : '—'}</td>
                <td className={`py-2 text-right ${row.y7 !== null && row.y7 > 0 ? "text-good" : row.y7 !== null ? "text-caution" : "text-muted-foreground"}`}>{row.y7 !== null ? `${row.y7 > 0 ? '+' : ''}${row.y7.toFixed(2)}%` : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-5 space-y-3 text-[11px] text-muted-foreground border-t border-hairline pt-4">
        <p><strong className="text-foreground font-medium">Simulation Details & Assumptions:</strong></p>
        <ul className="list-disc pl-4 space-y-1">
          <li><strong>Allocation:</strong> The portfolio is equally weighted across 5 core categories (Large, Mid, Small, Flexi, ELSS) at 20% each. Within each category, the capital is split equally between the top 2 recommended funds (10% per fund).</li>
          <li><strong>Lumpsum:</strong> Simulates a single bulk investment made on Jan 1st of the cohort year, held for exactly 36 months. Returns shown are absolute point-to-point growth.</li>
          <li><strong>SIP (Systematic Investment Plan):</strong> Simulates a fixed monthly investment (e.g., ₹10,000) made on the 1st of every month for 36 months. Returns shown are the absolute profit percentage on the total invested capital at the end of the period.</li>
          <li><strong>Benchmark:</strong> An equal-weighted basket of <em>all</em> active funds in those 5 core categories during the same period.</li>
          <li><strong>Taxes & Fees:</strong> All returns are calculated using Direct Plan NAVs (net of fund expenses) but before capital gains tax.</li>
          <li><strong>* Unfinished Cohorts:</strong> The 2023, 2024, and 2025 cohorts have not yet completed their full 3-year holding period, so their partial returns are excluded from the performance table above.</li>
        </ul>
      </div>
    </Card>
  );
}

function HowTested() {
  const metrics = useQuery({
    queryKey: ["all_metrics"],
    queryFn: async () => {
      const { data } = await sb.from("engine_metrics").select("*");
      return (data ?? []) as Metric[];
    },
  });
  const research = useQuery({
    queryKey: ["research_log_all"],
    queryFn: async () => {
      const { data } = await sb.from("research_log").select("*").order("id");
      return (data ?? []) as Research[];
    },
  });
  const cats = useQuery({
    queryKey: ["cat_edge"],
    queryFn: async () => {
      const { data } = await sb.from("category_summary").select("category,selection_edge_pct");
      return ((data ?? []) as CatSum[]).filter((c) => c.selection_edge_pct != null);
    },
  });

  const groups = ["performance", "significance", "product"];

  return (
    <Section eyebrow="VALIDATION" title="Model validation & controls">
      <p className="text-muted-foreground mb-10 max-w-2xl text-[14px]">
        The category-neutral model passes its fake-data negative control. The tables below list the underlying research
        checks — construction, significance, and product-level sanity — without claiming any live return figure.
      </p>

      {groups.map((g) => {
        const items = (metrics.data ?? []).filter((m) => m.group === g);
        if (items.length === 0) return null;
        return (
          <div key={g} className="mb-8">
            <div className="tag mb-3 uppercase">{g}</div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-hairline hairline rounded-md overflow-hidden">
              {items.map((m) => (
                <div key={m.metric} className="p-5 bg-card">
                  <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{m.metric.replace(/_/g, " ")}</div>
                  <div className="font-display text-3xl mt-2">{m.value}{m.unit ? <span className="text-lg text-muted-foreground">{m.unit}</span> : null}</div>
                  {m.label && <div className="text-xs text-muted-foreground mt-2">{m.label}</div>}
                </div>
              ))}
            </div>
          </div>
        );
      })}

      {cats.data && cats.data.length > 0 && (
        <Card className="p-6 mb-10">
          <div className="section-marker mb-3">◆ Model separation by category</div>
          <p className="text-xs text-muted-foreground mb-4">Where the within-category ranking model separates funds most cleanly. Dispersion is naturally larger in small-cap than large-cap peer sets.</p>
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={cats.data} margin={{ top: 5, right: 10, bottom: 20, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--hairline)" />
                <XAxis dataKey="category" tick={{ fill: "var(--muted-foreground)", fontSize: 10 }} />
                <YAxis tick={{ fill: "var(--muted-foreground)", fontSize: 10 }} unit="%" />
                <Tooltip contentStyle={{ background: "var(--surface-2)", border: "1px solid var(--hairline)", borderRadius: 2, fontSize: 12 }} />
                <Bar dataKey="selection_edge_pct" fill="var(--brand)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}

      <Evidence />
      <FullStrategySimulation />

      <h2 className="font-display text-2xl mb-4 mt-16">Research log</h2>
      <div className="space-y-2">
        {research.data?.map((r) => (
          <details key={r.id} className="hairline rounded-md bg-card group">
            <summary className="cursor-pointer p-4 flex items-center gap-3 list-none">
              <span className="font-mono text-xs text-muted-foreground w-8">{r.code}</span>
              <span className="text-sm flex-1">{r.title}</span>
              <VerdictChip v={r.verdict} />
            </summary>
            <div className="p-4 pt-0 text-sm text-muted-foreground leading-relaxed">
              {r.finding}
              {r.reference && <div className="mt-2 font-mono text-[10px] uppercase tracking-widest">{r.reference}</div>}
            </div>
          </details>
        ))}
      </div>
    </Section>
  );
}

function VerdictChip({ v }: { v: string }) {
  const map: Record<string, string> = {
    survived: "!text-good !border-good",
    dead: "text-muted-foreground",
    artifact: "!text-caution !border-caution",
  };
  return <span className={`tag ${map[v] ?? ""}`}>{v}</span>;
}

const strategySimData = [
  {
    "year": 2016,
    "actions": ["Bought Taurus Large Cap Fund (Rank #1)", "Bought Groww Largecap Fund (formerly known as Indiabulls Blue Chip Fund) (Rank #2)", "Bought quant Mid Cap Fund (Rank #1)", "Bought Baroda Mid cap Fund Plan B (Rank #2)", "Bought Aditya Birla Sun Life Small Cap Fund (Rank #1)", "Bought quant Small Cap Fund (Rank #2)", "Bought quant Flexi Cap Fund (Rank #1)", "Bought LIC MF Flexi Cap Fund (Rank #2)", "Bought quant ELSS Tax Saver Fund (Rank #1)", "Bought DSP ELSS Tax Saver Fund (Rank #2)"],
    "taxes_paid": 0.0,
    "port_return": 11.45,
    "bench_return": 12.26,
    "lumpsum_val": 1114494.25,
    "sip_val": 112783.95
  },
  {
    "year": 2017,
    "actions": ["Held Taurus Large Cap Fund (Rank #2)", "Held Groww Largecap Fund (formerly known as Indiabulls Blue Chip Fund) (Rank #1)", "Held quant Mid Cap Fund (Rank #1)", "Held Baroda Mid cap Fund Plan B (Rank #3)", "Held Aditya Birla Sun Life Small Cap Fund (Rank #4)", "Held quant Small Cap Fund (Rank #2)", "Held quant Flexi Cap Fund (Rank #3)", "Sold LIC MF Flexi Cap Fund (Rank #9). Tax paid: \u20b91,453", "Bought Parag Parikh Flexi Cap Fund (Rank #1)", "Sold quant ELSS Tax Saver Fund (Rank #11). Tax paid: \u20b92,238", "Held DSP ELSS Tax Saver Fund (Rank #4)", "Bought JM ELSS Tax Saver Fund (Rank #1)"],
    "taxes_paid": 3691.04,
    "port_return": 29.44,
    "bench_return": 30.99,
    "lumpsum_val": 1437798.93,
    "sip_val": 267747.09
  },
  {
    "year": 2018,
    "actions": ["Sold Taurus Large Cap Fund (Rank #16). Tax paid: \u20b93,482", "Sold Groww Largecap Fund (formerly known as Indiabulls Blue Chip Fund) (Rank #22). Tax paid: \u20b95,529", "Bought LIC MF Large Cap Fund (Rank #1)", "Bought Baroda Large cap Fund Plan B (Rank #2)", "Held quant Mid Cap Fund (Rank #1)", "Held Baroda Mid cap Fund Plan B (Rank #3)", "Sold Aditya Birla Sun Life Small Cap Fund (Rank #10). Tax paid: \u20b99,534", "Held quant Small Cap Fund (Rank #2)", "Bought ICICI Prudential Smallcap Fund (Rank #1)", "Held quant Flexi Cap Fund (Rank #3)", "Held Parag Parikh Flexi Cap Fund (Rank #2)", "Sold DSP ELSS Tax Saver Fund (Rank #9). Tax paid: \u20b96,441", "Sold JM ELSS Tax Saver Fund (Rank #19). Tax paid: \u20b94,863", "Bought LIC MF ELSS Tax Saver (Rank #1)", "Bought quant ELSS Tax Saver Fund (Rank #2)"],
    "taxes_paid": 29848.71,
    "port_return": -5.37,
    "bench_return": -6.19,
    "lumpsum_val": 1332280.09,
    "sip_val": 363708.28
  },
  {
    "year": 2019,
    "actions": ["Sold LIC MF Large Cap Fund (Rank #14). Tax paid: \u20b917", "Held Baroda Large cap Fund Plan B (Rank #1)", "Bought CANARA ROBECO LARGE CAP FUND (Rank #2)", "Held quant Mid Cap Fund (Rank #1)", "Held Baroda Mid cap Fund Plan B (Rank #2)", "Held quant Small Cap Fund (Rank #1)", "Sold ICICI Prudential Smallcap Fund (Rank #7). Tax paid: \u20b90", "Bought Axis Small Cap Fund (Rank #2)", "Held quant Flexi Cap Fund (Rank #1)", "Held Parag Parikh Flexi Cap Fund (Rank #2)", "Sold LIC MF ELSS Tax Saver (Rank #14). Tax paid: \u20b984", "Held quant ELSS Tax Saver Fund (Rank #1)", "Bought Mirae Asset ELSS Tax Saver Fund (Rank #2)"],
    "taxes_paid": 100.6,
    "port_return": 7.91,
    "bench_return": 10.68,
    "lumpsum_val": 1437593.61,
    "sip_val": 503565.04
  },
  {
    "year": 2020,
    "actions": ["Sold Baroda Large cap Fund Plan B (Rank #N/A). Tax paid: \u20b91,047", "Held CANARA ROBECO LARGE CAP FUND (Rank #4)", "Bought BANDHAN Large Cap Fund (Rank #1)", "Held quant Mid Cap Fund (Rank #1)", "Sold Baroda Mid cap Fund Plan B (Rank #N/A). Tax paid: \u20b93,908", "Bought PGIM India Midcap Fund (Rank #2)", "Held quant Small Cap Fund (Rank #1)", "Sold Axis Small Cap Fund (Rank #5). Tax paid: \u20b93,955", "Bought Kotak Small Cap Fund (Rank #2)", "Held quant Flexi Cap Fund (Rank #1)", "Held Parag Parikh Flexi Cap Fund (Rank #4)", "Held quant ELSS Tax Saver Fund (Rank #1)", "Sold Mirae Asset ELSS Tax Saver Fund (Rank #16). Tax paid: \u20b93,140", "Bought Mahindra Manulife ELSS Tax Saver Fund (Rank #2)"],
    "taxes_paid": 12050.74,
    "port_return": 33.1,
    "bench_return": 17.66,
    "lumpsum_val": 1897408.73,
    "sip_val": 825917.71
  },
  {
    "year": 2021,
    "actions": ["Sold CANARA ROBECO LARGE CAP FUND (Rank #15). Tax paid: \u20b97,273", "Sold BANDHAN Large Cap Fund (Rank #18). Tax paid: \u20b93,059", "Bought Nippon India Large Cap Fund (Rank #1)", "Bought HDFC Large Cap Fund (Rank #2)", "Held quant Mid Cap Fund (Rank #1)", "Sold PGIM India Midcap Fund (Rank #6). Tax paid: \u20b96,567", "Bought HDFC Mid Cap Fund (Rank #2)", "Held quant Small Cap Fund (Rank #1)", "Sold Kotak Small Cap Fund (Rank #11). Tax paid: \u20b94,843", "Bought Nippon India Small Cap Fund (Rank #2)", "Held quant Flexi Cap Fund (Rank #1)", "Sold Parag Parikh Flexi Cap Fund (Rank #15). Tax paid: \u20b911,436", "Bought HDFC Flexi Cap Fund (Rank #2)", "Held quant ELSS Tax Saver Fund (Rank #1)", "Sold Mahindra Manulife ELSS Tax Saver Fund (Rank #21). Tax paid: \u20b93,456", "Bought HDFC ELSS Tax saver (Rank #2)"],
    "taxes_paid": 36633.49,
    "port_return": 52.45,
    "bench_return": 39.63,
    "lumpsum_val": 2836802.1,
    "sip_val": 1379729.43
  },
  {
    "year": 2022,
    "actions": ["Held Nippon India Large Cap Fund (Rank #2)", "Held HDFC Large Cap Fund (Rank #1)", "Sold quant Mid Cap Fund (Rank #11). Tax paid: \u20b922,084", "Held HDFC Mid Cap Fund (Rank #1)", "Bought Kotak Midcap Fund (Rank #2)", "Held quant Small Cap Fund (Rank #4)", "Held Nippon India Small Cap Fund (Rank #1)", "Held quant Flexi Cap Fund (Rank #1)", "Held HDFC Flexi Cap Fund (Rank #2)", "Sold quant ELSS Tax Saver Fund (Rank #9). Tax paid: \u20b926,933", "Sold HDFC ELSS Tax saver (Rank #6). Tax paid: \u20b98,930", "Bought JM ELSS Tax Saver Fund (Rank #1)", "Bought Nippon India ELSS Tax Saver Fund (Rank #2)"],
    "taxes_paid": 57947.78,
    "port_return": 8.81,
    "bench_return": 3.61,
    "lumpsum_val": 3023659.98,
    "sip_val": 1622235.39
  },
  {
    "year": 2023,
    "actions": ["Held Nippon India Large Cap Fund (Rank #2)", "Held HDFC Large Cap Fund (Rank #1)", "Held HDFC Mid Cap Fund (Rank #2)", "Held Kotak Midcap Fund (Rank #1)", "Sold quant Small Cap Fund (Rank #8). Tax paid: \u20b926,550", "Held Nippon India Small Cap Fund (Rank #3)", "Bought BANDHAN SMALL CAP FUND (Rank #1)", "Sold quant Flexi Cap Fund (Rank #18). Tax paid: \u20b936,415", "Held HDFC Flexi Cap Fund (Rank #1)", "Bought Aditya Birla Sun Life Flexi Cap Fund (Rank #2)", "Held JM ELSS Tax Saver Fund (Rank #1)", "Held Nippon India ELSS Tax Saver Fund (Rank #4)"],
    "taxes_paid": 62964.43,
    "port_return": 39.63,
    "bench_return": 34.94,
    "lumpsum_val": 4133986.4,
    "sip_val": 2392713.75
  },
  {
    "year": 2024,
    "actions": ["Sold Nippon India Large Cap Fund (Rank #23). Tax paid: \u20b921,350", "Sold HDFC Large Cap Fund (Rank #19). Tax paid: \u20b918,470", "Bought JM Large Cap Fund (Rank #1)", "Bought Taurus Large Cap Fund (Rank #2)", "Sold HDFC Mid Cap Fund (Rank #17). Tax paid: \u20b928,498", "Sold Kotak Midcap Fund (Rank #18). Tax paid: \u20b914,579", "Bought Tata Mid Cap Fund (Rank #1)", "Bought Sundaram Mid Cap Fund (Rank #2)", "Sold Nippon India Small Cap Fund (Rank #18). Tax paid: \u20b945,797", "Held BANDHAN SMALL CAP FUND (Rank #4)", "Bought UTI Small Cap Fund (Rank #1)", "Sold HDFC Flexi Cap Fund (Rank #16). Tax paid: \u20b925,409", "Sold Aditya Birla Sun Life Flexi Cap Fund (Rank #17). Tax paid: \u20b913,488", "Bought JM Flexicap Fund (Rank #1)", "Bought Union Flexi Cap Fund (Rank #2)", "Sold JM ELSS Tax Saver Fund (Rank #8). Tax paid: \u20b914,686", "Sold Nippon India ELSS Tax Saver Fund (Rank #31). Tax paid: \u20b915,212", "Bought Groww ELSS Tax Saver Fund (formerly known as Indiabulls Tax Savings Fund) (Rank #1)", "Bought Shriram ELSS Tax Saver Fund (Rank #2)"],
    "taxes_paid": 197486.95,
    "port_return": 21.41,
    "bench_return": 19.79,
    "lumpsum_val": 4779140.72,
    "sip_val": 3005309.12
  },
  {
    "year": 2025,
    "actions": ["Sold JM Large Cap Fund (Rank #11). Tax paid: \u20b94,521", "Held Taurus Large Cap Fund (Rank #1)", "Bought BANDHAN Large Cap Fund (Rank #2)", "Sold Tata Mid Cap Fund (Rank #11). Tax paid: \u20b98,820", "Sold Sundaram Mid Cap Fund (Rank #13). Tax paid: \u20b913,391", "Bought ITI Mid Cap Fund (Rank #1)", "Bought Aditya Birla Sun Life Midcap Fund (Rank #2)", "Held BANDHAN SMALL CAP FUND (Rank #3)", "Sold UTI Small Cap Fund (Rank #11). Tax paid: \u20b915,822", "Bought Edelweiss Small Cap Fund (Rank #1)", "Sold JM Flexicap Fund (Rank #8). Tax paid: \u20b914,850", "Held Union Flexi Cap Fund (Rank #3)", "Bought Samco Flexi Cap Fund (Rank #1)", "Held Groww ELSS Tax Saver Fund (formerly known as Indiabulls Tax Savings Fund) (Rank #3)", "Held Shriram ELSS Tax Saver Fund (Rank #1)"],
    "taxes_paid": 57403.75,
    "port_return": 9.43,
    "bench_return": 10.23,
    "lumpsum_val": 5166921.64,
    "sip_val": 3416067.24
  },
  {
    "year": 2026,
    "actions": ["Held Taurus Large Cap Fund (Rank #1)", "Held BANDHAN Large Cap Fund (Rank #3)", "Sold ITI Mid Cap Fund (Rank #11). Tax paid: \u20b97,865", "Held Aditya Birla Sun Life Midcap Fund (Rank #2)", "Bought Union Midcap Fund (Rank #1)", "Held BANDHAN SMALL CAP FUND (Rank #4)", "Sold Edelweiss Small Cap Fund (Rank #5). Tax paid: \u20b95,833", "Bought PGIM India Small Cap Fund (Rank #1)", "Held Union Flexi Cap Fund (Rank #1)", "Sold Samco Flexi Cap Fund (Rank #5). Tax paid: \u20b90", "Bought Sundaram Flexicap Fund (Rank #2)", "Held Groww ELSS Tax Saver Fund (formerly known as Indiabulls Tax Savings Fund) (Rank #1)", "Sold Shriram ELSS Tax Saver Fund (Rank #5). Tax paid: \u20b911,361", "Bought 360 ONE ELSS Tax Saver Nifty 50 Index Fund (Rank #2)"],
    "taxes_paid": 25058.85,
    "port_return": 1.24,
    "bench_return": 1.02,
    "lumpsum_val": 5205835.82,
    "sip_val": 3482709.4
  }
];

function FullStrategySimulation() {
  return (
    <Section eyebrow="THE FULL STRATEGY" title="Annual Rebalance Simulation">
      <p className="text-muted-foreground mb-10 max-w-2xl text-[14px] leading-relaxed">
        This tracks what happens if you followed the system entirely: holding exactly 10 top-rated funds in Jan 2016, and rebalancing every January up to Mid-2026. 
        Crucially, it uses the <strong>Top-4 Buffer Rule</strong> (only selling a fund if it drops to 5th or worse) and deducts a strict <strong>12.5% LTCG tax</strong> from profits every time a fund is sold.
      </p>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-10">
        <Card className="p-6 bg-surface-2/30 border-hairline relative overflow-hidden">
           <div className="absolute top-0 right-0 p-4 opacity-5 text-brand">◆</div>
           <div className="text-[11px] uppercase tracking-widest text-muted-foreground mb-1">Lumpsum Journey (To 2026)</div>
           <div className="font-display text-4xl mb-2 text-foreground">₹52.05 Lakh</div>
           <p className="text-sm text-muted-foreground">₹10 Lakh invested in Jan 2016</p>
        </Card>
        <Card className="p-6 bg-surface-2/30 border-hairline relative overflow-hidden">
           <div className="absolute top-0 right-0 p-4 opacity-5 text-brand">◆</div>
           <div className="text-[11px] uppercase tracking-widest text-muted-foreground mb-1">SIP Journey (To 2026)</div>
           <div className="font-display text-4xl mb-2 text-foreground">₹34.82 Lakh</div>
           <p className="text-sm text-muted-foreground">₹10,000/month (₹12.6L total) since Jan 2016</p>
        </Card>
      </div>

      <div className="space-y-6">
        {strategySimData.map((y) => (
           <Card key={y.year} className="p-6 relative group">
              <div className="flex justify-between items-center mb-6">
                 <h3 className="font-display text-2xl text-foreground">{y.year} <span className="text-sm text-muted-foreground font-sans tracking-normal ml-2 font-normal">Holding Period</span></h3>
                 <div className="text-right">
                    <div className="text-[10px] uppercase tracking-widest text-muted-foreground">Strategy Return</div>
                    <div className={`font-mono text-xl ${y.port_return > y.bench_return ? 'text-good' : 'text-caution'}`}>
                      {y.port_return > 0 ? '+' : ''}{y.port_return.toFixed(1)}% <span className="text-xs text-muted-foreground ml-2">vs {y.bench_return.toFixed(1)}% bench</span>
                    </div>
                 </div>
              </div>
              
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div className="lg:col-span-2">
                  <div className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground mb-4 border-b border-hairline pb-2">Trading Actions (Top-4 Buffer & Taxes)</div>
                  <ul className="space-y-3 text-[13px] text-muted-foreground">
                    {y.actions.map((act, i) => {
                       const isSell = act.startsWith("Sold");
                       const isBuy = act.startsWith("Bought");
                       return (
                         <li key={i} className="flex gap-3 leading-relaxed">
                           <span className={isSell ? "text-caution" : isBuy ? "text-good" : "text-brand"}>
                             {isSell ? "↓" : isBuy ? "↑" : "−"}
                           </span> 
                           <span className={isSell ? "opacity-80" : "text-foreground"}>
                             {isSell ? act.split('. ')[0] : act} 
                             {isSell && act.includes('Tax paid') && (
                                <span className="ml-2 inline-flex items-center rounded-sm bg-caution/10 px-2 py-0.5 text-[10px] font-medium text-caution">
                                  {act.split('. ')[1]}
                                </span>
                             )}
                           </span>
                         </li>
                       );
                    })}
                  </ul>
                </div>
                <div>
                   <div className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground mb-4 border-b border-hairline pb-2">End of Year Balances</div>
                   <div className="space-y-4">
                      <div>
                        <div className="text-xs text-muted-foreground mb-1">Lumpsum Portfolio</div>
                        <div className="font-mono text-sm text-foreground bg-surface-2 p-2 rounded hairline flex justify-between">
                          <span>Value</span>
                          <span>₹{(y.lumpsum_val/100000).toFixed(2)} Lakh</span>
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-muted-foreground mb-1">SIP Portfolio</div>
                        <div className="font-mono text-sm text-foreground bg-surface-2 p-2 rounded hairline flex justify-between">
                          <span>Value</span>
                          <span>₹{(y.sip_val/100000).toFixed(2)} Lakh</span>
                        </div>
                      </div>
                      
                      <div className="pt-2">
                          <div className="text-[10px] uppercase tracking-widest text-muted-foreground mb-1">Total Tax Deducted</div>
                          <div className={`font-mono text-sm ${y.taxes_paid > 0 ? 'text-caution' : 'text-muted-foreground'}`}>
                            ₹{y.taxes_paid.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                          </div>
                      </div>
                   </div>
                </div>
              </div>
           </Card>
        ))}
      </div>

      {/* Final Verdict Summary */}
      <div className="mt-12 mb-8 p-6 bg-surface-2/40 border border-hairline rounded-lg">
        <h3 className="font-display text-2xl text-foreground mb-4">The Final Verdict (Jan 2016 - Mid 2026)</h3>
        <p className="text-sm text-muted-foreground mb-6">
          After exactly 10.5 years of strict adherence to the model—holding 10 funds equally, utilizing the Top-4 buffer to minimize churn, and paying 12.5% LTCG tax on every profitable sale—here is the definitive net-of-tax performance of the ₹10 Lakh initial investment. We compare our strategy against the Nifty 50, Sensex, and a custom <strong>Category Benchmark</strong> (which represents the average performance of buying and holding <em>every single active fund</em> across all 5 of our chosen categories).
        </p>
        
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <div className="p-4 bg-card rounded border-hairline relative overflow-hidden">
            <div className="absolute top-0 right-0 p-3 opacity-5 text-brand">◆</div>
            <div className="text-[10px] uppercase tracking-widest text-muted-foreground">The Strategy (Net)</div>
            <div className="text-2xl font-display mt-2 text-good">₹52.05 L</div>
            <div className="text-[11px] text-muted-foreground mt-1 mb-4">Lumpsum (17.1% CAGR)</div>
            <div className="text-xl font-display text-good">₹34.82 L</div>
            <div className="text-[11px] text-muted-foreground mt-1">SIP Value</div>
          </div>
          
          <div className="p-4 bg-card rounded border-hairline">
            <div className="text-[10px] uppercase tracking-widest text-muted-foreground">Category Benchmark</div>
            <div className="text-2xl font-display mt-2 text-foreground">₹48.46 L</div>
            <div className="text-[11px] text-muted-foreground mt-1 mb-4">Lumpsum (16.2% CAGR)</div>
            <div className="text-xl font-display text-foreground">₹28.60 L</div>
            <div className="text-[11px] text-muted-foreground mt-1">SIP Value</div>
          </div>

          <div className="p-4 bg-card rounded border-hairline">
            <div className="text-[10px] uppercase tracking-widest text-muted-foreground">Nifty 500</div>
            <div className="text-2xl font-display mt-2 text-foreground">₹34.20 L</div>
            <div className="text-[11px] text-muted-foreground mt-1 mb-4">Lumpsum (12.4% CAGR)</div>
            <div className="text-xl font-display text-foreground">₹24.96 L</div>
            <div className="text-[11px] text-muted-foreground mt-1">SIP Value</div>
          </div>

          <div className="p-4 bg-card rounded border-hairline">
            <div className="text-[10px] uppercase tracking-widest text-muted-foreground">Nifty 50</div>
            <div className="text-2xl font-display mt-2 text-foreground">₹29.74 L</div>
            <div className="text-[11px] text-muted-foreground mt-1 mb-4">Lumpsum (10.8% CAGR)</div>
            <div className="text-xl font-display text-foreground">₹22.28 L</div>
            <div className="text-[11px] text-muted-foreground mt-1">SIP Value</div>
          </div>

          <div className="p-4 bg-card rounded border-hairline">
            <div className="text-[10px] uppercase tracking-widest text-muted-foreground">Sensex</div>
            <div className="text-2xl font-display mt-2 text-foreground">₹28.85 L</div>
            <div className="text-[11px] text-muted-foreground mt-1 mb-4">Lumpsum (10.6% CAGR)</div>
            <div className="text-xl font-display text-foreground">₹21.57 L</div>
            <div className="text-[11px] text-muted-foreground mt-1">SIP Value</div>
          </div>
        </div>
      </div>
    </Section>
  );
}
