export { supabase } from "@/integrations/supabase/client";

// Formatting helpers
export const fmtPct = (v: number | null | undefined, digits = 1) =>
  v == null || Number.isNaN(v) ? "—" : `${(v * 100).toFixed(digits)}%`;

export const fmtPctRaw = (v: number | null | undefined, digits = 2) =>
  v == null || Number.isNaN(v) ? "—" : `${v.toFixed(digits)}%`;

export const fmtNum = (v: number | null | undefined, digits = 2) =>
  v == null || Number.isNaN(v) ? "—" : v.toFixed(digits);

// Indian number formatting: 431750 -> "4,31,750"
export const fmtINR = (n: number) => {
  if (!Number.isFinite(n)) return "—";
  const rounded = Math.round(n);
  const s = Math.abs(rounded).toString();
  if (s.length <= 3) return (rounded < 0 ? "-" : "") + s;
  const last3 = s.slice(-3);
  const rest = s.slice(0, -3);
  const withCommas = rest.replace(/\B(?=(\d{2})+(?!\d))/g, ",");
  return (rounded < 0 ? "-" : "") + withCommas + "," + last3;
};

// 431750 -> "4.3L", 43175000 -> "4.3Cr"
export const fmtINRShort = (n: number) => {
  if (!Number.isFinite(n)) return "—";
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (abs >= 1e7) return `${sign}₹${(abs / 1e7).toFixed(1)}Cr`;
  if (abs >= 1e5) return `${sign}₹${(abs / 1e5).toFixed(1)}L`;
  if (abs >= 1e3) return `${sign}₹${(abs / 1e3).toFixed(1)}K`;
  return `${sign}₹${abs.toFixed(0)}`;
};

export const fmtAUM = (lakh: number | null | undefined) => {
  if (lakh == null) return "—";
  const cr = lakh / 100;
  if (cr >= 1000) return `₹${(cr / 1000).toFixed(1)}kCr`;
  return `₹${cr.toFixed(0)}Cr`;
};
