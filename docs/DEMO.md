# Demo walkthrough

```bash
make setup && make install-web
make seed            # SYNTHETIC Lumen Commerce data
make dev-api         # terminal 1 (port 8111; needs Ollama with qwen3:4b-instruct for live answers)
make dev-web         # terminal 2 (port 3101)
```

1. **Dataset Explorer** (`/datasets`): pick `orders` → Overview shows 8 duplicate rows and
   the negative-quantity outliers; Columns → `revenue` histogram; Preview → search `P02`.
2. **Analysis Copilot** (`/workspace`): ask “Which plan has the highest churned rate?”.
   Watch the stages stream; open the inspector: Facts (verification checks, removed
   sentences), SQL (sandboxed statements), Trace (node timings, raw plan).
3. Ask “Show the monthly revenue trend by region” → line chart; open **Chart Studio**,
   switch to `stacked_bar`, save the view.
4. Ask “What will the weather be tomorrow?” → clarification instead of an answer.
5. **Export** a result card as HTML/Markdown/CSV.
6. **Query Console** (`/query`): run `DROP TABLE orders` or
   `SELECT * FROM read_csv('/etc/passwd')` to see the policy reject it; the audit log
   records both.
7. **Evaluation** (`/evaluation`): stored benchmark results.
