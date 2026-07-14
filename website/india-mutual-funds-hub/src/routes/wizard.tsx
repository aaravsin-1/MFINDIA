import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Card, Section } from "@/components/ui-bits";
import { FundCard } from "./index";
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceArea,
} from "recharts";

const sb = supabase as any;

export const Route = createFileRoute("/wizard")({
  head: () => ({
    meta: [
      { title: "Find my fund — FundLens" },
      { name: "description", content: "A 3-step wizard: pick a category, pick your risk comfort, and see funds ranked by our within-category Quality score." },
    ],
  }),
  component: Wizard,
});

type Cat = { category: string; n_funds: number; n_recommended: number; is_core: boolean };
type Fund = {
  scheme_id: number; fund_name: string; category: string; quality: number; risk: number;
  risk_band: string; recommended: boolean; rank: number; holding_period: string; reason_1: string; reason_2: string;
};

const CORE_DESC: Record<string, string> = {
  "Large Cap Fund": "Big established companies. Steadier.",
  "Mid Cap Fund": "Mid-sized firms — growth with real swings.",
  "Small Cap Fund": "Smaller, faster-growing, much bumpier.",
  "Flexi Cap Fund": "Manager picks across sizes.",
  "ELSS": "Tax-saving equity (3-yr lock-in).",
};

const BANDS = [
  { key: "Conservative", desc: "Calm ride, smaller dips. Best if you'll hold 5+ years." },
  { key: "Balanced", desc: "Moderate swings. Hold 3–5 years." },
  { key: "Aggressive", desc: "Bumpy — only if you can stay invested through sharp drops. 1–3 years+." },
];

function Wizard() {
  const [step, setStep] = useState(1);
  const [cat, setCat] = useState<string | null>(null);
  const [band, setBand] = useState<string | null>(null);

  const { data: cats } = useQuery({
    queryKey: ["category_summary"],
    queryFn: async () => {
      const { data } = await sb.from("category_summary").select("*").order("n_funds", { ascending: false });
      return (data ?? []) as Cat[];
    },
  });

  const core = cats?.filter((c) => c.is_core) ?? [];
  const other = cats?.filter((c) => !c.is_core) ?? [];

  return (
    <Section>
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center gap-2 mb-8 font-mono text-[11px] tracking-widest uppercase text-muted-foreground">
          <span className={step >= 1 ? "text-foreground" : ""}>1 · Category</span>
          <span>—</span>
          <span className={step >= 2 ? "text-foreground" : ""}>2 · Risk</span>
          <span>—</span>
          <span className={step >= 3 ? "text-foreground" : ""}>3 · Results</span>
        </div>

        {step === 1 && (
          <div>
            <h1 className="font-display text-3xl md:text-4xl mb-3">01 · Select a category.</h1>
            <p className="text-muted-foreground mb-8 max-w-2xl text-[14px]">
              Screening operates within a category. Quality scores are peer-relative — not comparable across sleeves.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {core.map((c) => (
                <button key={c.category} onClick={() => { setCat(c.category); setStep(2); }}
                  className="text-left hairline bg-card rounded-md p-5 hover:bg-surface-2 transition-colors">
                  <div className="text-[14px] font-medium">{c.category}</div>
                  <div className="text-xs text-muted-foreground mt-1">{CORE_DESC[c.category] ?? "—"}</div>
                  <div className="tag mt-4">{c.n_funds} funds · {c.n_recommended} picks</div>
                </button>
              ))}
            </div>
            {other.length > 0 && (
              <details className="mt-8">
                <summary className="cursor-pointer tag hover:text-foreground">Other categories ({other.length})</summary>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mt-4">
                  {other.map((c) => (
                    <button key={c.category} onClick={() => { setCat(c.category); setStep(2); }}
                      className="text-left hairline rounded-md p-4 hover:bg-surface-2 transition-colors">
                      <div className="text-[13px]">{c.category}</div>
                      <div className="tag mt-2">{c.n_funds} funds</div>
                    </button>
                  ))}
                </div>
              </details>
            )}
          </div>
        )}

        {step === 2 && (
          <div>
            <button onClick={() => setStep(1)} className="tag mb-6 hover:text-foreground">← Back</button>
            <h1 className="font-display text-4xl md:text-5xl mb-3">How much bumpiness can you sit through?</h1>
            <p className="text-muted-foreground mb-8">
              Selected: <span className="text-foreground">{cat}</span>. Not sure?{" "}
              <button className="underline" onClick={() => { setBand("Balanced"); setStep(3); }}>Start with Balanced.</button>
            </p>
            <div className="grid gap-3">
              {BANDS.map((b) => (
                <button key={b.key} onClick={() => { setBand(b.key); setStep(3); }}
                  className="text-left hairline bg-card rounded-md p-6 hover:bg-surface-2 transition-colors">
                  <div className="text-[15px] font-medium">{b.key}</div>
                  <div className="text-sm text-muted-foreground mt-1">{b.desc}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {step === 3 && cat && band && (
          <Results cat={cat} band={band} onBack={() => setStep(2)} />
        )}
      </div>
    </Section>
  );
}

function Results({ cat, band, onBack }: { cat: string; band: string; onBack: () => void }) {
  const [minQ, setMinQ] = useState(0);
  const [riskRange, setRiskRange] = useState<[number, number]>([0, 100]);

  const { data, isLoading } = useQuery({
    queryKey: ["wizard_results", cat, band],
    queryFn: async () => {
      const { data } = await sb
        .from("funds")
        .select("scheme_id,fund_name,category,quality,risk,risk_band,recommended,rank,holding_period,reason_1,reason_2")
        .eq("snapshot", "live")
        .eq("category", cat)
        .eq("risk_band", band)
        .order("quality", { ascending: false });
      return (data ?? []) as Fund[];
    },
  });

  const filtered = useMemo(() =>
    (data ?? []).filter((f) => (f.quality ?? 0) >= minQ && (f.risk ?? 0) >= riskRange[0] && (f.risk ?? 0) <= riskRange[1]),
    [data, minQ, riskRange]);

  const recs = filtered.filter((f) => f.recommended);
  const rest = filtered.filter((f) => !f.recommended);

  return (
    <div>
      <button onClick={onBack} className="tag mb-6 hover:text-foreground">← Back</button>
      <div className="flex flex-wrap items-baseline gap-3 mb-2">
        <h1 className="font-display text-3xl md:text-4xl">{cat}</h1>
        <span className="tag">{band}</span>
      </div>
      <p className="text-sm text-muted-foreground mb-8">
        {isLoading ? "Loading…" : `${filtered.length} of ${data?.length ?? 0} match your filters. Ranked by within-category Quality.`}
      </p>

      {data && data.length > 0 && (
        <Card className="p-4 mb-8">
          <div className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-3">Quality × Risk</div>
          <div className="h-64">
            <ResponsiveContainer>
              <ScatterChart margin={{ top: 10, right: 20, bottom: 30, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--hairline)" />
                <XAxis type="number" dataKey="risk" domain={[0, 100]} name="Risk"
                  label={{ value: "Risk →", position: "insideBottom", offset: -5, fill: "var(--muted-foreground)", fontSize: 11 }}
                  tick={{ fill: "var(--muted-foreground)", fontSize: 10 }} />
                <YAxis type="number" dataKey="quality" domain={[0, 100]} name="Quality"
                  label={{ value: "Quality ↑", angle: -90, position: "insideLeft", fill: "var(--muted-foreground)", fontSize: 11 }}
                  tick={{ fill: "var(--muted-foreground)", fontSize: 10 }} />
                <Tooltip cursor={{ strokeDasharray: "3 3" }}
                  contentStyle={{ background: "var(--surface-2)", border: "1px solid var(--hairline)", borderRadius: 4, fontSize: 12 }}
                  formatter={(v: any, n: string) => [v, n]}
                  labelFormatter={() => ""}
                  content={({ payload }) => {
                    const p: any = payload?.[0]?.payload;
                    if (!p) return null;
                    return (
                      <div style={{ background: "var(--surface-2)", border: "1px solid var(--hairline)", padding: 8, borderRadius: 4, fontSize: 12 }}>
                        <div>{p.fund_name}</div>
                        <div className="text-muted-foreground">Q {p.quality} · R {p.risk}</div>
                      </div>
                    );
                  }}
                />
                <ReferenceArea x1={riskRange[0]} x2={riskRange[1]} y1={minQ} y2={100} fill="var(--brand)" fillOpacity={0.05} />
                <Scatter data={data.filter((f) => !f.recommended)} fill="var(--muted-foreground)" />
                <Scatter data={data.filter((f) => f.recommended)} fill="var(--brand)" />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          <div className="grid md:grid-cols-2 gap-4 mt-4">
            <div>
              <div className="flex justify-between text-xs mb-1"><span>Minimum Quality</span><span className="font-mono">{minQ}</span></div>
              <input type="range" min={0} max={100} value={minQ} onChange={(e) => setMinQ(+e.target.value)} className="w-full" />
            </div>
            <div>
              <div className="flex justify-between text-xs mb-1"><span>Risk range</span><span className="font-mono">{riskRange[0]}–{riskRange[1]}</span></div>
              <div className="flex gap-2">
                <input type="range" min={0} max={100} value={riskRange[0]} onChange={(e) => setRiskRange([+e.target.value, riskRange[1]])} className="w-full" />
                <input type="range" min={0} max={100} value={riskRange[1]} onChange={(e) => setRiskRange([riskRange[0], +e.target.value])} className="w-full" />
              </div>
            </div>
          </div>
        </Card>
      )}

      {recs.length > 0 && (
        <div className="mb-8">
          <div className="tag mb-3 !text-brand !border-brand">▪ Top-ranked in category</div>
          <p className="text-xs text-muted-foreground mb-3">The highest within-category Quality scores in this sleeve, filtered to your risk band.</p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {recs.map((f) => <FundCard key={f.scheme_id} f={f} />)}
          </div>
        </div>
      )}

      {rest.length > 0 && (
        <div>
          <div className="tag mb-3">All matches</div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {rest.map((f) => <FundCard key={f.scheme_id} f={f} />)}
          </div>
        </div>
      )}

      {filtered.length === 0 && !isLoading && (
        <Card className="p-8 text-center text-sm text-muted-foreground">
          Nothing matches. Try widening the risk range, or{" "}
          <Link to="/browse" className="underline text-foreground">browse all funds</Link>.
        </Card>
      )}
    </div>
  );
}
