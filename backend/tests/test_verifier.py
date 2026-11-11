from __future__ import annotations

from typing import Any

import pytest

from insightforge.verify.numbers import format_value, verify_explanation

FACTS: list[dict[str, Any]] = [
    {
        "id": "a1",
        "label": "sum(revenue) for region=East",
        "value": 15234.5,
        "unit": "currency",
        "source": {"group": {"region": "East"}},
    },
    {
        "id": "a2",
        "label": "sum(revenue) for region=West",
        "value": 9800.0,
        "unit": "currency",
        "source": {"group": {"region": "West"}},
    },
    {
        "id": "a3",
        "label": "share of total sum(revenue) for region=East",
        "value": 60.85,
        "unit": "percent",
        "source": {"group": {"region": "East"}},
    },
    {"id": "a4", "label": "rows analysed", "value": 1200, "unit": "count", "source": {}},
    {"id": "g1", "label": "Welch t-test p-value", "value": 0.21, "unit": "pvalue", "source": {}},
]


def test_placeholders_render_exact_values() -> None:
    v = verify_explanation("East generated {{a1}} in revenue, {{a3}} of the total.", FACTS)
    assert v.status == "verified"
    assert v.text == "East generated $15,234.50 in revenue, 60.9% of the total."
    assert v.cited_fact_ids == ["a1", "a3"]


def test_hallucinated_number_is_removed() -> None:
    v = verify_explanation("East generated {{a1}}. Revenue grew 37% year over year.", FACTS)
    assert v.status == "corrected"
    assert "37%" not in v.text and v.removed[0]["reason"].startswith("unverified number")


def test_raw_number_matching_a_fact_is_accepted() -> None:
    v = verify_explanation("The analysis covered 1,200 rows. East had 60.9% of revenue.", FACTS)
    assert v.status == "verified"


def test_raw_number_with_wrong_precision_rounding_is_rejected() -> None:
    v = verify_explanation("East had 62% of revenue.", FACTS)
    assert v.status == "abstained"


def test_unknown_fact_id_rejected() -> None:
    v = verify_explanation("Revenue was {{a99}}.", FACTS)
    assert v.status == "abstained" and "unknown fact" in v.removed[0]["reason"]


def test_group_mislabel_detected() -> None:
    v = verify_explanation("West generated {{a1}} in revenue.", FACTS)
    assert v.status == "abstained" and "belongs to" in v.removed[0]["reason"]


def test_percent_sign_on_currency_fact_rejected() -> None:
    v = verify_explanation("East share was {{a1}}%.", FACTS)
    assert "non-percent" in v.removed[0]["reason"]


def test_unsupported_significance_claim_rejected() -> None:
    v = verify_explanation("East is significantly higher than West ({{g1}}).", FACTS)
    assert v.status == "abstained" and "0.210" in v.removed[0]["reason"]


def test_negated_significance_is_allowed() -> None:
    v = verify_explanation("The difference is not statistically significant ({{g1}}).", FACTS)
    assert v.status == "verified" and "p = 0.210" in v.text


def test_significance_without_any_test_rejected() -> None:
    facts = [f for f in FACTS if f["unit"] != "pvalue"]
    v = verify_explanation("East is significantly larger.", facts)
    assert "without a significance test" in v.removed[0]["reason"]


@pytest.mark.parametrize(
    "phrase",
    [
        "Discounts cause repeat purchases.",
        "Higher discounts lead to more refunds.",
        "Churn is driven by price.",
    ],
)
def test_causal_language_rejected(phrase: str) -> None:
    assert verify_explanation(phrase, FACTS).status == "abstained"


def test_dates_and_years_from_labels_are_not_numbers() -> None:
    facts = [
        {
            "id": "t1",
            "label": "sum(revenue) in month 2025-03-01",
            "value": 10.0,
            "unit": "currency",
            "source": {"period": "2025-03-01"},
        }
    ]
    v = verify_explanation("In March 2025 (2025-03-01) revenue was {{t1}}.", facts)
    assert v.status == "verified"


def test_numbers_from_question_are_allowed() -> None:
    v = verify_explanation(
        "Looking at the top 5 regions, East leads with {{a1}}.",
        FACTS,
        question="top 5 regions by revenue",
    )
    assert v.status == "verified"


@pytest.mark.parametrize(
    ("value", "unit", "text"),
    [
        (1234.567, "currency", "$1,234.57"),
        (-5, "currency", "-$5.00"),
        (12.345, "percent", "12.3%"),
        (0.0004, "pvalue", "p < 0.001"),
        (0.0312, "pvalue", "p = 0.031"),
        (1234.0, "count", "1,234"),
        (0.5, "ratio", "0.500"),
        (None, "number", "n/a"),
    ],
)
def test_format_value(value: Any, unit: str, text: str) -> None:
    assert format_value(value, unit) == text
