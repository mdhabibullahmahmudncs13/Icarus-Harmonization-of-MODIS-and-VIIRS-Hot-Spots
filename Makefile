.PHONY: cache demo fixture golden validate test lint help

# Prefer the project venv (created with `uv venv .venv`) when it exists.
PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
RUFF ?= $(if $(wildcard .venv/bin/ruff),.venv/bin/ruff,ruff)

help:
	@echo "Targets:"
	@echo "  venv  - create .venv and install the dependencies"
	@echo "  cache   - download NASA FIRMS hot spots to cache/raw (Suomi-NPP first)"
	@echo "  fixture - write the offline demo detections to demo_fixtures/"
	@echo "  golden  - regenerate the committed Phase 2 golden fixtures"
	@echo "  validate- run the E1-E9 validation experiments, write the report"
	@echo "  demo    - run the API offline (OFFLINE=1) against demo_fixtures/"
	@echo "  test    - run the test suite"
	@echo "  lint  - run ruff"
	@echo ""
	@echo "  cache options: make cache ARGS=\"--products VIIRS_SNPP_SP --start 2012-01-01\""

venv:
	[ -d .venv ] || uv venv .venv
	VIRTUAL_ENV=.venv uv pip install duckdb pandas pyarrow requests fastapi uvicorn httpx2 jsonschema pytest ruff earthaccess pyhdf

cache:
	@$(PYTHON) -m src.acquire.firms $(ARGS)

fixture:
	@$(PYTHON) -m src.demo

golden:
	@$(PYTHON) -m tools.gen_golden --check || $(PYTHON) -m tools.gen_golden

validate:
	@$(PYTHON) -m tools.experiments

demo:
	OFFLINE=1 $(PYTHON) -m uvicorn src.api.main:app

test:
	$(PYTHON) -m pytest -q

lint:
	$(RUFF) check .
