# Boring Architecture Tribunal: Technology Selection & Design

Use this workflow when evaluating architectural options, selecting technologies, designing system components, or responding to "how should we build X?" questions.

## Architecture Design Procedure

### Step 1: Define the Actual Problem (Not the Assumed Solution)

Before evaluating any technology, extract the actual business constraint:

1. What is the **demonstrated** throughput requirement right now? (Measure; do not speculate.)
2. What is the **demonstrated** data volume today and in 12 months based on current growth?
3. What is the team's **operational capacity** — who will debug this at 3AM?
4. What is the rollback plan if this decision is wrong?

### Step 2: Run the Boring Technology Check

Apply this decision tree in strict order:

```
Can PostgreSQL solve this?
  YES → Use PostgreSQL.
  NO  → Can Redis solve this?
          YES → Use Redis.
          NO  → Can a background cron job solve this?
                  YES → Use a cron job.
                  NO  → Can a single-process queue (BullMQ, pg-boss) solve this?
                          YES → Use it.
                          NO  → You have proven the need for distributed infrastructure.
                                Now quantify the full operational cost before proceeding.
```

### Step 3: The Subtraction Mandate

Before adding any new service, process, or layer:
1. Can an existing service absorb this responsibility with a new endpoint?
2. Can a database index make the existing query fast enough to eliminate the caching layer?
3. Can the monolith be organized into a module instead of split into a service?
4. Can the feature ship without a new dependency?

### Step 4: Monolith-First Validation

Extract a service boundary only after all three gates pass:
- [ ] Independent deployability is **demonstrated necessary** (different teams, different release cadences, explicit SLA requirements)
- [ ] The data model **enforces the boundary** (zero shared tables; any JOIN across the boundary means the boundary is wrong)
- [ ] The team **operates distributed infrastructure today** (service mesh, distributed tracing, polyglot CI/CD — not aspirationally)

### Step 5: Record the Decision

Produce a `boring-adr.json` per the [Boring Architecture Playbook](../playbooks/boring-architecture-playbook.md) format. The record is not optional — if the decision is not worth documenting, it is not worth making.

## Architecture Review Output Format

```markdown
### Architecture Review: <Feature or System Name>

**Boring Option Selected:**
<One sentence: exact technology and why it is sufficient.>

**Rejected Options:**
| Option | Rejection Reason |
| --- | --- |
| Kafka | 12 events/min; a cron job + PostgreSQL queue is sufficient and debuggable |
| Elasticsearch | 500k docs; PostgreSQL tsvector with GIN index returns results in <50ms |

**Operational Cost Delta:**
<What new operational surface area is introduced by this decision? Who owns it at 3AM?>

**Rollback Plan:**
<How is this reversed if wrong, and how long does reversal take?>

**Verdict:**
`PROCEED` | `SIMPLIFY_FURTHER` | `REJECT_COMPLEXITY`
```
