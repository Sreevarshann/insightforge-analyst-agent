# InsightForge web

Next.js 16 (App Router, Cache Components) + React 19 + Tailwind 4 + Radix + TanStack Query +
Motion + Plotly. The browser talks only to this origin; `/api/*` is rewritten to the FastAPI
backend (`INSIGHTFORGE_API_ORIGIN`, default `http://127.0.0.1:8111`).

```bash
npm install
npm run dev -- --port 3101
```

See the repository root README for the full setup.
