"""Local-first retail lakehouse portfolio demonstration."""

from retail_lakehouse.generator import SyntheticConfig, generate_dataset
from retail_lakehouse.pipeline import RetailLakehousePipeline

__all__ = ["RetailLakehousePipeline", "SyntheticConfig", "generate_dataset"]
__version__ = "0.1.0"

