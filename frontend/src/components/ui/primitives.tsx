"use client";

import { forwardRef } from "react";
import { cn } from "@/lib/cn";

export const Button = forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "outline" | "danger"; size?: "sm" | "md" }>(
  function Button({ className, variant = "outline", size = "md", ...props }, ref) {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
          size === "sm" ? "h-8 px-3 text-xs" : "h-10 px-4 text-sm",
          variant === "primary" && "bg-lime text-[#0f1012] hover:brightness-110",
          variant === "outline" && "border border-line bg-panel hover:bg-panel-2",
          variant === "ghost" && "hover:bg-panel-2",
          variant === "danger" && "border border-coral/40 text-coral hover:bg-coral-soft",
          className,
        )}
        {...props}
      />
    );
  },
);

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-2xl border border-line bg-panel", className)} {...props} />;
}

export function Badge({ tone = "neutral", className, ...props }: React.HTMLAttributes<HTMLSpanElement> & { tone?: "neutral" | "lime" | "coral" | "warn" | "sky" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium",
        tone === "neutral" && "bg-panel-2 text-muted",
        tone === "lime" && "bg-lime-soft text-lime",
        tone === "coral" && "bg-coral-soft text-coral",
        tone === "warn" && "bg-panel-2 text-warn",
        tone === "sky" && "bg-panel-2 text-sky",
        className,
      )}
      {...props}
    />
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("skeleton h-4", className)} />;
}

export function EmptyState({ icon, title, children, action }: { icon: React.ReactNode; title: string; children?: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="grid-bg flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-line px-6 py-14 text-center">
      <div className="grid size-11 place-items-center rounded-xl bg-panel-2 text-lime">{icon}</div>
      <h3 className="font-semibold">{title}</h3>
      {children && <p className="max-w-sm text-sm text-muted">{children}</p>}
      {action}
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start justify-between gap-4 rounded-xl border border-coral/40 bg-coral-soft p-4 text-sm">
      <div>
        <p className="font-medium text-coral">Something went wrong</p>
        <p className="mt-1 text-muted">{error instanceof Error ? error.message : String(error)}</p>
      </div>
      {onRetry && (
        <Button size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

export function Kbd({ children }: { children: React.ReactNode }) {
  return <kbd className="num rounded border border-line bg-panel-2 px-1.5 py-0.5 text-[10px] text-muted">{children}</kbd>;
}
