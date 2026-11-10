# Usecase: Auditing AST & Type-Slop

Instructions for auditing TypeScript and JavaScript projects against anti-slop rules using both CLI and Oxlint plugins.

---

## 1. Quick Diff Triage

To verify whether your uncommitted or staged changes contain type-level slop:

```bash
bunx anti-slop-engineering ast --base HEAD
```

To run with strict exit codes in pre-commit hooks or GitHub Actions:

```bash
bunx anti-slop-engineering ast --base HEAD --strict
```

---

## 2. Directory or File Sweep

To sweep an entire project or directory:

```bash
bunx anti-slop-engineering ast src/ --json
```

---

## 3. Vendoring Oxlint Rules

For comprehensive AST and lexical scope checks directly inside developer editors and Vite+/Oxlint workflows:

```bash
# Initial copy of plugin
bunx anti-slop-engineering install-oxlint tools/oxlint/anti-slop

# Check for updates or synchronize upstream improvements without losing local edits
bunx anti-slop-engineering update-oxlint tools/oxlint/anti-slop
```
