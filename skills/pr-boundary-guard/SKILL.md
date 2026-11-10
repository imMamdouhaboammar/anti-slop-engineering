---
name: pr-boundary-guard
description: Enforce Git provenance, branch topology, commit message conventions, PR template contracts, and logorrhea bounds. Use when preparing, reviewing, or triaging pull requests in local Git checkouts or automated CI pipelines.
license: MIT
metadata:
  version: "1.7.0"
  parent: anti-slop-engineering
---

# PR Boundary & Git Topology Guard

> Enforce clean Git provenance, branch hygiene, radio-button PR template contracts, and anti-logorrhea bounds across local checkouts and CI pipelines.

## Why This Skill Is Needed & Target State

Open-source maintainers and engineering teams face an influx of low-quality, AI-generated PRs characterized by:
- Direct pushes from unbranched default branches (`main`/`master`) on personal forks.
- Mismatched commit author identities and automated crawler cherry-picks.
- Excessive metadata logorrhea (4,000-word PR descriptions, 15+ inline code tokens, and emoji inflation).
- Hallucinated extra sections in PR templates and unselected radio-button sections.
- Micro-edits (<=3 lines) solely targeting `README.md` or `LICENSE` for metric gaming.

The target state is a deterministic, offline-first evaluation pipeline operating on local Git history and CI event payloads, returning machine-readable RFC 9457 problem details and remediation contracts.

## Invariant Rules

1. **Topology hygiene:** Never submit PRs directly from `main` or `master`. Always branch to an intent-revealing feature branch (`feat/`, `fix/`, `chore/`).
2. **Subject length discipline:** Limit commit subject lines to 100 characters max (warning at >72 chars). Rationale belongs in the commit body (up to 5,000 chars).
3. **Template radio-button contracts:** For mutually exclusive checklist sections, check exactly one option. Do not inject hallucinated sections not present in the repository template.
4. **Emoji and token restraint:** Bounded emoji count (<=3) and bounded inline code reference density in PR descriptions. Let clear engineering descriptions speak without marketing fluff.
5. **Shallow and detached resilience:** Automatically adapt when running in detached HEAD (`refs/pull/*/merge`) or shallow clones without crashing or emitting false alarms.

## CLI Usage

```bash
# Run local git topology and commit check
bunx anti-slop-engineering pr-guard --base origin/main

# Run full PR check with PR description and repository template
bunx anti-slop-engineering pr-guard \
  --base origin/main \
  --pr-title "feat(core): implement robust boundary validation" \
  --pr-body-file .github/pr-description.md \
  --template-file .github/pull_request_template.md \
  --require-conventional \
  --json
```
