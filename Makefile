.PHONY: test test-verbose test-cases guard sre lint oxlint check help build-rust build-go build-services test-rust test-go test-all check-all

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
	@echo "  make oxlint          Run oxlint linter"
	@echo "  make check           Run lint + test + guard + sre"
	@echo "  make check-all       Run check + test-rust + test-go"

test:
	$(PYTHON) -m unittest discover -s tests
	$(PYTHON) scripts/run_cases.py

test-verbose:
	$(PYTHON) -m unittest discover -s tests -v
	$(PYTHON) scripts/run_cases.py

test-cases:
	$(PYTHON) scripts/run_cases.py

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
	$(PYTHON) -m py_compile scripts/diff_guard.py scripts/sre_guard.py scripts/decision_guard.py scripts/root_fix_guard.py scripts/future_scale_guard.py scripts/paranoid_guard.py scripts/perf_guard.py scripts/rollout_guard.py scripts/simulation_guard.py scripts/privacy_guard.py scripts/api_contract_guard.py scripts/apple_craft_guard.py scripts/contrast_guard.py scripts/attention_guard.py scripts/demock_guard.py scripts/mandela_guard.py scripts/reduction_guard.py scripts/re0_handoff_guard.py scripts/backprop_guard.py scripts/system_drift_guard.py scripts/chroma_drift_guard.py scripts/house_tell_guard.py scripts/motion_runtime_guard.py scripts/asset_provenance_guard.py scripts/styleseed_guard.py scripts/tagore_guard.py scripts/audit_runner.py scripts/forensic_hunter.py scripts/exec_guard.py scripts/run_cases.py scripts/bump_version.py tests/test_diff_guard.py tests/test_sre_guard.py tests/test_decision_guard.py tests/test_root_fix_guard.py tests/test_future_scale_guard.py tests/test_paranoid_guard.py tests/test_perf_guard.py tests/test_rollout_guard.py tests/test_simulation_guard.py tests/test_privacy_guard.py tests/test_api_contract_guard.py tests/test_apple_craft_guard.py tests/test_contrast_guard.py tests/test_attention_guard.py tests/test_demock_guard.py tests/test_mandela_guard.py tests/test_reduction_guard.py tests/test_re0_handoff_guard.py tests/test_backprop_guard.py tests/test_system_drift_guard.py tests/test_chroma_drift_guard.py tests/test_house_tell_guard.py tests/test_motion_runtime_guard.py tests/test_asset_provenance_guard.py tests/test_styleseed_guard.py tests/test_tagore_guard.py tests/test_audit_runner.py tests/test_forensic_hunter.py tests/test_exec_guard.py tests/test_bump_version.py

oxlint:
	bunx oxlint

contrast:
	$(PYTHON) scripts/contrast_guard.py --selftest

audit:
	$(PYTHON) scripts/audit_runner.py audit

guard:
	$(PYTHON) scripts/diff_guard.py --base HEAD

sre:
	$(PYTHON) scripts/sre_guard.py --base HEAD

bump:
	$(PYTHON) scripts/bump_version.py $(PART)

check: lint test-verbose guard sre

check-all: check test-rust test-go
