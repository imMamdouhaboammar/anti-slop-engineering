# Evidence Base, Provenance, and Caveats

## Empirical studies (not unqualified universal claims)

1. **SlopCodeBench, Orlanski et al. (2026)**: https://arxiv.org/abs/2603.24755. A long-horizon iterative benchmark; the subsequently updated paper compares agents with histories from 473 Python repositories and reports higher measured code verbosity and structural erosion. These are its operationalized metrics, not universal quality scores; sampled human repositories are not a randomized head-to-head controlled experiment.
2. **Debt Behind the AI Boom, Liu et al. (2026)**: https://arxiv.org/abs/2603.28592. Studies 304,362 AI-authored commits from 6,275 repos, identifying code smells, bugs and security issues via static analysis. Interpretation is bounded by static analysis false positives, selection bias and the attribution method.
3. **Not All Agents Are Equal, Kraishan (2026)**: https://arxiv.org/abs/2609.17598. Analysis of 37,623 PRs across five agents and a human baseline reports strong vendor-dependent outcomes and some lower aggregate security smell rates in AI PRs. Counter-evidence against blanket 'AI is always worse' claims; regex smells are not proven exploitable vulnerabilities.

## Engineering practices and standards

4. **Google Engineering Practices: Small CLs**: https://google.github.io/eng-practices/review/developer/small-cls.html. Small, coherent code changes ease review and rollback. Not a fixed LOC prohibition; related tests belong with changes.
5. **Martin Fowler: Testing / Mutation Testing**: https://martinfowler.com/testing/ and https://martinfowler.com/bliki/MutationTesting.html. Good tests support safe changes; mutation testing probes whether tests would detect deliberate faults.
6. **OWASP Agentic Top 10 2026**: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/. Agent-specific trust, tool-use, privilege and security risks.
7. **Agent Skills specification**: https://agentskills.io/specification. Required SKILL.md frontmatter, directory naming and reference rules; portable across agents implementing the specification.
8. **Agent Skills best practices**: https://agentskills.io/skill-creation/best-practices. Progressive disclosure, narrow skill scope, concrete execution procedures and validation.

## Community experience, not statistical proof

9. **Reddit r/ExperiencedDevs**: https://www.reddit.com/r/ExperiencedDevs/comments/1rqwfjj/workflow_setup_to_make_your_coding_agent_ship/. Discussion about mixing changes across layers into oversized AI PRs, duplication and review burden. Community comments disagree about best decomposition patterns.
10. **Reddit r/dataengineering**: https://www.reddit.com/r/dataengineering/comments/1vg6k87/how_do_you_deal_with_ai_slop_prs_from_team_members/. Practitioners debate responsibility and the ability to explain AI-authored diffs.
11. **X: Saoud Rizwan referencing SlopCodeBench**: https://x.com/sdrzn/status/2077121290440454467. Public discussion of empirical benchmark, not an independent study.
12. **X: Ray Fernando on low-signal unit tests**: https://x.com/RayFernando1337/status/2102927565778522610. Practitioner experience; a quoted preference for E2E-only testing is explicitly *not* adopted as a universal rule here.

## Provenance policy

Do not attach a source to an individual catalog item unless the source actually supports that mechanism. Much of this catalog is engineering synthesis based on longstanding failure modes plus agent-specific risks. Community anecdotes are not prevalence estimates. Findings on a specific PR need **direct local evidence** and verification, not a citation to a general blog post.
