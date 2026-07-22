import { Link, useRouterState } from "@tanstack/react-router";

const nav = [
  { to: "/", label: "Overview" },
  { to: "/find-my-portfolio", label: "Find my portfolio" },
  { to: "/wizard", label: "Screener" },
  { to: "/browse", label: "Universe" },
  { to: "/optimise", label: "Optimiser" },
  { to: "/how-it-works", label: "Method" },
  { to: "/how-we-tested", label: "Validation" },
] as const;

export function SiteHeader() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  return (
    <header className="sticky top-0 z-30 backdrop-blur-md bg-background/90 border-b border-hairline">
      <div className="mx-auto max-w-7xl px-6 h-12 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-3 group">
          <div className="relative h-4 w-4">
            <div className="absolute inset-0 border border-brand" />
            <div className="absolute inset-[3px] bg-brand" />
          </div>
          <div className="leading-none flex items-baseline gap-2">
            <div className="text-[13px] tracking-tight font-semibold">FundLens</div>
            <div className="text-[9px] font-mono tracking-[0.2em] text-muted-foreground uppercase">
              / IN-EQ / v1.0
            </div>
          </div>
        </Link>

        <nav className="hidden md:flex items-center gap-0.5">
          {nav.map((n) => {
            const active =
              n.to === "/" ? pathname === "/" : pathname.startsWith(n.to);
            return (
              <Link
                key={n.to}
                to={n.to}
                className={`px-3 py-1 text-[11px] font-mono uppercase tracking-widest transition-colors ${
                  active
                    ? "text-brand"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {n.label}
              </Link>
            );
          })}
        </nav>

        <div className="hidden sm:flex items-center gap-3">
          <button
            onClick={() => alert("You can reach me at: aaravsinghal2005@gmail.com")}
            className="font-mono text-[10px] text-muted-foreground tracking-[0.2em] uppercase hover:text-brand transition-colors"
          >
            → contact
          </button>
        </div>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-hairline mt-20">
      <div className="mx-auto max-w-7xl px-6 py-8 space-y-4 text-[11px] text-muted-foreground">
        <div className="grid md:grid-cols-3 gap-6">
          <div>
            <div className="mono-label mb-2">Scope</div>
            <p className="leading-relaxed">Indian equity mutual funds · direct plans · month-end NAV series. Universe: 381 live-rated schemes.</p>
          </div>
          <div>
            <div className="mono-label mb-2">Method</div>
            <p className="leading-relaxed">Two independent scores — a within-category ML rank (Quality) and an absolute volatility + drawdown score (Risk). No return forecasts are produced or displayed.</p>
          </div>
          <div>
            <div className="mono-label mb-2">Disclaimer</div>
            <p className="leading-relaxed">Educational research tool. Not investment advice, not SEBI-registered. Past performance does not predict future results. Consult a registered advisor.</p>
          </div>
        </div>
        <div className="font-mono uppercase tracking-[0.2em] flex flex-col sm:flex-row gap-2 sm:justify-between pt-4 border-t border-hairline text-[10px]">
          <div>FundLens · IN-EQ Analytics Desk</div>
          <div>Not investment advice</div>
        </div>
      </div>
    </footer>
  );
}
