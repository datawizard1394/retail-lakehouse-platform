.PHONY: help install generate run demo compile test check lint quality clean

PYTHON ?= python3
SEED ?= 20260728

help:
	@echo "Retail Lakehouse Portfolio Demo"
	@echo "  make install   Install the package in editable mode"
	@echo "  make generate  Create deterministic synthetic source data"
	@echo "  make run       Build bronze, silver, and gold layers"
	@echo "  make demo      Generate data and run the complete pipeline"
	@echo "  make check     Compile and run the dependency-free test suite"
	@echo "  make test      Run the dependency-free unit test suite"
	@echo "  make lint      Run ruff when installed"
	@echo "  make quality   Print the latest quality report"
	@echo "  make clean     Remove generated local data and build artifacts"

install:
	$(PYTHON) -m pip install -e .

generate:
	PYTHONPATH=src $(PYTHON) -m retail_lakehouse.cli generate \
		--output data/raw --seed $(SEED) --customers 50 --products 20 --orders 200

run:
	PYTHONPATH=src $(PYTHON) -m retail_lakehouse.cli run \
		--input data/raw --output warehouse

demo:
	PYTHONPATH=src $(PYTHON) -m retail_lakehouse.cli demo \
		--workspace .demo --seed $(SEED) --customers 50 --products 20 --orders 200

compile:
	PYTHONPATH=src $(PYTHON) -m compileall -q src tests

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

check: compile test

lint:
	$(PYTHON) -m ruff check src tests

quality:
	PYTHONPATH=src $(PYTHON) -m retail_lakehouse.cli quality \
		--report warehouse/_meta/quality_report.json

clean:
	$(PYTHON) -c "import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ('data/raw', 'warehouse', '.demo', 'build', 'dist')]"
