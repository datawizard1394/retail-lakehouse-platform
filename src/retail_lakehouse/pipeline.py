"""Idempotent bronze, silver, and gold retail transformations."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from retail_lakehouse.io import (
    atomic_write_csv,
    atomic_write_json,
    fingerprint_files,
    read_csv,
    sha256_file,
)
from retail_lakehouse.quality import (
    DataQualityError,
    validate_silver_contracts,
    validate_source_contracts,
)

MONEY = Decimal("0.01")
SOURCE_TABLES = ("customers", "products", "orders", "order_items")


def _money(value: Decimal) -> str:
    return str(value.quantize(MONEY, rounding=ROUND_HALF_UP))


def _clean_text(value: str) -> str:
    return " ".join(value.strip().split())


def _record_hash(row: dict[str, str]) -> str:
    material = "\x1f".join(f"{key}={row[key]}" for key in sorted(row))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class RetailLakehousePipeline:
    """A dependency-free reference implementation of medallion processing."""

    def __init__(
        self,
        input_dir: Path,
        output_dir: Path,
        ingestion_timestamp: str = "2026-01-01T00:00:00Z",
    ) -> None:
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.ingestion_timestamp = ingestion_timestamp

    def run(self) -> dict[str, object]:
        source_paths = [self.input_dir / f"{table}.csv" for table in SOURCE_TABLES]
        missing = [str(path) for path in source_paths if not path.exists()]
        if missing:
            raise FileNotFoundError(f"Missing source files: {', '.join(missing)}")

        source_fingerprint = fingerprint_files(source_paths)
        run_id = source_fingerprint[:16]
        raw = {table: read_csv(self.input_dir / f"{table}.csv") for table in SOURCE_TABLES}

        source_report = validate_source_contracts(raw)
        if not source_report.passed:
            self._write_quality_report(source_report.as_dict(), run_id, "source")
            raise DataQualityError("Source data contract failed")

        bronze = self._build_bronze(raw, run_id)
        silver = self._build_silver(raw, run_id)
        silver_report = validate_silver_contracts(silver)
        self._write_quality_report(silver_report.as_dict(), run_id, "silver")
        if not silver_report.passed:
            raise DataQualityError("Silver data-quality contract failed")

        gold = self._build_gold(silver)
        self._write_layer("bronze", bronze)
        self._write_layer("silver", silver)
        self._write_layer("gold", gold)

        materialized_paths = [
            self.output_dir / layer / f"{table}.csv"
            for layer, tables in (("bronze", bronze), ("silver", silver), ("gold", gold))
            for table in tables
        ]
        completed_orders = [
            row for row in silver["orders"] if row["status"] == "COMPLETED"
        ]
        manifest: dict[str, object] = {
            "pipeline": "retail_lakehouse",
            "pipeline_version": 1,
            "synthetic": True,
            "run_id": run_id,
            "input_fingerprint": source_fingerprint,
            "ingestion_timestamp": self.ingestion_timestamp,
            "quality_gate": "PASSED",
            "row_counts": {
                layer: {table: len(rows) for table, rows in tables.items()}
                for layer, tables in (
                    ("bronze", bronze),
                    ("silver", silver),
                    ("gold", gold),
                )
            },
            "business_metrics": {
                "completed_orders": len(completed_orders),
                "completed_revenue": _money(
                    sum(
                        (Decimal(row["order_total"]) for row in completed_orders),
                        Decimal("0.00"),
                    )
                ),
                "active_customers": len(
                    {row["customer_id"] for row in completed_orders}
                ),
                "products_sold": len(gold["product_performance"]),
            },
            "output_checksums": {
                str(path.relative_to(self.output_dir)): sha256_file(path)
                for path in materialized_paths
            },
        }
        atomic_write_json(self.output_dir / "_meta" / "pipeline_manifest.json", manifest)
        return manifest

    def _write_quality_report(
        self,
        report: dict[str, object],
        run_id: str,
        stage: str,
    ) -> None:
        report = {**report, "run_id": run_id, "stage": stage, "synthetic": True}
        atomic_write_json(self.output_dir / "_meta" / "quality_report.json", report)

    def _build_bronze(
        self,
        raw: dict[str, list[dict[str, str]]],
        run_id: str,
    ) -> dict[str, list[dict[str, str]]]:
        bronze: dict[str, list[dict[str, str]]] = {}
        for table, rows in raw.items():
            bronze[table] = [
                {
                    **row,
                    "_source_file": f"{table}.csv",
                    "_ingested_at": self.ingestion_timestamp,
                    "_pipeline_run_id": run_id,
                    "_record_hash": _record_hash(row),
                }
                for row in rows
            ]
        return bronze

    def _build_silver(
        self,
        raw: dict[str, list[dict[str, str]]],
        run_id: str,
    ) -> dict[str, list[dict[str, str]]]:
        customers = [
            {
                "customer_id": _clean_text(row["customer_id"]).upper(),
                "first_name": _clean_text(row["first_name"]).title(),
                "last_name": _clean_text(row["last_name"]).title(),
                "email": _clean_text(row["email"]).lower(),
                "segment": _clean_text(row["segment"]).lower(),
                "joined_date": date.fromisoformat(row["joined_date"]).isoformat(),
                "country": _clean_text(row["country"]).upper(),
                "is_active": str(row["is_active"]).strip().lower(),
                "_pipeline_run_id": run_id,
            }
            for row in raw["customers"]
        ]
        products = [
            {
                "product_id": _clean_text(row["product_id"]).upper(),
                "product_name": _clean_text(row["product_name"]),
                "category": _clean_text(row["category"]),
                "unit_price": _money(Decimal(row["unit_price"])),
                "unit_cost": _money(Decimal(row["unit_cost"])),
                "is_active": str(row["is_active"]).strip().lower(),
                "_pipeline_run_id": run_id,
            }
            for row in raw["products"]
        ]
        orders = [
            {
                "order_id": _clean_text(row["order_id"]).upper(),
                "customer_id": _clean_text(row["customer_id"]).upper(),
                "order_date": date.fromisoformat(row["order_date"]).isoformat(),
                "status": _clean_text(row["status"]).upper(),
                "payment_method": _clean_text(row["payment_method"]).lower(),
                "order_total": _money(Decimal(row["order_total"])),
                "_pipeline_run_id": run_id,
            }
            for row in raw["orders"]
        ]
        order_items = [
            {
                "order_item_id": _clean_text(row["order_item_id"]).upper(),
                "order_id": _clean_text(row["order_id"]).upper(),
                "product_id": _clean_text(row["product_id"]).upper(),
                "quantity": str(int(row["quantity"])),
                "unit_price": _money(Decimal(row["unit_price"])),
                "discount_rate": str(Decimal(row["discount_rate"]).quantize(MONEY)),
                "line_total": _money(Decimal(row["line_total"])),
                "_pipeline_run_id": run_id,
            }
            for row in raw["order_items"]
        ]
        return {
            "customers": sorted(customers, key=lambda row: row["customer_id"]),
            "products": sorted(products, key=lambda row: row["product_id"]),
            "orders": sorted(orders, key=lambda row: row["order_id"]),
            "order_items": sorted(order_items, key=lambda row: row["order_item_id"]),
        }

    def _build_gold(
        self,
        silver: dict[str, list[dict[str, str]]],
    ) -> dict[str, list[dict[str, str]]]:
        customers = {row["customer_id"]: row for row in silver["customers"]}
        products = {row["product_id"]: row for row in silver["products"]}
        completed_orders = {
            row["order_id"]: row
            for row in silver["orders"]
            if row["status"] == "COMPLETED"
        }
        completed_items = [
            row for row in silver["order_items"] if row["order_id"] in completed_orders
        ]

        daily: dict[str, dict[str, object]] = defaultdict(
            lambda: {
                "orders": set(),
                "customers": set(),
                "units": 0,
                "revenue": Decimal("0.00"),
            }
        )
        for item in completed_items:
            order = completed_orders[item["order_id"]]
            bucket = daily[order["order_date"]]
            bucket["orders"].add(order["order_id"])  # type: ignore[union-attr]
            bucket["customers"].add(order["customer_id"])  # type: ignore[union-attr]
            bucket["units"] += int(item["quantity"])  # type: ignore[operator]
            bucket["revenue"] += Decimal(item["line_total"])  # type: ignore[operator]

        daily_sales: list[dict[str, str]] = []
        for sales_date, bucket in sorted(daily.items()):
            order_count = len(bucket["orders"])  # type: ignore[arg-type]
            revenue = bucket["revenue"]  # type: ignore[assignment]
            daily_sales.append(
                {
                    "sales_date": sales_date,
                    "net_revenue": _money(revenue),
                    "order_count": str(order_count),
                    "customer_count": str(len(bucket["customers"])),  # type: ignore[arg-type]
                    "units_sold": str(bucket["units"]),
                    "average_order_value": _money(revenue / order_count),
                }
            )

        product_buckets: dict[str, dict[str, object]] = defaultdict(
            lambda: {
                "orders": set(),
                "units": 0,
                "revenue": Decimal("0.00"),
                "cost": Decimal("0.00"),
            }
        )
        customer_buckets: dict[str, dict[str, object]] = defaultdict(
            lambda: {
                "orders": set(),
                "revenue": Decimal("0.00"),
                "dates": [],
            }
        )
        for item in completed_items:
            order = completed_orders[item["order_id"]]
            product = products[item["product_id"]]
            product_bucket = product_buckets[item["product_id"]]
            product_bucket["orders"].add(item["order_id"])  # type: ignore[union-attr]
            product_bucket["units"] += int(item["quantity"])  # type: ignore[operator]
            product_bucket["revenue"] += Decimal(item["line_total"])  # type: ignore[operator]
            product_bucket["cost"] += (  # type: ignore[operator]
                Decimal(product["unit_cost"]) * int(item["quantity"])
            )

            customer_bucket = customer_buckets[order["customer_id"]]
            customer_bucket["orders"].add(order["order_id"])  # type: ignore[union-attr]
            customer_bucket["revenue"] += Decimal(item["line_total"])  # type: ignore[operator]
            customer_bucket["dates"].append(order["order_date"])  # type: ignore[union-attr]

        product_performance: list[dict[str, str]] = []
        for product_id, bucket in sorted(product_buckets.items()):
            product = products[product_id]
            revenue = bucket["revenue"]  # type: ignore[assignment]
            cost = bucket["cost"]  # type: ignore[assignment]
            margin = revenue - cost
            product_performance.append(
                {
                    "product_id": product_id,
                    "product_name": product["product_name"],
                    "category": product["category"],
                    "order_count": str(len(bucket["orders"])),  # type: ignore[arg-type]
                    "units_sold": str(bucket["units"]),
                    "net_revenue": _money(revenue),
                    "gross_margin": _money(margin),
                    "gross_margin_pct": (
                        str((margin / revenue * 100).quantize(MONEY))
                        if revenue
                        else "0.00"
                    ),
                }
            )
        product_performance.sort(
            key=lambda row: (-Decimal(row["net_revenue"]), row["product_id"])
        )

        customer_360: list[dict[str, str]] = []
        for customer_id, bucket in sorted(customer_buckets.items()):
            customer = customers[customer_id]
            order_count = len(bucket["orders"])  # type: ignore[arg-type]
            revenue = bucket["revenue"]  # type: ignore[assignment]
            dates = bucket["dates"]  # type: ignore[assignment]
            customer_360.append(
                {
                    "customer_id": customer_id,
                    "customer_name": f"{customer['first_name']} {customer['last_name']}",
                    "segment": customer["segment"],
                    "country": customer["country"],
                    "lifetime_order_count": str(order_count),
                    "lifetime_revenue": _money(revenue),
                    "average_order_value": _money(revenue / order_count),
                    "first_order_date": min(dates),
                    "last_order_date": max(dates),
                }
            )
        customer_360.sort(
            key=lambda row: (-Decimal(row["lifetime_revenue"]), row["customer_id"])
        )

        return {
            "daily_sales": daily_sales,
            "product_performance": product_performance,
            "customer_360": customer_360,
        }

    def _write_layer(
        self,
        layer: str,
        tables: dict[str, list[dict[str, str]]],
    ) -> None:
        for table, rows in tables.items():
            if not rows:
                raise DataQualityError(f"{layer}.{table} unexpectedly produced no rows")
            atomic_write_csv(
                self.output_dir / layer / f"{table}.csv",
                rows,
                tuple(rows[0]),
            )
