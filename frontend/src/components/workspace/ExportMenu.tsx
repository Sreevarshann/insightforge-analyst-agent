"use client";

import * as Menu from "@radix-ui/react-dropdown-menu";
import { Download, FileCode2, FileText, Sheet } from "lucide-react";
import type { Analysis } from "@/lib/types";

const item = "flex cursor-pointer items-center gap-2 rounded-md px-2.5 py-1.5 text-xs outline-none data-[highlighted]:bg-panel-2";

export function ExportMenu({ a }: { a: Analysis }) {
  const base = `/api/analyses/${a.id}`;
  const tables = a.steps.flatMap((s) => s.tables.filter((t) => t.name !== "raw").map((t) => ({ step: s.step, name: t.name })));
  return (
    <Menu.Root>
      <Menu.Trigger onClick={(e) => e.stopPropagation()} className="rounded-lg p-1.5 text-muted hover:bg-panel-2 hover:text-text" aria-label="Export">
        <Download className="size-4" />
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Content align="end" sideOffset={6} className="z-50 min-w-52 rounded-xl border border-line bg-panel p-1 shadow-xl">
          <Menu.Item asChild className={item}><a href={`${base}/report?format=html`} target="_blank" rel="noopener"><FileCode2 className="size-3.5" /> Open HTML report</a></Menu.Item>
          <Menu.Item asChild className={item}><a href={`${base}/report?format=html&download=true`}><FileCode2 className="size-3.5" /> Download HTML</a></Menu.Item>
          <Menu.Item asChild className={item}><a href={`${base}/report?format=md&download=true`}><FileText className="size-3.5" /> Download Markdown</a></Menu.Item>
          {tables.length > 0 && <Menu.Separator className="my-1 h-px bg-line" />}
          {tables.map((t) => (
            <Menu.Item key={`${t.step}-${t.name}`} asChild className={item}>
              <a href={`${base}/export.csv?step=${t.step}&table=${encodeURIComponent(t.name)}`}><Sheet className="size-3.5" /> CSV · step {t.step} · {t.name}</a>
            </Menu.Item>
          ))}
          <Menu.Separator className="my-1 h-px bg-line" />
          <p className="px-2.5 py-1 text-[10px] text-muted">Charts: use the camera icon on each chart for PNG.</p>
        </Menu.Content>
      </Menu.Portal>
    </Menu.Root>
  );
}
