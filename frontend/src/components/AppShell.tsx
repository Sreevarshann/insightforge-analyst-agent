"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Database, FlaskConical, Moon, Sparkles, Sun, Terminal, BookMarked, Menu, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { Wordmark } from "./Logo";
import { useTheme } from "./theme";
import { Kbd } from "./ui/primitives";

interface NavItem { href: string; label: string; icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>; key: string }
const NAV: { group: string; items: NavItem[] }[] = [
  { group: "Analyze", items: [
    { href: "/workspace", label: "Analysis Copilot", icon: Sparkles, key: "w" },
    { href: "/query", label: "Query Console", icon: Terminal, key: "q" },
  ] },
  { group: "Data", items: [{ href: "/datasets", label: "Dataset Explorer", icon: Database, key: "d" }] },
  { group: "Results", items: [
    { href: "/analyses", label: "Saved Analyses", icon: BookMarked, key: "s" },
    { href: "/evaluation", label: "Evaluation", icon: FlaskConical, key: "e" },
  ] },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 30_000 });

  // "g" then a letter jumps between sections (like many developer tools).
  useEffect(() => {
    let armed = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.closest("input, textarea, [contenteditable], .monaco-editor") || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "g") {
        armed = true;
        clearTimeout(timer);
        timer = setTimeout(() => (armed = false), 900);
        return;
      }
      if (armed) {
        const hit = NAV.flatMap((g) => g.items).find((i) => i.key === e.key);
        if (hit) router.push(hit.href);
        armed = false;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [router]);

  // Close the mobile menu after navigation (state adjusted during render, not in an effect).
  const [lastPath, setLastPath] = useState(pathname);
  if (lastPath !== pathname) {
    setLastPath(pathname);
    setOpen(false);
  }

  const nav = (
    <nav aria-label="Primary" className="flex flex-col gap-6">
      {NAV.map((g) => (
        <div key={g.group}>
          <p className="px-3 pb-2 text-[11px] font-medium uppercase tracking-[0.12em] text-muted">{g.group}</p>
          <ul className="flex flex-col gap-0.5">
            {g.items.map((item) => {
              const active = pathname.startsWith(item.href);
              const Icon = item.icon;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={cn("group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors", active ? "bg-panel-2 text-text" : "text-muted hover:bg-panel-2 hover:text-text")}
                  >
                    <Icon className={cn("size-4", active && "text-lime")} aria-hidden />
                    <span className="flex-1">{item.label}</span>
                    <span className="hidden gap-0.5 group-hover:flex">
                      <Kbd>g</Kbd>
                      <Kbd>{item.key}</Kbd>
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );

  return (
    <div className="flex min-h-dvh">
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col gap-8 border-r border-line bg-panel px-3 py-5 lg:flex">
        <Link href="/" className="px-3" aria-label="InsightForge home">
          <Wordmark />
        </Link>
        {nav}
        <div className="mt-auto flex flex-col gap-3 px-3 text-xs text-muted">
          <ModelStatus health={health.data} error={health.isError} />
          <button onClick={toggle} className="flex items-center gap-2 hover:text-text" aria-label="Toggle colour theme">
            {theme === "dark" ? <Sun className="size-3.5" /> : <Moon className="size-3.5" />}
            {theme === "dark" ? "Light mode" : "Dark mode"}
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-panel/90 px-4 py-3 backdrop-blur lg:hidden">
          <Link href="/" aria-label="InsightForge home">
            <Wordmark />
          </Link>
          <button onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-label="Open navigation" className="rounded-lg p-2 hover:bg-panel-2">
            {open ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </header>
        {open && <div className="border-b border-line bg-panel px-3 py-4 lg:hidden">{nav}</div>}
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}

function ModelStatus({ health, error }: { health?: { llm_provider: string; version: string }; error: boolean }) {
  return (
    <div className="flex items-center gap-2" title="Backend API and LLM provider">
      <span className={cn("size-2 rounded-full", error ? "bg-coral" : health ? "bg-lime" : "bg-muted")} aria-hidden />
      <span>{error ? "API offline" : health ? `API v${health.version} · ${health.llm_provider}` : "Connecting…"}</span>
    </div>
  );
}
