# Playbook: Agent-to-Agent Swarm Attention Budgeting

This playbook defines protocols for managing attention budgets and context window preservation across multi-agent swarms (e.g. Fable, Jev, EGM Goldfish Reviewers).

---

## 1. The Context Inflation Hazard

In autonomous swarms, a coordinator agent delegates subtasks to worker agents. When workers return verbose responses (reasoning traces, raw tool logs, full file contents), the coordinator context window experiences rapid token inflation. This results in:
1. **Attention Decay:** Later decisions forget initial architectural invariants.
2. **Blocker Obscuration:** Critical failure codes get buried in long status prose.
3. **Runaway Cost:** Exponential growth in multi-turn token consumption.

---

## 2. The TOON Swarm Compression Protocol

All worker subagents must communicate state using compact TOON envelopes:

```toon
[SubagentExecutionReport] (schema: 1.0)
fields: 6
  subagent_id: string
  task_slug: string
  outcome: enum(SUCCESS|BLOCKED|INCONCLUSIVE|FAILED)
  metrics: map[string, number] (duration_ms, tests_passed, tests_failed)
  terminal_blocker: optional[string]
  artifacts_written: list[N] of string
```

### Invariants:
1. **Summary Before Diffs:** A subagent must never return a full file diff unless requested. It returns file path and line modification count.
2. **Terminal Escalation:** If the subagent encountered a blocking decision (e.g. API credential missing, migration collision), it must report `outcome: BLOCKED` and include `terminal_blocker` as the final field.
3. **Zero Affordance Meta-Text:** Subagents must not emit greetings, apologies, or conversational closers to other agents.

---

## 3. Coordinator Pruning Gate

Before appending subagent output to the persistent conversation transcript:
1. Verify that `attention_guard` passes with zero blockers.
2. If `longest_wall_words > 60`, automatically reformat into concise bullet points.
3. Strip all opener wrappers and closer offers before storing to disk.
