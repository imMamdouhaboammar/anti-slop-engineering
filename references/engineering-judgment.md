# Judgment, Trade-offs, and Legitimate Exceptions

## Avoid a new anti-slop slop

A huge mandatory checklist can itself cause excessive code, bureaucracy and agent confusion. The skill's core is workflow; the catalog is a selective diagnostic. Read only relevant sections on demand. Prefer precise corrective action to mechanically satisfying counts or scores.

## Trade-off rules

- A necessary authorization check, error handler, or transaction boundary is not overengineering even if it adds many lines.
- Extract shared code for *stable* duplication; tolerate short/local duplication when abstraction would couple unrelated future changes.
- Consistent framework boilerplate may be necessary; hand-rolling standard cryptography, parsing, auth, or date/time logic to save lines is dangerous.
- New dependencies are justified when their tested behavior meaningfully reduces risk/maintenance; don't reinvent complex libraries for a two-line LOC goal.
- Prefer readability to dense one-liners. A small function can be worse than a slightly longer clear function.
- Some comments are essential for non-obvious invariants, concurrency hazards, or business reasons. Banning all comments is counterproductive.
- Production logging must be structured and privacy-safe; having many necessary operational events is not 'console pollution'.
- Changing existing tests is valid when the approved contract changes; changing tests to fit a regression is not.
- Unit vs integration vs E2E should reflect system risk and cost; neither all-unit nor all-E2E is a universal rule.
- Rule thresholds (file length, diff size, number of files) are prompts for scrutiny, not blockers without measured harm.
- In existing codebases, preserve established version constraints and lockfile stability without uncoordinated major-version drift. However, when introducing **new** libraries, packages, or SDK integrations, always strictly resolve and pin the **latest stable version** from the official registry rather than guessing outdated versions from model training memory.
- For greenfield projects, new modules, or SDK integrations, always use the **official boilerplate, CLI installer, or generator** (e.g., `uv init`, `cargo init`, `bun create`, official SDK starters). Hand-rolling ad-hoc scaffolding from memory introduces missing build flags, broken toolchains, and dirty slop.
- UI microcopy should be succinct, high-signal, and respectful of the user's attention. Tooltips and helper text should clarify non-obvious interactions, not narrate obvious UI controls.
- Dev notes, internal TODOs, mock data disclaimers, or notes intended for other agents have zero place in production UI or client DOM. If mock data is required during dev or prototyping, display clean realistic domain data without meta-disclaimers in the UI layout; log diagnostic state to the devtools console or test harnesses instead.
- Visual hierarchy and restraint in headers, navbars, and toolbars: prioritize the primary task. Not every available action belongs in the navigation bar; cluster secondary actions into clean contextual menus or dedicated sub-views.
- Documentation must describe existing, verified behavior—not imagined futures or unrequested distribution channels. Creating elaborate submission dossiers, reviewer packets, or platform guides for third-party ecosystems (e.g. deprecated plugin stores like OpenAI plugins) adds negative value: it misleads users with dead links and creates unmaintained clutter. Prefer a single accurate README to ten speculative markdown files.
- **The Non-Obviousness Test (Silence Over Noise):** High engineering judgment recognizes when a comment, docstring, UI helper text, or documentation section adds zero net-new information. If a comment merely restates syntax in English (e.g. `// return user`), a docstring merely rephrases the function name, a UI helper merely re-reads an input label (e.g. `"Enter your email"` under an Email field), or a README lists obvious prerequisites (e.g. `"Requires a computer and internet connection"`), it is noise. Omit it completely. Good comments document *why*, edge-case invariants, architectural constraints, and failure modes; good code and UI speak for themselves.
- **The Direct Payload & Affordance Principle (Silence Over Meta-Narration):** Every sentence that explains a tool's mechanism instead of its domain value is pure cognitive debt. Readers know how to click play on a video, expand an accordion, click a link, or copy a code snippet. Telling users how to interact with standard UI affordances (e.g. `"(شاهد التجربة هنا دون مغادرة الصفحة)"`, `"Click to expand the table below"`), writing transitional conversational preambles (`"The following table outlines..."`, `"In this section we will explore..."`), or stacking dual-language translations (`"Live Demo · مشغل العرض"`) insults the user's intelligence. Transition directly from domain headings into payloads (code, table, media, schema). Silence over meta-narration.

## How to classify a suspected smell

1. **Observed**: exact path, line or executable evidence.
2. **Invariant / cost**: what contract, trust boundary or maintenance burden might be affected?
3. **Counterexample**: could this be intentional and justified under this repo's requirements?
4. **Impact and confidence**: what breaks and how certain are we?
5. **Action**: smallest safe correction or documented exception.

If a finding fails steps 1 or 2, label it **unverified observation**, not a defect.
