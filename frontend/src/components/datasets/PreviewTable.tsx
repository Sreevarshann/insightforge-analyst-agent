"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Search } from "lucide-react";
import { useDeferredValue, useState } from "react";
import { api } from "@/lib/api";
import { formatCell } from "@/lib/format";
import { Button, ErrorBox, Skeleton } from "../ui/primitives";
import { TypeIcon } from "./TypeIcon";

const PAGE = 50;

/** Server-side sorted / searched / paginated preview (queries run on a locked DuckDB connection). */
export function PreviewTable({ datasetId }: { datasetId: string }) {
  const [offset, setOffset] = useState(0);
  const [sort, setSort] = useState<{ col: string; order: "asc" | "desc" } | null>(null);
  const [search, setSearch] = useState("");
  const deferred = useDeferredValue(search);
  const q = useQuery({
    queryKey: ["preview", datasetId, offset, sort, deferred],
    queryFn: () => api.preview(datasetId, { offset, limit: PAGE, sort: sort?.col, order: sort?.order, search: deferred }),
    placeholderData: keepPreviousData,
  });
  if (q.isError) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />;
  const data = q.data;
  const toggleSort = (col: string) => {
    setOffset(0);
    setSort((s) => (s?.col !== col ? { col, order: "asc" } : s.order === "asc" ? { col, order: "desc" } : null));
  };
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <label className="relative w-full max-w-xs">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
          <input value={search} onChange={(e) => (setSearch(e.target.value), setOffset(0))} placeholder="Search all columns…" aria-label="Search rows" className="w-full rounded-lg border border-line bg-panel-2 py-2 pl-9 pr-3 text-sm outline-none focus:border-lime" />
        </label>
        {data && (
          <div className="flex items-center gap-2 text-xs text-muted">
            <span className="num">
              {data.total_rows === 0 ? "0" : `${offset + 1}–${Math.min(offset + PAGE, data.total_rows)}`} of {data.total_rows.toLocaleString()}
            </span>
            <Button size="sm" variant="ghost" aria-label="Previous page" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE))}>
              <ChevronLeft className="size-4" />
            </Button>
            <Button size="sm" variant="ghost" aria-label="Next page" disabled={offset + PAGE >= data.total_rows} onClick={() => setOffset((o) => o + PAGE)}>
              <ChevronRight className="size-4" />
            </Button>
          </div>
        )}
      </div>
      <div className="overflow-auto rounded-xl border border-line" style={{ maxHeight: 520 }}>
        {!data ? (
          <div className="flex flex-col gap-2 p-4">{Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-6" />)}</div>
        ) : (
          <table className="w-full border-collapse text-sm">
            <thead className="sticky top-0 z-10 bg-panel-2">
              <tr>
                {data.columns.map((c) => (
                  <th key={c.name} scope="col" aria-sort={sort?.col === c.name ? (sort.order === "asc" ? "ascending" : "descending") : "none"} className="whitespace-nowrap border-b border-line px-3 py-2 text-left font-medium">
                    <button onClick={() => toggleSort(c.name)} className="flex items-center gap-1.5 hover:text-lime">
                      <TypeIcon type={c.type} />
                      {c.name}
                      {sort?.col === c.name && (sort.order === "asc" ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />)}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className={q.isFetching ? "opacity-60 transition-opacity" : ""}>
              {data.rows.map((r, i) => (
                <tr key={offset + i} className="border-b border-line/60 hover:bg-panel-2/60">
                  {r.map((v, j) => (
                    <td key={j} className={`whitespace-nowrap px-3 py-1.5 ${typeof v === "number" ? "num text-right" : ""} ${v === null ? "text-muted/60" : ""}`}>
                      {formatCell(v)}
                    </td>
                  ))}
                </tr>
              ))}
              {data.rows.length === 0 && (
                <tr>
                  <td colSpan={data.columns.length} className="px-3 py-10 text-center text-muted">No rows match “{deferred}”.</td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
