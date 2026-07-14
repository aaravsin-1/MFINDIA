import { createFileRoute, Link } from "@tanstack/react-router";
import { Section, Card } from "@/components/ui-bits";

export const Route = createFileRoute("/how-it-works")({
  head: () => ({
    meta: [
      { title: "Method — FundLens" },
      { name: "description", content: "The two scores explained: within-category Quality rank and absolute Risk score." },
    ],
  }),
  component: HowItWorks,
});

function HowItWorks() {
  return (
    <Section eyebrow="METHOD" title="Two independent scores.">
      <div className="max-w-3xl">
        <p className="text-[14px] text-muted-foreground mb-10">
          FundLens does not produce return forecasts. It produces two orthogonal descriptive scores per fund and lets you screen the universe on them.
        </p>

        <Card className="p-6 mb-4">
          <div className="section-marker !text-good mb-3">◆ QUALITY · WITHIN-CATEGORY</div>
          <p className="text-[13px] leading-relaxed">
            A gradient-boosted model ranks each fund against <em>only its SEBI-category peers</em> — Small Cap against Small Cap,
            ELSS against ELSS. Features are multi-year risk-adjusted return statistics, consistency measures,
            expense ratio, AUM stability, and manager tenure. Output is a 0–100 percentile within the peer group.
          </p>
          <p className="text-[12px] text-muted-foreground mt-3">
            Never compare Quality across categories. A Small Cap 90 and a Large Cap 90 are each strong within their own peer set.
          </p>
        </Card>

        <Card className="p-6 mb-4">
          <div className="section-marker !text-caution mb-3">◆ RISK · ABSOLUTE MATHS</div>
          <p className="text-[13px] leading-relaxed">
            Realized volatility of monthly returns plus worst historical drawdown, normalized to a 0–100 scale and
            bucketed into Conservative / Balanced / Aggressive. This is descriptive statistics — how the fund has
            actually behaved — not a prediction.
          </p>
        </Card>

        <Card className="p-6 mb-10">
          <div className="section-marker mb-3">◆ SCREENING</div>
          <p className="text-[13px] leading-relaxed">
            Screening operates within a category and within a risk band. The tool surfaces the highest within-category
            Quality scores that match your absolute-risk preference. It does not tell you which <em>category</em> to hold —
            that is an allocation decision, and no one has an edge there.
          </p>
        </Card>

        <div className="mt-10 flex gap-3">
          <Link to="/wizard" className="hairline bg-brand text-background px-4 py-2 text-[12px] font-mono uppercase tracking-widest">→ Open screener</Link>
          <Link to="/how-we-tested" className="hairline px-4 py-2 text-[12px] font-mono uppercase tracking-widest hover:bg-surface-2">Validation</Link>
        </div>
      </div>
    </Section>
  );
}
