# Key technical decisions

1. **Typed operations first, SQL second.** Most questions map to 12 validated operations,
   which are easier for a 4B local model to fill correctly than free SQL and give
   statistically correct implementations (Welch, Wilson intervals, Holt-Winters backtests).
2. **Facts + placeholders for explanations.** Rather than asking the model to copy numbers
   (and hoping), it cites fact ids; the verifier renders exact values and prunes anything
   it cannot verify.
3. **Process-level sandbox, not a query filter.** DuckDB is powerful (file, HTTP, extension
   access), so a read-only filter is insufficient; every statement runs in a separate OS
   sandboxed process even after AST validation.
4. **Parquet as the canonical store.** Uploads of any format become immutable, hashed,
   versioned Parquet files; analyses pin the version ids they used.
5. **Process-per-query** costs ~100-300 ms per statement but gives a clean failure domain;
   a warm worker pool is a future optimisation.
6. **SQLite metadata** keeps the project runnable with zero services; models and
   migrations are database-agnostic.
7. **Local-first LLM** (Ollama, `qwen3:4b-instruct`) with JSON-schema constrained decoding;
   an OpenAI-compatible adapter exists for larger hosted models. No paid API is required.
8. **Server-built charts.** The model never emits Plotly JSON; a typed config is turned
   into a figure validated by Plotly's schema.
9. **SSE over WebSockets** for one-way progress streams; a pure-ASGI middleware marks them
   `no-transform` because the Next.js server otherwise gzip-buffers them (found in testing).
