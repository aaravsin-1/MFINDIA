import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Section, Card } from "@/components/ui-bits";
import { usePortfolio } from "@/lib/portfolio";
import {
  type FundInput, type RawHolding, type FundDist,
  toDist, lookThrough, sectorExposure, overlapMatrix,
  effectiveStocks, weightedQuality, optimise,
  avgPairwiseOverlap, redundantPairs, weightedRisk,
} from "@/lib/optimise";

const sb = supabase as any;

export const Route = createFileRoute("/optimise")({
  head: () => ({
    meta: [
      { title: "Portfolio optimiser — FundLens" },
      { name: "description", content: "X-ray the funds you own down to their shared stocks: see how much they overlap, which funds are duplicates, and rebalance to cut the overlap." },
    ],
  }),
  component: Optimiser,
});

const INR = (n: number) => "₹" + Math.round(n).toLocaleString("en-IN");
const pct = (x: number) => (x * 100).toFixed(1) + "%";

type FundMeta = {
  scheme_id: number; fund_name: string; category: string | null;
  quality: number | null; risk: number | null; risk_band: string | null;
};

function Optimiser() {
  const { portfolio, add, remove, setAmount } = usePortfolio();
  const ids = portfolio.map((h) => h.scheme_id);

  const meta = useQuery({
    queryKey: ["opt_meta", ids.slice().sort().join(",")],
    enabled: ids.length > 0,
    queryFn: async () => {
      const { data } = await sb
        .from("funds")
        .select("scheme_id,fund_name,category,quality,risk,risk_band")
        .eq("snapshot", "live")
        .in("scheme_id", ids);
      return (data ?? []) as FundMeta[];
    },
  });

  const holdings = useQuery({
    queryKey: ["opt_holdings", ids.slice().sort().join(",")],
    enabled: ids.length > 0,
    queryFn: async () => {
      const { data } = await sb
        .from("fund_holdings")
        .select("scheme_id,instrument,isin,industry,pct_nav,source")
        .in("scheme_id", ids);
      return (data ?? []) as RawHolding[];
    },
  });

  const inputs: FundInput[] = useMemo(() => {
    const m = new Map((meta.data ?? []).map((f) => [f.scheme_id, f]));
    const byFund = new Map<number, RawHolding[]>();
    for (const h of holdings.data ?? []) {
      if (!byFund.has(h.scheme_id)) byFund.set(h.scheme_id, []);
      byFund.get(h.scheme_id)!.push(h);
    }
    return portfolio.map((p) => {
      const f = m.get(p.scheme_id);
      return {
        scheme_id: p.scheme_id,
        fund_name: f?.fund_name ?? `Scheme ${p.scheme_id}`,
        category: f?.category ?? null,
        quality: f?.quality ?? null,
        risk: f?.risk ?? null,
        risk_band: f?.risk_band ?? null,
        amount: p.amount,
        holdings: byFund.get(p.scheme_id) ?? [],
      };
    });
  }, [portfolio, meta.data, holdings.data]);

  const withHoldings = inputs.filter((f) => f.holdings.length > 0);
  const missing = inputs.filter((f) => f.holdings.length === 0);

  if (ids.length === 0) return <EmptyState add={add} />;

  return (
    <Section
      eyebrow="Portfolio optimiser"
      title="Are your funds secretly the same bet?"
      lede="Own several funds and they often hold the same stocks — so you pay twice for one position and feel diversified when you aren't. This tool X-rays your funds down to the shared stocks, flags the duplicates, and rebalances to cut the overlap."
    >
      <div className="grid lg:grid-cols-[340px_1fr] gap-6">
        <div className="space-y-4">
          <AddFund add={add} heldIds={ids} />
          <Holdings inputs={inputs} remove={remove} setAmount={setAmount} />
        </div>

        <div className="space-y-6">
          {holdings.isLoading || meta.isLoading ? (
            <Card className="p-8 text-sm text-muted-foreground">Loading holdings…</Card>
          ) : withHoldings.length === 0 ? (
            <Card className="p-8 text-sm text-muted-foreground">
              None of your funds have disclosed holdings in our dataset yet. Try adding an
              equity fund — 368 of the rated funds have look-through data.
            </Card>
          ) : (
            <Analysis funds={withHoldings} missing={missing} remove={remove} setAmount={setAmount} />
          )}
        </div>
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------------------
function Analysis({ funds, missing, remove, setAmount }: {
  funds: FundInput[]; missing: FundInput[];
  remove: (id: number) => void; setAmount: (id: number, amt: number) => void;
}) {
  const dists: FundDist[] = useMemo(() => funds.map(toDist), [funds]);
  const amtTotal = funds.reduce((s, f) => s + f.amount, 0) || 1;
  const currentW = funds.map((f) => f.amount / amtTotal);

  const [preset, setPreset] = useState<"cut" | "balance" | "quality">("cut");
  const gamma = preset === "cut" ? 0.2 : preset === "balance" ? 0.5 : 0.8;
  const suggestedW = useMemo(() => optimise(dists, gamma, { cap: 0.6 }), [dists, gamma]);
  const [undoAmts, setUndoAmts] = useState<{ id: number; amt: number }[] | null>(null);

  const curExp = useMemo(() => lookThrough(dists, currentW), [dists, currentW]);
  const sugExp = useMemo(() => lookThrough(dists, suggestedW), [dists, suggestedW]);
  const sectors = useMemo(() => sectorExposure(curExp), [curExp]);
  const mtx = useMemo(() => overlapMatrix(dists), [dists]);
  const pairs = useMemo(() => redundantPairs(dists, 30), [dists]);

  const presentCats = new Set(funds.map((f) => f.category));
  const CORE = ["Large Cap Fund", "Mid Cap Fund", "Small Cap Fund", "Flexi Cap Fund"];
  const missingCats = CORE.filter((c) => !presentCats.has(c)).map((c) => c.replace(" Fund", ""));

  const single = dists.length < 2;
  const curOv = avgPairwiseOverlap(dists, currentW);
  const sugOv = avgPairwiseOverlap(dists, suggestedW);
  const curEff = effectiveStocks(curExp);
  const sugEff = effectiveStocks(sugExp);
  const curQ = weightedQuality(dists, currentW);
  const sugQ = weightedQuality(dists, suggestedW);
  const curRisk = weightedRisk(dists, currentW);
  const sugRisk = weightedRisk(dists, suggestedW);
  const topStock = curExp[0];
  const avgCoverage = dists.reduce((s, f) => s + f.coverage, 0) / dists.length;

  const verdict = curOv < 12
    ? { t: "Well diversified", tone: "good" as const, border: "border-good/50", txt: "text-good",
        msg: "Your funds barely share stocks — each one is pulling its own weight." }
    : curOv < 28
    ? { t: "Some duplication", tone: "caution" as const, border: "border-caution/50", txt: "text-caution",
        msg: "A few of your funds lean on the same names. Worth trimming the weakest." }
    : { t: "Heavy duplication", tone: "bad" as const, border: "border-bad/50", txt: "text-bad",
        msg: "Your funds are largely the same bet — extra fees for little extra diversification." };

  const applySuggested = () => {
    setUndoAmts(funds.map((f) => ({ id: f.scheme_id, amt: f.amount })));
    funds.forEach((f, i) =>
      setAmount(f.scheme_id, Math.max(500, Math.round((amtTotal * suggestedW[i]) / 500) * 500)));
  };
  const undo = () => { undoAmts?.forEach((p) => setAmount(p.id, p.amt)); setUndoAmts(null); };

  return (
    <>
      {missing.length > 0 && (
        <div className="tag !text-caution !border-caution">
          {missing.length} held fund{missing.length > 1 ? "s" : ""} excluded — no holdings data
        </div>
      )}

      {/* 1 · plain-English verdict */}
      <Card className={`p-6 border ${verdict.border}`}>
        {single ? (
          <div className="text-sm text-muted-foreground">Add a second fund to see how much they overlap.</div>
        ) : (
          <>
            <div className="flex items-baseline gap-3 flex-wrap">
              <div className="font-display text-5xl tabular-nums">{curOv.toFixed(0)}%</div>
              <div>
                <div className={`text-sm font-medium ${verdict.txt}`}>{verdict.t}</div>
                <div className="text-[11px] text-muted-foreground">average overlap between any two of your funds</div>
              </div>
            </div>
            <p className="text-sm text-muted-foreground mt-3 max-w-xl">{verdict.msg}</p>
          </>
        )}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-hairline hairline rounded-md overflow-hidden mt-5">
          <Metric label="Really holding" value={`${curEff.toFixed(0)}`} hint={`distinct stocks, across ${funds.length} funds`} />
          <Metric label="Biggest single stock" value={topStock ? pct(topStock.weight) : "—"} hint={topStock?.name}
            tone={topStock && topStock.weight > 0.09 ? "caution" : "default"} />
          <Metric label="Blended Quality" value={curQ.toFixed(0)} hint="rupee-weighted /100" tone="good" />
          <Metric label="Blended Risk" value={curRisk.toFixed(1)} hint="rupee-weighted score" tone="default" />
        </div>
      </Card>

      {/* 2 · redundant funds — the strongest, most intuitive fix */}
      {pairs.length > 0 && (
        <Card className="p-5">
          <div className="mono-label mb-1">Funds doing the same job</div>
          <p className="text-xs text-muted-foreground mb-4 max-w-xl">
            These pairs hold largely the same stocks. Dropping the weaker one is the quickest way to cut
            overlap — you keep the exposure, lose the duplicate fee.
          </p>
          <div className="space-y-2">
            {pairs.slice(0, 3).map((p) => {
              const drop = dists[p.dropIdx], keep = dists[p.keepIdx];
              return (
                <div key={`${p.i}-${p.j}`} className="hairline rounded-sm p-3 flex items-center gap-3 flex-wrap">
                  <div className="font-mono text-xl tabular-nums text-caution w-14">{p.overlap.toFixed(0)}%</div>
                  <div className="flex-1 min-w-[220px] text-[12px]">
                    <span className="text-foreground">{shorten(keep.fund_name)}</span>
                    <span className="text-muted-foreground"> ⇄ </span>
                    <span className="text-foreground">{shorten(drop.fund_name)}</span>
                    <div className="text-[11px] text-muted-foreground mt-0.5">
                      Keep <span className="text-foreground">{shorten(keep.fund_name)}</span> (Q{keep.quality ?? "—"}) ·
                      it's the higher-Quality of the two.
                    </div>
                  </div>
                  <button onClick={() => remove(drop.scheme_id)}
                    className="tag hover:!border-bad hover:!text-bad transition-colors whitespace-nowrap">
                    ✕ Drop {shorten(drop.fund_name)}
                  </button>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* 3 · rebalance what you keep — actually updates the portfolio */}
      {!single && (
        <Card className="p-5">
          <div className="flex items-baseline justify-between flex-wrap gap-2 mb-1">
            <div className="mono-label">Or rebalance what you keep</div>
            <div className="flex gap-1">
              {([["cut", "Cut overlap"], ["balance", "Balance"], ["quality", "Keep Quality"]] as const).map(([k, l]) => (
                <button key={k} onClick={() => setPreset(k)}
                  className={`tag ${preset === k ? "!border-brand !text-brand" : "hover:text-foreground"}`}>{l}</button>
              ))}
            </div>
          </div>
          <p className="text-xs text-muted-foreground mb-4 max-w-xl">
            Shifts money toward the funds that add distinct stocks, keeping Quality in mind. No single fund exceeds 60%.
          </p>
          {sugOv > 25 && (
            <div className="text-[11px] text-caution mb-4 leading-relaxed hairline rounded-sm p-3 !border-caution/40">
              Reweighting can only do so much here — your funds hold too many of the same stocks. The real fix is to
              drop a duplicate above{missingCats.length > 0 ? ` and add a different category (e.g. ${missingCats.slice(0, 3).join(", ")})` : " and add a fund from a different category"} for genuine diversification.
            </div>
          )}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <Delta label="Avg overlap" from={curOv} to={sugOv} good="down" fmt={(x) => x.toFixed(0) + "%"} />
            <Delta label="Really holding" from={curEff} to={sugEff} good="up" fmt={(x) => x.toFixed(0)} />
            <Delta label="Blended Quality" from={curQ} to={sugQ} good="up" fmt={(x) => x.toFixed(0)} />
            <Delta label="Blended Risk" from={curRisk} to={sugRisk} good="down" fmt={(x) => x.toFixed(1)} />
          </div>
          <div className="space-y-1.5 mb-4">
            {dists.map((f, i) => (
              <div key={f.scheme_id} className="flex items-center gap-3 text-[12px]">
                <div className="flex-1 truncate">{shorten(f.fund_name)}</div>
                <div className="font-mono tabular-nums text-muted-foreground w-12 text-right">{pct(currentW[i])}</div>
                <div className="w-4 text-center text-muted-foreground">→</div>
                <div className="font-mono tabular-nums w-12 text-right text-brand">{pct(suggestedW[i])}</div>
              </div>
            ))}
          </div>
          <div className="flex gap-2 items-center flex-wrap">
            <button onClick={applySuggested}
              className="tag !border-brand !text-brand hover:bg-brand/10 transition-colors">
              ▪ Apply to my portfolio
            </button>
            {undoAmts && <button onClick={undo} className="tag hover:text-foreground">Undo</button>}
            {undoAmts && <span className="text-[11px] text-good">Rupee amounts updated on the left.</span>}
          </div>
        </Card>
      )}

      {/* 4 · combined look-through */}
      <div className="grid md:grid-cols-2 gap-6">
        <Card className="p-5">
          <div className="mono-label mb-3">Where your money really sits — top 15 stocks</div>
          <BarList items={curExp.slice(0, 15).map((e) => ({ name: e.name, weight: e.weight }))} />
          <p className="text-[10px] text-muted-foreground mt-3">
            Covers ≈ {pct(avgCoverage)} of NAV on average (disclosed top holdings only).
          </p>
        </Card>
        <Card className="p-5">
          <div className="mono-label mb-3">Sector mix</div>
          <BarList items={sectors.slice(0, 12).map((s) => ({ name: s.sector, weight: s.weight }))} tone="brand" />
        </Card>
      </div>

      {/* 5 · fund-by-fund overlap grid */}
      {dists.length > 1 && (
        <Card className="p-5 overflow-x-auto">
          <div className="mono-label mb-1">Fund-by-fund overlap</div>
          <p className="text-xs text-muted-foreground mb-4 max-w-xl">
            Each cell is how much of two funds' stock baskets coincide. Darker = more duplication.
          </p>
          <table className="text-[11px] border-collapse">
            <tbody>
              {dists.map((f, i) => (
                <tr key={f.scheme_id}>
                  <td className="pr-3 py-1 whitespace-nowrap text-muted-foreground max-w-[220px] truncate">
                    {shorten(f.fund_name)}
                  </td>
                  {dists.map((_, j) => {
                    const v = mtx[i][j];
                    const self = i === j;
                    return (
                      <td key={j} className="p-0">
                        <div className="w-11 h-8 flex items-center justify-center font-mono tabular-nums"
                          style={{
                            background: self ? "var(--surface-2)" : overlapColor(v),
                            color: !self && v > 40 ? "black" : "var(--foreground)",
                          }}>
                          {self ? "·" : v.toFixed(0)}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
function AddFund({ add, heldIds }: { add: (id: number, amt?: number) => void; heldIds: number[] }) {
  const [q, setQ] = useState("");
  const { data } = useQuery({
    queryKey: ["opt_search", q],
    enabled: q.length >= 2,
    queryFn: async () => {
      const { data } = await sb
        .from("funds")
        .select("scheme_id,fund_name,category")
        .eq("snapshot", "live")
        .ilike("fund_name", `%${q}%`)
        .limit(8);
      return (data ?? []) as { scheme_id: number; fund_name: string; category: string }[];
    },
  });
  return (
    <Card className="p-4">
      <div className="mono-label mb-2">Add a fund</div>
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search fund name…"
        className="w-full hairline bg-background text-sm px-3 py-2 rounded-sm focus:outline-none focus:border-brand" />
      {q.length >= 2 && (
        <div className="mt-2 space-y-1">
          {(data ?? []).filter((f) => !heldIds.includes(f.scheme_id)).map((f) => (
            <button key={f.scheme_id} onClick={() => { add(f.scheme_id, 10000); setQ(""); }}
              className="w-full text-left text-[12px] px-2 py-1.5 rounded-sm hover:bg-surface-2 transition-colors">
              <span className="text-brand mr-1">＋</span>{f.fund_name}
              <span className="text-muted-foreground ml-1">· {f.category}</span>
            </button>
          ))}
          {data && data.length === 0 && <div className="text-[12px] text-muted-foreground px-2 py-1">No matches.</div>}
        </div>
      )}
    </Card>
  );
}

function Holdings({ inputs, remove, setAmount }: {
  inputs: FundInput[]; remove: (id: number) => void; setAmount: (id: number, a: number) => void;
}) {
  const total = inputs.reduce((s, f) => s + f.amount, 0);
  return (
    <Card className="p-4">
      <div className="flex items-baseline justify-between mb-3">
        <div className="mono-label">Your holdings · {inputs.length}</div>
        <div className="font-mono text-[11px] tabular-nums">{INR(total)}</div>
      </div>
      <div className="space-y-2">
        {inputs.map((f) => (
          <div key={f.scheme_id} className="hairline rounded-sm p-2.5">
            <div className="flex items-start gap-2">
              <Link to="/fund/$schemeId" params={{ schemeId: String(f.scheme_id) }}
                className="text-[12px] leading-tight flex-1 hover:text-brand">{f.fund_name}</Link>
              <button onClick={() => remove(f.scheme_id)}
                className="text-muted-foreground hover:text-bad text-xs leading-none">✕</button>
            </div>
            <div className="flex items-center gap-2 mt-2">
              <span className="text-[10px] text-muted-foreground font-mono">₹</span>
              <input type="number" min={0} step={1000} value={f.amount}
                onChange={(e) => setAmount(f.scheme_id, Math.max(0, +e.target.value))}
                className="w-28 hairline bg-background text-[12px] px-2 py-1 rounded-sm font-mono tabular-nums focus:outline-none focus:border-brand" />
              {f.holdings.length === 0 && <span className="tag !text-caution !border-caution">no holdings</span>}
              {f.quality != null && <span className="tag ml-auto">Q {f.quality}</span>}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function EmptyState({ add }: { add: (id: number, amt?: number) => void }) {
  return (
    <Section eyebrow="Portfolio optimiser" title="Are your funds secretly the same bet?">
      <Card className="p-6 max-w-xl">
        <p className="text-sm text-muted-foreground mb-4">
          Add the equity funds you hold (or are considering). We'll X-ray them down to the shared stocks,
          tell you how much they overlap, flag any duplicates, and rebalance to cut it.
        </p>
        <AddFund add={add} heldIds={[]} />
        <p className="text-[11px] text-muted-foreground mt-4">
          Not sure what you hold? Build a set from <Link to="/find-my-portfolio" className="underline text-foreground">Find my portfolio</Link>,
          or browse the <Link to="/browse" className="underline text-foreground">universe</Link>.
        </p>
      </Card>
    </Section>
  );
}

// ---- small presentational bits ---------------------------------------------
function Metric({ label, value, hint, tone = "default" }: {
  label: string; value: string; hint?: string; tone?: "default" | "good" | "caution" | "bad";
}) {
  const t = { default: "text-foreground", good: "text-good", caution: "text-caution", bad: "text-bad" }[tone];
  return (
    <div className="p-4 bg-card">
      <div className="mono-label">{label}</div>
      <div className={`mt-2 font-mono text-2xl md:text-3xl leading-none tabular-nums ${t}`}>{value}</div>
      {hint && <div className="mt-2 text-[10px] text-muted-foreground leading-tight truncate">{hint}</div>}
    </div>
  );
}

function Delta({ label, from, to, good, fmt }: {
  label: string; from: number; to: number; good: "up" | "down"; fmt: (x: number) => string;
}) {
  const diff = to - from;
  const better = good === "up" ? diff > 0.5 : diff < -0.5;
  const worse = good === "up" ? diff < -0.5 : diff > 0.5;
  const col = better ? "text-good" : worse ? "text-bad" : "text-muted-foreground";
  return (
    <div className="hairline rounded-sm p-3">
      <div className="mono-label">{label}</div>
      <div className="font-mono tabular-nums mt-1 flex items-baseline gap-2">
        <span className="text-muted-foreground">{fmt(from)}</span>
        <span className="text-muted-foreground">→</span>
        <span className={col}>{fmt(to)}</span>
      </div>
    </div>
  );
}

function BarList({ items, tone = "good" }: { items: { name: string; weight: number }[]; tone?: "good" | "brand" }) {
  const max = Math.max(...items.map((i) => i.weight), 0.0001);
  const bar = tone === "brand" ? "var(--brand)" : "var(--good)";
  return (
    <div className="space-y-1.5">
      {items.map((it) => (
        <div key={it.name} className="flex items-center gap-2 text-[11px]">
          <div className="w-40 truncate">{it.name}</div>
          <div className="flex-1 h-3 bg-surface-2 rounded-sm overflow-hidden">
            <div className="h-full rounded-sm" style={{ width: `${(it.weight / max) * 100}%`, background: bar, opacity: 0.55 }} />
          </div>
          <div className="w-12 text-right font-mono tabular-nums text-muted-foreground">{pct(it.weight)}</div>
        </div>
      ))}
    </div>
  );
}

function shorten(name: string): string {
  return name.replace(/\s+(Direct|Regular|Plan|Growth|-)\b.*$/i, "").slice(0, 40);
}

function overlapColor(v: number): string {
  // 0 -> transparent, 100 -> amber brand. simple linear alpha ramp.
  const a = Math.min(1, v / 70);
  return `color-mix(in oklch, var(--brand) ${Math.round(a * 100)}%, transparent)`;
}
