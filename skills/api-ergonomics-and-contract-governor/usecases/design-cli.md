# Use Case: Design an Ergonomic CLI Tool

> Step-by-step workflow for designing developer-facing CLI interfaces with Pit of Success defaults, progressive disclosure, and RFC 9457 error output.

## Step 1: Enforce Zero-Config Pit-of-Success Defaults

1. Running the CLI without flags should execute the most common, safest local workflow (e.g. auditing current workspace against `HEAD`).
2. Provide sensible defaults for paths, output formats, and concurrency limits.
3. Automatically detect interactive TTY vs non-interactive CI/CD pipe and format accordingly.

---

## Step 2: Structure Progressive Flag Disclosure

1. Top-level commands for common verbs: `audit`, `init`, `run`, `verify`.
2. Advanced tuning flags tucked behind optional parameters: `--json`, `--verbose`, `--timeout`, `--concurrency`.
3. Reject conflicting flag combinations with clear explanatory errors during argument parsing (e.g. `--all` and `--file <path>` cannot be combined).

---

## Step 3: Implement RFC 9457 Structured Error Output

When `--json` is active or in headless automation, errors must follow RFC 9457 Problem Details:

```json
{
  "type": "https://cli.platform.example.com/errors/invalid_arguments",
  "title": "Invalid Command Arguments",
  "status": 400,
  "code": "conflicting_flags",
  "detail": "Cannot specify both --watch and --dry-run simultaneously.",
  "instance": "urn:cli:command:audit",
  "suggested_action": "Omit --watch when running in dry-run mode.",
  "invalid_params": [
    { "name": "--watch", "reason": "Incompatible with --dry-run" }
  ]
}
```

---

## Step 4: Standardize Exit Codes

| Exit Code | Semantics | Output Format |
| --- | --- | --- |
| `0` | Success / All checks passed | Clean summary or JSON `{ "status": "ok" }` |
| `1` | System or unrecoverable error | Problem Details to stderr |
| `2` | Lint / Audit findings detected | Structured findings report to stdout/stderr |
