import Link from "next/link";
import { ArrowRight, Calculator, ShieldCheck, Sigma, Workflow } from "lucide-react";
import { Wordmark } from "@/components/Logo";
import { HeroPreview } from "@/components/HeroPreview";

const PILLARS = [
  { icon: Workflow, title: "Planned, not guessed", body: "A LangGraph agent turns your question into typed operations or validated SQL, retrying with feedback when a plan fails." },
  { icon: ShieldCheck, title: "Sandboxed execution", body: "Untrusted SQL runs in a separate OS-sandboxed process on a locked DuckDB connection, with time, memory and row limits." },
  { icon: Sigma, title: "Real statistics", body: "Trends, cohorts, segments, regressions and significance tests computed by DuckDB, SciPy, scikit-learn and statsmodels." },
  { icon: Calculator, title: "Every number verified", body: "Explanations may only cite computed facts. Unverifiable numbers, wrong groups and causal claims are removed." },
];

export default function Landing() {
  return (
    <div className="min-h-dvh">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <Wordmark />
        <nav className="flex items-center gap-2 text-sm">
          <Link href="/datasets" className="rounded-lg px-3 py-2 text-muted hover:text-text">Datasets</Link>
          <Link href="/workspace" className="inline-flex items-center gap-2 rounded-lg bg-lime px-4 py-2 font-medium text-[#0f1012] hover:brightness-110">
            Open workspace <ArrowRight className="size-4" />
          </Link>
        </nav>
      </header>
      <section className="grid-bg">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-6 py-16 lg:grid-cols-[1.05fr_1fr] lg:py-24">
          <div>
            <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-line bg-panel px-3 py-1 text-xs text-muted">
              <span className="size-1.5 rounded-full bg-lime" /> Autonomous data analyst · runs on a local LLM
            </p>
            <h1 className="text-4xl font-semibold leading-[1.05] tracking-tight sm:text-6xl">
              From data to decisions, <span className="text-lime">with every number explained.</span>
            </h1>
            <p className="mt-6 max-w-xl text-lg text-muted">
              Upload a dataset, ask a question in plain language, and get safe SQL, reproducible statistics and interactive Plotly charts, all traced back to the computation that produced them.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/workspace" className="inline-flex items-center gap-2 rounded-xl bg-lime px-5 py-3 font-medium text-[#0f1012] hover:brightness-110">
                Ask a question <ArrowRight className="size-4" />
              </Link>
              <Link href="/datasets" className="rounded-xl border border-line bg-panel px-5 py-3 font-medium hover:bg-panel-2">Explore datasets</Link>
            </div>
          </div>
          <HeroPreview />
        </div>
      </section>
      <section className="mx-auto grid max-w-6xl gap-4 px-6 py-16 sm:grid-cols-2 lg:grid-cols-4">
        {PILLARS.map(({ icon: Icon, title, body }) => (
          <div key={title} className="rounded-2xl border border-line bg-panel p-5">
            <Icon className="size-5 text-lime" aria-hidden />
            <h2 className="mt-4 font-semibold">{title}</h2>
            <p className="mt-2 text-sm text-muted">{body}</p>
          </div>
        ))}
      </section>
      <footer className="mx-auto max-w-6xl px-6 pb-10 text-xs text-muted">
        Demo datasets are synthetic and labelled as such. InsightForge never fabricates analytical numbers.
      </footer>
    </div>
  );
}
