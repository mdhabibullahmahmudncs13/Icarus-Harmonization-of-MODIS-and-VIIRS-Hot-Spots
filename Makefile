.PHONY: cache demo test lint help

help:
	@echo "Targets:"
	@echo "  cache - populate cache/ from NASA FIRMS"
	@echo "  demo  - run the API offline (OFFLINE=1) against demo_fixtures/"
	@echo "  test  - run the test suite"
	@echo "  lint  - run ruff"

cache:
	@echo "TODO: run src/acquire/*"

demo:
	OFFLINE=1 uvicorn src.api.main:app

test:
	pytest -q

lint:
	ruff check .