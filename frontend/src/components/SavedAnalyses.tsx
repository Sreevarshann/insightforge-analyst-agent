"use client";

import { useQuery } from "@tanstack/react-query";
import { BookMarked, Search } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import type { Analysis } from "@/lib/types";
import { Badge, Card, EmptyState, ErrorBox, Skeleton } from "./ui/primitives";
import { ExportMenu } from "./workspace/ExportMenu";
import { VerificationBadge } from "./workspace/VerificationBadge";

const STATUS = ["all", "completed", "needs_clarification", "failed"] as const;

export function SavedAnalyses() {
  const [savedOnly, setSavedOnly] = useState(true);
  const [status, setStatus] = useState<(typeof STATUS)[number]>("all");
  const [q, setQ] = useState("");
  const list = useQuery({ queryKey: ["analyses", savedOnly], queryFn: () => api.analyses(savedOnly ? true : undefined) });
  const items = (list.data ?? []).filter((a) => (status === "all" || a.status === status) && `${a.question} ${a.title ?? ""}`.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="mx-auto max-w-5xl p-4 sm:p-8">
      <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight"><BookMarked className="size-5 text-lime" /> Analyses</h1>
      <p className="mt-1 text-sm text-muted">Every analysis stores its question, plan, executed SQL, pinned dataset versions, results, charts and verification record.</p>
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <label className="relative min-w-56 flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search questions" aria-label="Search analyses" className="w-full rounded-lg border border-line bg-panel-2 py-2 pl-9 pr-3 text-sm outline-none focus:border-lime" />
        </label>
        <div role="group" aria-label="Scope" className="flex rounded-lg border border-line p-0.5 text-xs">
          {[true, false].map((v) => (
            <button key={String(v)} onClick={() => setSavedOnly(v)} aria-pressed={savedOnly === v} className={`rounded-md px-3 py-1.5 ${savedOnly === v ? "bg-panel-2 text-text" : "text-muted"}`}>{v ? "Saved" : "All"}</button>
          ))}
        </div>
        <select value={status} onChange={(e) => setStatus(e.target.value as (typeof STATUS)[number])} aria-label="Status filter" className="rounded-lg border border-line bg-panel-2 px-3 py-2 text-xs">
          {STATUS.map((s) => <option key={s} value={s}>{s.replaceAll("_", " ")}</option>)}
        </select>
      </div>
      <div className="mt-5 flex flex-col gap-3">
        {list.isLoading && Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-24" />)}
        {list.isError && <ErrorBox error={list.error} onRetry={() => list.refetch()} />}
        {list.data && items.length === 0 && (
          <EmptyState icon={<BookMarked className="size-5" />} title={savedOnly ? "No saved analyses" : "No analyses match"}>Bookmark an analysis in the Copilot to keep it here.</EmptyState>
        )}
        {items.map((a) => <Row key={a.id} a={a} />)}
      </div>
    </div>
  );
}

function Row({ a }: { a: Analysis }) {
  return (
    <Card className="flex flex-wrap items-start gap-4 p-4">
      <div className="min-w-0 flex-1">
        <p className="font-medium">{a.title ?? a.question}</p>
        {a.title && <p className="text-sm text-muted">{a.question}</p>}
        {a.explanation && <p className="mt-2 line-clamp-2 text-sm">{a.explanation}</p>}
        <p className="num mt-2 flex flex-wrap gap-2 text-[11px] text-muted">
          <span>{relativeTime(a.created_at)}</span>
          <span>{a.model_name}</span>
          {a.steps.map((s) => <Badge key={s.step}>{s.op}</Badge>)}
        </p>
      </div>
      <div className="flex items-center gap-2">
        <VerificationBadge v={a.verification} />
        <ExportMenu a={a} />
      </div>
    </Card>
  );
}
