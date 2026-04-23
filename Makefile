.PHONY: install check test gen-all e2e

install:
	pip install -e ".[dev]"

check:
	python3 -m ruff check src tests examples
	python3 -m ruff format --check src tests examples

test:
	python3 -m pytest -q

# E2E: real @ath-protocol/server gateway + upstream; mock OAuth only.
# Requires Node 18+, pnpm, and typescript-sdk/ at repo root (clone ath-protocol/typescript-sdk).
e2e:
	bash -c 'set -e; pnpm -C typescript-sdk install && pnpm -C typescript-sdk run build; \
	  OAUTH_PORT=18100 GATEWAY_PORT=18101 UPSTREAM_PORT=18102 node scripts/e2e_gateway_stack.mjs & PID=$$!; \
	  trap "kill $$PID 2>/dev/null" EXIT; \
	  sleep 1; ATH_GATEWAY_URL=http://127.0.0.1:18101 python3 -m pytest tests/test_e2e.py -v'

gen-all:
	python3 scripts/gen_schema.py
