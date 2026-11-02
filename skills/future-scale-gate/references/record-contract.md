# Future-Scale decision record

Records capture decisions that are costly to reverse, not every code change. Save JSON only when the architecture needs an auditable future operating envelope.

```json
{
  "goal": "Long-lived product objective",
  "horizon": "Product generations and workload diversity, not an invented user count",
  "scenarios": [
    {"id": "another-engine", "stress": "A second runtime consumes programs", "basis": "credible", "source": "Product roadmap", "failure_if_unprepared": "Public language semantics are tied to one interpreter"},
    {"id": "larger-programs", "stress": "Higher event volumes", "basis": "credible", "source": "Product scope", "failure_if_unprepared": "Memory and event scheduling assumptions become immovable"}
  ],
  "commitments": [
    {"decision": "Version semantic IR", "reversibility": "high", "failure_cost": "Breaking persisted or shared programs", "exit_path": "Versioned adapters and fixture migration"}
  ],
  "options": [
    {"name": "Embed semantics in the Python engine", "now_cost": "Small initial change", "future_cost": "Potential interpreter rewrite", "selected": false},
    {"name": "Separate semantic IR from execution", "now_cost": "Boundary tests and adapter", "future_cost": "Compatibility maintenance", "selected": true}
  ],
  "foundations": [
    {"boundary": "Compiler to engine", "choice_now": "Stable semantic IR", "future_capacity": "Add another backend without changing language semantics", "scenario_refs": ["another-engine"], "proof_ref": "second-backend"}
  ],
  "proofs": [
    {"id": "second-backend", "method": "Run golden program with a second engine", "status": "not_run", "evidence": "Proposed test, not a result"}
  ],
  "deferred": [
    {"capability": "Distributed execution", "trigger": "Verified single-host throughput/latency limit", "pathway": "Scheduler outside the stable execution interface"}
  ],
  "decision": {"action": "pause", "reason": "Evolution experiment not yet run", "revisit_when": "Second backend fixture passes"}
}
```

### Rules

- `decision.action`: `proceed`, `pause`, or `stop`; always explain `reason` and `revisit_when`.
- `basis`: `observed`, `credible`, or `speculative`. Plausible future workloads are not present measurements. The checker cannot validate source truth.
- `reversibility`: `low`, `medium`, or `high`. For `medium` and `high` commitments, `proceed` requires an `exit_path`.
- A `proceed` record needs at least one source-backed future scenario with a non-speculative basis, two distinct architecture alternatives with one selected **or** one viable option plus `sole_option_reason`, a named foundational boundary, a referenced completed proof, and a recorded deferred-work list (which may be empty). Do not invent a second stress or choice to satisfy a quota.
- Foundation `scenario_refs` use `scenarios[].id`; `proof_ref` uses `proofs[].id`. `proceed` rejects references to failed or unrun proofs.
- For `pause` and `stop`, a goal and explicit decision are sufficient; do not fabricate fields to satisfy `proceed` checks. Record missing evidence honestly in `reason`/`revisit_when`.
- The checklist validates **record completeness only**. It cannot confirm a future stress is credible, an experiment actually happened, an option is safe, or a rollout is authorized.

```bash
python3 scripts/future_scale_guard.py audit record.json --json
```

Exit `0` structurally complete, `2` incomplete, `1` invalid JSON/I/O. No production actions are executed.
