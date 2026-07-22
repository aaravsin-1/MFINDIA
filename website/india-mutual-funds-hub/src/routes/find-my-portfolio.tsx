import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Section, Card } from "@/components/ui-bits";
import { usePortfolio } from "@/lib/portfolio";
import {
  QUESTIONS, classify, targetAllocation, type Profile,
} from "@/lib/investor-profile";
import {
  candidatesByCategory, candidateIds, buildPortfolio, portfolioStats,
  type FundRow, type Pick,
} from "@/lib/portfolio-builder";
import {
  toDist, lookThrough, effectiveStocks, type RawHolding, type FundInput,
} from "@/lib/optimise";

const sb = supabase as any;
const pct = (x: number) => `${Math.round(x * 100)}%`;

export const Route = createFileRoute("/find-my-portfolio")({
  head: () => ({
    meta: [
      { title: "Find my portfolio — FundLens" },
      { name: "description", content: "Answer 10 questions to discover your investor type, then get an equity portfolio optimised for both risk and return." },
    ],
  }),
  component: FindMyPortfolio,
});

function FindMyPortfolio() {
  const [step, setStep] = useState(-1); // -1 intro, 0..9 questions, 10 result
  const [answers, setAnswers] = useState<(number | null)[]>(QUESTIONS.map(() => null));

  const answered = answers.filter((a) => a != null).length;
  const setAns = (qi: number, oi: number) => {
    const next = [...answers]; next[qi] = oi; setAnswers(next);
    if (qi < QUESTIONS.length - 1) setTimeout(() => setStep(qi + 1), 120);
    else setStep(QUESTIONS.length);
  };

  if (step === -1) return <Intro onStart={() => setStep(0)} />;
  if (step >= 0 && step < QUESTIONS.length) {
    const q = QUESTIONS[step];
    return (
      <Section>
        <div className="max-w-2xl mx-auto">
          <Progress step={step} total={QUESTIONS.length} answered={answered} onJump={setStep} />
          <div className="tag mt-8 mb-3">{q.axis}</div>
          <h1 className="font-display text-2xl md:text-3xl mb-2 leading-tight">
            {step + 1}. {q.prompt}
          </h1>
          {q.help && <p className="text-sm text-muted-foreground mb-6">{q.help}</p>}
          <div className="grid gap-2 mt-6">
            {q.options.map((o, oi) => (
              <button key={oi} onClick={() => setAns(step, oi)}
                className={`text-left hairline rounded-md p-4 hover:bg-surface-2 transition-colors ${
                  answers[step] === oi ? "!border-brand bg-surface-2" : ""}`}>
                <span className="text-[14px]">{o.label}</span>
              </button>
            ))}
          </div>
          <div className="flex justify-between mt-8">
            <button onClick={() => setStep(step - 1 < 0 ? -1 : step - 1)} className="tag hover:text-foreground">← Back</button>
            {answers[step] != null && (
              <button onClick={() => setStep(step + 1)} className="tag hover:text-foreground">Skip / Next →</button>
            )}
          </div>
        </div>
      </Section>
    );
  }
  return <Result answers={answers} onRetake={() => { setAnswers(QUESTIONS.map(() => null)); setStep(-1); }} onEdit={(i) => setStep(i)} />;
}

function Intro({ onStart }: { onStart: () => void }) {
  return (
    <Section eyebrow="Find my portfolio"
      title="Ten questions. Your investor type. A portfolio built for it."
      lede="We profile you on three research-backed axes — risk capacity, risk tolerance, and behavioral style — then construct an equity portfolio from our rated universe, optimised for both risk and return.">
      <Card className="p-6 max-w-2xl">
        <div className="grid sm:grid-cols-3 gap-4 mb-6 text-sm">
          <Axis n="1" t="Risk capacity" d="Your objective ability to take risk — horizon, income, buffer." />
          <Axis n="2" t="Risk tolerance" d="Your psychological willingness — how you handle a drawdown." />
          <Axis n="3" t="Behavioral style" d="Active vs passive, and the biases that trip you up." />
        </div>
        <p className="text-xs text-muted-foreground mb-6">
          Grounded in the risk capacity/tolerance standard and Pompian's Behavioral Investor Types
          (Preserver · Follower · Independent · Accumulator). 3 × 3 × 4 = 36 investor types.
        </p>
        <button onClick={onStart}
          className="tag !border-brand !text-brand hover:bg-brand/10 transition-colors text-[13px]">
          Start — takes about 2 minutes →
        </button>
      </Card>
    </Section>
  );
}

function Axis({ n, t, d }: { n: string; t: string; d: string }) {
  return (
    <div className="hairline rounded-sm p-3">
      <div className="font-mono text-[10px] text-brand">AXIS {n}</div>
      <div className="text-[13px] font-medium mt-1">{t}</div>
      <div className="text-[11px] text-muted-foreground mt-1 leading-relaxed">{d}</div>
    </div>
  );
}

function Progress({ step, total, answered, onJump }: { step: number; total: number; answered: number; onJump: (i: number) => void }) {
  return (
    <div>
      <div className="flex items-center justify-between font-mono text-[10px] uppercase tracking-widest text-muted-foreground mb-2">
        <span>Question {step + 1} / {total}</span>
        <span>{answered} answered</span>
      </div>
      <div className="flex gap-1">
        {Array.from({ length: total }).map((_, i) => (
          <button key={i} onClick={() => onJump(i)}
            className={`h-1 flex-1 rounded-full transition-colors ${i <= step ? "bg-brand" : "bg-hairline"}`} />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
function Result({ answers, onRetake, onEdit }: {
  answers: (number | null)[]; onRetake: () => void; onEdit: (i: number) => void;
}) {
  const profile = useMemo(() => classify(answers), [answers]);
  const alloc = useMemo(() => targetAllocation(profile), [profile]);
  const [emphasis, setEmphasis] = useState(alloc.riskEmphasisDefault);

  const fundsQ = useQuery({
    queryKey: ["fmp_funds"],
    queryFn: async () => {
      const { data } = await sb.from("funds")
        .select("scheme_id,fund_name,category,quality,risk,risk_band,recommended")
        .eq("snapshot", "live").limit(2000);
      return (data ?? []) as FundRow[];
    },
  });

  const cands = useMemo(
    () => (fundsQ.data ? candidatesByCategory(fundsQ.data, alloc.mix, emphasis) : {}),
    [fundsQ.data, alloc.mix, emphasis]);
  const ids = useMemo(() => candidateIds(cands), [cands]);

  const holdingsQ = useQuery({
    queryKey: ["fmp_holdings", ids.slice().sort().join(",")],
    enabled: ids.length > 0,
    queryFn: async () => {
      const { data } = await sb.from("fund_holdings")
        .select("scheme_id,instrument,isin,industry,pct_nav,source").in("scheme_id", ids);
      return (data ?? []) as RawHolding[];
    },
  });

  const holdingsById = useMemo(() => {
    const m = new Map<number, RawHolding[]>();
    for (const h of holdingsQ.data ?? []) {
      if (!m.has(h.scheme_id)) m.set(h.scheme_id, []);
      m.get(h.scheme_id)!.push(h);
    }
    return m;
  }, [holdingsQ.data]);

  const built = useMemo(
    () => (fundsQ.data ? buildPortfolio(fundsQ.data, alloc, holdingsById, emphasis) : { picks: [], equityCovered: 0 }),
    [fundsQ.data, alloc, holdingsById, emphasis]);

  const stats = portfolioStats(built.picks);
  const exposure = useMemo(() => {
    const inputs: FundInput[] = built.picks
      .filter((p) => holdingsById.get(p.scheme_id)?.length)
      .map((p) => ({ ...p, category: p.category, amount: p.weight, holdings: holdingsById.get(p.scheme_id)! } as any));
    if (inputs.length === 0) return [];
    const dists = inputs.map(toDist);
    return lookThrough(dists, dists.map((d) => d.amount));
  }, [built.picks, holdingsById]);
  const effStocks = exposure.length ? effectiveStocks(exposure) : 0;

  return (
    <Section>
      <div className="max-w-4xl mx-auto">
        <button onClick={onRetake} className="tag mb-6 hover:text-foreground">← Retake</button>

        {/* type header */}
        <div className="tag mb-3">Your investor type</div>
        <h1 className="font-display text-4xl md:text-5xl mb-2">{profile.name}</h1>
        <p className="text-muted-foreground mb-5 max-w-2xl">{profile.tagline}</p>
        <div className="flex flex-wrap gap-2 mb-8">
          <Chip k="Capacity" v={profile.capacity} onClick={() => onEdit(0)} />
          <Chip k="Tolerance" v={profile.tolerance} onClick={() => onEdit(5)} />
          <Chip k="Style" v={profile.behavioral} onClick={() => onEdit(8)} />
          <span className="tag">Risk tier {profile.tier}/5</span>
        </div>

        {/* coaching + biases */}
        <div className="grid md:grid-cols-2 gap-4 mb-8">
          <Card className="p-5">
            <div className="mono-label mb-3">How to work with your wiring</div>
            <ul className="space-y-2 text-sm">
              {profile.coaching.map((c, i) => (
                <li key={i} className="flex gap-2"><span className="text-brand">▪</span><span className="leading-relaxed">{c}</span></li>
              ))}
            </ul>
          </Card>
          <Card className="p-5">
            <div className="mono-label mb-3">Biases to watch</div>
            <div className="flex flex-wrap gap-2">
              {profile.biases.map((b) => <span key={b} className="tag !text-caution !border-caution">{b}</span>)}
            </div>
            <div className="mono-label mt-5 mb-2">Suggested overall split</div>
            <SplitBar equityPct={alloc.equityPct} safeLabel={alloc.safeLabel} />
          </Card>
        </div>

        {/* the portfolio */}
        <div className="flex items-baseline justify-between mb-1 flex-wrap gap-2">
          <h2 className="font-display text-2xl">Your equity portfolio</h2>
          <Emphasis value={emphasis} onChange={setEmphasis} />
        </div>
        <p className="text-xs text-muted-foreground mb-5">
          {fundsQ.isLoading ? "Loading universe…" :
            `${built.picks.length} funds across ${new Set(built.picks.map(p=>p.category)).size} categories, picked for high Quality and controlled Risk, then checked for stock overlap.`}
        </p>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-hairline hairline rounded-md overflow-hidden mb-6">
          <Metric label="Blended Quality" value={String(stats.quality)} tone="good" hint="rupee-weighted, /100" />
          <Metric label="Blended Risk" value={String(stats.risk)} tone="caution" hint="volatility + drawdown, /100" />
          <Metric label="Funds" value={String(built.picks.length)} hint={`cap ${pct(alloc.perFundCap)} each`} />
          <Metric label="Effective stocks" value={effStocks ? effStocks.toFixed(0) : "—"} hint="look-through diversity" />
        </div>

        <div className="hairline rounded-md overflow-hidden mb-4">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline text-left">
                <th className="px-3 py-2 mono-label font-normal">Fund</th>
                <th className="px-3 py-2 mono-label font-normal text-right w-20">Weight</th>
                <th className="px-3 py-2 mono-label font-normal text-right w-16 hidden sm:table-cell">Qual</th>
                <th className="px-3 py-2 mono-label font-normal text-right w-16 hidden sm:table-cell">Risk</th>
              </tr>
            </thead>
            <tbody>
              {built.picks.map((p) => (
                <tr key={p.scheme_id} className="border-b border-hairline last:border-0 align-top">
                  <td className="px-3 py-2.5">
                    <Link to="/fund/$schemeId" params={{ schemeId: String(p.scheme_id) }} className="hover:text-brand text-[13px]">{p.fund_name}</Link>
                    <div className="text-[11px] text-muted-foreground mt-0.5">{p.category} · {p.reason}</div>
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-brand">{pct(p.weight)}</td>
                  <td className="px-3 py-2.5 text-right font-mono text-good hidden sm:table-cell">{p.quality ?? "—"}</td>
                  <td className="px-3 py-2.5 text-right font-mono text-caution hidden sm:table-cell">{p.risk ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {exposure.length > 0 && (
          <Card className="p-5 mb-6">
            <div className="mono-label mb-3">Where your money really sits — top 10 stocks (look-through)</div>
            <div className="grid sm:grid-cols-2 gap-x-6 gap-y-1.5">
              {exposure.slice(0, 10).map((e) => (
                <div key={e.key} className="flex items-center gap-2 text-[12px]">
                  <div className="flex-1 truncate">{e.name}</div>
                  <div className="font-mono tabular-nums text-muted-foreground">{(e.weight * 100).toFixed(1)}%</div>
                </div>
              ))}
            </div>
          </Card>
        )}

        <SaveBar picks={built.picks} />

        <p className="text-[11px] text-muted-foreground mt-8 leading-relaxed border-t border-hairline pt-4">
          Educational tool, not investment advice and not SEBI-registered. The overall equity split is
          general guidance — the fund picks cover only the equity sleeve (our rated universe is equity
          funds). Quality is a within-category rank, not a return forecast. Consult a registered
          adviser before investing.
        </p>
      </div>
    </Section>
  );
}

function Chip({ k, v, onClick }: { k: string; v: string; onClick: () => void }) {
  return (
    <button onClick={onClick} className="tag hover:!border-brand hover:!text-brand transition-colors">
      {k}: <span className="text-foreground">{v}</span>
    </button>
  );
}

function SplitBar({ equityPct, safeLabel }: { equityPct: number; safeLabel: string }) {
  return (
    <div>
      <div className="flex h-6 rounded-sm overflow-hidden hairline">
        <div className="bg-brand/60 flex items-center justify-center text-[10px] font-mono" style={{ width: `${equityPct}%` }}>{equityPct}% equity</div>
        <div className="bg-surface-2 flex items-center justify-center text-[10px] font-mono text-muted-foreground" style={{ width: `${100 - equityPct}%` }}>{100 - equityPct}%</div>
      </div>
      <div className="text-[10px] text-muted-foreground mt-1.5">The {100 - equityPct}% belongs in {safeLabel}. This page builds the equity portion.</div>
    </div>
  );
}

function Emphasis({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">Lower risk</span>
      <input type="range" min={0} max={100} value={value * 100} onChange={(e) => onChange(+e.target.value / 100)} className="w-28" />
      <span className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">More return</span>
    </div>
  );
}

function Metric({ label, value, hint, tone = "default" }: {
  label: string; value: string; hint?: string; tone?: "default" | "good" | "caution";
}) {
  const t = { default: "text-foreground", good: "text-good", caution: "text-caution" }[tone];
  return (
    <div className="p-4 bg-card">
      <div className="mono-label">{label}</div>
      <div className={`mt-2 font-mono text-2xl md:text-3xl leading-none tabular-nums ${t}`}>{value}</div>
      {hint && <div className="mt-2 text-[10px] text-muted-foreground leading-tight">{hint}</div>}
    </div>
  );
}

function SaveBar({ picks }: { picks: Pick[] }) {
  const { add, remove, portfolio } = usePortfolio();
  const [saved, setSaved] = useState(false);
  const TOTAL = 100000; // ₹1,00,000 illustrative
  const save = () => {
    portfolio.forEach((h) => remove(h.scheme_id));
    picks.forEach((p) => add(p.scheme_id, Math.max(500, Math.round((p.weight * TOTAL) / 500) * 500)));
    setSaved(true);
  };
  return (
    <div className="flex flex-wrap items-center gap-3">
      <button onClick={save} disabled={picks.length === 0}
        className="tag !border-brand !text-brand hover:bg-brand/10 transition-colors disabled:opacity-40">
        ▪ Save as my portfolio (₹1L example)
      </button>
      {saved && (
        <span className="text-[12px] text-good">
          Saved. <Link to="/optimise" className="underline">Open in the optimiser →</Link>
        </span>
      )}
    </div>
  );
}
