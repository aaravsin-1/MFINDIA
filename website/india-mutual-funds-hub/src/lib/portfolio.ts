import { useEffect, useState } from "react";

export type Holding = { scheme_id: number; amount: number };
const KEY = "mfr_portfolio_v1";

function read(): Holding[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(KEY) || "[]");
  } catch {
    return [];
  }
}

function write(h: Holding[]) {
  localStorage.setItem(KEY, JSON.stringify(h));
  window.dispatchEvent(new Event("mfr:portfolio"));
}

export function usePortfolio() {
  const [portfolio, setPortfolio] = useState<Holding[]>([]);
  useEffect(() => {
    setPortfolio(read());
    const on = () => setPortfolio(read());
    window.addEventListener("mfr:portfolio", on);
    window.addEventListener("storage", on);
    return () => {
      window.removeEventListener("mfr:portfolio", on);
      window.removeEventListener("storage", on);
    };
  }, []);
  return {
    portfolio,
    add: (scheme_id: number, amount = 10000) => {
      const cur = read();
      if (cur.find((h) => h.scheme_id === scheme_id)) return;
      write([...cur, { scheme_id, amount }]);
    },
    remove: (scheme_id: number) => write(read().filter((h) => h.scheme_id !== scheme_id)),
    setAmount: (scheme_id: number, amount: number) =>
      write(read().map((h) => (h.scheme_id === scheme_id ? { ...h, amount } : h))),
    has: (scheme_id: number) => portfolio.some((h) => h.scheme_id === scheme_id),
  };
}
