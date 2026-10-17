.PHONY: test test-verbose guard lint check help

PYTHON ?= python3

help:
	@echo "Available targets:"
	@echo "  make test          Run unittest suite"
	@echo "  make test-verbose  Run unittest suite with verbose output"
	@echo "  make guard         Run diff_guard against HEAD"
	@echo "  make lint          Validate python syntax"
	@echo "  make check         Run lint + test + guard"

test:
	$(PYTHON) -m unittest discover -s tests

test-verbose:
	$(PYTHON) -m unittest discover -s tests -v

guard:
	$(PYTHON) scripts/diff_guard.py --base HEAD

lint:
	$(PYTHON) -m py_compile scripts/diff_guard.py tests/test_diff_guard.py

check: lint test-verbose guard
