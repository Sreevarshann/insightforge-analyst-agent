import type { Analysis, Dataset, Preview, Profile, QueryLog, QueryResult, AgentEvent, ChartConfig, Chart } from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function detailMessage(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) return String((detail as { message: unknown }).message);
  if (Array.isArray(detail)) return detail.map((d) => (d && typeof d === "object" && "msg" in d ? String(d.msg) : String(d))).join("; ");
  return "Request failed";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, { ...init, headers: init?.body instanceof FormData ? init.headers : { "Content-Type": "application/json", ...init?.headers } });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      msg = detailMessage((await res.json()).detail);
    } catch {}
    throw new ApiError(res.status, msg);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export const api = {
  health: () => request<{ status: string; version: string; llm_provider: string }>("/health"),
  datasets: () => request<Dataset[]>("/datasets"),
  dataset: (id: string) => request<Dataset>(`/datasets/${id}`),
  profile: (id: string) => request<Profile>(`/datasets/${id}/profile`),
  preview: (id: string, p: { offset?: number; limit?: number; sort?: string; order?: "asc" | "desc"; search?: string }) => {
    const q = new URLSearchParams();
    Object.entries(p).forEach(([k, v]) => v !== undefined && v !== "" && q.set(k, String(v)));
    return request<Preview>(`/datasets/${id}/preview?${q}`);
  },
  upload: (file: File, name?: string) => {
    const fd = new FormData();
    fd.append("file", file);
    if (name) fd.append("name", name);
    return request<Dataset[]>("/datasets", { method: "POST", body: fd });
  },
  deleteDataset: (id: string) => request<void>(`/datasets/${id}`, { method: "DELETE" }),
  query: (sql: string) => request<QueryResult>("/query", { method: "POST", body: JSON.stringify({ sql }) }),
  queryHistory: () => request<QueryLog[]>("/query/history"),
  analyses: (saved?: boolean) => request<Analysis[]>(`/analyses${saved === undefined ? "" : `?saved=${saved}`}`),
  analysis: (id: string) => request<Analysis>(`/analyses/${id}`),
  setSaved: (id: string, saved: boolean) => request<Analysis>(`/analyses/${id}`, { method: "PATCH", body: JSON.stringify({ saved }) }),
  previewChart: (id: string, step: number, config: ChartConfig) => request<Chart>(`/analyses/${id}/charts/preview`, { method: "POST", body: JSON.stringify({ step, config }) }),
  saveCharts: (id: string, charts: { step: number; config: ChartConfig }[]) => request<Analysis>(`/analyses/${id}/charts`, { method: "PUT", body: JSON.stringify(charts) }),
};

/** POST a question and consume the server-sent event stream of real agent progress. */
export async function streamAnalysis(question: string, onEvent: (e: AgentEvent) => void, signal?: AbortSignal): Promise<void> {
  const res = await fetch("/api/analyses/stream", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }), signal });
  if (!res.ok || !res.body) throw new ApiError(res.status, "Could not start analysis");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const data = chunk.split("\n").filter((l) => l.startsWith("data: ")).map((l) => l.slice(6)).join("\n");
      if (data) onEvent(JSON.parse(data) as AgentEvent);
    }
  }
}
