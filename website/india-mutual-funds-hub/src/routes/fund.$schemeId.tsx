import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import { Section, Card } from "@/components/ui-bits";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

const sb = supabase as any;

export const Route = createFileRoute("/fund/$schemeId")({
  head: ({ params }) => ({
    meta: [
      { title: `Fund ${params.schemeId} — FundLens` },
      { name: "description", content: "Fund detail: Quality and Risk scores, NAV trend, managers, and plain-English reasons." },
    ],
  }),
  component: FundDetail,
  errorComponent: ({ error }) => <div className="p-8 text-sm text-muted-foreground">Error: {error.message}</div>,
  notFoundComponent: () => (
    <div className="p-8 text-center">
      <h1 className="font-display text-3xl">Fund not found.</h1>
      <Link to="/browse" className="tag mt-4 inline-block">← Browse all funds</Link>
    </div>
  ),
});

function FundDetail() {
  const { schemeId } = Route.useParams();
  const sid = Number(schemeId);

  const detail = useQuery({
    queryKey: ["fund_detail", sid],
    queryFn: async () => {
      const { data } = await sb.from("fund_detail").select("*").eq("scheme_id", sid).maybeSingle();
      if (!data) throw notFound();
      return data as any;
    },
  });
  const nav = useQuery({
    queryKey: ["fund_nav", sid],
    queryFn: async () => {
      const { data } = await sb.from("fund_nav").select("date,nav").eq("scheme_id", sid).order("date");
      return (data ?? []) as { date: string; nav: number }[];
    },
  });
  const mgrs = useQuery({
    queryKey: ["fund_managers", sid],
    queryFn: async () => {
      const { data } = await sb.from("fund_managers").select("*").eq("scheme_id", sid).eq("is_current", true);
      return (data ?? []) as any[];
    },
  });
  const funds = useQuery({
    queryKey: ["fund_reasons", sid],
    queryFn: async () => {
      const { data } = await sb.from("funds").select("reason_1,reason_2,why,holding_period,risk_band").eq("scheme_id", sid).eq("snapshot", "live").maybeSingle();
      return data as any;
    },
  });

  if (detail.isLoading) return <Section><div className="text-sm text-muted-foreground">Loading…</div></Section>;
  const d = detail.data;
  if (!d) return <Section><div>Not found.</div></Section>;

  const reasons: string[] = funds.data?.why ? String(funds.data.why).split("|").map((s: string) => s.trim()).filter(Boolean) : [
    funds.data?.reason_1, funds.data?.reason_2,
  ].filter(Boolean);

  return (
    <Section>
      <Link to="/browse" className="tag mb-4 inline-block hover:text-foreground">← Browse</Link>
      <div className="flex items-start justify-between gap-4 flex-wrap mb-2">
        <h1 className="font-display text-3xl md:text-5xl leading-tight max-w-3xl">{d.fund_name}</h1>
        {d.recommended && <span className="tag !text-brand !border-brand">▪ TOP-RANKED IN CATEGORY</span>}
      </div>
      <div className="flex flex-wrap gap-2 mb-8">
        {d.amc && <span className="tag">{d.amc}</span>}
        {d.category && <span className="tag">{d.category}</span>}
        {d.risk_band && <span className="tag">{d.risk_band}</span>}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <Card className="p-6">
          <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Quality</div>
          <div className="font-display text-6xl text-good leading-none mt-2">{d.quality ?? "—"}<span className="text-2xl text-muted-foreground">/100</span></div>
          <p className="text-xs text-muted-foreground mt-3">The model's view of this fund <em>within its own category</em>. Not comparable across categories.</p>
        </Card>
        <Card className="p-6">
          <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Risk</div>
          <div className="font-display text-6xl text-caution leading-none mt-2">{d.risk ?? "—"}<span className="text-2xl text-muted-foreground">/100</span></div>
          <p className="text-xs text-muted-foreground mt-3">Pure maths — how bumpy the ride was and how deep its worst fall. No prediction involved.</p>
        </Card>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-hairline hairline rounded-md overflow-hidden mb-8">
        <Fact label="AUM" value={d.aum_cr != null ? `₹${Math.round(d.aum_cr).toLocaleString("en-IN")} cr` : "—"} />
        <Fact label="Expense ratio" value={d.ter_pct != null ? `${Number(d.ter_pct).toFixed(2)}%` : "—"} />
        <Fact label="Inception" value={d.inception_date ? `since ${new Date(d.inception_date).getFullYear()}` : "—"} />
        <Fact label="Hold" value={funds.data?.holding_period ?? "—"} />
      </div>

      {nav.data && nav.data.length > 1 && (
        <Card className="p-4 mb-8">
          <div className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-2">
            NAV · last {nav.data.length} months
          </div>
          <div className="h-48">
            <ResponsiveContainer>
              <LineChart data={nav.data} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                <XAxis dataKey="date" hide />
                <YAxis domain={["auto", "auto"]} hide />
                <Tooltip
                  contentStyle={{ background: "var(--surface-2)", border: "1px solid var(--hairline)", borderRadius: 4, fontSize: 12 }}
                  formatter={(v: any) => [Number(v).toFixed(2), "NAV"]}
                />
                <Line type="monotone" dataKey="nav" stroke="var(--brand)" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="text-[10px] text-muted-foreground mt-2">Direct plan, last 12 months — for trend only, not a return promise.</p>
        </Card>
      )}

      {mgrs.data && mgrs.data.length > 0 && (
        <Card className="p-6 mb-8">
          <div className="tag mb-3">Managers</div>
          <ul className="space-y-1 text-sm">
            {mgrs.data.map((m: any, i: number) => (
              <li key={i}>
                {m.manager_name} <span className="text-muted-foreground">· {m.tenure_years != null ? `${Number(m.tenure_years).toFixed(1)} yrs tenure` : "—"}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {reasons.length > 0 && (
        <Card className="p-6 mb-8">
          <div className="tag mb-4">Why this rating</div>
          <div className="grid gap-2">
            {reasons.map((r, i) => {
              const isPos = r.startsWith("[+]");
              const isNeg = r.startsWith("[-]");
              const text = r.replace(/^\[[+-]\]\s*/, "");
              return (
                <div key={i} className={`flex items-start gap-3 p-3 rounded-sm hairline ${isPos ? "border-good/40" : isNeg ? "border-caution/40" : ""}`}>
                  <span className={`font-mono text-lg leading-none ${isPos ? "text-good" : isNeg ? "text-caution" : "text-muted-foreground"}`}>
                    {isPos ? "✓" : isNeg ? "!" : "·"}
                  </span>
                  <span className="text-sm leading-relaxed">{text}</span>
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </Section>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-4 bg-card">
      <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm">{value}</div>
    </div>
  );
}
