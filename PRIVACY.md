# Privacy

Last updated: 2026-11-09

Anti-Slop Engineering is an open-source, skills-only developer tool. It does not operate a publisher-hosted backend, user account service, telemetry collector, analytics endpoint, advertising service, or remote data store.

## Data Collected by the Publisher

None through the tool itself. The publisher does not receive, store, sell, or retain prompts, repository contents, source code, credentials, or generated release artifacts through an Anti-Slop Engineering service because no such remote service is operated.

## Data Used During a Workflow

When a user asks ChatGPT, Codex, or an AI coding assistant to inspect a repository, file, diff, or build output, that material is processed locally or within the host execution environment according to the host's own terms and policies. Anti-Slop Engineering provides rules, heuristics, and validation scripts for that workflow and does not transmit data to external servers.

Users should not place reusable secrets in manifests, skill files, release archives, support reports, or public test fixtures. Credentials required by external services must remain in the user's secure credential store, environment variables, or CI secret storage.

## Third-Party Services

Third-party AI platforms, hosting providers, Git forges, and CI pipelines chosen by the user are governed by their respective privacy policies. Anti-Slop Engineering does not connect to these services autonomously.

## Retention and User Controls

Publisher retention through Anti-Slop Engineering is zero. Local files, test outputs, and repository artifacts generated during use remain entirely under the user's filesystem and repository controls.
