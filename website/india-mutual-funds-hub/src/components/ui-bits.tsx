import type { ReactNode } from "react";

export function Section({
  eyebrow,
  title,
  lede,
  children,
  className = "",
}: {
  eyebrow?: string;
  title?: ReactNode;
  lede?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <section className={`mx-auto max-w-7xl px-6 py-14 ${className}`}>
      {(eyebrow || title || lede) && (
        <header className="mb-8 max-w-4xl border-b border-hairline pb-6">
          {eyebrow && (
            <div className="section-marker mb-3">
              <span>▪</span>
              {eyebrow}
            </div>
          )}
          {title && (
            <h2 className="font-display text-2xl md:text-3xl leading-tight">
              {title}
            </h2>
          )}
          {lede && <p className="mt-3 text-muted-foreground text-[14px] leading-relaxed max-w-2xl">{lede}</p>}
        </header>
      )}
      {children}
    </section>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`hairline bg-card ${className}`}>{children}</div>
  );
}

export function Stat({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "default" | "good" | "caution" | "bad" | "brand";
}) {
  const toneCls = {
    default: "text-foreground",
    good: "text-good",
    caution: "text-caution",
    bad: "text-bad",
    brand: "text-brand",
  }[tone];
  return (
    <div className="p-5 bg-card">
      <div className="mono-label">{label}</div>
      <div className={`mt-3 font-mono text-3xl md:text-4xl font-medium leading-none tabular-nums ${toneCls}`}>{value}</div>
      {hint && <div className="mt-3 text-[11px] text-muted-foreground leading-relaxed">{hint}</div>}
    </div>
  );
}
