"""Command-line interface for the portfolio demonstration."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from retail_lakehouse.generator import SyntheticConfig, generate_dataset
from retail_lakehouse.pipeline import RetailLakehousePipeline


def _size_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--seed", type=int, default=20260728)
    parser.add_argument("--customers", type=int, default=50)
    parser.add_argument("--products", type=int, default=20)
    parser.add_argument("--orders", type=int, default=200)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2025, 1, 1))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="retail-lakehouse",
        description="Run the local synthetic retail lakehouse portfolio demo.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Generate synthetic CSV sources")
    generate.add_argument("--output", type=Path, required=True)
    _size_arguments(generate)

    run = subparsers.add_parser("run", help="Build bronze, silver, and gold tables")
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)

    demo = subparsers.add_parser("demo", help="Generate sources and run the pipeline")
    demo.add_argument("--workspace", type=Path, required=True)
    _size_arguments(demo)

    quality = subparsers.add_parser("quality", help="Print a quality report")
    quality.add_argument("--report", type=Path, required=True)
    return parser


def _config(args: argparse.Namespace) -> SyntheticConfig:
    return SyntheticConfig(
        seed=args.seed,
        customers=args.customers,
        products=args.products,
        orders=args.orders,
        start_date=args.start_date,
        days=args.days,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "generate":
        result = generate_dataset(args.output, _config(args))
    elif args.command == "run":
        result = RetailLakehousePipeline(args.input, args.output).run()
    elif args.command == "demo":
        raw = args.workspace / "data" / "raw"
        warehouse = args.workspace / "warehouse"
        generate_dataset(raw, _config(args))
        result = RetailLakehousePipeline(raw, warehouse).run()
    else:
        result = json.loads(args.report.read_text(encoding="utf-8"))

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
