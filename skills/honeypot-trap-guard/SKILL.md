---
name: honeypot-trap-guard
description: Detect automated AI slop and ungrounded LLM ingestion using active prompt canary traps, decoy issue references, and decoy template checkboxes while preventing self-blocking on template maintenance.
license: MIT
metadata:
  version: "1.7.0"
  parent: anti-slop-engineering
---

# Honeypot Trap & Prompt Canary Guard

> Catch automated bot campaigns and ungrounded AI ingestion using active canary tokens, decoy issues, and decoy checkbox traps with zero false positives.

## Why This Skill Is Needed & Target State

Automated AI agents frequently scrape issues, PR templates, and issue trackers, echoing instructions, hallucinating fixes, or submitting mass PRs without human review. Passive regex filters can false-positive on human contributors or get evaded by clever prompt wrappers.

The target state is an active canary trap defense:
1. **Canary tokens**: Deterministic HMAC-SHA256 tokens embedded as invisible HTML instructions in issue templates (`<!-- anti-slop-canary:canary-xxx -->`). If an automated agent echoes or acknowledges the canary, it is flagged with 100% precision.
2. **Decoy issue numbers**: Known non-existent issue numbers (`#9999`, `#8888`) placed in bait questions. Automated bots referencing them are trapped.
3. **Decoy checkboxes**: Obvious bait checkboxes (e.g. `- [ ] I confirm this PR contains quantum teleportation`) that humans naturally leave unchecked, but ungrounded LLM summarizers blindly check.
4. **Maintenance exemption**: Edits to `.github/` templates and workflow files are strictly exempt so maintainers are never self-blocked.

## Invariant Rules

1. **Active trap over passive substring:** Never flag standard HTML comments that GitHub automatically populates into the PR text box. Only flag when an active instruction is explicitly triggered.
2. **Template maintenance isolation:** Never evaluate honeypot traps against diffs in `.github/` templates or workflow files.
3. **Deterministic verification:** Canary tokens must be generated deterministically via HMAC-SHA256 to allow verifiable rotation without persistent databases.

## CLI Usage

```bash
# Generate a new HMAC canary token to place in issue/PR templates
bunx anti-slop-engineering honeypot --generate-canary --secret "my-repo-secret"

# Audit a PR description or git diff against active canary tokens
bunx anti-slop-engineering honeypot \
  --pr-body-file pr_body.md \
  --canary-token canary-98fbc12a \
  --diff-file diff.patch \
  --json
```
