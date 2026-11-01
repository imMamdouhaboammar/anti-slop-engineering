.PHONY: test test-verbose guard sre lint check help build-rust build-go build-services test-rust test-go test-all check-all

PYTHON ?= python3

help:
	@echo "Available targets:"
	@echo "  make test            Run unittest suite"
	@echo "  make test-verbose    Run unittest suite with verbose output"
	@echo "  make test-rust       Run Rust engine test suite"
	@echo "  make test-go         Run Go SRE engine test suite"
	@echo "  make test-all        Run Python, Rust, and Go test suites"
	@echo "  make build-rust      Compile release binary for Rust engine"
	@echo "  make build-go        Compile binary for Go SRE engine"
	@echo "  make build-services  Compile both Rust and Go microservices"
	@echo "  make guard           Run diff_guard against HEAD"
	@echo "  make sre             Run sre_guard against HEAD"
	@echo "  make lint            Validate python syntax"
	@echo "  make check           Run lint + test + guard + sre"
	@echo "  make check-all       Run check + test-rust + test-go"

test:
	$(PYTHON) -m unittest discover -s tests

test-verbose:
	$(PYTHON) -m unittest discover -s tests -v

test-rust:
	cd services/anti-slop-rust && cargo test

test-go:
	cd services/toil-guard-go && go test -v ./...

build-rust:
	cd services/anti-slop-rust && cargo build --release

build-go:
	cd services/toil-guard-go && go build -o bin/toil-guard ./cmd/toil-guard

build-services: build-rust build-go

test-all: test-verbose test-rust test-go

lint:
	$(PYTHON) -m py_compile scripts/diff_guard.py scripts/sre_guard.py scripts/decision_guard.py tests/test_diff_guard.py tests/test_sre_guard.py tests/test_decision_guard.py

guard:
	$(PYTHON) scripts/diff_guard.py --base HEAD

sre:
	$(PYTHON) scripts/sre_guard.py --base HEAD

check: lint test-verbose guard sre

check-all: check test-rust test-go
