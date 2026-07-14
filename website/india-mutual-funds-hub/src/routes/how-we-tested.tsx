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

      <h2 className="font-display text-2xl mb-4">Research log</h2>
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
