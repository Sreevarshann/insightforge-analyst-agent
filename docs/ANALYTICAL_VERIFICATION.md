# Analytical verification

**Goal:** no number reaches the user unless it was computed.

## How numbers flow

1. Typed operations / sandboxed SQL produce result tables **and facts**
   (`{id, label, value, unit, source}`), e.g. `a3 = share of total sum(revenue) for region=East`.
2. The explainer LLM sees only fact ids, labels and formatted values. It must write numbers as
   `{{a3}}` placeholders (`agent/prompts.py: EXPLAIN_SYSTEM`).
3. `verify/numbers.py` checks the draft sentence by sentence and **removes** any sentence that:
   - cites an unknown fact id,
   - contains a raw number that does not match a fact within its displayed precision
     (dates/years, numbers in cited labels and numbers in the question are exempt),
   - puts `%` on a non-percent fact or `$` on a non-currency fact,
   - cites a group-specific fact while naming a *different* group (e.g. "West … {{East fact}}"),
   - claims significance without a p-value fact, or when the smallest p-value ≥ 0.05
     (negations such as "not significant" are allowed),
   - uses causal language ("causes", "drives", "leads to", "due to", …).
4. Placeholders are replaced with exactly formatted computed values.
5. Status: `verified` (nothing removed), `corrected` (some sentences removed), `abstained`
   (nothing verifiable left → deterministic summary of computed facts). The draft, every
   removed sentence and the reason are stored with the analysis and shown in the UI.

Headlines must contain no digits; otherwise the step purpose is used.

## Observed with the real local model (qwen3:4b-instruct, 2026-11-11)

| Question | Status | What the verifier did |
|---|---|---|
| Which region has the highest churn rate? | verified | All cited numbers were placeholders that resolved to the right group. |
| What is the total revenue by region? | corrected | Kept a raw `$15,742.54` (matches the computed total); removed "All shares add up to 100%." (no 100% fact exists). |

## Limitations

* The verifier checks **numbers, units, group labels, significance and causal wording**. It
  cannot verify arbitrary qualitative statements — in the churn run above the model added
  "Data for all regions is complete…", which is not checked. The UI therefore always shows
  the computed tables and facts next to the prose.
* Group-label checking only applies to facts that carry group metadata.
* A raw number that coincidentally equals some unrelated fact would pass the number check.
