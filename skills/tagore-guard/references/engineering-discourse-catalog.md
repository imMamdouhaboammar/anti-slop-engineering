# Engineering Discourse Anti-Pattern Catalog

> 29 Cataloged AI Tells Adapted and Extended for Software Engineering Artifacts (PRs, Commits, ADRs, Code Comments, and Agent Handoffs).

---

## 1. Content Patterns

### T01: Significance & Legacy Inflation
- **Words to Watch:** `stands as`, `serves as an enduring testament`, `pivotal moment`, `vital milestone`, `underscores the importance`, `marks a shift`, `evolving landscape`, `indelible mark`, `setting the stage`.
- **Engineering Manifestation:** Inflating routine bug fixes or refactors into historic architectural breakthroughs.
- **Before:** "This refactoring of the connection pool serves as an enduring testament to our commitment to resilience, marking a pivotal milestone in the evolving landscape of our backend."
- **After:** "We increased connection pool capacity from 10 to 50 connections to prevent pool exhaustion under 2,000 req/s load."

### T02: Undue Emphasis on Notability
- **Words to Watch:** `independent coverage`, `leading expert`, `industry leader`, `active presence`.
- **Engineering Manifestation:** Appending vague claims of external validation instead of citing verifiable metrics.
- **Before:** "This caching pattern has garnered independent praise and is widely considered industry best-practice by leading experts."
- **After:** "This LRU cache implementation follows the Linux kernel page-replacement strategy described in RFC 4821."

### T03: Superficial Participle (-ing) Chaining
- **Words to Watch:** `highlighting...`, `underscoring...`, `ensuring...`, `reflecting...`, `fostering...`, `enhancing...`, `facilitating...`, `cultivating...`.
- **Engineering Manifestation:** Tacking multiple present participle phrases to the end of a sentence to simulate analytical depth.
- **Before:** "We decoupled the notification worker, enhancing system modularity, ensuring horizontal scalability, and fostering developer velocity."
- **After:** "We moved the notification worker to a separate queue. Worker failures no longer block the main HTTP checkout thread."

### T04: Promotional & Marketing Vocabulary
- **Words to Watch:** `groundbreaking`, `game-changer`, `revolutionary`, `unparalleled`, `seamlessly`, `best-in-class`, `unlock the power`, `nestled at the intersection`.
- **Engineering Manifestation:** Inserting breathless marketing adjectives into internal architectural documentation.
- **Before:** "A groundbreaking solution nestled at the intersection of streaming and caching that seamlessly delivers best-in-class throughput."
- **After:** "An in-memory stream buffer that batches writes to disk every 500ms."

### T05: Vague Attributions & Weasel Words
- **Words to Watch:** `industry observers note`, `experts agree`, `studies show`, `widely considered`.
- **Engineering Manifestation:** Appealing to anonymous consensus rather than empirical measurements.
- **Before:** "Experts agree that microservices improve team independence."
- **After:** "Team A can deploy the billing service without waiting for Team B's auth service deployment window."

### T06: Formulaic Challenges & Outlook Section
- **Words to Watch:** `Despite these challenges... continues to thrive`, `Challenges and Future Outlook`, `journey toward excellence`.
- **Engineering Manifestation:** Ending technical proposals with upbeat, generic corporate narrative boilerplate.
- **Before:** "Despite ongoing challenges with network latency, the platform continues to thrive, setting the stage for an exciting journey toward excellence."
- **After:** "Unresolved: cross-region latency between us-east-1 and eu-central-1 remains 85ms. Cross-region replication will be addressed in Q2."

---

## 2. Language & Grammar Patterns

### T07: High-Frequency AI Vocabulary
- **Words to Watch:** `delve`, `tapestry`, `intricate`, `intricacies`, `interplay`, `showcase`, `fostering`, `garner`, `pivotal`, `testament`, `vibrant`.
- **Engineering Manifestation:** Statistical over-representation of specific post-2023 LLM favorite words.
- **Before:** "Let us delve into the intricate interplay between the scheduler and the event loop, showcasing how they foster low latency."
- **After:** "The scheduler assigns tasks to the event loop using round-robin distribution."

### T08: Copula Avoidance
- **Words to Watch:** `serves as a`, `stands as a`, `functions as a`, `boasts an impressive`, `features a comprehensive`.
- **Engineering Manifestation:** Refusing to use simple linking verbs ('is', 'are', 'has').
- **Before:** "The auth middleware serves as a robust security barrier that features comprehensive token validation."
- **After:** "The auth middleware validates JWT tokens and rejects expired sessions."

### T09: Negative Parallelisms & Tailing Negations
- **Words to Watch:** `It's not just about X; it's about Y`, `not only does it X, but it also Y`, trailing `, no guessing.`, `, no wasted motion.`
- **Engineering Manifestation:** Dramatic oratorical contrasting rather than factual exposition.
- **Before:** "It's not just about caching responses; it's about fundamentally transforming how users experience data. Clean config, no guessing."
- **After:** "The cache stores rendered responses for 60 seconds."

### T10: Rule of Three Overuse
- **Words to Watch:** Grouping adjectives, nouns, or bullet items into formulaic triads (`X, Y, and Z`).
- **Engineering Manifestation:** Forcing technical trade-offs into artificial groups of three.
- **Before:** "The framework delivers reliability, scalability, and security."
- **After:** "The framework provides atomic commits and bounded memory queues."

### T11: Elegant Variation (Synonym Cycling)
- **Words to Watch:** Alternating words for the exact same system entity within a paragraph (`engine`, `mechanism`, `component`, `subsystem`, `apparatus`).
- **Engineering Manifestation:** Confusion caused by renaming canonical components to avoid repetition.
- **Before:** "The parser handles AST nodes. The parsing engine then transforms tokens. Finally, the syntactic mechanism emits bytecode."
- **After:** "The parser parses tokens into AST nodes and emits bytecode."

### T12: False Ranges
- **Words to Watch:** `from X to Y, from A to B` where endpoints are not on a coherent scalar axis.
- **Engineering Manifestation:** AI attempting to sound comprehensive by naming disconnected domains.
- **Before:** "We optimized everything from database query plans to frontend button animations."
- **After:** "We added missing indexes on `users.email` and debounced the checkout click handler."

### T13: Passive Voice & Subjectless Fragments
- **Words to Watch:** `No configuration is needed`, `Results are automatically preserved`, `The payload is executed by the system`.
- **Engineering Manifestation:** Erasing the engineer or daemon actually performing the operation.
- **Before:** "No configuration needed. All data is automatically sanitized."
- **After:** "The sanitization middleware strips script tags from request bodies by default."

---

## 3. Style & Communication Patterns

### T14: Em Dash Overuse
- **Watch:** Using em dashes (`—`) multiple times per paragraph to simulate breathless, snappy copywriting.
- **Remedy:** Replace with periods, commas, or parentheses.

### T15: Mechanical Boldface Overuse
- **Watch:** Bolding every noun or abbreviation in bulleted lists (`**JWT (JSON Web Token)**`).
- **Remedy:** Bold strictly for error states, breaking changes, or key numeric thresholds.

### T16: Inline-Header Vertical Lists
- **Watch:** Repetitive `- **Topic:** Explanation` structures.
- **Remedy:** Write cohesive narrative prose or use a structured markdown table.

### T17: Title Case in Headings
- **Watch:** `## Advanced Dynamic Configuration Management`.
- **Remedy:** Use sentence case: `## Dynamic configuration management`.

### T18: Gratuitous Emojis
- **Watch:** `🚀 Launching`, `💡 Insight`, `✅ Done`, `🔥 Blazing Fast`.
- **Remedy:** Eliminate decorative emojis from technical docs and PR descriptions.

### T19: Curly Quotes
- **Watch:** Smart quotes (`“`, `”`, `‘`, `’`) instead of straight ASCII quotes (`"`, `'`).
- **Remedy:** Enforce standard ASCII quotation marks.

### T20: Chatbot Preambles & Closers
- **Watch:** `I hope this helps!`, `Certainly!`, `Of course!`, `Here is an overview...`, `Let me know if you need anything else.`
- **Remedy:** Strip completely per Direct Payload Invariant.

### T21: Knowledge-Cutoff Hedging
- **Watch:** `As of my last update...`, `While specific details are limited...`.
- **Remedy:** State verified repository state directly.

### T22: Sycophantic / Servile Tone
- **Watch:** `Great question!`, `Excellent point!`, `You're absolutely right!`.
- **Remedy:** Evaluate technical proposals purely on engineering merit.

### T23: Bloated Filler Phrases
- **Watch:** `in order to` (use `to`), `due to the fact that` (use `because`), `at this point in time` (use `now`), `has the ability to` (use `can`).

### T24: Excessive Hedging
- **Watch:** `It could potentially possibly be argued that this might cause...`.
- **Remedy:** `This increases memory usage by 15% under concurrent load.`

### T25: Generic Upbeat Conclusions
- **Watch:** `The future looks bright...`, `Exciting times lie ahead...`.
- **Remedy:** End with concrete next verification steps or rollback plans.

### T26: Hyphenated Word Pair Overuse
- **Watch:** Uniform hyphenation of common terms (`cross-functional`, `data-driven`, `decision-making`).

### T27: Persuasive Authority Tropes
- **Watch:** `At its core...`, `The real question is...`, `What really matters is...`.
- **Remedy:** Delete the ceremonial frame; state the technical fact.

### T28: Signposting & Announcements
- **Watch:** `Let's dive in...`, `Now let's look at...`, `Without further ado...`.
- **Remedy:** Transition directly into technical code or specification.

### T29: Fragmented Warmup Headers
- **Watch:** A header followed by a tautological one-sentence paragraph before the actual payload begins.
- **Remedy:** Delete the warmup sentence.
