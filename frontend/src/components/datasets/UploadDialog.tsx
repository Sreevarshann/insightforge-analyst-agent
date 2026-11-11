"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileUp, Loader2, X } from "lucide-react";
import { useRef, useState } from "react";
import { api } from "@/lib/api";
import type { Dataset } from "@/lib/types";
import { Button } from "../ui/primitives";

const ACCEPT = ".csv,.tsv,.tab,.xlsx,.parquet,.pq,.sqlite,.sqlite3,.db";

export function UploadDialog({ onUploaded }: { onUploaded?: (d: Dataset[]) => void }) {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const qc = useQueryClient();
  const upload = useMutation({
    mutationFn: () => api.upload(file!, name || undefined),
    onSuccess: (ds) => {
      qc.invalidateQueries({ queryKey: ["datasets"] });
      setOpen(false);
      setFile(null);
      setName("");
      onUploaded?.(ds);
    },
  });
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button variant="primary" size="sm" className="w-full">
          <FileUp className="size-4" /> Upload data
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(92vw,480px)] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-line bg-panel p-6 shadow-2xl">
          <div className="flex items-start justify-between">
            <div>
              <Dialog.Title className="text-lg font-semibold">Upload a dataset</Dialog.Title>
              <Dialog.Description className="mt-1 text-sm text-muted">CSV, TSV, Excel (.xlsx), Parquet or SQLite. Up to 50 MB. Each sheet or table becomes a dataset.</Dialog.Description>
            </div>
            <Dialog.Close className="rounded-lg p-1 text-muted hover:bg-panel-2" aria-label="Close">
              <X className="size-4" />
            </Dialog.Close>
          </div>
          <button
            type="button"
            onClick={() => input.current?.click()}
            onDragOver={(e) => (e.preventDefault(), setDrag(true))}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              const f = e.dataTransfer.files[0];
              if (f) setFile(f);
            }}
            className={`mt-5 flex w-full flex-col items-center gap-2 rounded-xl border border-dashed px-4 py-8 text-sm transition-colors ${drag ? "border-lime bg-lime-soft" : "border-line hover:bg-panel-2"}`}
          >
            <FileUp className="size-6 text-lime" aria-hidden />
            {file ? <span className="font-medium">{file.name} · {(file.size / 1024).toFixed(0)} KB</span> : <span className="text-muted">Drop a file here or click to browse</span>}
          </button>
          <input ref={input} type="file" accept={ACCEPT} className="sr-only" onChange={(e) => setFile(e.target.files?.[0] ?? null)} aria-label="Dataset file" />
          <label className="mt-4 block text-sm">
            <span className="text-muted">Display name (optional)</span>
            <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} className="mt-1 w-full rounded-lg border border-line bg-panel-2 px-3 py-2 outline-none focus:border-lime" placeholder="e.g. Orders 2025" />
          </label>
          {upload.isError && <p role="alert" className="mt-3 text-sm text-coral">{(upload.error as Error).message}</p>}
          <div className="mt-6 flex justify-end gap-2">
            <Dialog.Close asChild>
              <Button variant="ghost">Cancel</Button>
            </Dialog.Close>
            <Button variant="primary" disabled={!file || upload.isPending} onClick={() => upload.mutate()}>
              {upload.isPending && <Loader2 className="size-4 animate-spin" />} Ingest & profile
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
