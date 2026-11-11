export type Unit = "count" | "currency" | "percent" | "ratio" | "number" | "date" | "pvalue" | "text";

/** Mirrors backend verify/numbers.py:format_value so UI and verified prose agree. */
export function formatValue(value: unknown, unit: Unit = "number"): string {
  if (value === null || value === undefined) return "n/a";
  if (typeof value === "string") return value;
  if (typeof value !== "number" || Number.isNaN(value)) return String(value);
  switch (unit) {
    case "currency":
      return `${value < 0 ? "-" : ""}$${Math.abs(value).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    case "percent":
      return `${value.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
    case "pvalue":
      return value < 0.001 ? "p < 0.001" : `p = ${value.toFixed(3)}`;
    case "count":
      return Math.round(value).toLocaleString("en-US");
    case "ratio":
      return value.toFixed(3);
    default:
      return Math.abs(value) >= 1000
        ? value.toLocaleString("en-US", { maximumFractionDigits: 0 })
        : value.toLocaleString("en-US", { maximumFractionDigits: 2 });
  }
}

export function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return Number.isInteger(value) ? value.toLocaleString("en-US") : value.toLocaleString("en-US", { maximumFractionDigits: 4 });
  if (typeof value === "boolean") return value ? "true" : "false";
  return String(value);
}

export function relativeTime(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}
