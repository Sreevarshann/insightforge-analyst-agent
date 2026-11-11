"use client";

import * as Tabs from "@radix-ui/react-tabs";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Copy, Save, XCircle } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { formatValue } from "@/lib/format";
import type { Analysis, Chart, ChartConfig } from "@/lib/types";
import { Plot } from "../charts/Plot";
import { Badge, Button, EmptyState } from "../ui/primitives";

export function Inspector({ analysis }: { analysis: Analysis | null }) {
  if (!analysis) {
    return (
      <div className="p-4">
        <EmptyState icon={<CheckCircle2 className="size-5" />} title="Inspector">Select an analysis to see its plan, executed SQL, cited facts, verification checks and chart settings.</EmptyState>
      </div>
    );
  }
  return (
    <Tabs.Root defaultValue="verify" className="flex h-full flex-col">
      <Tabs.List aria-label="Inspector" className="flex shrink-0 gap-1 border-b border-line px-3 pt-3">
        {[["verify", "Facts"], ["sql", "SQL"], ["trace", "Trace"], ["chart", "Chart Studio"]].map(([v, l]) => (
          <Tabs.Trigger key={v} value={v} className="rounded-t-lg px-3 py-2 text-xs text-muted data-[state=active]:bg-panel-2 data-[state=active]:text-text">{l}</Tabs.Trigger>
        ))}
      </Tabs.List>
      <div className="min-h-0 flex-1 overflow-auto p-4 text-sm">
        <Tabs.Content value="verify"><FactsPanel a={analysis} /></Tabs.Content>
        <Tabs.Content value="sql"><SqlPanel a={analysis} /></Tabs.Content>
        <Tabs.Content value="trace"><TracePanel a={analysis} /></Tabs.Content>
        <Tabs.Content value="chart"><ChartStudio key={analysis.id} a={analysis} /></Tabs.Content>
      </div>
    </Tabs.Root>
  );
}

function FactsPanel({ a }: { a: Analysis }) {
  const v = a.verification;
  const cited = new Set(v?.cited_fact_ids ?? []);
  const facts = a.steps.flatMap((s) => s.facts);
  return (
    <div className="flex flex-col gap-5">
      {v?.checks && (
        <section>
          <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-muted">Verification checks</h3>
          <ul className="flex flex-col gap-1">
            {v.checks.map((c) => (
              <li key={c.name} className="flex items-center gap-2">
                {c.passed ? <CheckCircle2 className="size-3.5 text-lime" aria-label="passed" /> : <XCircle className="size-3.5 text-coral" aria-label="failed" />}
                <span>{c.name.replaceAll("_", " ")}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {!!v?.removed_sentences?.length && (
        <section>
          <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-muted">Removed from the model&apos;s draft</h3>
          <ul className="flex flex-col gap-2">
            {v.removed_sentences.map((r, i) => (
              <li key={i} className="rounded-lg border border-coral/30 bg-coral-soft p-2.5">
                <p className="line-through decoration-coral/60">{r.sentence}</p>
                <p className="mt-1 text-xs text-coral">{r.reason}</p>
              </li>
            ))}
          </ul>
        </section>
      )}
      {v?.draft && (
        <details className="rounded-lg bg-panel-2 p-2.5 text-xs">
          <summary className="cursor-pointer text-muted">Model draft (with placeholders)</summary>
          <p className="mt-2 font-mono leading-relaxed">{v.draft}</p>
        </details>
      )}
      <section>
        <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-muted">Computed facts ({facts.length})</h3>
        <ul className="flex flex-col divide-y divide-line rounded-lg border border-line">
          {facts.map((f) => (
            <li key={f.id} className="flex items-start gap-2 px-2.5 py-2">
              <code className={`num mt-0.5 rounded px-1 text-[10px] ${cited.has(f.id) ? "bg-lime-soft text-lime" : "bg-panel-2 text-muted"}`}>{f.id}</code>
              <span className="flex-1 text-xs">{f.label}</span>
              <span className="num text-xs font-medium">{formatValue(f.value, f.unit)}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function SqlPanel({ a }: { a: Analysis }) {
  const [copied, setCopied] = useState<string | null>(null);
  const stmts = a.steps.flatMap((s) => s.sql.map((sql, i) => ({ sql, id: s.query_ids[i], step: s.step })));
  if (!stmts.length) return <p className="text-muted">No SQL was executed.</p>;
  return (
    <ol className="flex flex-col gap-3">
      {stmts.map((s) => (
        <li key={s.id} className="rounded-lg border border-line">
          <div className="flex items-center justify-between border-b border-line px-2.5 py-1.5 text-[11px] text-muted">
            <span>step {s.step} · query <code className="num">{s.id.slice(0, 8)}</code> · sandboxed</span>
            <button onClick={() => (navigator.clipboard.writeText(s.sql), setCopied(s.id))} className="flex items-center gap-1 hover:text-text" aria-label="Copy SQL">
              <Copy className="size-3" /> {copied === s.id ? "copied" : "copy"}
            </button>
          </div>
          <pre className="overflow-auto whitespace-pre-wrap p-2.5 font-mono text-[11px] leading-relaxed">{s.sql}</pre>
        </li>
      ))}
    </ol>
  );
}

function TracePanel({ a }: { a: Analysis }) {
  const trace = a.plan?.trace ?? [];
  const total = trace.reduce((t, e) => t + e.ms, 0) || 1;
  return (
    <div className="flex flex-col gap-4">
      <ol className="flex flex-col gap-2">
        {trace.map((t, i) => (
          <li key={i}>
            <div className="flex justify-between text-xs"><span className="font-medium">{t.node}</span><span className="num text-muted">{t.ms < 1000 ? `${t.ms.toFixed(0)} ms` : `${(t.ms / 1000).toFixed(2)} s`}</span></div>
            <div className="mt-1 h-1.5 overflow-hidden rounded bg-panel-2"><div className="h-full bg-lime/70" style={{ width: `${Math.max(2, (100 * t.ms) / total)}%` }} /></div>
            {Array.isArray(t.errors) && t.errors.length > 0 && <ul className="mt-1 text-[11px] text-coral">{(t.errors as string[]).map((e) => <li key={e}>{e}</li>)}</ul>}
          </li>
        ))}
      </ol>
      {a.plan?.raw && (
        <details open className="rounded-lg bg-panel-2 p-2.5 text-xs">
          <summary className="cursor-pointer text-muted">Plan proposed by the model (validated before execution)</summary>
          <pre className="mt-2 overflow-auto font-mono text-[11px]">{JSON.stringify(a.plan.raw, null, 2)}</pre>
        </details>
      )}
      {a.plan?.llm_usage && (
        <p className="num text-[11px] text-muted">LLM calls {a.plan.llm_usage.calls} · prompt tokens {a.plan.llm_usage.prompt_tokens} · completion tokens {a.plan.llm_usage.completion_tokens}</p>
      )}
    </div>
  );
}

function Select({ label, value, options, onChange, allowEmpty }: { label: string; value?: string | null; options: string[]; onChange: (v: string | null) => void; allowEmpty?: boolean }) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="text-muted">{label}</span>
      <select value={value ?? ""} onChange={(e) => onChange(e.target.value || null)} className="rounded-lg border border-line bg-panel-2 px-2 py-1.5">
        {allowEmpty && <option value="">—</option>}
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
}

const TYPES = ["bar", "line", "area", "stacked_bar", "grouped_bar", "scatter", "box", "histogram", "heatmap", "treemap", "funnel", "forecast"];

function ChartStudio({ a }: { a: Analysis }) {
  const qc = useQueryClient();
  const first = a.charts[0];
  const [step, setStep] = useState(first?.step ?? a.steps[0]?.step ?? 1);
  const stepData = a.steps.find((s) => s.step === step);
  const [cfg, setCfg] = useState<ChartConfig>(first?.config ?? { type: "bar", table: stepData?.tables[0]?.name ?? "result" });
  const [preview, setPreview] = useState<Chart | null>(first ?? null);
  const table = stepData?.tables.find((t) => t.name === cfg.table) ?? stepData?.tables[0];
  const columns = table?.columns ?? [];
  const render = useMutation({ mutationFn: (c: ChartConfig) => api.previewChart(a.id, step, c), onSuccess: setPreview });
  const save = useMutation({ mutationFn: () => api.saveCharts(a.id, [{ step, config: cfg }]), onSuccess: () => qc.invalidateQueries({ queryKey: ["analyses"] }) });
  const update = (patch: Partial<ChartConfig>) => {
    const next = { ...cfg, ...patch };
    setCfg(next);
    render.mutate(next);
  };
  if (!stepData) return <p className="text-muted">This analysis has no result tables.</p>;
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-2">
        <Select label="Step" value={String(step)} options={a.steps.map((s) => String(s.step))} onChange={(v) => setStep(Number(v))} />
        <Select label="Table" value={cfg.table} options={stepData.tables.map((t) => t.name)} onChange={(v) => update({ table: v ?? "result" })} />
        <Select label="Chart type" value={cfg.type} options={TYPES} onChange={(v) => update({ type: v ?? "bar" })} />
        <Select label="Orientation" value={cfg.orientation ?? "v"} options={["v", "h"]} onChange={(v) => update({ orientation: (v as "v" | "h") ?? "v" })} />
        <Select label="X axis" value={cfg.x} options={columns} allowEmpty onChange={(v) => update({ x: v })} />
        <Select label="Y axis" value={cfg.y} options={columns} allowEmpty onChange={(v) => update({ y: v })} />
        <Select label="Group / colour" value={cfg.color} options={columns} allowEmpty onChange={(v) => update({ color: v })} />
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-muted">Top N</span>
          <input type="number" min={1} max={200} value={cfg.top_n ?? 30} onChange={(e) => update({ top_n: Number(e.target.value) })} className="rounded-lg border border-line bg-panel-2 px-2 py-1.5" />
        </label>
      </div>
      <label className="flex flex-col gap-1 text-xs">
        <span className="text-muted">Title</span>
        <input value={cfg.title ?? ""} onChange={(e) => setCfg({ ...cfg, title: e.target.value })} onBlur={() => render.mutate(cfg)} className="rounded-lg border border-line bg-panel-2 px-2 py-1.5" />
      </label>
      <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={!!cfg.log_y} onChange={(e) => update({ log_y: e.target.checked })} /> Log scale (y)</label>
      {render.isError && <p role="alert" className="text-xs text-coral">{(render.error as Error).message}</p>}
      {preview && <div className="rounded-lg border border-line p-1"><Plot figure={preview.figure} height={260} /></div>}
      <div className="flex items-center gap-2">
        <Button size="sm" variant="primary" onClick={() => save.mutate()} disabled={save.isPending}><Save className="size-3.5" /> Save view</Button>
        {save.isSuccess && <Badge tone="lime">saved</Badge>}
      </div>
      <p className="text-[11px] text-muted">Figures are rebuilt server-side from stored results and validated against Plotly&apos;s schema.</p>
    </div>
  );
}
