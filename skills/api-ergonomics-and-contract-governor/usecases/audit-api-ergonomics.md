# Use Case: Audit API Ergonomics & Contract Governance

> Adversarial review workflow for evaluating SDKs, CLIs, and internal boundaries against Microsoft TypeScript compiler rigor and Stripe DX standards.

## Step 1: Execute Automated Heuristic Scan

Run the zero-dependency contract guard against the source implementation:

```bash
npx anti-slop-engineering contract audit record.json --source src/client.ts --json
# or: python3 scripts/api_contract_guard.py audit record.json --source src/client.ts --json
```

---

## Step 2: Audit the Four Ergonomic Dimensions

1. **Pit of Success Defaults:**
   - Are timeouts configured by default (<= 10s)?
   - Are retries bounded and randomized with full jitter?
   - Is idempotency automatic or transparent for mutations?
2. **Illegal States Unrepresentable:**
   - Are multi-state objects modeled as tagged discriminated unions?
   - Are domain IDs nominally branded?
   - Are consecutive boolean parameters eliminated?
3. **Progressive Disclosure:**
   - Can a caller execute the 80% use case in a single readable line?
   - Are advanced options cleanly decoupled in optional secondary bags?
   - Is root namespace pollution prevented?
4. **RFC 9457 Problem Details:**
   - Do error classes expose standard `type`, `title`, `status`, `detail`, `instance`, and `code`?
   - Are `invalid_params` structured for machine parsing?
   - Is `retryable` explicitly exposed?

---

## Step 3: Issue Assessment Verdict

Emit an `ApiContractRecord` JSON file declaring `proceed`, `pause`, or `refuse` with revisit triggers and concrete remediation steps.
