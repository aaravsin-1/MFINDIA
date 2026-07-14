import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Section, Card } from "@/components/ui-bits";

const sb = supabase as any;

export const Route = createFileRoute("/browse")({
  head: () => ({
    meta: [
      { title: "Browse all funds — FundLens" },
      { name: "description", content: "All 381 live-rated Indian equity mutual funds. Filter by category, risk band, minimum quality." },
    ],
  }),
  component: Browse,
});

type Fund = {
  scheme_id: number; fund_name: string; category: string; quality: number; risk: number;
  risk_band: string; recommended: boolean; holding_period: string; rank: number;
};

const PAGE_SIZE = 25;

function Browse() {
  const [cat, setCat] = useState("");
  const [band, setBand] = useState<string>("");
  const [recOnly, setRecOnly] = useState(false);
  const [minQ, setMinQ] = useState(0);
  const [maxR, setMaxR] = useState(100);
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<"rank" | "quality" | "risk">("rank");
  const [page, setPage] = useState(0);

  const { data, isLoading } = useQuery({
    queryKey: ["browse_funds"],
    queryFn: async () => {
      const { data } = await sb
        .from("funds")
        .select("scheme_id,fund_name,category,quality,risk,risk_band,recommended,holding_period,rank")
        .eq("snapshot", "live")
        .limit(2000);
      return (data ?? []) as Fund[];
    },
  });

  const cats = useMemo(() => Array.from(new Set((data ?? []).map((f) => f.category))).sort(), [data]);

  const filtered = useMemo(() => {
    let out = (data ?? []).filter((f) => {
      if (cat && f.category !== cat) return false;
      if (band && f.risk_band !== band) return false;
      if (recOnly && !f.recommended) return false;
      if ((f.quality ?? 0) < minQ) return false;
      if ((f.risk ?? 0) > maxR) return false;
      if (q && !f.fund_name.toLowerCase().includes(q.toLowerCase())) return false;
      return true;
    });
    out.sort((a, b) => {
      if (sort === "quality") return (b.quality ?? 0) - (a.quality ?? 0);
      if (sort === "risk") return (a.risk ?? 0) - (b.risk ?? 0);
      return (a.rank ?? 999) - (b.rank ?? 999);
    });
    return out;
  }, [data, cat, band, recOnly, minQ, maxR, q, sort]);

  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);

  return (
    <Section>
      <h1 className="font-display text-4xl md:text-5xl mb-2">Browse all funds</h1>
      <p className="text-muted-foreground mb-8">{isLoading ? "Loading…" : `${filtered.length} of ${data?.length ?? 0} live funds.`}</p>

      <Card className="p-4 mb-6 grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        <div>
          <div className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-1">Category</div>
          <select value={cat} onChange={(e) => { setCat(e.target.value); setPage(0); }}
            className="w-full hairline bg-background text-sm px-2 py-1.5 rounded-sm">
            <option value="">All categories</option>
            {cats.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <div className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-1">Risk band</div>
          <div className="flex gap-1">
            {["", "Conservative", "Balanced", "Aggressive"].map((b) => (
              <button key={b || "all"} onClick={() => { setBand(b); setPage(0); }}
                className={`text-xs px-2 py-1.5 rounded-sm hairline ${band === b ? "bg-surface-2 text-foreground" : "text-muted-foreground"}`}>
                {b || "All"}
              </button>
            ))}
          </div>
        </div>
        <div>
          <div className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-1">Search</div>
          <input value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} placeholder="Fund name…"
            className="w-full hairline bg-background text-sm px-2 py-1.5 rounded-sm" />
        </div>
        <div className="flex items-end">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={recOnly} onChange={(e) => { setRecOnly(e.target.checked); setPage(0); }} />
            Recommended only
          </label>
        </div>
        <div>
          <div className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-1">Min Quality {minQ}</div>
          <input type="range" min={0} max={100} value={minQ} onChange={(e) => { setMinQ(+e.target.value); setPage(0); }} className="w-full" />
        </div>
        <div>
          <div className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-1">Max Risk {maxR}</div>
          <input type="range" min={0} max={100} value={maxR} onChange={(e) => { setMaxR(+e.target.value); setPage(0); }} className="w-full" />
        </div>
      </Card>

      <Card className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-left border-b border-hairline">
            <tr className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">
              <th className="p-3 cursor-pointer" onClick={() => setSort("rank")}>Rank</th>
              <th className="p-3">Fund</th>
              <th className="p-3 hidden md:table-cell">Category</th>
              <th className="p-3 cursor-pointer" onClick={() => setSort("quality")}>Quality</th>
              <th className="p-3 cursor-pointer" onClick={() => setSort("risk")}>Risk</th>
            </tr>
          </thead>
          <tbody>
            {paged.map((f) => (
              <tr key={f.scheme_id} className="border-b border-hairline hover:bg-surface-2 transition-colors">
                <td className="p-3 font-mono text-xs text-muted-foreground">{f.rank}</td>
                <td className="p-3">
                  <Link to="/fund/$schemeId" params={{ schemeId: String(f.scheme_id) }} className="hover:text-brand">
                    {f.fund_name}
                    {f.recommended && <span className="ml-2 text-[10px] text-brand">★</span>}
                  </Link>
                </td>
                <td className="p-3 text-xs text-muted-foreground hidden md:table-cell">{f.category}</td>
                <td className="p-3 font-display text-lg text-good">{f.quality ?? "—"}</td>
                <td className="p-3 font-display text-lg text-caution">{f.risk ?? "—"} <span className="text-[10px] text-muted-foreground font-mono uppercase tracking-widest ml-1">{f.risk_band}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4 text-sm">
          <button disabled={page === 0} onClick={() => setPage(page - 1)} className="tag disabled:opacity-30 hover:text-foreground">← Prev</button>
          <div className="font-mono text-xs text-muted-foreground">Page {page + 1} / {totalPages}</div>
          <button disabled={page + 1 >= totalPages} onClick={() => setPage(page + 1)} className="tag disabled:opacity-30 hover:text-foreground">Next →</button>
        </div>
      )}
    </Section>
  );
}
