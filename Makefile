.PHONY: install check test gen-all

install:
	pip install -e ".[dev]"

check:
	python3 -m ruff check src tests examples
	python3 -m ruff format --check src tests examples

test:
	python3 -m pytest -q

gen-all:
	python3 scripts/gen_schema.py
