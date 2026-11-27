# Design integrity guard

An opt-in approval boundary for UI changes. It complements StyleSeed, Design System Drift Guard, and the existing execution guard. It does not certify visual quality.

## Owner-controlled trust

The trusted hook launcher or CI job supplies `ANTI_SLOP_DESIGN_TRUST` with an absolute canonical path outside the target repository. Keep that file, the private signing key, and the verifier outside agent write access. The trust document has five fields:

- `workspace`: canonical absolute path of the target checkout.
- `repository_id`: stable owner/repository identity, matching the manifest.
- `manifest_sha256`: SHA-256 of the exact approved manifest bytes, or 64 zeroes before first approval.
- `public_key`: OpenSSH Ed25519 public key (algorithm and base64 key only).
- `non_ui_paths`: explicit, exact relative paths allowed before first approval. In v3, externally designated non-UI JS/TS data modules can also bypass the static source check; do not list UI modules. Protected paths cannot be excluded.

There is no agent-side signing command. An independent owner reviews the proposed contract and its artifacts, places approved files at their final paths, signs the manifest with an independently held key, and updates the external digest pin. A valid older signature does not override the current pin.

## Workflow

Run from the target project using a trusted checkout of this tool:

```bash
bun /trusted/anti-slop-engineering/bin/cli.js design discover
bun /trusted/anti-slop-engineering/bin/cli.js design harvest
bun /trusted/anti-slop-engineering/bin/cli.js design validate --file .anti-slop/design/proposals/candidate.json
bun /trusted/anti-slop-engineering/bin/cli.js design preview --file .anti-slop/design/proposals/candidate.json
```

Discovery inventories CSS custom properties with source paths and content digests. Both discovery and preview are unapproved outputs. JSON, Markdown and PNG proposals may be written under `.anti-slop/design/proposals/`, including during drift; executable source is not exempt. They cannot be signed as approved artifacts.

Manifest v1, v2 or v3 contains exactly:

- `schema_version`: integer 1 (approval/static CSS), 2 (signed executable policy and browser scenarios), or 3 (strict AST checks plus runtime verification).
- `repository_id`: same stable identifier as the external trust document.
- `tokens`: nonempty object mapping lowercase CSS custom-property names to values.
- `components` and `surfaces`: nonempty arrays of distinct names.
- `artifacts`: object mapping canonical relative paths to SHA-256 digests; includes `PRODUCT.md` and `DESIGN.md`. Include approved reference files or visual baselines when available.

The owner publishes `.anti-slop/design/contract.json` and signs the exact bytes:

```bash
ssh-keygen -Y sign -f /owner-controlled/design-key -n anti-slop-design-v1 .anti-slop/design/contract.json
shasum -a 256 .anti-slop/design/contract.json
```

Update the external trust pin to the resulting digest. The signature file is `.anti-slop/design/contract.json.sig`. OpenSSH with SSH signature support is required.

```bash
bun /trusted/anti-slop-engineering/bin/cli.js design status
bun /trusted/anti-slop-engineering/bin/cli.js design verify
bun /trusted/anti-slop-engineering/bin/cli.js design check --base HEAD
```

Commands return JSON and exit 0 for allowance, 2 for rejection. Run the independent check against a clean checkout of the proposed commit with an explicit trusted comparison base in CI. Protect the CI policy, trust configuration, and verifier independently of the proposed changes. Do not pass private signing keys to the agent or CI verification job.

## Enforcement and limits

- Structured pre-tool writes are denied without an approved manifest, except approved exact non-UI paths and proposal files. With approval, protected paths and signed artifacts remain write-protected. Unknown mutation targets are denied.
- Post-tool checks are advisory where the host cannot undo writes. The independent CLI check is the merge boundary; it detects manifest/artifact drift and changes to protected paths not covered by the approved manifest.
- CSS checks inspect declarations in changed plain CSS files for unknown custom properties, modified token definitions, direct hexadecimal or functional colors, and raw values in a defined subset of color, spacing, type and radius properties. Approved token references and neutral CSS keywords are accepted. Signed CSS artifacts are verified by digest instead. This is a lexical check, not a complete CSS parser; it can miss alternate syntaxes and can reject legitimate expressions. Version 2 adds the bounded source and browser checks below.
- Version 1 component and surface lists are approval metadata only. Versions 2 and 3 require a signed policy.
- This guard is not a sandbox. Shell or unsupported host actions can bypass local hooks. A process with authority over the launcher, trust file, verifier or signing key can defeat the boundary. The external trusted CI check is mandatory for protected merges; configuring such a check and host-level enforcement is the operator's responsibility.

General audit intentionally excludes this guard because approval verification needs independently supplied trust. Run it explicitly.

Without the environment variable, the existing execution guard behaves as before; the explicit design verification commands still require trusted configuration.


## Version 2: executable policy and runtime evidence

Add `.anti-slop/design/policy.json` to the manifest's signed artifacts and include every scenario baseline under `.anti-slop/design/baselines/`. Example policy (adapt every value to the actual product; use the exact browser version of the trusted runner):

```json
{
  "schema_version": 1,
  "browser": {"channel": "chrome", "version": "158.0.8127.89"},
  "allowed_classes": ["flex", "gap-2", "text-primary"],
  "scenarios": [{
    "id": "settings-mobile-ltr",
    "surface": "settings",
    "path": "/settings",
    "viewport": [390, 844],
    "direction": "ltr",
    "state": "ready",
    "components": {"Button": [1, 2]},
    "baseline": ".anti-slop/design/baselines/settings-mobile-ltr.png",
    "checks": {
      "min_target": 24,
      "no_horizontal_overflow": true,
      "align": [{"selectors": ["#save", "#cancel"], "edge": "top", "epsilon": 0.5}],
      "no_overlap": [["#save", "#cancel"]],
      "computed": [{"selector": "#save", "property": "color", "token": "--color-text"}],
      "contrast": [{"foreground": "#save", "background": "#save", "minimum": 4.5}],
      "keyboard": ["#save", "#cancel"]
    }
  }]
}
```

Each declared surface must have at least one scenario. The application exposes a single visible `data-design-surface` root with its `data-design-state`, and component instances expose `data-design-component`. Declare viewport, language direction, theme/state routes, component counts and measured rules for every required case.

The browser runner measures real DOM rectangles and computed styles, checks declared keyboard order and focus indication, and compares the actual PNG digest against the approved baseline. It uses exact PNG equality: keep OS, fonts, browser version, fixture data and browser configuration stable.

The minimum target rule is a project requirement, not a complete WCAG 2.2 conformance audit.

Runtime requires Python Playwright with websocket routing support (tested with 1.58.0) and the selected Chromium/Chrome executable. Start a disposable, deterministic local fixture application from the candidate revision; no production credentials or live customer data. Run the browser in an independently restricted environment.

Route interception rejects external origins and redirects but is not an OS network sandbox.

```bash
bun /trusted/anti-slop-engineering/bin/cli.js design import --file exported-tokens.json
bun /trusted/anti-slop-engineering/bin/cli.js design capture --origin http://127.0.0.1:4173 --output /owner-review/capture-001 --file .anti-slop/design/proposals/candidate.json --policy-file .anti-slop/design/proposals/policy.json
bun /trusted/anti-slop-engineering/bin/cli.js design runtime --origin http://127.0.0.1:4173
bun /trusted/anti-slop-engineering/bin/cli.js design ci --base "$TRUSTED_BASE_SHA" --origin http://127.0.0.1:4173
```

Import supports a bounded subset of DTCG 2025.10 local token exports: RGB color spaces, dimension, duration, number, font family, font weight and whole-token aliases.

Unknown types, cyclic aliases and naming collisions fail. It emits source digests and unapproved proposals, not Figma or screenshot-derived estimates. Capture writes PNGs to a new explicit external directory and never seals them.

An owner must review the images, publish the approved baselines and policy, update the manifest digests, and sign independently. A capture receipt is never sufficient for merge.

Version 2 static checks use a lexical registry for changed JSX/TSX/HTML/Vue/Svelte files: named component tags, literal classes, and rejection of inline styles, spreads and unresolved style/class expressions. They are not a full framework AST, CSS parser, or import graph.

Browser checks cover only declared scenarios, selectors and rendered content. Annotated components and actual class names are checked; unannotated elements are not classified as components.

Contrast checks support opaque RGB foreground/background pairs, not compositing, images or gradients. A signed screenshot is not proof that every interaction is correct.

For protected merge, invoke `design ci` from an independently pinned verifier checkout with an external trust file and a trusted base commit.

The trusted pipeline must build and serve the candidate under review, prevent candidate code from modifying the verifier, trust, or results, use an isolated fixture environment, and require the check through branch protection/rulesets. The repository does not install branch protection or a signing key for the consumer.

## Verification

```bash
python3 -m unittest discover -s tests -p test_design_integrity_guard.py -v
python3 test/design_runtime_integration.py -v
```

The second command requires Playwright and Chrome. It verifies actual browser DOM, baseline capture, signed approval and CI rejection after visual drift.


## Version 3: strict AST enforcement and brownfield inspection

Set the manifest `schema_version` to 3. The signed policy keeps its version 1 schema.
Install parser dependencies **in the independently trusted verifier checkout**, never in the candidate repository:

```bash
cd /trusted/anti-slop-engineering/scripts/design-parser
bun install --frozen-lockfile --ignore-scripts
```

The verifier runs TypeScript 5.9.3, CSS Tree 3.2.1, and Parse5 8.1.1 through Bun in an isolated package with a committed lockfile.

Source content is passed as JSON over stdin; candidate modules are not evaluated or imported, and Bun auto-install and dotenv loading are disabled. The trusted launcher must supply a trusted executable PATH.

Missing Bun, dependencies or invalid parser output blocks source verification; version 3 never silently falls back to the lexical checker.

- JSX/TSX and JS/TS: parse actual syntax, check registered JSX tags and literal classes (including both branches of conditional expressions), reject inline styles, spreads, unresolved class expressions, and selected direct DOM/CSS mutation APIs. This conservative source analysis may flag ordinary data properties or shared helpers; it is not complete dataflow or import-graph analysis.
- CSS: parse declarations including nested rules and escapes, check approved custom-property names/values and a bounded set of design properties, reject direct colors, unverified fallbacks and imports, and require tokens for bounded dimension and transform properties (with neutral values and limited structural sizing exceptions). Framework directives and preprocessing, including Tailwind imports, require review and signed source artifacts or an additional adapter.
- HTML: parse attributes including case normalization and character references, check class/component registries and inline style blocks, reject inline style attributes, embedded scripts, and inline SVG; separately reviewed source artifacts may be signed.
- Other changed file formats require an owner-signed artifact or an exact external non-UI exclusion. Exact exclusions also support JS/TS data modules that would otherwise trigger ambiguous property-name checks; CSS, HTML and JSX/TSX remain checked after approval. Directories are not structured file targets. This is a conservative diff gate, not full-program semantic analysis; supported files still need complete signed browser scenarios.

For migration, inspect explicit files using an unapproved candidate manifest and policy:

```bash
bun /trusted/anti-slop-engineering/bin/cli.js design inspect \
  --file .anti-slop/design/proposals/candidate.json \
  --policy-file .anti-slop/design/proposals/policy.json \
  ui/src/App.tsx ui/src/index.css
```

The report contains a per-file first rejection reason and counts. It is explicitly unapproved, does not require an owner key, and cannot establish conformance or authorize a merge. Deriving registries from the current code is discovery, not approval. Unsafe paths receive individual rejection records.

Strict v3 CI requires a clean tracked checkout at a candidate commit, rejects hidden index flags, verifies the contract, signature and signed artifacts are tracked, and checks the candidate and base commit identities again after the browser run.

Receipts include those commit identities. Ignored build outputs, fixture provenance and the integrity of the build environment remain the independent runner's responsibility.

Browser validation excludes frames and embedded objects, checks component containment and visibility, and requires a declared keyboard focus indicator to change visibly on focus. These are bounded checks, not full accessibility or interaction verification.

### Manifest V3 extension fixture transport

Use manifest version 3 of the design contract and a signed policy with `"extension": {"id": "<32 a-p characters>"}` and browser channel `chromium`. The extension's public manifest key determines the ID.

Declare scenarios for every entry point present in the extension manifest: `popup`, `side-panel`, `options`; their paths must match `action.default_popup`, `side_panel.default_path`, and `options_ui.page` or `options_page`. The runner requires an explicit canonical absolute path to a separately built, unpacked test extension.

```bash
python3 -m pip install playwright==1.58.0
python3 -m playwright install chromium
bun /trusted/anti-slop-engineering/bin/cli.js design capture --extension-dir /isolated/extension-fixture --output /owner-review/crx-capture --file .anti-slop/design/proposals/candidate.json --policy-file .anti-slop/design/proposals/policy.json
bun /trusted/anti-slop-engineering/bin/cli.js design ci --base "$TRUSTED_BASE_SHA" --extension-dir /isolated/extension-fixture
```

The runner loads an actual unpacked MV3 extension in a disposable Chromium profile and visits its `chrome-extension://` pages at declared viewports. It checks DOM geometry, computed styles and exact screenshots as in web transport.

It does not drive native toolbar chrome or the browser's side-panel container, nor test extension service workers, host permissions, content scripts, or browser API interactions.

The restricted fixture manifest rejects background workers, broad permissions and unknown manifest fields; only the optional `sidePanel` permission is allowed.

This is not a sandbox: the trusted pipeline must separately restrict filesystem and network access, use no personal profile or credentials, build from the exact reviewed commit, and independently protect trust and verification results.

### Regression test job

The repository CI job runs the strict AST suite, signed web-browser integration suite and restricted MV3 fixture suite. This validates the tool itself; consumer-required merge checks remain a separate deployment step.

```bash
python3 test/design_ast_integration.py
DESIGN_TEST_BROWSER=chromium python3 test/design_runtime_integration.py -v
python3 test/design_extension_integration.py -v
```

## Build a review package

The builder prepares a v3 candidate and policy from an explicit JSON specification. It never creates an approval signature or modifies approved files.

Put the specification in `.anti-slop/design/proposals/input.json`. It must contain the following fields:

| Field | Value |
| --- | --- |
| `schema_version` | 1 (builder input format) |
| `repository_id` | Intended repository identity |
| `token_file` | Repository-relative DTCG JSON export |
| `components`, `surfaces`, `allowed_classes` | Explicit registries |
| `browser`, `scenarios` | Runtime policy entries; omit each scenario's `baseline` field |
| `artifacts` | Additional repository-relative reference files, possibly empty |
| `extension` | Optional MV3 extension identity |

The builder hashes the token export, `PRODUCT.md`, `DESIGN.md`, and additional artifacts. It derives baseline filenames from the scenario IDs. All scenarios and registries must be supplied explicitly, not inferred as approved from existing code.

**1. Prepare a draft**

```bash
bun /trusted/anti-slop-engineering/bin/cli.js design build --file .anti-slop/design/proposals/input.json --output .anti-slop/design/proposals/draft
```

The new directory contains `candidate.json`, `policy.json` and `receipt.json`. Missing baselines have zero-digest placeholders. The draft cannot pass approved artifact verification.

**2. Capture the declared scenarios**

```bash
bun /trusted/anti-slop-engineering/bin/cli.js design capture --origin http://127.0.0.1:4173 --output /owner-review/capture-001 --file .anti-slop/design/proposals/draft/candidate.json --policy-file .anti-slop/design/proposals/draft/policy.json
```

Capture checks that the policy bytes match the manifest hash before opening a browser. Use the corresponding extension transport for an MV3 fixture.

**3. Prepare the review package**

```bash
bun /trusted/anti-slop-engineering/bin/cli.js design build --file .anti-slop/design/proposals/input.json --output .anti-slop/design/proposals/review --capture-dir /owner-review/capture-001
```

The builder requires an exact set of PNG filenames, matching viewport dimensions, complete chunk framing and valid chunk checksums. It copies the images into a fresh proposal directory and records their digests.

`READY_FOR_REVIEW` means the package is structurally complete, not that the images depict the intended UI. The receipt is unsigned and cannot attest image origin. Inspect the reference files, policy, screenshots and candidate independently before publishing and signing.

The output must be a new direct child of the proposals directory. Existing packages are never overwritten.

## Independent CI with build provenance

Use `design ci-independent` from an independently pinned verifier checkout. This command binds a signed fixture bundle to the exact candidate commit, trusted base commit and approved manifest digest.

The trusted build service produces a static web or restricted MV3 fixture in an isolated job. Candidate build scripts never run in the verification job. Keep the builder's private signing key outside candidate-controlled processes.

The separate build receipt contains exactly these fields:

| Field | Value |
| --- | --- |
| `schema_version` | 1 |
| `repository_id` | Approved repository identity |
| `candidate_sha`, `base_sha` | Full Git commit hashes |
| `manifest_sha256` | Approved manifest digest |
| `files` | Complete fixture-relative file-to-SHA-256 mapping |

Sign the exact receipt bytes in the trusted build service:

```bash
ssh-keygen -Y sign -f /builder-only/private-key -n anti-slop-design-build-v1 /trusted/build.json
```

The verifier receives the receipt, its sibling `build.json.sig`, an independently configured builder public key, and the fixture directory. All are outside the candidate checkout. The builder and design-owner public keys must differ.

```bash
bun /trusted/verifier/bin/cli.js design --repo /isolated/candidate --trust /trusted/design.json ci-independent --candidate "$CANDIDATE_SHA" --base "$BASE_SHA" --fixture-dir /isolated/fixture --build-receipt /trusted/build.json --build-key /trusted/builder.pub
```

The command requires a clean v3 candidate, verifies that the base is an ancestor, checks the diff, and validates the exact fixture file inventory and digests. It renders only the verified bytes, not a separately supplied local application server.

The optional `--preflight` flag checks identity and provenance without rendering. Its receipt always has `approved: false`; do not use it for a required merge check.

### Configure the protected merge check

Use a trusted external workflow or GitHub App with the following responsibilities:

1. Obtain candidate and base SHAs from trusted pull request or merge queue metadata.
2. Fetch the candidate into a fresh isolated checkout and build a fixture without access to approval or publication credentials.
3. Have the independent build service attest the artifact. Transfer only the fixture, receipt and signature to the verifier.
4. Run the full command above using a pinned verifier and external trust. Require exit zero and `approved: true`.
5. Publish the check for the exact tested candidate SHA through a trusted identity. Require that identity and check in the repository ruleset.

Do not run the verifier from candidate-controlled workflows or let the candidate update the trust pin, builder key, or check result. Do not pass secrets into candidate JavaScript. Use an OS-isolated browser with no production access.

A signed build receipt establishes provenance relative to the trusted builder; it does not prove that the builder faithfully executed its prescribed process. The verifier does not create GitHub rulesets or publish check runs. Those remain operator-controlled deployment tasks.
