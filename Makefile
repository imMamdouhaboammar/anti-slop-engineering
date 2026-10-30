.PHONY: test test-verbose guard sre lint check help

PYTHON ?= python3

help:
	@echo "Available targets:"
	@echo "  make test          Run unittest suite"
	@echo "  make test-verbose  Run unittest suite with verbose output"
	@echo "  make guard         Run diff_guard against HEAD"
	@echo "  make sre           Run sre_guard against HEAD"
	@echo "  make lint          Validate python syntax"
	@echo "  make check         Run lint + test + guard + sre"

test:
	$(PYTHON) -m unittest discover -s tests

test-verbose:
	$(PYTHON) -m unittest discover -s tests -v

guard:
	$(PYTHON) scripts/diff_guard.py --base HEAD

sre:
	$(PYTHON) scripts/sre_guard.py --base HEAD

lint:
	$(PYTHON) -m py_compile scripts/diff_guard.py scripts/sre_guard.py tests/test_diff_guard.py tests/test_sre_guard.py

check: lint test-verbose guard sre
