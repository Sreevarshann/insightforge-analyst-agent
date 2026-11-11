import type { Data, Layout } from "plotly.js";

export interface Column { name: string; type: string; nullable: boolean }
export interface Version { id: string; version: number; source_format: string; source_name: string; sha256: string; row_count: number; column_count: number; created_at: string }
export interface Dataset { id: string; table_name: string; display_name: string; description: string | null; is_demo: boolean; created_at: string; current: Version; columns: Column[]; version_count: number }

export interface ColumnProfile {
  name: string; type: string; kind: "numeric" | "temporal" | "text" | "boolean" | "other";
  null_count: number; missing_pct: number; distinct_count: number;
  is_id_like: boolean; is_date_candidate: boolean; is_dimension_candidate: boolean; looks_numeric?: boolean;
  numeric?: { min: number | null; max: number | null; mean: number | null; std: number | null; p25: number | null; median: number | null; p75: number | null; sum: number | null; zero_count: number; histogram: { start: number; end: number; count: number }[]; outliers: { method: string; count: number; lower_fence: number | null; upper_fence: number | null } };
  temporal?: { min: string | null; max: string | null };
  top_values?: { value: unknown; count: number }[];
  text?: { min_length: number | null; max_length: number | null; untrimmed: number };
}
export interface Profile {
  dataset_id: string; version: number; row_count: number; column_count: number; duplicate_rows: number; total_missing_cells: number;
  columns: ColumnProfile[]; sample_rows: unknown[][]; candidate_date_columns: string[]; candidate_dimensions: string[]; candidate_measures: string[];
  suggestions: { severity: "info" | "warning"; column: string; message: string }[];
}
export interface Preview { columns: Column[]; rows: unknown[][]; total_rows: number; offset: number; limit: number }

export interface Fact { id: string; label: string; value: number | string | null; unit: import("./format").Unit; source: Record<string, unknown> }
export interface ResultTable { name: string; columns: string[]; rows: unknown[][]; truncated: boolean }
export interface StepResult {
  step: number; purpose: string; op: string; args: Record<string, unknown>; tables: ResultTable[]; facts: Fact[];
  notes: string[]; query_ids: string[]; sql: string[]; dataset_versions: string[]; chart_hint: Record<string, unknown> | null;
}
export interface ChartConfig { type: string; table: string; x?: string | null; y?: string | null; color?: string | null; title?: string | null; orientation?: "v" | "h"; top_n?: number; category_filter?: string[]; log_y?: boolean; value_suffix?: string | null }
export interface Chart { step: number; config: ChartConfig; figure: { data: Data[]; layout: Partial<Layout> } }
export interface Verification {
  status: "verified" | "corrected" | "abstained" | "deterministic";
  checks?: { name: string; passed: boolean; detail: string }[];
  removed_sentences?: { sentence: string; reason: string }[];
  cited_fact_ids?: string[]; draft?: string; fallback?: string;
}
export interface TraceEntry { node: string; ms: number; [k: string]: unknown }
export interface Analysis {
  id: string; question: string; status: "running" | "completed" | "failed" | "needs_clarification"; title: string | null; explanation: string | null;
  plan: { raw: Record<string, unknown> | null; steps: Record<string, unknown>[]; attempts: number; errors: string[]; trace: TraceEntry[]; llm_usage: Record<string, number> } | null;
  steps: StepResult[]; charts: Chart[]; verification: Verification | null; dataset_versions: string[]; model_name: string | null; duration_ms: number | null; saved: boolean; created_at: string;
}
export interface QueryResult { query_id: string; sql: string; columns: string[]; types: string[]; rows: unknown[][]; truncated: boolean; elapsed_ms: number; isolation: string; tables: string[]; dataset_versions: string[] }
export interface QueryLog { id: string; sql: string; origin: string; accepted: boolean; rejection_reason: string | null; row_count: number | null; duration_ms: number | null; analysis_id: string | null; created_at: string }
export type AgentEvent =
  | { type: "analysis"; id: string; status: string }
  | { type: "stage"; stage: string; status: "start" | "done"; ms?: number; [k: string]: unknown }
  | { type: "plan"; plan: Record<string, unknown> }
  | { type: "result"; result: StepResult }
  | { type: "chart"; chart: Chart }
  | { type: "explanation"; explanation: { headline: string; text: string; verification: Verification; assumptions: string[]; notes: string[] } }
  | { type: "done"; analysis: Analysis }
  | { type: "error"; message: string };
