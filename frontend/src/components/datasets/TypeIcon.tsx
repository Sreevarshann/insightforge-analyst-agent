import { Binary, Calendar, CaseSensitive, Hash, ToggleLeft } from "lucide-react";

export function kindOf(type: string): "numeric" | "temporal" | "text" | "boolean" | "other" {
  const t = type.toUpperCase();
  if (/INT|DOUBLE|FLOAT|DECIMAL|REAL|HUGEINT/.test(t)) return "numeric";
  if (/DATE|TIME/.test(t)) return "temporal";
  if (t === "BOOLEAN") return "boolean";
  if (t === "VARCHAR") return "text";
  return "other";
}

export function TypeIcon({ type, className = "size-3.5" }: { type: string; className?: string }) {
  const k = kindOf(type);
  const Icon = k === "numeric" ? Hash : k === "temporal" ? Calendar : k === "boolean" ? ToggleLeft : k === "text" ? CaseSensitive : Binary;
  return <Icon className={`${className} shrink-0 ${k === "numeric" ? "text-lime" : k === "temporal" ? "text-sky" : "text-muted"}`} aria-label={type} />;
}
