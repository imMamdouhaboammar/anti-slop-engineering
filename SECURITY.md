# Security Policy

Security is a foundational tenet of Anti-Slop Engineering. As a framework and triage guard designed to protect production codebases against code bloat, test-oracle erosion, synthetic hallucinations, and unauthorized security shortcuts, we hold our own codebase to the highest security, correctness, and supply-chain integrity standards.

We welcome responsible security research and encourage researchers and practitioners to report vulnerabilities privately so they can be investigated and addressed before public disclosure.

## Supported Versions

| Version | Status | Security Support |
| --- | --- | --- |
| `1.6.x` | Stable Release | :white_check_mark: Actively supported with patches |
| `main` | Active Development | :white_check_mark: Latest security fixes |
| `< 1.6.0` | Legacy Releases | :x: Not maintained (please upgrade) |
| Third-party forks | Unofficial | :x: Not maintained by this project |

## Reporting a Vulnerability

**Please do not disclose security vulnerabilities through public GitHub Issues, Discussions, or Pull Requests.**

To report a vulnerability:

1. Visit [GitHub Security Advisories](https://github.com/imMamdouhaboammar/anti-slop-engineering/security/advisories).
2. Click **Report a vulnerability** to submit findings via GitHub's Private Vulnerability Reporting.
3. If private reporting is temporarily unavailable, report directly via email:
   - **Email:** `mamdouhfces1997@gmail.com`
   - **Subject:** `[Security] Anti-Slop Engineering Vulnerability Report`

### What to Include in Your Report

A useful security report should contain:

- A clear description of the vulnerability or security bypass mechanism.
- The affected component, file, CLI flag, or script (e.g. `diff_guard.py`, `sre_guard.py`, `bin/cli.js`, native engine).
- Reproducible steps or a minimal proof-of-concept diff.
- Potential impact or risk evaluation (e.g., heuristic evasion, arbitrary execution, denial of service).
- Relevant logs, stack traces, or environment details.
- Suggested remediation or patch if available.

Never include real production secrets, private API keys, or live infrastructure credentials in any report.

## Security Scope

We are particularly interested in vulnerabilities affecting:

### Heuristic & AST Engine Integrity
- **Guard Evasions & Parser Bypasses:** Novel syntactic or AST obfuscations that bypass Diff Guard, SRE Guard, Ast Slop Guard, or Type-Level guards while smuggling banned antipatterns.
- **Tautological Oracle Leaks:** Vulnerabilities in test verification or audit runners that allow circular or self-grading test suites to pass undetected.
- **ReDoS (Regular Expression Denial of Service):** Catastrophic backtracking in regex patterns within `diff_guard.py`, `sre_guard.py`, or rule definitions.

### CLI & Native Runtime Security
- **Command Injection & Subprocess Escapes:** Unsanitized arguments or environment variables leading to unauthorized command execution in `bin/cli.js` or Python/Rust/Go runtimes.
- **Path Traversal & Arbitrary File Access:** Improper directory resolution or symlink following during recursive codebase walks.
- **Tampering with Invariant Ledgers:** Unauthenticated or unauthorized modification of `.anti-slop/invariant-ledger.json` and decision audit trails.

### Honeypot & Prompt Canary Security
- **Canary Cryptographic Forgery:** Vulnerabilities in HMAC-SHA256 canary generation or validation that allow automated agents to forge valid canary tokens.
- **Decoy Tampering:** Exploits that manipulate decoy issues or PR template honeypots.

### Supply Chain & Credential Safety
- **Credential Leakage:** Hardcoded keys, tokens, or sensitive material in repository files, fixtures, or CLI outputs.
- **Dependency Drift & Tampering:** Vulnerabilities introduced into npm, Cargo, or Go module trees.

## Responsible Security Research

We ask security researchers to:
- Test only against local environments or authorized clones.
- Refrain from destructive testing, denial-of-service attacks, or spamming automated issue trackers.
- Avoid publishing exploit code or disclosing details before a patch has been released.
- Give maintainers a reasonable opportunity (within the SLA below) to investigate and remediate confirmed vulnerabilities.

## Disclosure and Response SLA

Our standard vulnerability handling process:

1. **Acknowledgment:** Reports are acknowledged within **48 hours**.
2. **Assessment & Triage:** Vulnerability severity is evaluated (using CVSS v3.1 scoring) within **5 business days**.
3. **Remediation & Testing:** Patches and regression tests are prepared and verified across all supported platforms.
4. **Coordinated Disclosure:** A GitHub Security Advisory and patched release are published concurrently. Reporters may be credited in the advisory with their consent.

## Secure Integration Recommendations

When embedding Anti-Slop Engineering into CI/CD pipelines or AI agent harnesses:
- Run CLI invocations with minimum required file permissions.
- Keep dependencies updated via Dependabot and automated security audits (`bun run security:audit`).
- Enforce secret scanning push protection to prevent accidental credential commits.
- Run `osv-scanner` and CodeQL analysis as part of PR merge criteria.

## Maintainer

**Mamdouh Aboammar**  
GitHub: [@imMamdouhaboammar](https://github.com/imMamdouhaboammar)  
Repository: [anti-slop-engineering](https://github.com/imMamdouhaboammar/anti-slop-engineering)  
Security Contact: `mamdouhfces1997@gmail.com`
