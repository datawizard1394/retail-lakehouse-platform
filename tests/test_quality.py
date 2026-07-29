from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from retail_lakehouse.generator import SyntheticConfig, generate_dataset
from retail_lakehouse.pipeline import RetailLakehousePipeline
from retail_lakehouse.quality import DataQualityError


class QualityGateTests(unittest.TestCase):
    def test_orphan_customer_blocks_silver_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw"
            warehouse = root / "warehouse"
            generate_dataset(
                raw,
                SyntheticConfig(seed=8, customers=5, products=4, orders=10),
            )
            orders_path = raw / "orders.csv"
            with orders_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
                fieldnames = tuple(rows[0])
            rows[0]["customer_id"] = "C_DOES_NOT_EXIST"
            with orders_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            with self.assertRaises(DataQualityError):
                RetailLakehousePipeline(raw, warehouse).run()

            report = json.loads(
                (warehouse / "_meta" / "quality_report.json").read_text()
            )
            failed_names = {
                check["name"] for check in report["checks"] if not check["passed"]
            }
            self.assertIn(
                "orders.customer_id.referential_integrity",
                failed_names,
            )
            self.assertFalse((warehouse / "gold").exists())

    def test_missing_required_column_blocks_processing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw"
            warehouse = root / "warehouse"
            generate_dataset(
                raw,
                SyntheticConfig(seed=9, customers=5, products=4, orders=10),
            )
            customers_path = raw / "customers.csv"
            with customers_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            for row in rows:
                row.pop("email")
            with customers_path.open("w", encoding="utf-8", newline="") as handle:
                fieldnames = tuple(rows[0])
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            with self.assertRaises(DataQualityError):
                RetailLakehousePipeline(raw, warehouse).run()

            report = json.loads(
                (warehouse / "_meta" / "quality_report.json").read_text()
            )
            self.assertEqual(report["stage"], "source")
            self.assertFalse(report["passed"])


if __name__ == "__main__":
    unittest.main()

