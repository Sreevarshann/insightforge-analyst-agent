# API

Base URL `http://127.0.0.1:8111/api` (proxied as `/api` by the web app). Interactive
OpenAPI docs: `/docs`.

| Method & path | Description |
|---|---|
| `GET /health` | Status, version, LLM provider |
| `GET /datasets` · `POST /datasets` (multipart `file`, optional `name`) | List / upload (one dataset per sheet or table) |
| `GET /datasets/{id}` · `DELETE /datasets/{id}` | Detail / delete (files removed) |
| `GET /datasets/{id}/profile?version=` | Cached real profile |
| `GET /datasets/{id}/preview?offset&limit&sort&order&search&version` | Locked-DuckDB preview |
| `GET/POST /datasets/{id}/versions` | Version history / upload new version |
| `GET/POST /relationships` · `DELETE /relationships/{id}` | Declared joins (validated on data) |
| `POST /query` `{sql, max_rows?}` | Validated + sandboxed read-only SQL (422 rejected, 400 execution error) |
| `GET /query/history` | Audit log |
| `GET /ops` · `POST /ops/run` | Operation JSON schemas / run one typed operation |
| `POST /analyses` `{question, dataset_ids?}` | Run the agent (blocking) |
| `POST /analyses/stream` | Same, as Server-Sent Events (`analysis`, `stage`, `plan`, `result`, `chart`, `explanation`, `done`, `error`) |
| `GET /analyses?saved=` · `GET /analyses/{id}` · `PATCH /analyses/{id}` `{saved?, title?}` | History / detail / save |
| `POST /analyses/{id}/charts/preview` · `PUT /analyses/{id}/charts` | Chart Studio render / save |
| `GET /analyses/{id}/report?format=md|html&download=` | Reproducible report |
| `GET /analyses/{id}/export.csv?step&table` | CSV of a result table |
| `GET /evaluation` | Latest stored benchmark reports |
