"""Deterministic SYNTHETIC demo data for "Lumen Commerce", a fictional B2B SaaS + hardware seller.

Everything here is generated from a fixed seed. No real customers or companies are
represented. Planted, documented patterns (used by the evaluation benchmark, whose
expected answers are recomputed from these files with pandas, never hard-coded):

* West region grows fastest through 2025 (higher monthly growth multiplier).
* Starter-plan subscriptions churn more often than Growth / Scale.
* The "Nimbus Hub" product has an abnormally high refund rate.
* Higher discounts are mildly associated with customers placing repeat orders.
* Data-quality anomalies: ~1% missing regions in customers, a handful of exact duplicate
  order rows, a few negative quantities, untrimmed acquisition-channel strings.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20251110
START, END = pd.Timestamp("2024-01-01"), pd.Timestamp("2025-09-30")
REGIONS = ["North", "South", "East", "West"]
REGION_P = [0.22, 0.24, 0.30, 0.24]
SEGMENTS = ["SMB", "Mid-Market", "Enterprise"]
PLANS = {"Starter": 49.0, "Growth": 199.0, "Scale": 799.0}
PRODUCTS = [
    ("P01", "Lumen Sensor Kit", "Hardware", 129.0),
    ("P02", "Nimbus Hub", "Hardware", 349.0),
    ("P03", "Flux Gateway", "Hardware", 589.0),
    ("P04", "Pulse Analytics Add-on", "Software", 99.0),
    ("P05", "Atlas Integration Pack", "Software", 249.0),
    ("P06", "Priority Support (annual)", "Services", 1200.0),
    ("P07", "Onboarding Workshop", "Services", 650.0),
    ("P08", "Orbit Display", "Hardware", 219.0),
]


def generate(n_customers: int = 2400) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(SEED)
    days = (END - START).days

    # ---- customers
    signup = START + pd.to_timedelta(rng.integers(0, days - 30, n_customers), unit="D")
    region = rng.choice(REGIONS, n_customers, p=REGION_P).astype(object)
    segment = rng.choice(SEGMENTS, n_customers, p=[0.6, 0.3, 0.1])
    channel = rng.choice(
        ["Organic", "Paid Search", "Partner", "Outbound"], n_customers, p=[0.4, 0.3, 0.15, 0.15]
    ).astype(object)
    channel[rng.random(n_customers) < 0.03] = " Partner "  # untrimmed values (anomaly)
    region[rng.random(n_customers) < 0.01] = None  # missing regions (anomaly)
    customers = pd.DataFrame(
        {
            "customer_id": [f"C{i:05d}" for i in range(1, n_customers + 1)],
            "signup_date": signup.date,
            "region": region,
            "segment": segment,
            "acquisition_channel": channel,
            "company_size": np.where(
                segment == "Enterprise",
                rng.integers(500, 5000, n_customers),
                np.where(
                    segment == "Mid-Market",
                    rng.integers(50, 500, n_customers),
                    rng.integers(2, 50, n_customers),
                ),
            ),
        }
    )

    # ---- subscriptions (one per customer)
    plan = np.where(
        segment == "Enterprise",
        rng.choice(list(PLANS), n_customers, p=[0.05, 0.35, 0.6]),
        np.where(
            segment == "Mid-Market",
            rng.choice(list(PLANS), n_customers, p=[0.25, 0.55, 0.2]),
            rng.choice(list(PLANS), n_customers, p=[0.65, 0.3, 0.05]),
        ),
    )
    churn_p = np.select([plan == "Starter", plan == "Growth"], [0.34, 0.16], 0.08)
    churned = rng.random(n_customers) < churn_p
    tenure = rng.integers(30, 540, n_customers)
    end = pd.to_datetime(signup) + pd.to_timedelta(tenure, unit="D")
    end_date = np.where(churned & (end <= END), end.date, None)
    churned = churned & (end <= END)
    seats = np.maximum(
        1, (customers.company_size * rng.uniform(0.05, 0.3, n_customers)).astype(int)
    )
    mrr = np.array([PLANS[p] for p in plan]) + np.where(plan == "Scale", seats * 4.0, 0)
    subscriptions = pd.DataFrame(
        {
            "subscription_id": [f"S{i:05d}" for i in range(1, n_customers + 1)],
            "customer_id": customers.customer_id,
            "plan": plan,
            "start_date": signup.date,
            "end_date": end_date,
            "mrr": mrr.round(2),
            "churned": churned.astype(int),
        }
    )

    # ---- orders
    growth = {"North": 0.010, "South": 0.012, "East": 0.015, "West": 0.045}
    rows = []
    order_id = 1
    prod_idx = np.arange(len(PRODUCTS))
    prod_p = np.array([0.22, 0.14, 0.08, 0.18, 0.12, 0.06, 0.05, 0.15])
    for i in range(n_customers):
        cust_region = region[i] if region[i] is not None else rng.choice(REGIONS)
        # customers who get larger discounts come back slightly more often (planted association)
        base_disc = rng.choice([0.0, 0.05, 0.1, 0.15, 0.2], p=[0.35, 0.25, 0.2, 0.12, 0.08])
        months_active = max(1, int(((END - pd.Timestamp(signup[i])).days) / 30))
        lam = 0.12 + 0.9 * base_disc + (0.05 if segment[i] == "Enterprise" else 0)
        n_orders = 1 + rng.poisson(lam * months_active)
        for _ in range(min(n_orders, 40)):
            offset = int(rng.integers(0, max(1, (END - pd.Timestamp(signup[i])).days)))
            d = pd.Timestamp(signup[i]) + pd.Timedelta(days=offset)
            months_since = (d.year - START.year) * 12 + d.month - 1
            # thinning makes later months heavier in fast-growing regions
            if rng.random() > min(1.0, 0.35 * (1 + growth[cust_region]) ** months_since):
                continue
            p = int(rng.choice(prod_idx, p=prod_p))
            pid, _, _, price = PRODUCTS[p]
            qty = int(rng.integers(1, 6)) if PRODUCTS[p][2] == "Hardware" else 1
            disc = float(np.clip(base_disc + rng.normal(0, 0.02), 0, 0.4).round(3))
            revenue = round(qty * price * (1 - disc), 2)
            refund_p = 0.17 if pid == "P02" else 0.035
            refunded = int(rng.random() < refund_p)
            rows.append(
                (
                    f"O{order_id:06d}",
                    customers.customer_id[i],
                    pid,
                    d.date(),
                    cust_region,
                    qty,
                    price,
                    disc,
                    revenue,
                    refunded,
                    revenue if refunded else 0.0,
                )
            )
            order_id += 1
    orders = pd.DataFrame(
        rows,
        columns=[
            "order_id",
            "customer_id",
            "product_id",
            "order_date",
            "region",
            "quantity",
            "unit_price",
            "discount_pct",
            "revenue",
            "refunded",
            "refund_amount",
        ],
    )
    orders = orders.sort_values(["order_date", "order_id"]).reset_index(drop=True)
    bad = rng.choice(len(orders), 6, replace=False)
    orders.loc[bad, "quantity"] = -orders.loc[bad, "quantity"]  # negative quantities (anomaly)
    dupes = orders.sample(8, random_state=1)
    orders = (
        pd.concat([orders, dupes]).sort_values("order_date", kind="stable").reset_index(drop=True)
    )  # duplicates (anomaly)

    products = pd.DataFrame(
        PRODUCTS, columns=["product_id", "product_name", "category", "list_price"]
    )
    return {
        "customers": customers,
        "subscriptions": subscriptions,
        "orders": orders,
        "products": products,
    }


def write(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, df in generate().items():
        p = out_dir / f"{name}.csv"
        df.to_csv(p, index=False)
        paths.append(p)
    return paths


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Write the synthetic Lumen Commerce demo CSVs.")
    ap.add_argument("--out", type=Path, default=Path("../demo-data"))
    for p in write(ap.parse_args().out):
        print(p)
