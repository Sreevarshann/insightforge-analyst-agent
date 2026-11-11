"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";
import type { Config, Data, Layout } from "plotly.js";
import { useTheme } from "../theme";
import { Skeleton } from "../ui/primitives";

// plotly.js is large and browser-only: load the minified dist bundle on the client.
const Plotly = dynamic(
  async () => {
    const [{ default: createPlotlyComponent }, plotly] = await Promise.all([import("react-plotly.js/factory"), import("plotly.js-dist-min")]);
    return createPlotlyComponent(plotly.default ?? plotly);
  },
  { ssr: false, loading: () => <Skeleton className="h-full min-h-60 w-full" /> },
);

const PALETTE = {
  dark: { text: "#ecebe6", muted: "#9a9ca3", grid: "#2a2c31", colorway: ["#b5f23d", "#7aa7ff", "#ff8a65", "#c084fc", "#2dd4bf", "#fbbf24", "#f472b6", "#94a3b8"] },
  light: { text: "#17181a", muted: "#5e6066", grid: "#e4e2da", colorway: ["#4d7c0f", "#2563eb", "#c2410c", "#7c3aed", "#0f766e", "#b45309", "#be185d", "#475569"] },
};

export interface Figure {
  data: Data[];
  layout: Partial<Layout>;
}

/** Themed, responsive Plotly chart with zoom/pan/legend toggling and PNG/SVG export. */
export function Plot({ figure, height = 340, title }: { figure: Figure; height?: number; title?: string }) {
  const { theme } = useTheme();
  const p = PALETTE[theme];
  const layout = useMemo<Partial<Layout>>(
    () => ({
      ...figure.layout,
      autosize: true,
      height,
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      colorway: p.colorway,
      font: { family: "var(--font-geist-sans), system-ui, sans-serif", color: p.text, size: 12 },
      xaxis: { gridcolor: p.grid, zerolinecolor: p.grid, linecolor: p.grid, ...(figure.layout.xaxis ?? {}), tickfont: { color: p.muted } },
      yaxis: { gridcolor: p.grid, zerolinecolor: p.grid, linecolor: p.grid, ...(figure.layout.yaxis ?? {}), tickfont: { color: p.muted } },
      hoverlabel: { bgcolor: theme === "dark" ? "#1d1f23" : "#ffffff", bordercolor: p.grid, font: { color: p.text } },
      legend: { ...(figure.layout.legend ?? {}), font: { color: p.muted } },
      title: title ? { text: title, font: { size: 13 } } : figure.layout.title,
      transition: { duration: 300, easing: "cubic-in-out" },
    }),
    [figure.layout, height, p, theme, title],
  );
  return (
    <div className="w-full" role="img" aria-label={title ?? "Interactive chart"}>
      <Plotly
        data={figure.data}
        layout={layout}
        useResizeHandler
        style={{ width: "100%", height }}
        config={({ displaylogo: false, responsive: true, modeBarButtonsToRemove: ["lasso2d", "select2d"], toImageButtonOptions: { format: "png", filename: "insightforge-chart", scale: 2 } } satisfies Partial<Config>)}
      />
    </div>
  );
}
