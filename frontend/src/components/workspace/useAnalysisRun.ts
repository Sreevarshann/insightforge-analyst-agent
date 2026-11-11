"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";
import { streamAnalysis } from "@/lib/api";
import type { AgentEvent, Analysis, Chart, StepResult, Verification } from "@/lib/types";

export const STAGES = ["catalog", "plan", "validate", "execute", "inspect", "charts", "explain"] as const;

export interface LiveRun {
  question: string;
  stages: Record<string, { status: "start" | "done"; ms?: number; attempt?: number }>;
  results: StepResult[];
  charts: Chart[];
  explanation?: { headline: string; text: string; verification: Verification };
  analysis?: Analysis;
  error?: string;
}

/** Drives one streamed analysis: every state change comes from a real server event. */
export function useAnalysisRun(onDone: (a: Analysis) => void) {
  const [run, setRun] = useState<LiveRun | null>(null);
  const abort = useRef<AbortController | null>(null);
  const qc = useQueryClient();

  const start = useCallback(
    async (question: string) => {
      abort.current?.abort();
      const ctrl = new AbortController();
      abort.current = ctrl;
      setRun({ question, stages: {}, results: [], charts: [] });
      const apply = (e: AgentEvent) =>
        setRun((r) => {
          if (!r) return r;
          switch (e.type) {
            case "stage":
              return { ...r, stages: { ...r.stages, [e.stage]: { status: e.status, ms: e.ms as number | undefined, attempt: e.attempt as number | undefined } } };
            case "result":
              return { ...r, results: [...r.results.filter((x) => x.step !== e.result.step), e.result] };
            case "chart":
              return { ...r, charts: [...r.charts, e.chart] };
            case "explanation":
              return { ...r, explanation: e.explanation };
            case "done":
              return { ...r, analysis: e.analysis };
            case "error":
              return { ...r, error: e.message };
            default:
              return r;
          }
        });
      try {
        await streamAnalysis(
          question,
          (e) => {
            apply(e);
            if (e.type === "done") {
              qc.invalidateQueries({ queryKey: ["analyses"] });
              onDone(e.analysis);
            }
          },
          ctrl.signal,
        );
      } catch (err) {
        if (!ctrl.signal.aborted) setRun((r) => (r ? { ...r, error: err instanceof Error ? err.message : "Stream failed" } : r));
      }
    },
    [onDone, qc],
  );

  const cancel = useCallback(() => abort.current?.abort(), []);
  return { run, start, cancel, clear: () => setRun(null) };
}
