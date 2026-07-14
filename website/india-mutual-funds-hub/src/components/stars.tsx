import { Star } from "lucide-react";

export function Stars({ n, className = "" }: { n: number | null; className?: string }) {
  if (n == null) return <span className="text-muted-foreground text-xs">unrated</span>;
  return (
    <div className={`inline-flex items-center gap-0.5 ${className}`} aria-label={`${n} stars`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Star
          key={i}
          className={`h-3.5 w-3.5 ${
            i <= n ? "fill-star text-star" : "text-hairline"
          }`}
          strokeWidth={1.5}
        />
      ))}
    </div>
  );
}
