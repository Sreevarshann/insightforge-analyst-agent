"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, FlaskConical, MinusCircle, XCircle } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/cn";
import { Plot } from "./charts/Plot";
import { Badge, Card, EmptyState, ErrorBox, Skeleton } from "./ui/primitives";

interface Summary { label: string; run_at: string; cases: number; execution_success: number | null; numerical_correct: number | null; op_appropriate: number | null; chart_appropriate: number | null; clarification: number | null; injection_safe: number | null; policy_rejection: number; latency_ms_median: number; latency_ms_p90: number }
interface CaseRow { id: string; kind: string; question: string; status: string; ops: string[]; charts: string[]; attempts: number | null; verification: string | null; latency_ms: number; numerical_correct?: boolean; numerical_partial?: number; op_appropriate?: boolean; chart_appropriate?: boolean; clarification?: boolean; injection_safe?: boolean; note?: string }
interface Report { summary: Summary; cases: CaseRow[]; policy: { sql: string; rejected: boolean; reason?: string }[] }

const METRICS: [keyof Summary, string][] = [
  ["execution_success", "Execution success"],
  ["numerical_correct", "Numerical correctness"],
  ["op_appropriate", "Appropriate operation"],
  ["chart_appropriate", "Appropriate chart"],
  ["clarification", "Clarification behaviour"],
  ["injection_safe", "Prompt-injection safe"],
  ["policy_rejection", "Unsafe SQL rejected"],
];

export function Evaluation() {
  const q = useQuery({ queryKey: ["evaluation"], queryFn: () => fetch("/api/evaluation").then((r) => r.json() as Promise<Report[]>) });
  const [active, setActive] = useState(0);
  if (q.isLoading) return <div className="p-8"><Skeleton className="h-64" /></div>;
  if (q.isError) return <div className="p-8"><ErrorBox error={q.error} onRetry={() => q.refetch()} /></div>;
  const reports = q.data ?? [];
  if (!reports.length) return <div className="p-8"><EmptyState icon={<FlaskConical className="size-5" />} title="No benchmark results yet" action={<code className="rounded bg-panel-2 px-2 py-1 text-xs">make evaluate</code>}>Run the benchmark to measure the analyst against answers recomputed independently with pandas.</EmptyState></div>;
  const r = reports[Math.min(active, reports.length - 1)];
  return (
    <div className="mx-auto max-w-6xl p-4 sm:p-8">
      <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight"><FlaskConical className="size-5 text-lime" /> Evaluation</h1>
      <p className="mt-1 max-w-3xl text-sm text-muted">Stored results of <code>make evaluate</code>. Expected answers are recomputed with pandas from the synthetic data at run time. The <b>fixture</b> run uses a deterministic keyword heuristic (not an LLM) and exists to test the pipeline; model runs use a real local LLM.</p>

      <Card className="mt-6 p-5">
        <h2 className="mb-1 font-semibold">Metric comparison by run</h2>
        <Plot
          height={340}
          figure={{
            data: reports.map((rep) => ({ type: "bar", name: rep.summary.label, x: METRICS.map(([, l]) => l), y: METRICS.map(([k]) => ((rep.summary[k] as number | null) ?? 0) * 100), hovertemplate: "%{x}: %{y:.1f}%<extra>" + rep.summary.label + "</extra>" })),
            layout: { barmode: "group", yaxis: { range: [0, 105], ticksuffix: "%" }, margin: { l: 48, r: 16, t: 16, b: 90 } },
          }}
        />
      </Card>

      <div role="tablist" aria-label="Benchmark runs" className="mt-6 flex flex-wrap gap-2">
        {reports.map((rep, i) => (
          <button key={rep.summary.label} role="tab" aria-selected={i === active} onClick={() => setActive(i)} className={cn("rounded-lg border px-3 py-1.5 text-sm", i === active ? "border-lime bg-lime-soft text-lime" : "border-line text-muted hover:text-text")}>
            {rep.summary.label}
          </button>
        ))}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        {METRICS.map(([k, l]) => (
          <Card key={k} className="p-4">
            <p className="text-xs text-muted">{l}</p>
            <p className="num mt-1 text-2xl font-semibold">{r.summary[k] === null ? "—" : `${(((r.summary[k] as number) ?? 0) * 100).toFixed(1)}%`}</p>
          </Card>
        ))}
        <Card className="p-4">
          <p className="text-xs text-muted">Latency (median / p90)</p>
          <p className="num mt-1 text-2xl font-semibold">{(r.summary.latency_ms_median / 1000).toFixed(1)}s <span className="text-sm text-muted">/ {(r.summary.latency_ms_p90 / 1000).toFixed(1)}s</span></p>
        </Card>
      </div>
      <p className="num mt-2 text-xs text-muted">Run at {new Date(r.summary.run_at).toLocaleString()} · {r.summary.cases} questions · {r.policy.length} policy probes</p>

      <Card className="mt-6 overflow-hidden">
        <h2 className="border-b border-line px-5 py-3 font-semibold">Per-question results</h2>
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead className="bg-panel-2 text-left text-xs text-muted">
              <tr>{["Case", "Kind", "Status", "Operation", "Chart", "Result", "Attempts", "Latency"].map((h) => <th key={h} scope="col" className="px-4 py-2 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody>
              {r.cases.map((c) => (
                <tr key={c.id} className="border-t border-line/60 align-top">
                  <td className="px-4 py-2"><p className="font-medium">{c.id}</p><p className="max-w-xs text-xs text-muted">{c.question}</p></td>
                  <td className="px-4 py-2"><Badge>{c.kind}</Badge></td>
                  <td className="px-4 py-2 text-xs">{c.status.replaceAll("_", " ")}</td>
                  <td className="px-4 py-2 text-xs">{c.ops.join(", ") || "—"} {c.op_appropriate !== undefined && <Mark ok={c.op_appropriate} />}</td>
                  <td className="px-4 py-2 text-xs">{c.charts.join(", ") || "—"} {c.chart_appropriate !== undefined && <Mark ok={c.chart_appropriate} />}</td>
                  <td className="px-4 py-2 text-xs">
                    {c.numerical_correct !== undefined && <span className="flex items-center gap-1"><Mark ok={c.numerical_correct} /> numbers {c.numerical_partial !== undefined && `(${Math.round(c.numerical_partial * 100)}% of expected)`}</span>}
                    {c.clarification !== undefined && <span className="flex items-center gap-1"><Mark ok={c.clarification} /> no fabricated answer</span>}
                    {c.injection_safe !== undefined && <span className="flex items-center gap-1"><Mark ok={c.injection_safe} /> no unsafe statement executed</span>}
                  </td>
                  <td className="num px-4 py-2 text-xs">{c.attempts ?? "—"}</td>
                  <td className="num px-4 py-2 text-xs">{(c.latency_ms / 1000).toFixed(1)}s</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card className="mt-6 p-5">
        <h2 className="mb-3 font-semibold">SQL policy probes (deterministic)</h2>
        <ul className="grid gap-1.5 md:grid-cols-2">
          {r.policy.map((p) => (
            <li key={p.sql} className="flex items-start gap-2 text-xs">
              <Mark ok={p.rejected} />
              <span><code className="break-all">{p.sql}</code>{p.reason && <span className="block text-muted">{p.reason}</span>}</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

function Mark({ ok }: { ok: boolean | undefined }) {
  if (ok === undefined) return <MinusCircle className="inline size-3.5 text-muted" />;
  return ok ? <CheckCircle2 className="inline size-3.5 text-lime" aria-label="pass" /> : <XCircle className="inline size-3.5 text-coral" aria-label="fail" />;
}
