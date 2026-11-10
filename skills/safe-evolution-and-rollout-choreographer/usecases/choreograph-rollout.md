# Choreograph Rollout: Safe Deployment & Shadow Launch Workflow

Use this workflow when planning a rolling deployment, enabling a critical feature path, or setting up dark launch shadow execution.

## Step-by-Step Procedure

### 1. Conduct Coexistence Pre-Mortem
1. Identify fleet version skew: determine how long version $N$ and version $N+1$ will coexist in production (e.g. 4-hour rolling deploy across 1,000 pods).
2. Audit cross-pod communication: if pod $N+1$ writes a payload to cache, message bus, or DB, prove that pod $N$ can deserialize it without panics.
3. Check mobile app tail: determine the oldest active client version ($N-k$) still making API calls.

### 2. Configure Feature Flag with Instant Kill-Switch
1. Declare flag definition conforming to the contract:
   - Unique snake_case name (e.g. `checkout_v2_fast_path`).
   - Owner email and link to design spec.
   - ISO creation date and hard expiration date ($\le 90$ days).
   - Link to demolition issue/ticket.
2. Wire sub-second in-memory push invalidation for the kill-switch:
   ```typescript
   if (featureFlags.isEnabled("checkout_v2_fast_path", userContext)) {
     return executeV2Path(input);
   }
   return executeLegacyPath(input);
   ```
3. Test kill-switch toggle locally and in staging to verify $< 1\text{s}$ propagation time.

### 3. Establish Dark Launch & Shadow Mirroring
1. If the change alters an algorithmic or high-throughput read path, enable shadow mode before live traffic exposure.
2. Decouple shadow execution from the user thread:
   - Use asynchronous fire-and-forget or edge proxy mirroring.
   - User response returns immediately with zero added latency.
3. Enforce side-effect fencing:
   - Ensure all write sinks, persistent mutations, and external notification APIs are mocked, stubbed, or sandboxed.
4. Run semantic diffing to verify output parity across at least $100,000$ requests with $< 0.001\%$ mismatch rate.

### 4. Execute Multi-Tier Canary Ramp
1. **Tier 1 (1%):** Route 1% of users via deterministic hash (`hash(user_id) % 100 < 1`). Bake for 2 hours.
2. **Tier 2 (5%):** Expand to 5%. Monitor database connection saturation and CPU. Bake for 4 hours.
3. **Tier 3 (25%):** Expand to 25%. Monitor multi-region cache hit ratios. Bake for 12 hours.
4. **Tier 4 (50%):** Expand to 50%. Endure diurnal peak load. Bake for 24 hours.
5. **Tier 5 (100%):** Full rollout across all regions.

### 5. Automated SLO Circuit Breakers
1. Wire automated canary analysis (ACA) to error budget burn rates.
2. If error rate increases by $> 0.05\%$ or p99 latency degrades by $> 10\%$, immediately trip the kill-switch.

### 6. Audit & Record Verification
Save the rollout choreography record and audit:
```bash
python3 scripts/rollout_guard.py audit rollout-record.json --json
```
Proceed only when audit returns `verdict.status == "proceed"`.
