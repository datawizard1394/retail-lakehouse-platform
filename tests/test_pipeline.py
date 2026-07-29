from __future__ import annotations

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from retail_lakehouse.generator import SyntheticConfig, generate_dataset
from retail_lakehouse.io import read_csv
from retail_lakehouse.pipeline import RetailLakehousePipeline


class RetailLakehousePipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        root = Path(self.temporary_directory.name)
        self.raw = root / "raw"
        self.warehouse = root / "warehouse"
        generate_dataset(
            self.raw,
            SyntheticConfig(seed=4242, customers=20, products=10, orders=75),
        )

    def test_pipeline_builds_all_medallion_layers(self) -> None:
        manifest = RetailLakehousePipeline(self.raw, self.warehouse).run()

        for layer, tables in (
            ("bronze", ("customers", "products", "orders", "order_items")),
            ("silver", ("customers", "products", "orders", "order_items")),
            ("gold", ("daily_sales", "product_performance", "customer_360")),
        ):
            for table in tables:
                self.assertTrue((self.warehouse / layer / f"{table}.csv").exists())

        self.assertEqual(manifest["quality_gate"], "PASSED")
        self.assertEqual(manifest["row_counts"]["silver"]["orders"], 75)
        quality = json.loads(
            (self.warehouse / "_meta" / "quality_report.json").read_text()
        )
        self.assertTrue(quality["passed"])
        self.assertEqual(quality["summary"]["failed"], 0)

    def test_gold_revenue_reconciles_to_completed_orders(self) -> None:
        manifest = RetailLakehousePipeline(self.raw, self.warehouse).run()
        daily_sales = read_csv(self.warehouse / "gold" / "daily_sales.csv")
        gold_revenue = sum(
            (Decimal(row["net_revenue"]) for row in daily_sales),
            Decimal("0.00"),
        )

        self.assertEqual(
            gold_revenue.quantize(Decimal("0.01")),
            Decimal(manifest["business_metrics"]["completed_revenue"]),
        )

    def test_rerun_is_idempotent(self) -> None:
        pipeline = RetailLakehousePipeline(self.raw, self.warehouse)
        first = pipeline.run()
        first_manifest_bytes = (
            self.warehouse / "_meta" / "pipeline_manifest.json"
        ).read_bytes()
        second = pipeline.run()
        second_manifest_bytes = (
            self.warehouse / "_meta" / "pipeline_manifest.json"
        ).read_bytes()

        self.assertEqual(first, second)
        self.assertEqual(first_manifest_bytes, second_manifest_bytes)
        self.assertEqual(first["output_checksums"], second["output_checksums"])

    def test_missing_source_table_fails_fast(self) -> None:
        (self.raw / "products.csv").unlink()
        with self.assertRaises(FileNotFoundError):
            RetailLakehousePipeline(self.raw, self.warehouse).run()


if __name__ == "__main__":
    unittest.main()

