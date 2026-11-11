"use client";

import { AlertTriangle, Info } from "lucide-react";
import { useMemo, useState } from "react";
import type { ColumnProfile, Profile } from "@/lib/types";
import { formatCell, formatValue } from "@/lib/format";
import { cn } from "@/lib/cn";
import { Plot } from "../charts/Plot";
import { Badge, Card } from "../ui/primitives";
import { TypeIcon } from "./TypeIcon";

export function StatCards({ profile }: { profile: Profile }) {
  const cells = profile.row_count * profile.column_count;
  const stats = [
    { label: "Rows", value: formatValue(profile.row_count, "count") },
    { label: "Columns", value: formatValue(profile.column_count, "count") },
    { label: "Missing cells", value: `${formatValue(profile.total_missing_cells, "count")}`, sub: cells ? formatValue((100 * profile.total_missing_cells) / cells, "percent") : undefined },
    { label: "Duplicate rows", value: formatValue(profile.duplicate_rows, "count"), tone: profile.duplicate_rows ? "coral" : undefined },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {stats.map((s) => (
        <Card key={s.label} className="p-4">
          <p className="text-xs text-muted">{s.label}</p>
          <p className={cn("num mt-1 text-2xl font-semibold", s.tone === "coral" && "text-coral")}>{s.value}</p>
          {s.sub && <p className="num text-xs text-muted">{s.sub} of all cells</p>}
        </Card>
      ))}
    </div>
  );
}

export function Suggestions({ profile }: { profile: Profile }) {
  if (!profile.suggestions.length) return <p className="text-sm text-muted">No data-quality issues detected by the profiler.</p>;
  return (
    <ul className="flex flex-col gap-2">
      {profile.suggestions.map((s, i) => (
        <li key={i} className="flex items-start gap-3 rounded-lg bg-panel-2 px-3 py-2 text-sm">
          {s.severity === "warning" ? <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warn" aria-label="warning" /> : <Info className="mt-0.5 size-4 shrink-0 text-sky" aria-label="info" />}
          <span>
            {s.column && <code className="mr-1 rounded bg-panel px-1 text-xs">{s.column}</code>}
            {s.message}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function MissingChart({ profile }: { profile: Profile }) {
  const cols = profile.columns.filter((c) => c.null_count > 0).sort((a, b) => b.missing_pct - a.missing_pct);
  if (!cols.length) return <p className="text-sm text-muted">No missing values in any column.</p>;
  return (
    <Plot
      height={Math.max(160, cols.length * 28 + 60)}
      figure={{
        data: [{ type: "bar", orientation: "h", x: cols.map((c) => c.missing_pct), y: cols.map((c) => c.name), hovertemplate: "%{y}: %{x:.2f}% missing<extra></extra>" }],
        layout: { xaxis: { title: { text: "% missing" }, ticksuffix: "%" }, yaxis: { autorange: "reversed" }, margin: { l: 140, r: 16, t: 8, b: 40 } },
      }}
    />
  );
}

export function SchemaInspector({ profile }: { profile: Profile }) {
  const [selected, setSelected] = useState(profile.columns[0]?.name);
  const col = profile.columns.find((c) => c.name === selected) ?? profile.columns[0];
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(220px,280px)_1fr]">
      <ul role="listbox" aria-label="Columns" className="flex max-h-[520px] flex-col gap-0.5 overflow-auto rounded-xl border border-line p-1.5">
        {profile.columns.map((c) => (
          <li key={c.name} role="option" aria-selected={c.name === col?.name}>
            <button onClick={() => setSelected(c.name)} className={cn("flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm", c.name === col?.name ? "bg-panel-2" : "hover:bg-panel-2/60")}>
              <TypeIcon type={c.type} />
              <span className="flex-1 truncate">{c.name}</span>
              <span className="h-1.5 w-10 overflow-hidden rounded-full bg-panel-2" title={`${c.missing_pct.toFixed(1)}% missing`}>
                <span className="block h-full bg-coral" style={{ width: `${Math.min(100, c.missing_pct)}%` }} />
              </span>
            </button>
          </li>
        ))}
      </ul>
      {col && <ColumnDetail col={col} rows={profile.row_count} />}
    </div>
  );
}

function ColumnDetail({ col, rows }: { col: ColumnProfile; rows: number }) {
  const figure = useMemo(() => {
    if (col.numeric?.histogram.length) {
      const h = col.numeric.histogram;
      return { data: [{ type: "bar" as const, x: h.map((b) => (b.start + b.end) / 2), y: h.map((b) => b.count), width: h.map((b) => b.end - b.start), hovertemplate: "%{x:.4g}: %{y} rows<extra></extra>" }], layout: { bargap: 0.04, xaxis: { title: { text: col.name } }, yaxis: { title: { text: "rows" } } } };
    }
    if (col.top_values?.length) {
      return { data: [{ type: "bar" as const, orientation: "h" as const, x: col.top_values.map((t) => t.count), y: col.top_values.map((t) => String(t.value)), hovertemplate: "%{y}: %{x} rows<extra></extra>" }], layout: { yaxis: { autorange: "reversed" as const }, margin: { l: 120, r: 16, t: 8, b: 32 } } };
    }
    return null;
  }, [col]);
  const n = col.numeric;
  const facts: [string, string][] = [
    ["Type", col.type],
    ["Distinct", formatValue(col.distinct_count, "count")],
    ["Missing", `${formatValue(col.null_count, "count")} (${formatValue(col.missing_pct, "percent")})`],
    ...(n ? ([["Mean", formatCell(n.mean)], ["Std dev", formatCell(n.std)], ["Min / Max", `${formatCell(n.min)} / ${formatCell(n.max)}`], ["Quartiles", `${formatCell(n.p25)} · ${formatCell(n.median)} · ${formatCell(n.p75)}`], ["IQR outliers", formatValue(n.outliers.count, "count")]] as [string, string][]) : []),
    ...(col.temporal ? ([["Range", `${col.temporal.min} → ${col.temporal.max}`]] as [string, string][]) : []),
    ...(col.text ? ([["Length", `${col.text.min_length}–${col.text.max_length} chars`]] as [string, string][]) : []),
  ];
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-center gap-2">
        <TypeIcon type={col.type} className="size-4" />
        <h3 className="font-semibold">{col.name}</h3>
        {col.is_id_like && <Badge>identifier</Badge>}
        {col.is_date_candidate && <Badge tone="sky">date</Badge>}
        {col.is_dimension_candidate && <Badge tone="lime">dimension</Badge>}
        {col.kind === "numeric" && !col.is_id_like && <Badge tone="lime">measure</Badge>}
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
        {facts.map(([k, v]) => (
          <div key={k}>
            <dt className="text-xs text-muted">{k}</dt>
            <dd className="num">{v}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-4">{figure ? <Plot figure={figure} height={260} /> : <p className="text-sm text-muted">No distribution available for this column type.</p>}</div>
      <p className="mt-2 text-xs text-muted">Computed by DuckDB over all {rows.toLocaleString()} rows at ingest.</p>
    </Card>
  );
}
