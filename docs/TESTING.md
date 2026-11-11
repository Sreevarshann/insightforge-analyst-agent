# Testing

| Layer | Command | What it covers |
|---|---|---|
| Backend unit + integration | `make test` | 170+ pytest tests: ingestion (all formats, malicious files), profiling vs NumPy, SQL policy, DuckDB lockdown, **real sandbox subprocesses**, typed operations vs pandas/SciPy/statsmodels, agent graph with fixture + scripted adversarial providers, verifier, charts, reports, streaming, relationships, benchmark |
| Live LLM | `make test-live` | Agent against a real local Ollama model (`-m live`, excluded from CI) |
| Frontend unit | `make test-web` | ESLint, `tsc --noEmit`, Vitest component tests |
| End-to-end | `make e2e` | Playwright: isolated stack (ports 8191/3191, fixture provider, fresh synthetic data) – landing, explorer, upload, streamed copilot answer, query-policy rejection, 404s |
| Benchmark | `make evaluate` / `make evaluate-fixture` | See `EVALUATION.md` |

The **fixture provider is a deterministic keyword heuristic, not a language model**. It
exists so CI can exercise the full graph, validators, verifier and UI without model
weights. Results produced with it are labelled `fixture` everywhere. Nothing in the
sandbox or SQL policy tests is mocked.

CI (`.github/workflows/ci.yml`): backend (ruff, mypy strict, pytest, pip-audit), frontend
(lint, types, Vitest, build, npm audit), Playwright E2E, Docker image build + health
check, gitleaks over the full history.
