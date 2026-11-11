"use client";

import { motion } from "motion/react";
import { CheckCircle2 } from "lucide-react";

/** Static illustration of the verification flow (labelled as an illustration, not data). */
export function HeroPreview() {
  const steps = ["catalog", "plan", "validate", "execute", "charts", "verify"];
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="rounded-2xl border border-line bg-panel p-5 shadow-2xl shadow-black/20">
      <div className="flex items-center justify-between text-xs text-muted">
        <span>How an answer is produced</span>
        <span className="rounded bg-panel-2 px-1.5 py-0.5">illustration</span>
      </div>
      <p className="mt-4 text-sm font-medium">“Which plan has the highest churn rate?”</p>
      <ol className="mt-4 grid grid-cols-3 gap-2 sm:grid-cols-6">
        {steps.map((s, i) => (
          <motion.li key={s} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.25 + i * 0.12 }} className="flex flex-col items-center gap-1 rounded-lg bg-panel-2 px-2 py-2 text-[11px] text-muted">
            <CheckCircle2 className="size-3.5 text-lime" aria-hidden />
            {s}
          </motion.li>
        ))}
      </ol>
      <div className="mt-4 rounded-xl border border-line p-4 font-mono text-xs leading-relaxed text-muted">
        <p><span className="text-sky">rate</span>(dataset=<span className="text-lime">subscriptions</span>, outcome=<span className="text-lime">churned</span>, group_by=[<span className="text-lime">plan</span>])</p>
        <p className="mt-2">→ draft: “Starter has the highest churn at <span className="text-coral">{"{{r3}}"}</span>.”</p>
        <p className="mt-1">→ verifier: placeholder resolved to the computed fact; group label matches ✓</p>
      </div>
    </motion.div>
  );
}
