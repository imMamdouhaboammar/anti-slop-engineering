# Data Minimization & Mandatory Retention TTL

> The Apple Privacy Standard: Reject unnecessary data collection at the source, bind every column to an audited purpose, and enforce automated TTL garbage collection across all persistence layers.

## The Principle of Data Minimization

Collecting user data creates an ongoing operational liability. Every byte of stored personal information is susceptible to subpoena, insider threat, credential stuffing, and configuration leaks.

The most resilient defense is **not collecting the data in the first place**.

### The Minimization Hierarchy

Before creating a database column, payload attribute, or telemetry metric, apply the Minimization Hierarchy:

```text
1. Zero Collection: Solve the problem client-side (On-Device Intelligence)
       │
       ▼ (if server requires verification)
2. Zero-Knowledge / Boolean Assertion: Send boolean assertion (e.g. is_adult: true), NOT the underlying attribute (birthdate: 1994-05-12)
       │
       ▼ (if continuous attribute is required)
3. Coarse Bucketing: Truncate precision (e.g. country_code or geohash_4char instead of exact GPS latitude/longitude)
       │
       ▼ (if unique identifier is required)
4. Ephemeral Salted Pseudonym: Rotate pseudonyms daily; never persist hardware UDID or IDFA
```

---

## Precision Reduction Matrix

| Data Type | Prohibited Raw Format | Mandatory Minimized Replacement | Justification |
| --- | --- | --- | --- |
| **User Age** | `birth_date: "1990-04-12"` | `is_over_21: boolean` or `age_bracket: "25-34"` | Eliminates exact identity re-identification in data breaches |
| **Geolocation** | `lat: 37.774929, lng: -122.419416` (6 decimals, ~10cm) | `geohash: "9q8y"` (~20km) or `metro_area: "US-CA-SFO"` | Prevents stalking, routine tracking, and dwelling identification |
| **Client IP** | `ipv4: "198.51.100.42"` | `ipv4_subnet: "198.51.100.0/24"` (zero last octet) | Preserves regional routing diagnostics while removing individual endpoint attribution |
| **Device ID** | `idfa: "EA7583CD-..."` or `imei: "35... "` | Rotating Ephemeral Session Token (24h TTL) | Strictly adheres to Apple App Tracking Transparency |

---

## Purpose Binding & Purpose Specification

Data collected for one business purpose must never be repurposed for another without explicit user re-consent.

Every table, column, and pipeline interface must declare an explicit `PurposeBinding`:

```typescript
export type PurposeBinding =
  | "AUTHENTICATION"             // User login, password reset, session validation
  | "BILLING_TRANSACTION"        // Payment processing, tax invoicing, chargebacks
  | "LEGAL_AUDIT"                // Financial regulatory compliance (SOX, anti-money laundering)
  | "SECURITY_FRAUD_PREVENTION"  // Bot detection, brute-force mitigation, account takeover defense
  | "ANALYTICS_OPT_IN";          // Aggregated product improvement with explicit opt-in
```

### Purpose Enforcement Invariant
Queries attempting to join data across incompatible purpose boundaries (e.g., joining `SECURITY_FRAUD_PREVENTION` IP logs with `ANALYTICS_OPT_IN` feature engagement tables) are blocked at the query admission gate and reported as security violations.

---

## Mandatory Retention TTL & Automated Garbage Collection

**No user data table may exist without an explicit, automated deletion lifecycle.**

### Schema PR Checklist

1. Does the table define an explicit `retention_ttl_days`? (Maximum permissible default: 90 days; absolute ceiling: 730 days for financial records).
2. Is there an automated background pipeline responsible for executing the purge?
   - **Postgres:** Partitioned tables by month (`events_2026_03`) with automated `DROP TABLE` cron job.
   - **DynamoDB:** `TTL` attribute configured on the table definition.
   - **Redis / Key-Value:** `EXPIRE` / `SETEX` command invoked on every write.
   - **ClickHouse:** Table definition must include `TTL recorded_at + INTERVAL 90 DAY DELETE`.
3. If an engineer submits a pull request creating a table storing user identifiers without a retention TTL policy, the CI gate must fail with `UNBOUNDED_RETENTION_TABLE`.
