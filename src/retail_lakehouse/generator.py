"""Deterministic synthetic retail dataset generator."""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from retail_lakehouse.io import atomic_write_csv, atomic_write_json, sha256_file

MONEY = Decimal("0.01")


@dataclass(frozen=True)
class SyntheticConfig:
    """Controls the size and repeatability of the generated demonstration data."""

    seed: int = 20260728
    customers: int = 50
    products: int = 20
    orders: int = 200
    max_items_per_order: int = 4
    start_date: date = date(2025, 1, 1)
    days: int = 30

    def validate(self) -> None:
        if min(self.customers, self.products, self.orders, self.days) < 1:
            raise ValueError("customers, products, orders, and days must be positive")
        if self.max_items_per_order < 1:
            raise ValueError("max_items_per_order must be positive")


FIRST_NAMES = (
    "Avery",
    "Jordan",
    "Morgan",
    "Riley",
    "Taylor",
    "Casey",
    "Drew",
    "Cameron",
    "Quinn",
    "Reese",
)
LAST_NAMES = (
    "Chen",
    "Patel",
    "Garcia",
    "Martin",
    "Kim",
    "Brown",
    "Singh",
    "Wilson",
    "Nguyen",
    "Clark",
)
CATEGORIES = ("Electronics", "Home", "Outdoors", "Office", "Wellness")
PAYMENT_METHODS = ("card", "digital_wallet", "gift_card")
SEGMENTS = ("consumer", "small_business", "enterprise")


def _money(value: Decimal) -> str:
    return str(value.quantize(MONEY, rounding=ROUND_HALF_UP))


def generate_dataset(output_dir: Path, config: SyntheticConfig) -> dict[str, object]:
    """Generate four referentially consistent source tables.

    The generator uses only a local pseudo-random number generator seeded by the
    caller. The same configuration produces byte-for-byte identical CSV files.
    All names, email addresses, purchases, and identifiers are fictional.
    """
    config.validate()
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(config.seed)

    customers: list[dict[str, str]] = []
    for index in range(1, config.customers + 1):
        first_name = rng.choice(FIRST_NAMES)
        last_name = rng.choice(LAST_NAMES)
        customers.append(
            {
                "customer_id": f"C{index:05d}",
                "first_name": first_name,
                "last_name": last_name,
                "email": f"{first_name}.{last_name}.{index}@example.test".lower(),
                "segment": rng.choices(SEGMENTS, weights=(75, 20, 5), k=1)[0],
                "joined_date": (
                    config.start_date - timedelta(days=rng.randint(1, 730))
                ).isoformat(),
                "country": "CA",
                "is_active": "true",
            }
        )

    products: list[dict[str, str]] = []
    product_prices: dict[str, Decimal] = {}
    for index in range(1, config.products + 1):
        product_id = f"P{index:04d}"
        category = CATEGORIES[(index - 1) % len(CATEGORIES)]
        unit_price = Decimal(rng.randint(1_500, 35_000)) / 100
        unit_cost = unit_price * Decimal(str(rng.uniform(0.42, 0.74)))
        product_prices[product_id] = unit_price.quantize(MONEY)
        products.append(
            {
                "product_id": product_id,
                "product_name": f"{category} Product {index:02d}",
                "category": category,
                "unit_price": _money(unit_price),
                "unit_cost": _money(unit_cost),
                "is_active": "true",
            }
        )

    orders: list[dict[str, str]] = []
    order_items: list[dict[str, str]] = []
    product_ids = list(product_prices)
    item_sequence = 1
    maximum_items = min(config.max_items_per_order, config.products)

    for index in range(1, config.orders + 1):
        order_id = f"O{index:06d}"
        customer_id = rng.choice(customers)["customer_id"]
        order_date = config.start_date + timedelta(days=rng.randrange(config.days))
        status = rng.choices(
            ("COMPLETED", "RETURNED", "CANCELLED"),
            weights=(91, 6, 3),
            k=1,
        )[0]
        selected_products = rng.sample(product_ids, rng.randint(1, maximum_items))
        order_total = Decimal("0.00")

        for product_id in selected_products:
            quantity = rng.randint(1, 4)
            discount_rate = Decimal(
                rng.choices(("0.00", "0.05", "0.10"), weights=(72, 18, 10), k=1)[0]
            )
            unit_price = product_prices[product_id]
            line_total = (
                unit_price * quantity * (Decimal("1.00") - discount_rate)
            ).quantize(MONEY, rounding=ROUND_HALF_UP)
            order_total += line_total
            order_items.append(
                {
                    "order_item_id": f"I{item_sequence:07d}",
                    "order_id": order_id,
                    "product_id": product_id,
                    "quantity": str(quantity),
                    "unit_price": _money(unit_price),
                    "discount_rate": str(discount_rate),
                    "line_total": _money(line_total),
                }
            )
            item_sequence += 1

        orders.append(
            {
                "order_id": order_id,
                "customer_id": customer_id,
                "order_date": order_date.isoformat(),
                "status": status,
                "payment_method": rng.choice(PAYMENT_METHODS),
                "order_total": _money(order_total),
            }
        )

    tables = {
        "customers": customers,
        "products": products,
        "orders": orders,
        "order_items": order_items,
    }
    for name, rows in tables.items():
        atomic_write_csv(output_dir / f"{name}.csv", rows, tuple(rows[0]))

    serialized_config = asdict(config)
    serialized_config["start_date"] = config.start_date.isoformat()
    checksums = {
        f"{name}.csv": sha256_file(output_dir / f"{name}.csv") for name in tables
    }
    manifest: dict[str, object] = {
        "dataset": "synthetic_retail_demo",
        "synthetic": True,
        "generator_version": 1,
        "config": serialized_config,
        "row_counts": {name: len(rows) for name, rows in tables.items()},
        "checksums": checksums,
    }
    atomic_write_json(output_dir / "generator_manifest.json", manifest)
    return manifest
