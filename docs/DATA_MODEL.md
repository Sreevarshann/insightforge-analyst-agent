# Data model

Metadata lives in SQLite (`var/insightforge.sqlite3`, migrations in
`backend/src/insightforge/migrations`). Analytical data lives in versioned Parquet files
(`var/datasets/<dataset_id>/v<n>.parquet`) and is only ever read through DuckDB.

| Table | Purpose | Key columns |
|---|---|---|
| `datasets` | Logical dataset | `table_name` (unique SQL identifier), `display_name`, `is_demo` |
| `dataset_versions` | Immutable upload | `version`, `source_format`, `sha256`, `storage_path`, `row_count`, `schema_json`, `profile_json` |
| `relationships` | Declared, validated join | left/right dataset + column, inferred `cardinality` |
| `analyses` | Reproducible analysis record | `question`, `status`, `plan_json` (raw plan, steps, attempts, errors, trace, LLM usage), `steps_json` (tables, facts, SQL, query ids), `charts_json`, `explanation`, `verification_json`, `dataset_versions`, `model_name`, `duration_ms`, `saved` |
| `query_log` | Audit of every SQL statement | `sql`, `origin` (agent/user), `accepted`, `rejection_reason`, `row_count`, `duration_ms`, `analysis_id` |

## Facts

Every operation returns facts: `{id, label, value, unit, source}` where `unit ∈ count,
currency, percent, ratio, number, date, pvalue, text` and `source` carries provenance
(group values, period, column, statistic). Facts are the only numbers an explanation may
cite.

## Synthetic demo data (SYNTHETIC — fictional "Lumen Commerce")

Generated deterministically by `insightforge.demo.generate` (seed 20251110):
`customers` (2,400), `subscriptions` (2,400), `orders` (≈3.5k incl. 8 planted duplicates
and 6 negative quantities), `products` (8). Planted patterns are documented in the
module docstring and used by the benchmark.
