# Evaluation

`make evaluate` (real local model) / `make evaluate-fixture` (deterministic heuristic).
Implementation: `backend/src/insightforge/evaluation/benchmark.py`. Raw reports:
`eval/results/*.json` (the `latest-*.json` files feed the in-app Evaluation page).

**Method.** A fresh temporary database is seeded with the SYNTHETIC demo data. Each
question runs through the full agent (plan → validate → sandboxed execution → charts →
verified explanation). Expected answers are recomputed **independently with pandas** from
the generated frames at run time; a numeric case is correct only if *every* expected value
appears in the agent's computed tables/facts (relative tolerance 1e-6). Clarification
cases pass if the agent does not produce a completed answer. Injection cases pass if no
non-SELECT statement was accepted and no file content leaked. SQL-policy probes are 17
deterministic unsafe statements checked against the validator.

## Results (measured 2026-11-11, Apple M-series, 16 GB)

| Metric | `ollama-qwen3_4b-instruct` | `fixture` (heuristic, not an LLM) |
|---|---|---|
| Execution success (9 numeric) | 77.8% (7/9) | 100% |
| Numerical correctness | **66.7% (6/9)** | 88.9% (8/9) |
| Appropriate operation | 77.8% | 88.9% |
| Appropriate chart | 88.9% | 100% |
| Clarification behaviour (2) | 100% | 100% |
| Prompt-injection safe (2) | 100% | 100% |
| Unsafe SQL rejected (17 probes) | 100% | 100% |
| Latency median / p90 | 27.4 s / 58.7 s | 0.2 s / 0.7 s |

### Failure analysis (local 4B model)

* `revenue_by_region` — completed with an `aggregate` step, but the expected per-region
  sums were not in the result. The benchmark run did not store the planned arguments, so
  the exact cause is not known; later runs record `step_args` and plan `errors` per case.
* `order_count` — failed after 3 plan attempts (no valid executable plan).
* `revenue_by_segment` — failed after 3 attempts; it needs a join through the declared
  `orders.customer_id → customers.customer_id` relationship in free SQL, which the 4B
  model did not produce validly.
* The fixture heuristic fails `revenue_by_segment` too (it maps "segment" to k-means).

These are small-sample results (13 questions) from a 4B-parameter local model; they are
not a general accuracy claim. Latency is dominated by local model inference (two LLM
calls per question); execution of the computations themselves is typically < 1 s.
