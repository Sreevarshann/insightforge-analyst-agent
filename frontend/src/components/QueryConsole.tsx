"use client";

import Editor from "@monaco-editor/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, Play, ShieldCheck, Terminal, XCircle } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { formatCell, relativeTime } from "@/lib/format";
import { useDatasets } from "@/lib/useDatasets";
import { useTheme } from "./theme";
import { Badge, Button, Card, EmptyState } from "./ui/primitives";

const START = "SELECT region, count(*) AS orders, round(sum(revenue), 2) AS revenue\nFROM orders\nGROUP BY region\nORDER BY revenue DESC";

export function QueryConsole() {
  const { theme } = useTheme();
  const qc = useQueryClient();
  const datasets = useDatasets();
  const [sql, setSql] = useState(START);
  const history = useQuery({ queryKey: ["query-history"], queryFn: api.queryHistory });
  const run = useMutation({ mutationFn: () => api.query(sql), onSettled: () => qc.invalidateQueries({ queryKey: ["query-history"] }) });
  return (
    <div className="grid min-h-dvh lg:grid-cols-[1fr_340px]">
      <section className="flex min-w-0 flex-col gap-4 p-4 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight"><Terminal className="size-5 text-lime" /> Query Console</h1>
            <p className="mt-1 text-sm text-muted">Read-only DuckDB SQL. Every statement passes the AST policy, then runs in the OS sandbox with time, memory and row limits.</p>
          </div>
          <Button variant="primary" onClick={() => run.mutate()} disabled={run.isPending}>
            {run.isPending ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />} Run <span className="text-[10px] opacity-70">⌘↵</span>
          </Button>
        </div>
        <Card className="overflow-hidden">
          <Editor
            height="220px"
            language="sql"
            theme={theme === "dark" ? "vs-dark" : "light"}
            value={sql}
            onChange={(v) => setSql(v ?? "")}
            onMount={(editor, monaco) => editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => run.mutate())}
            options={{ minimap: { enabled: false }, fontSize: 13, scrollBeyondLastLine: false, padding: { top: 12 }, ariaLabel: "SQL editor" }}
          />
        </Card>
        <div className="flex flex-wrap gap-1.5 text-xs">
          <span className="text-muted">Tables:</span>
          {(datasets.data ?? []).map((d) => <code key={d.id} className="rounded bg-panel-2 px-1.5 py-0.5">{d.table_name}</code>)}
        </div>
        {run.isError && (
          <div role="alert" className="flex items-start gap-2 rounded-xl border border-coral/40 bg-coral-soft p-4 text-sm">
            <XCircle className="mt-0.5 size-4 shrink-0 text-coral" />
            <div><p className="font-medium text-coral">Query not executed</p><p className="mt-1">{(run.error as Error).message}</p></div>
          </div>
        )}
        {run.data && (
          <Card className="overflow-hidden">
            <div className="num flex flex-wrap items-center gap-3 border-b border-line px-4 py-2 text-xs text-muted">
              <span className="flex items-center gap-1 text-lime"><ShieldCheck className="size-3.5" /> {run.data.isolation}</span>
              <span>{run.data.rows.length} rows{run.data.truncated && " (truncated)"}</span>
              <span>{run.data.elapsed_ms.toFixed(1)} ms</span>
              <span>tables: {run.data.tables.join(", ")}</span>
            </div>
            <div className="max-h-[420px] overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-panel-2"><tr>{run.data.columns.map((c, i) => <th key={c} scope="col" className="whitespace-nowrap px-3 py-2 text-left font-medium">{c} <span className="text-[10px] font-normal text-muted">{run.data.types[i]}</span></th>)}</tr></thead>
                <tbody>{run.data.rows.map((r, i) => <tr key={i} className="border-t border-line/60">{r.map((v, j) => <td key={j} className={`whitespace-nowrap px-3 py-1.5 ${typeof v === "number" ? "num text-right" : ""}`}>{formatCell(v)}</td>)}</tr>)}</tbody>
              </table>
            </div>
          </Card>
        )}
        {!run.data && !run.isError && <EmptyState icon={<Play className="size-5" />} title="Run a query">Try a forbidden statement such as <code>DROP TABLE orders</code> or <code>SELECT * FROM read_csv(&apos;/etc/passwd&apos;)</code> to see the policy reject it.</EmptyState>}
      </section>
      <aside className="border-t border-line p-4 lg:border-l lg:border-t-0" aria-label="Query history">
        <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-muted">Audit log</h2>
        <ul className="flex flex-col gap-2">
          {(history.data ?? []).slice(0, 40).map((h) => (
            <li key={h.id}>
              <button onClick={() => setSql(h.sql)} className="w-full rounded-lg border border-line p-2.5 text-left hover:bg-panel-2">
                <span className="flex items-center gap-1.5 text-[11px] text-muted">
                  {h.accepted && !h.rejection_reason ? <CheckCircle2 className="size-3 text-lime" /> : <XCircle className="size-3 text-coral" />}
                  <Badge>{h.origin}</Badge> {relativeTime(h.created_at)} {h.row_count !== null && `· ${h.row_count} rows`}
                </span>
                <code className="mt-1 line-clamp-2 block text-[11px]">{h.sql}</code>
                {h.rejection_reason && <span className="mt-1 block text-[11px] text-coral">{h.rejection_reason}</span>}
              </button>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}
