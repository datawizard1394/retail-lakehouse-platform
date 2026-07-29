from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from retail_lakehouse.generator import SyntheticConfig, generate_dataset
from retail_lakehouse.io import sha256_file


class SyntheticGeneratorTests(unittest.TestCase):
    def test_same_seed_produces_byte_identical_sources(self) -> None:
        config = SyntheticConfig(seed=17, customers=12, products=8, orders=30)
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_path = Path(first)
            second_path = Path(second)
            first_manifest = generate_dataset(first_path, config)
            second_manifest = generate_dataset(second_path, config)

            self.assertEqual(first_manifest, second_manifest)
            for name in (
                "customers.csv",
                "products.csv",
                "orders.csv",
                "order_items.csv",
            ):
                self.assertEqual(
                    sha256_file(first_path / name),
                    sha256_file(second_path / name),
                )

    def test_generator_preserves_expected_cardinality(self) -> None:
        config = SyntheticConfig(seed=99, customers=7, products=5, orders=16)
        with tempfile.TemporaryDirectory() as directory:
            manifest = generate_dataset(Path(directory), config)

        self.assertEqual(manifest["row_counts"]["customers"], 7)
        self.assertEqual(manifest["row_counts"]["products"], 5)
        self.assertEqual(manifest["row_counts"]["orders"], 16)
        self.assertGreaterEqual(manifest["row_counts"]["order_items"], 16)
        self.assertTrue(manifest["synthetic"])

    def test_invalid_size_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SyntheticConfig(customers=0).validate()


if __name__ == "__main__":
    unittest.main()
