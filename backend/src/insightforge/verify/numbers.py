"""Numerical verification of model-written explanations.

Contract given to the model: every number must be written as a ``{{fact_id}}`` placeholder
for a computed fact. The verifier then

1. substitutes placeholders with formatted computed values (so cited numbers are exact),
2. rejects unknown fact ids,
3. checks every *other* numeric token against the facts (with display-precision tolerance)
   or an allow-list of non-quantitative context (years/dates in labels, the question),
4. checks percent / currency signs against fact units,
5. checks that a sentence citing a group-specific fact does not name a different group,
6. rejects significance claims not backed by a p-value fact < 0.05,
7. rejects causal language (the operations measure association, not causation).

Sentences that fail are removed and reported; if nothing verifiable remains the explainer
abstains and falls back to a deterministic summary.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z]+\d+)\s*\}\}")
NUMBER = re.compile(r"(?<![\w.])[-+]?\$?\d[\d,]*(?:\.\d+)?%?")
DATE_LIKE = re.compile(r"\b\d{4}-\d{2}(?:-\d{2})?\b|\bQ[1-4]\b|\b(?:19|20)\d{2}\b")
SIGNIFICANCE = re.compile(r"\bstatistically significant|\bsignificant(?:ly)?\b", re.IGNORECASE)
INSIGNIFICANT = re.compile(r"\b(?:not|no|non-?)\s*(?:statistically\s+)?significant", re.IGNORECASE)
CAUSAL = re.compile(
    r"\b(?:causes?|caused|causing|leads? to|led to|drives?|driven by|driving|results? in|resulted in|because of|due to)\b",
    re.IGNORECASE,
)
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z{\"'(])")


def format_value(value: Any, unit: str) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, str):
        return value
    v = float(value)
    if math.isnan(v):
        return "n/a"
    match unit:
        case "currency":
            return f"-${abs(v):,.2f}" if v < 0 else f"${v:,.2f}"
        case "percent":
            return f"{v:,.1f}%"
        case "pvalue":
            return "p < 0.001" if v < 0.001 else f"p = {v:.3f}"
        case "count":
            return f"{round(v):,}"
        case "ratio":
            return f"{v:.3f}"
        case _:
            return f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.2f}".rstrip("0").rstrip(".")


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class Verification:
    status: str  # verified | corrected | abstained
    text: str
    checks: list[Check] = field(default_factory=list)
    removed: list[dict[str, str]] = field(default_factory=list)
    cited_fact_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "checks": [c.__dict__ for c in self.checks],
            "removed_sentences": self.removed,
            "cited_fact_ids": self.cited_fact_ids,
        }


def _num(token: str) -> float | None:
    t = token.replace("$", "").replace(",", "").rstrip("%")
    try:
        return float(t)
    except ValueError:
        return None


def _decimals(token: str) -> int:
    t = token.rstrip("%")
    return len(t.split(".")[1]) if "." in t else 0


def _matches_fact(token: str, facts: list[dict[str, Any]]) -> bool:
    v = _num(token)
    if v is None:
        return False
    is_pct = token.endswith("%")
    tol = 0.5 * 10 ** (-_decimals(token)) + 1e-9
    for f in facts:
        fv = f.get("value")
        if not isinstance(fv, (int, float)) or isinstance(fv, bool):
            continue
        if is_pct and f["unit"] != "percent":
            continue
        candidates = [float(fv)]
        if f["unit"] == "ratio":
            candidates.append(float(fv) * 100)
        if any(abs(abs(c) - abs(v)) <= max(tol, 1e-9 * abs(c)) for c in candidates):
            return True
    return False


def _group_values(f: dict[str, Any]) -> set[str]:
    g = f.get("source", {}).get("group")
    if isinstance(g, dict):
        return {str(x) for x in g.values() if x is not None}
    if g is not None:
        return {str(g)}
    return set()


def verify_explanation(
    draft: str, facts: list[dict[str, Any]], *, question: str = ""
) -> Verification:
    by_id = {f["id"]: f for f in facts}
    min_p = min(
        (
            f["value"]
            for f in facts
            if f["unit"] == "pvalue" and isinstance(f["value"], (int, float))
        ),
        default=None,
    )
    all_groups = set().union(*(_group_values(f) for f in facts)) if facts else set()
    allowed_numbers = {m.group(0) for m in NUMBER.finditer(question)}
    checks: list[Check] = []
    kept: list[str] = []
    removed: list[dict[str, str]] = []
    cited: list[str] = []

    for sentence in (s.strip() for s in SENTENCE_SPLIT.split(draft.strip()) if s.strip()):
        problems: list[str] = []
        ids = PLACEHOLDER.findall(sentence)
        for fid in ids:
            if fid not in by_id:
                problems.append(f"cites unknown fact {fid}")
        known = [by_id[i] for i in ids if i in by_id]
        # unit signs adjacent to placeholders
        for m in re.finditer(r"(\$?)\{\{\s*([A-Za-z]+\d+)\s*\}\}(%?)", sentence):
            f = by_id.get(m.group(2))
            if f and m.group(3) and f["unit"] != "percent":
                problems.append(f"'%' used with non-percent fact {f['id']}")
            if f and m.group(1) and f["unit"] != "currency":
                problems.append(f"'$' used with non-currency fact {f['id']}")
        # raw numbers outside placeholders
        stripped = PLACEHOLDER.sub(" ", sentence)
        label_context = " ".join(f["label"] for f in known)
        for m in NUMBER.finditer(DATE_LIKE.sub(" ", stripped)):
            tok = m.group(0).strip()
            if tok in allowed_numbers or tok.lstrip("$") in label_context:
                continue
            if _matches_fact(tok, facts):
                continue
            problems.append(f"unverified number '{tok}'")
        # group labels: a sentence citing a group fact must not name only other groups
        for f in known:
            groups = _group_values(f)
            if not groups:
                continue
            mentioned = {g for g in all_groups if re.search(rf"\b{re.escape(g)}\b", sentence)}
            if mentioned and not (mentioned & groups):
                problems.append(
                    f"fact {f['id']} belongs to {sorted(groups)} but sentence names {sorted(mentioned)}"
                )
        if SIGNIFICANCE.search(sentence) and not INSIGNIFICANT.search(sentence):
            if min_p is None:
                problems.append("claims significance without a significance test")
            elif min_p >= 0.05:
                problems.append(f"claims significance but smallest p-value is {min_p:.3f}")
        if CAUSAL.search(sentence):
            problems.append("uses causal language; analysis shows association only")
        if problems:
            removed.append({"sentence": sentence, "reason": "; ".join(problems)})
        else:
            kept.append(sentence)
            cited.extend(i for i in ids if i not in cited)

    checks.append(
        Check("placeholders_resolve", not any("unknown fact" in r["reason"] for r in removed))
    )
    checks.append(
        Check("numbers_match_facts", not any("unverified number" in r["reason"] for r in removed))
    )
    checks.append(
        Check("units_consistent", not any("used with non-" in r["reason"] for r in removed))
    )
    checks.append(
        Check("group_labels_consistent", not any("belongs to" in r["reason"] for r in removed))
    )
    checks.append(
        Check("significance_supported", not any("significance" in r["reason"] for r in removed))
    )
    checks.append(Check("no_causal_claims", not any("causal" in r["reason"] for r in removed)))

    text = " ".join(kept)
    text = PLACEHOLDER.sub(
        lambda m: format_value(by_id[m.group(1)]["value"], by_id[m.group(1)]["unit"]), text
    )
    text = re.sub(r"\$\$", "$", text).replace("%%", "%")
    status = "verified" if not removed else ("corrected" if kept else "abstained")
    return Verification(
        status=status, text=text, checks=checks, removed=removed, cited_fact_ids=cited
    )
