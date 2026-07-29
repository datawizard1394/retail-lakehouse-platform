"""Data-quality contracts and referential-integrity checks."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from decimal import Decimal


class DataQualityError(RuntimeError):
    """Raised when a blocking data-quality contract fails."""


@dataclass(frozen=True)
class QualityCheck:
    name: str
    passed: bool
    observed: int | str
    expectation: str
    severity: str = "ERROR"


@dataclass(frozen=True)
class QualityReport:
    checks: tuple[QualityCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed or check.severity != "ERROR" for check in self.checks)

    def as_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "summary": {
                "total": len(self.checks),
                "passed": sum(check.passed for check in self.checks),
                "failed": sum(not check.passed for check in self.checks),
            },
            "checks": [asdict(check) for check in self.checks],
        }


REQUIRED_COLUMNS: dict[str, set[str]] = {
    "customers": {
        "customer_id",
        "first_name",
        "last_name",
        "email",
        "segment",
        "joined_date",
        "country",
        "is_active",
    },
    "products": {
        "product_id",
        "product_name",
        "category",
        "unit_price",
        "unit_cost",
        "is_active",
    },
    "orders": {
        "order_id",
        "customer_id",
        "order_date",
        "status",
        "payment_method",
        "order_total",
    },
    "order_items": {
        "order_item_id",
        "order_id",
        "product_id",
        "quantity",
        "unit_price",
        "discount_rate",
        "line_total",
    },
}


def validate_source_contracts(
    tables: Mapping[str, list[dict[str, str]]],
) -> QualityReport:
    """Validate required tables and columns before transformation."""
    checks: list[QualityCheck] = []
    for table, columns in REQUIRED_COLUMNS.items():
        rows = tables.get(table, [])
        checks.append(
            QualityCheck(
                name=f"{table}.not_empty",
                passed=bool(rows),
                observed=len(rows),
                expectation="row_count > 0",
            )
        )
        observed_columns = set(rows[0]) if rows else set()
        missing = sorted(columns - observed_columns)
        checks.append(
            QualityCheck(
                name=f"{table}.required_columns",
                passed=not missing,
                observed=",".join(missing) if missing else "none",
                expectation="no required columns missing",
            )
        )
    return QualityReport(tuple(checks))


def _duplicate_count(values: Iterable[str]) -> int:
    counts = Counter(values)
    return sum(count - 1 for count in counts.values() if count > 1)


def validate_silver_contracts(
    tables: Mapping[str, list[dict[str, str]]],
) -> QualityReport:
    """Validate curated entities, keys, and business invariants."""
    customers = tables["customers"]
    products = tables["products"]
    orders = tables["orders"]
    items = tables["order_items"]
    checks: list[QualityCheck] = []

    for table_name, rows, key in (
        ("customers", customers, "customer_id"),
        ("products", products, "product_id"),
        ("orders", orders, "order_id"),
        ("order_items", items, "order_item_id"),
    ):
        duplicate_count = _duplicate_count(row[key] for row in rows)
        checks.append(
            QualityCheck(
                name=f"{table_name}.{key}.unique",
                passed=duplicate_count == 0,
                observed=duplicate_count,
                expectation="duplicate_count = 0",
            )
        )

    customer_ids = {row["customer_id"] for row in customers}
    product_ids = {row["product_id"] for row in products}
    order_ids = {row["order_id"] for row in orders}
    orphan_orders = sum(row["customer_id"] not in customer_ids for row in orders)
    orphan_item_orders = sum(row["order_id"] not in order_ids for row in items)
    orphan_item_products = sum(row["product_id"] not in product_ids for row in items)
    for name, count in (
        ("orders.customer_id.referential_integrity", orphan_orders),
        ("order_items.order_id.referential_integrity", orphan_item_orders),
        ("order_items.product_id.referential_integrity", orphan_item_products),
    ):
        checks.append(
            QualityCheck(
                name=name,
                passed=count == 0,
                observed=count,
                expectation="orphan_count = 0",
            )
        )

    invalid_emails = sum(
        "@" not in row["email"] or row["email"].endswith("@") for row in customers
    )
    checks.append(
        QualityCheck(
            name="customers.email.valid",
            passed=invalid_emails == 0,
            observed=invalid_emails,
            expectation="invalid_count = 0",
        )
    )

    invalid_statuses = sum(
        row["status"] not in {"COMPLETED", "RETURNED", "CANCELLED"} for row in orders
    )
    checks.append(
        QualityCheck(
            name="orders.status.accepted_values",
            passed=invalid_statuses == 0,
            observed=invalid_statuses,
            expectation="values in COMPLETED, RETURNED, CANCELLED",
        )
    )

    nonpositive_items = sum(
        int(row["quantity"]) <= 0
        or Decimal(row["unit_price"]) <= 0
        or Decimal(row["line_total"]) < 0
        for row in items
    )
    checks.append(
        QualityCheck(
            name="order_items.amounts.valid",
            passed=nonpositive_items == 0,
            observed=nonpositive_items,
            expectation="quantity and price positive; line total non-negative",
        )
    )

    item_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for row in items:
        item_totals[row["order_id"]] += Decimal(row["line_total"])
    mismatched_totals = sum(
        item_totals[row["order_id"]].quantize(Decimal("0.01"))
        != Decimal(row["order_total"]).quantize(Decimal("0.01"))
        for row in orders
        if row["order_id"] in item_totals
    )
    orders_without_items = sum(row["order_id"] not in item_totals for row in orders)
    checks.extend(
        (
            QualityCheck(
                name="orders.total.reconciles_to_items",
                passed=mismatched_totals == 0,
                observed=mismatched_totals,
                expectation="mismatch_count = 0",
            ),
            QualityCheck(
                name="orders.has_items",
                passed=orders_without_items == 0,
                observed=orders_without_items,
                expectation="orders_without_items = 0",
            ),
        )
    )
    return QualityReport(tuple(checks))
