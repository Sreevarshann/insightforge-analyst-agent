"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUp, BookMarked, Clock, Database, Loader2, PanelRightClose, PanelRightOpen, Sparkles, Square } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatValue, relativeTime } from "@/lib/format";
import type { Analysis } from "@/lib/types";
import { useDatasets } from "@/lib/useDatasets";
import { Badge, EmptyState, Kbd } from "../ui/primitives";
import { Inspector } from "./Inspector";
import { fromAnalysis, fromRun, ResultCard } from "./ResultCard";
import { useAnalysisRun } from "./useAnalysisRun";

const EXAMPLES = [
  "What is the total revenue by region?",
  "Show the monthly revenue trend by region",
  "Which plan has the highest churned rate?",
  "Which products have abnormal refunded rates?",
  "Is there a relationship between discount_pct and revenue?",
  "Compare monthly retention for customer cohorts",
];

export function Workspace() {
  const qc = useQueryClient();
  const datasets = useDatasets();
  const history = useQuery({ queryKey: ["analyses"], queryFn: () => api.analyses() });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const input = useRef<HTMLTextAreaElement>(null);
  const onDone = useCallback((a: Analysis) => setSelectedId(a.id), []);
  const { run, start, cancel } = useAnalysisRun(onDone);
  const running = !!run && !run.analysis && !run.error;

  const toggleSave = useMutation({
    mutationFn: (a: Analysis) => api.setSaved(a.id, !a.saved),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["analyses"] }),
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const ask = (q: string) => {
    const text = q.trim();
    if (!text || running) return;
    setQuestion("");
    setSelectedId(null);
    start(text);
  };

  const past = (history.data ?? []).filter((a) => a.id !== run?.analysis?.id);
  const selected = run?.analysis?.id === selectedId ? run?.analysis : (history.data ?? []).find((a) => a.id === selectedId) ?? null;

  return (
    <div className="flex h-dvh min-h-0">
      {/* Left: datasets & history */}
      <aside className="hidden w-64 shrink-0 flex-col gap-5 overflow-auto border-r border-line p-4 md:flex">
        <section>
          <h2 className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-muted"><Database className="size-3.5" /> Datasets</h2>
          <ul className="flex flex-col gap-1">
            {(datasets.data ?? []).map((d) => (
              <li key={d.id} className="rounded-lg px-2 py-1.5 text-sm hover:bg-panel-2">
                <span className="flex items-center gap-1.5"><code className="text-xs">{d.table_name}</code>{d.is_demo && <Badge tone="sky">synthetic</Badge>}</span>
                <span className="num block text-[11px] text-muted">{formatValue(d.current.row_count, "count")} rows · {d.columns.length} cols</span>
              </li>
            ))}
          </ul>
        </section>
        <HistoryList title="Saved" icon={<BookMarked className="size-3.5" />} items={past.filter((a) => a.saved)} selectedId={selectedId} onSelect={setSelectedId} />
        <HistoryList title="Recent" icon={<Clock className="size-3.5" />} items={past.filter((a) => !a.saved).slice(0, 15)} selectedId={selectedId} onSelect={setSelectedId} />
      </aside>

      {/* Center: conversation */}
      <section className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-between border-b border-line px-5 py-3">
          <h1 className="flex items-center gap-2 font-semibold"><Sparkles className="size-4 text-lime" /> Analysis Copilot</h1>
          <button onClick={() => setInspectorOpen((o) => !o)} className="hidden rounded-lg p-1.5 text-muted hover:bg-panel-2 xl:block" aria-label={inspectorOpen ? "Hide inspector" : "Show inspector"}>
            {inspectorOpen ? <PanelRightClose className="size-4" /> : <PanelRightOpen className="size-4" />}
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-auto px-4 py-5 sm:px-6">
          <div className="mx-auto flex max-w-3xl flex-col gap-5">
            {!run && !selected && (
              <EmptyState icon={<Sparkles className="size-5" />} title="Ask a question about your data">
                Answers are computed by typed operations or sandboxed SQL, charted with Plotly, and explained with verified numbers only.
              </EmptyState>
            )}
            {!run && !selected && (
              <div className="flex flex-wrap justify-center gap-2">
                {EXAMPLES.map((e) => <button key={e} onClick={() => ask(e)} className="rounded-full border border-line bg-panel px-3 py-1.5 text-xs text-muted hover:border-lime hover:text-text">{e}</button>)}
              </div>
            )}
            {run && <ResultCard data={fromRun(run)} selected={selectedId === run.analysis?.id} onSelect={() => run.analysis && setSelectedId(run.analysis.id)} onToggleSave={() => run.analysis && toggleSave.mutate(run.analysis)} onAskClarified={ask} />}
            {selected && selected.id !== run?.analysis?.id && <ResultCard data={fromAnalysis(selected)} selected onToggleSave={() => toggleSave.mutate(selected)} onAskClarified={ask} />}
          </div>
        </div>
        <form onSubmit={(e) => (e.preventDefault(), ask(question))} className="border-t border-line bg-panel/60 px-4 py-3 sm:px-6">
          <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-line bg-panel p-2 focus-within:border-lime">
            <textarea
              ref={input}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  ask(question);
                }
              }}
              rows={1}
              maxLength={2000}
              placeholder="Ask about revenue, churn, cohorts, refunds…"
              aria-label="Analytical question"
              className="max-h-40 min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none"
            />
            {running ? (
              <button type="button" onClick={cancel} className="grid size-9 place-items-center rounded-xl bg-panel-2" aria-label="Stop"><Square className="size-3.5" /></button>
            ) : (
              <button type="submit" disabled={!question.trim()} className="grid size-9 place-items-center rounded-xl bg-lime text-[#0f1012] disabled:opacity-40" aria-label="Ask">
                {running ? <Loader2 className="size-4 animate-spin" /> : <ArrowUp className="size-4" />}
              </button>
            )}
          </div>
          <p className="mx-auto mt-1.5 max-w-3xl text-[11px] text-muted"><Kbd>⌘K</Kbd> focus · <Kbd>Enter</Kbd> ask · <Kbd>Shift</Kbd>+<Kbd>Enter</Kbd> new line</p>
        </form>
      </section>

      {/* Right: inspector */}
      {inspectorOpen && (
        <aside className="hidden w-[380px] shrink-0 border-l border-line bg-panel xl:block" aria-label="Inspector">
          <Inspector analysis={selected ?? null} />
        </aside>
      )}
    </div>
  );
}

function HistoryList({ title, icon, items, selectedId, onSelect }: { title: string; icon: React.ReactNode; items: Analysis[]; selectedId: string | null; onSelect: (id: string) => void }) {
  return (
    <section>
      <h2 className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-muted">{icon} {title}</h2>
      {items.length === 0 ? (
        <p className="px-2 text-xs text-muted">Nothing yet.</p>
      ) : (
        <ul className="flex flex-col gap-0.5">
          {items.map((a) => (
            <li key={a.id}>
              <button onClick={() => onSelect(a.id)} className={cn("w-full rounded-lg px-2 py-1.5 text-left text-sm", a.id === selectedId ? "bg-panel-2" : "hover:bg-panel-2/60")}>
                <span className="line-clamp-2">{a.question}</span>
                <span className="text-[11px] text-muted">{relativeTime(a.created_at)} · {a.status.replaceAll("_", " ")}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
