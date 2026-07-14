import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Card } from "@/components/ui-bits";

const sb = supabase as any;

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "FundLens — Indian mutual fund analytics" },
      { name: "description", content: "Browse the analytical universe of Indian equity mutual funds." },
    ],
  }),
  component: HomePage,
});

type FundRow = {
  scheme_id: number; fund_name: string; category: string; quality: number; risk: number;
  risk_band: string; recommended: boolean; rank: number;
};

function HomePage() {
  const { data, isLoading } = useQuery({
    queryKey: ["home_funds"],
    queryFn: async () => {
      const { data } = await sb
        .from("funds")
        .select("scheme_id,fund_name,category,quality,risk,risk_band,recommended,rank")
        .eq("snapshot", "live")
        .limit(2000);
      return (data ?? []) as FundRow[];
    },
  });

  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [band, setBand] = useState("");
  const [sort, setSort] = useState<"quality" | "risk" | "name">("quality");

  const cats = useMemo(
    () => Array.from(new Set((data ?? []).map((f) => f.category))).sort(),
    [data]
  );

  const rows = useMemo(() => {
    let out = (data ?? []).filter((f) => {
      if (q && !f.fund_name.toLowerCase().includes(q.toLowerCase())) return false;
      if (cat && f.category !== cat) return false;
      if (band && f.risk_band !== band) return false;
      return true;
    });
    out.sort((a, b) => {
      if (sort === "risk") return (a.risk ?? 999) - (b.risk ?? 999);
      if (sort === "name") return a.fund_name.localeCompare(b.fund_name);
      return (b.quality ?? 0) - (a.quality ?? 0);
    });
    return out;
  }, [data, q, cat, band, sort]);

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <div className="flex items-baseline justify-between mb-6">
        <h1 className="font-display text-lg tracking-tight">Find a fund</h1>
        <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground tabular-nums">
          {isLoading ? "…" : `${rows.length} / ${data?.length ?? 0}`}
        </div>
      </div>

      <div className="grid gap-2 md:grid-cols-[1fr_auto_auto_auto] mb-4">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search fund name…"
          className="hairline bg-background text-sm px-3 py-2 rounded-sm focus:outline-none focus:border-brand"
        />
        <select
          value={cat}
          onChange={(e) => setCat(e.target.value)}
          className="hairline bg-background text-sm px-3 py-2 rounded-sm"
        >
          <option value="">All categories</option>
          {cats.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select
          value={band}
          onChange={(e) => setBand(e.target.value)}
          className="hairline bg-background text-sm px-3 py-2 rounded-sm"
        >
          <option value="">All risk</option>
          <option value="Conservative">Conservative</option>
          <option value="Balanced">Balanced</option>
          <option value="Aggressive">Aggressive</option>
        </select>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as any)}
          className="hairline bg-background text-sm px-3 py-2 rounded-sm"
        >
          <option value="quality">Sort: Quality</option>
          <option value="risk">Sort: Risk</option>
          <option value="name">Sort: Name</option>
        </select>
      </div>

      <div className="hairline">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-hairline text-left">
              <th className="px-3 py-2 mono-label font-normal">Fund</th>
              <th className="px-3 py-2 mono-label font-normal hidden md:table-cell">Category</th>
              <th className="px-3 py-2 mono-label font-normal text-right w-20">Quality</th>
              <th className="px-3 py-2 mono-label font-normal text-right w-28">Risk</th>
            </tr>
          </thead>
          <tbody className="tabular-nums">
            {rows.map((f) => (
              <tr key={f.scheme_id} className="border-b border-hairline last:border-0 hover:bg-surface-2 transition-colors">
                <td className="px-3 py-2.5">
                  <Link to="/fund/$schemeId" params={{ schemeId: String(f.scheme_id) }} className="hover:text-brand">
                    {f.fund_name}
                  </Link>
                </td>
                <td className="px-3 py-2.5 text-muted-foreground text-[12px] hidden md:table-cell">{f.category}</td>
                <td className="px-3 py-2.5 text-right font-mono text-good">{f.quality ?? "—"}</td>
                <td className="px-3 py-2.5 text-right font-mono">
                  <span className="text-caution">{f.risk ?? "—"}</span>
                  <span className="ml-2 text-[9px] uppercase tracking-widest text-muted-foreground">{f.risk_band}</span>
                </td>
              </tr>
            ))}
            {!isLoading && rows.length === 0 && (
              <tr><td colSpan={4} className="px-3 py-10 text-center text-muted-foreground text-[12px]">No funds match.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function FundCard({ f }: { f: FundRow }) {
  return (
    <Link to="/fund/$schemeId" params={{ schemeId: String(f.scheme_id) }}>
      <Card className="p-4 hover:bg-surface-2 transition-colors h-full flex flex-col">
        <div className="flex items-start justify-between gap-2 mb-3">
          <div className="text-[13px] font-medium leading-tight flex-1">{f.fund_name}</div>
          {f.recommended && (
            <span className="tag !text-brand !border-brand shrink-0">TOP</span>
          )}
        </div>
        <div className="tag mb-4 self-start">{f.category}</div>
        <div className="grid grid-cols-2 gap-3 mt-auto font-mono tabular-nums">
          <div>
            <div className="mono-label">Quality</div>
            <div className="text-2xl text-good leading-none mt-1">{f.quality ?? "—"}</div>
          </div>
          <div>
            <div className="mono-label">Risk · {f.risk_band}</div>
            <div className="text-2xl text-caution leading-none mt-1">{f.risk ?? "—"}</div>
          </div>
        </div>
      </Card>
    </Link>
  );
}
