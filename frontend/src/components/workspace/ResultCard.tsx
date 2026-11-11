"use client";

import * as Collapsible from "@radix-ui/react-collapsible";
import { AlertCircle, Bookmark, BookmarkCheck, ChevronDown, Download, HelpCircle, Table2 } from "lucide-react";
import { motion } from "motion/react";
import { formatCell } from "@/lib/format";
import type { Analysis, Chart, StepResult, Verification } from "@/lib/types";
import { cn } from "@/lib/cn";
import { Plot } from "../charts/Plot";
import { Badge, Button, Card, Skeleton } from "../ui/primitives";
import { StageProgress } from "./StageProgress";
import type { LiveRun } from "./useAnalysisRun";
import { VerificationBadge } from "./VerificationBadge";

interface CardData {
  question: string;
  status: Analysis["status"] | "running";
  headline?: string | null;
  text?: string | null;
  verification?: Verification | null;
  results: StepResult[];
  charts: Chart[];
  stages?: LiveRun["stages"];
  analysis?: Analysis;
  error?: string;
}

export function fromAnalysis(a: Analysis): CardData {
  return { question: a.question, status: a.status, headline: a.title, text: a.explanation, verification: a.verification, results: a.steps, charts: a.charts, analysis: a };
}

export function fromRun(r: LiveRun): CardData {
  if (r.analysis) return { ...fromAnalysis(r.analysis), stages: r.stages };
  return { question: r.question, status: "running", headline: r.explanation?.headline, text: r.explanation?.text, verification: r.explanation?.verification, results: r.results, charts: r.charts, stages: r.stages, error: r.error };
}

export function ResultCard({ data, selected, onSelect, onToggleSave, onAskClarified }: { data: CardData; selected: boolean; onSelect?: () => void; onToggleSave?: () => void; onAskClarified?: (q: string) => void }) {
  const a = data.analysis;
  return (
    <motion.article initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }} aria-label={`Analysis: ${data.question}`}>
      <Card className={cn("overflow-hidden transition-shadow", selected && "ring-1 ring-lime/50")} onClick={onSelect}>
        <header className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div className="min-w-0">
            <p className="text-sm text-muted">You asked</p>
            <h2 className="font-medium">{data.question}</h2>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <VerificationBadge v={data.verification} />
            {a && (
              <>
                <a href={`/api/analyses/${a.id}/report?format=html`} target="_blank" rel="noopener" onClick={(e) => e.stopPropagation()} className="rounded-lg p-1.5 text-muted hover:bg-panel-2 hover:text-text" aria-label="Open report">
                  <Download className="size-4" />
                </a>
                <button onClick={(e) => (e.stopPropagation(), onToggleSave?.())} className="rounded-lg p-1.5 text-muted hover:bg-panel-2 hover:text-text" aria-label={a.saved ? "Remove from saved" : "Save analysis"} aria-pressed={a.saved}>
                  {a.saved ? <BookmarkCheck className="size-4 text-lime" /> : <Bookmark className="size-4" />}
                </button>
              </>
            )}
          </div>
        </header>
        <div className="flex flex-col gap-4 px-5 py-4">
          {data.stages && data.status === "running" && <StageProgress stages={data.stages} />}
          {data.error && <p role="alert" className="flex items-center gap-2 text-sm text-coral"><AlertCircle className="size-4" /> {data.error}</p>}
          {data.status === "needs_clarification" ? (
            <Clarification text={data.text ?? ""} question={data.question} onAsk={onAskClarified} />
          ) : data.status === "failed" ? (
            <p className="flex items-start gap-2 rounded-lg bg-coral-soft p-3 text-sm text-coral"><AlertCircle className="mt-0.5 size-4 shrink-0" /> {data.text}</p>
          ) : (
            <>
              {data.headline && <h3 className="text-lg font-semibold tracking-tight">{data.headline}</h3>}
              {data.text ? <p className="leading-relaxed">{data.text}</p> : data.status === "running" && <div className="flex flex-col gap-2"><Skeleton className="w-11/12" /><Skeleton className="w-2/3" /></div>}
            </>
          )}
          {data.charts.map((c, i) => (
            <div key={`${c.step}-${i}`} className="rounded-xl border border-line p-2" onClick={(e) => e.stopPropagation()}>
              <Plot figure={c.figure} height={320} title={c.config.title ?? undefined} />
            </div>
          ))}
          {data.results.map((r) => <StepTables key={r.step} step={r} />)}
          {data.results.some((r) => r.notes.length) && (
            <ul className="flex flex-col gap-1 text-xs text-muted">
              {[...new Set(data.results.flatMap((r) => r.notes))].map((n) => <li key={n}>• {n}</li>)}
            </ul>
          )}
          {a && (
            <footer className="num flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted">
              <span>{a.model_name}</span>
              {a.duration_ms !== null && <span>{(a.duration_ms / 1000).toFixed(1)}s</span>}
              {a.plan && <span>{a.plan.attempts} plan attempt{a.plan.attempts === 1 ? "" : "s"}</span>}
              <span>{a.dataset_versions.length} dataset version{a.dataset_versions.length === 1 ? "" : "s"} pinned</span>
            </footer>
          )}
        </div>
      </Card>
    </motion.article>
  );
}

function Clarification({ text, question, onAsk }: { text: string; question: string; onAsk?: (q: string) => void }) {
  return (
    <div className="rounded-xl border border-sky/40 bg-panel-2 p-4 text-sm">
      <p className="flex items-center gap-2 font-medium text-sky"><HelpCircle className="size-4" /> The analyst needs a clarification</p>
      <p className="mt-2">{text}</p>
      <form
        className="mt-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          const v = new FormData(e.currentTarget).get("c");
          if (v) onAsk?.(`${question} (${String(v)})`);
        }}
      >
        <input name="c" placeholder="Add the missing detail…" className="flex-1 rounded-lg border border-line bg-panel px-3 py-2 outline-none focus:border-lime" aria-label="Clarification" />
        <Button size="sm" variant="primary" type="submit">Re-run</Button>
      </form>
    </div>
  );
}

function StepTables({ step }: { step: StepResult }) {
  const tables = step.tables.filter((t) => t.name !== "raw");
  return (
    <Collapsible.Root>
      <Collapsible.Trigger className="group flex w-full items-center gap-2 text-left text-xs text-muted hover:text-text" onClick={(e) => e.stopPropagation()}>
        <Table2 className="size-3.5" />
        <span>Step {step.step}: <Badge>{step.op}</Badge> {step.purpose} · {tables.map((t) => `${t.rows.length} rows`).join(", ")}</span>
        <ChevronDown className="ml-auto size-3.5 transition-transform group-data-[state=open]:rotate-180" />
      </Collapsible.Trigger>
      <Collapsible.Content onClick={(e) => e.stopPropagation()}>
        {tables.map((t) => (
          <div key={t.name} className="mt-2 max-h-72 overflow-auto rounded-lg border border-line">
            <table className="w-full text-xs">
              <caption className="sr-only">{t.name}</caption>
              <thead className="sticky top-0 bg-panel-2">
                <tr>{t.columns.map((c) => <th key={c} scope="col" className="whitespace-nowrap px-2.5 py-1.5 text-left font-medium">{c}</th>)}</tr>
              </thead>
              <tbody>
                {t.rows.slice(0, 200).map((r, i) => (
                  <tr key={i} className="border-t border-line/60">
                    {r.map((v, j) => <td key={j} className={cn("whitespace-nowrap px-2.5 py-1", typeof v === "number" && "num text-right")}>{formatCell(v)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
            {t.truncated && <p className="px-2.5 py-1 text-[11px] text-warn">Truncated at the row limit.</p>}
          </div>
        ))}
      </Collapsible.Content>
    </Collapsible.Root>
  );
}
