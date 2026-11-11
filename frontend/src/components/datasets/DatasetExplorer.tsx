"use client";

import * as Tabs from "@radix-ui/react-tabs";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, GitCompareArrows, Search, Trash2 } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatValue, relativeTime } from "@/lib/format";
import type { Dataset } from "@/lib/types";
import { useDatasets } from "@/lib/useDatasets";
import { Badge, Button, Card, EmptyState, ErrorBox, Skeleton } from "../ui/primitives";
import { PreviewTable } from "./PreviewTable";
import { MissingChart, SchemaInspector, StatCards, Suggestions } from "./ProfilePanels";
import { UploadDialog } from "./UploadDialog";

const TABS = ["overview", "columns", "preview", "versions", "compare"] as const;

export function DatasetExplorer() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const datasets = useDatasets();
  const [filter, setFilter] = useState("");
  const selectedId = params.get("id") ?? datasets.data?.[0]?.id;
  const tab = (TABS as readonly string[]).includes(params.get("tab") ?? "") ? (params.get("tab") as (typeof TABS)[number]) : "overview";
  const select = (id: string, t: string = tab) => router.replace(`${pathname}?id=${id}&tab=${t}`, { scroll: false });
  const selected = datasets.data?.find((d) => d.id === selectedId);
  const visible = (datasets.data ?? []).filter((d) => `${d.display_name} ${d.table_name}`.toLowerCase().includes(filter.toLowerCase()));

  return (
    <div className="flex min-h-dvh flex-col lg:flex-row">
      <aside className="flex w-full shrink-0 flex-col gap-3 border-b border-line p-4 lg:w-72 lg:border-b-0 lg:border-r">
        <UploadDialog onUploaded={(ds) => ds[0] && select(ds[0].id, "overview")} />
        <label className="relative">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
          <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter datasets" aria-label="Filter datasets" className="w-full rounded-lg border border-line bg-panel-2 py-2 pl-9 pr-3 text-sm outline-none focus:border-lime" />
        </label>
        {datasets.isLoading && Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-14" />)}
        {datasets.isError && <ErrorBox error={datasets.error} onRetry={() => datasets.refetch()} />}
        <ul className="flex flex-col gap-1" aria-label="Datasets">
          {visible.map((d) => (
            <li key={d.id}>
              <button onClick={() => select(d.id)} aria-current={d.id === selectedId} className={cn("w-full rounded-xl px-3 py-2.5 text-left transition-colors", d.id === selectedId ? "bg-panel-2 ring-1 ring-line" : "hover:bg-panel-2/60")}>
                <span className="flex items-center gap-2 text-sm font-medium">
                  <Database className={cn("size-3.5", d.id === selectedId ? "text-lime" : "text-muted")} aria-hidden />
                  <span className="truncate">{d.display_name}</span>
                  {d.is_demo && <Badge tone="sky">synthetic</Badge>}
                </span>
                <span className="num mt-0.5 block text-xs text-muted">
                  {d.table_name} · {formatValue(d.current.row_count, "count")} rows · v{d.current.version}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </aside>
      <section className="min-w-0 flex-1 p-4 sm:p-6">
        {datasets.data && datasets.data.length === 0 ? (
          <EmptyState icon={<Database className="size-5" />} title="No datasets yet" action={<code className="rounded bg-panel-2 px-2 py-1 text-xs">make seed</code>}>
            Upload a CSV, Excel, Parquet or SQLite file — or load the synthetic Lumen Commerce demo data.
          </EmptyState>
        ) : selected ? (
          <DatasetView key={selected.id} dataset={selected} tab={tab} onTab={(t) => select(selected.id, t)} all={datasets.data ?? []} />
        ) : (
          <Skeleton className="h-40" />
        )}
      </section>
    </div>
  );
}

function DatasetView({ dataset, tab, onTab, all }: { dataset: Dataset; tab: string; onTab: (t: string) => void; all: Dataset[] }) {
  const profile = useQuery({ queryKey: ["profile", dataset.id, dataset.current.version], queryFn: () => api.profile(dataset.id) });
  const qc = useQueryClient();
  const router = useRouter();
  const del = useMutation({
    mutationFn: () => api.deleteDataset(dataset.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["datasets"] });
      router.replace("/datasets");
    },
  });
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{dataset.display_name}</h1>
          <p className="num mt-1 text-sm text-muted">
            <code>{dataset.table_name}</code> · {dataset.current.source_format.toUpperCase()} · {dataset.current.source_name} · updated {relativeTime(dataset.current.created_at)}
          </p>
          {dataset.description && <p className="mt-2 max-w-2xl text-sm text-muted">{dataset.description}</p>}
        </div>
        <div className="flex gap-2">
          <Link href={`/workspace?dataset=${dataset.id}`} className="inline-flex h-8 items-center rounded-lg bg-lime px-3 text-xs font-medium text-[#0f1012] hover:brightness-110">Analyse</Link>
          <Button size="sm" variant="danger" onClick={() => confirm(`Delete “${dataset.display_name}” and all its versions? This cannot be undone.`) && del.mutate()}>
            <Trash2 className="size-3.5" /> Delete
          </Button>
        </div>
      </div>
      <Tabs.Root value={tab} onValueChange={onTab} className="mt-6">
        <Tabs.List aria-label="Dataset views" className="flex gap-1 overflow-x-auto border-b border-line">
          {TABS.map((t) => (
            <Tabs.Trigger key={t} value={t} className="relative px-3 pb-2.5 pt-1 text-sm capitalize text-muted data-[state=active]:text-text">
              {t}
              {tab === t && <motion.span layoutId="ds-tab" className="absolute inset-x-2 -bottom-px h-0.5 rounded bg-lime" />}
            </Tabs.Trigger>
          ))}
        </Tabs.List>
        <div className="pt-5">
          {profile.isError && <ErrorBox error={profile.error} onRetry={() => profile.refetch()} />}
          <Tabs.Content value="overview">
            {profile.data ? (
              <div className="flex flex-col gap-5">
                <StatCards profile={profile.data} />
                <div className="grid gap-5 xl:grid-cols-2">
                  <Card className="p-5">
                    <h2 className="mb-3 font-semibold">Data-quality suggestions</h2>
                    <Suggestions profile={profile.data} />
                  </Card>
                  <Card className="p-5">
                    <h2 className="mb-1 font-semibold">Missing values by column</h2>
                    <MissingChart profile={profile.data} />
                  </Card>
                </div>
                <Card className="p-5">
                  <h2 className="mb-3 font-semibold">Detected roles</h2>
                  <Roles label="Dates" items={profile.data.candidate_date_columns} tone="sky" />
                  <Roles label="Dimensions" items={profile.data.candidate_dimensions} tone="lime" />
                  <Roles label="Measures" items={profile.data.candidate_measures} tone="neutral" />
                </Card>
              </div>
            ) : (
              <Skeleton className="h-64" />
            )}
          </Tabs.Content>
          <Tabs.Content value="columns">{profile.data ? <SchemaInspector profile={profile.data} /> : <Skeleton className="h-64" />}</Tabs.Content>
          <Tabs.Content value="preview">
            <PreviewTable datasetId={dataset.id} />
          </Tabs.Content>
          <Tabs.Content value="versions">
            <Versions dataset={dataset} />
          </Tabs.Content>
          <Tabs.Content value="compare">
            <Compare base={dataset} all={all} />
          </Tabs.Content>
        </div>
      </Tabs.Root>
    </motion.div>
  );
}

function Roles({ label, items, tone }: { label: string; items: string[]; tone: "sky" | "lime" | "neutral" }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5 py-1.5 text-sm">
      <span className="w-24 text-muted">{label}</span>
      {items.length ? items.map((i) => <Badge key={i} tone={tone}>{i}</Badge>) : <span className="text-xs text-muted">none detected</span>}
    </div>
  );
}

function Versions({ dataset }: { dataset: Dataset }) {
  const q = useQuery({ queryKey: ["versions", dataset.id], queryFn: () => fetch(`/api/datasets/${dataset.id}/versions`).then((r) => r.json() as Promise<Dataset["current"][]>) });
  return (
    <Card className="divide-y divide-line">
      {(q.data ?? []).slice().reverse().map((v) => (
        <div key={v.id} className="flex flex-wrap items-center gap-4 px-5 py-3 text-sm">
          <Badge tone={v.version === dataset.current.version ? "lime" : "neutral"}>v{v.version}</Badge>
          <span className="flex-1">{v.source_name}</span>
          <span className="num text-muted">{formatValue(v.row_count, "count")} rows · {v.column_count} cols</span>
          <code className="num text-xs text-muted" title="SHA-256 of the uploaded file">{v.sha256.slice(0, 12)}</code>
          <span className="text-xs text-muted">{relativeTime(v.created_at)}</span>
        </div>
      ))}
    </Card>
  );
}

function Compare({ base, all }: { base: Dataset; all: Dataset[] }) {
  const others = all.filter((d) => d.id !== base.id);
  const [otherId, setOtherId] = useState(others[0]?.id);
  const other = others.find((d) => d.id === otherId);
  const diff = (() => {
    if (!other) return null;
    const a = new Map(base.columns.map((c) => [c.name, c.type]));
    const b = new Map(other.columns.map((c) => [c.name, c.type]));
    const shared = [...a.keys()].filter((k) => b.has(k));
    return { shared, onlyA: [...a.keys()].filter((k) => !b.has(k)), onlyB: [...b.keys()].filter((k) => !a.has(k)), typeDiff: shared.filter((k) => a.get(k) !== b.get(k)) };
  })();
  if (!others.length) return <EmptyState icon={<GitCompareArrows className="size-5" />} title="Nothing to compare">Upload another dataset to compare schemas.</EmptyState>;
  return (
    <div className="flex flex-col gap-4">
      <label className="flex items-center gap-3 text-sm">
        <span className="text-muted">Compare with</span>
        <select value={otherId} onChange={(e) => setOtherId(e.target.value)} className="rounded-lg border border-line bg-panel-2 px-3 py-2">
          {others.map((d) => <option key={d.id} value={d.id}>{d.display_name}</option>)}
        </select>
      </label>
      {diff && other && (
        <div className="grid gap-4 md:grid-cols-3">
          <Card className="p-5"><p className="text-xs text-muted">Rows</p><p className="num mt-1 text-lg">{formatValue(base.current.row_count, "count")} vs {formatValue(other.current.row_count, "count")}</p></Card>
          <Card className="p-5"><p className="text-xs text-muted">Shared columns</p><p className="num mt-1 text-lg">{diff.shared.length}</p><p className="mt-2 flex flex-wrap gap-1">{diff.shared.map((c) => <Badge key={c} tone={diff.typeDiff.includes(c) ? "coral" : "lime"}>{c}</Badge>)}</p>{diff.typeDiff.length > 0 && <p className="mt-2 text-xs text-coral">Type differs: {diff.typeDiff.join(", ")}</p>}</Card>
          <Card className="p-5"><p className="text-xs text-muted">Unique columns</p><p className="mt-2 text-xs text-muted">Only in {base.table_name}</p><p className="flex flex-wrap gap-1">{diff.onlyA.map((c) => <Badge key={c}>{c}</Badge>)}</p><p className="mt-2 text-xs text-muted">Only in {other.table_name}</p><p className="flex flex-wrap gap-1">{diff.onlyB.map((c) => <Badge key={c}>{c}</Badge>)}</p></Card>
        </div>
      )}
    </div>
  );
}
