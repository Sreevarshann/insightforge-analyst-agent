"use client";

import { Check, Loader2 } from "lucide-react";
import { motion } from "motion/react";
import { cn } from "@/lib/cn";
import { STAGES, type LiveRun } from "./useAnalysisRun";

const LABEL: Record<string, string> = { catalog: "Read catalog", plan: "Plan", validate: "Validate", execute: "Execute", inspect: "Inspect", charts: "Charts", explain: "Explain & verify" };

/** Shows only stages the server has actually reported; no simulated progress. */
export function StageProgress({ stages }: { stages: LiveRun["stages"] }) {
  return (
    <ol className="flex flex-wrap gap-1.5" aria-label="Analysis progress">
      {STAGES.map((s) => {
        const st = stages[s];
        return (
          <motion.li key={s} layout className={cn("flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs", st?.status === "done" ? "border-lime/40 bg-lime-soft text-lime" : st ? "border-line bg-panel-2 text-text" : "border-line text-muted/60")}>
            {st?.status === "done" ? <Check className="size-3" aria-hidden /> : st ? <Loader2 className="size-3 animate-spin" aria-hidden /> : <span className="size-1.5 rounded-full bg-current" aria-hidden />}
            {LABEL[s]}
            {st?.attempt && st.attempt > 1 && <span className="num">#{st.attempt}</span>}
            {st?.ms !== undefined && <span className="num opacity-70">{st.ms < 1000 ? `${Math.round(st.ms)}ms` : `${(st.ms / 1000).toFixed(1)}s`}</span>}
            <span className="sr-only">{st?.status === "done" ? "complete" : st ? "running" : "pending"}</span>
          </motion.li>
        );
      })}
    </ol>
  );
}
