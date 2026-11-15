---
name: context-window-and-token-economics-architect
description: Review LLM context selection, retrieval evidence, prompt cache boundaries, time to first token, and structured output contracts. Use for changes that affect what an LLM sees, reuses, or returns.
license: MIT
metadata:
  version: "0.1.0"
  parent: anti-slop-engineering
---

# Context Window and Token Economics

## Define the request budget

- Capture the model and API version, tokenizer or usage source, prompt revision, tool/schema revisions, retrieval index revision, and the target task. Include provider-added or tool/schema overhead when the API reports it; mark unrecoverable overhead unknown.
- Reserve output and reasoning capacity as defined by the selected API. Allocate the remaining input budget to instructions, history, tools, and retrieved evidence. Measure tokens on the rendered request. Reject or narrow requests that exceed the model limit even when some tokens are cached.
- Write task-specific thresholds before comparing variants: context cap, minimum evidence recall, maximum p95 time to first token, and allowed regression in exact task outcomes. If a required document will not fit, return an explicit evidence gap or ask for a narrower scope.

## Select evidence

- Retrieve small, answer-bearing passages with source ID, revision, and a section or span. Keep headers, table labels, or adjacent text when removing them changes meaning. Deduplicate overlapping passages by source and span before filling the budget.
- Apply tenant and document authorization before any retrieval intended for the prompt. Preserve provenance through derived summaries. Redact payloads and logs before sending them to a model, cache, analytics endpoint, or reviewer when authorization or retention requirements demand it.
- Verify that schema validation and source grounding independently pass. For each required claim in the evaluation set, check that the chosen context contains its evidence and that the output cites that evidence. If the model must report insufficient evidence, make it a valid structured output.

## Inspect cache reuse

| Cache | Evidence for review |
| --- | --- |
| Provider prefix | Stable rendered prefix and provider-reported cached input. Record model, tool/schema settings, and cache eligibility. Design the prefix around public or otherwise authorized stable inputs. Count cached tokens toward the context limit. |
| Application retrieval or prompt fragments | Include tenant/policy scope, source revision, and rendering/config revisions in cache identity. On document update, deletion, access revocation, or schema change, invalidate or recompute before reuse. Verify the result for an authorized reader and a reader whose access changed. |
| Application responses | Revalidate authorization and evidence freshness before reuse. Include exact task inputs, output schema version, and relevant model settings in cache identity. Disable sharing where the output depends on private context. |

## Compare before and after

1. Reuse the same labeled task set, model settings, and workload distribution. Compare cold and warm runs separately, including expiry or changed-prefix cases. Record time from request dispatch to first user-visible token for streaming responses and end-to-end time separately. Record sample counts, p50 and p95; leave time to first token unavailable for requests where it cannot be observed.
2. Record total input, cached reads, cache writes when exposed, output, and retries per completed task. Cache-read share is cached-read input tokens divided by total input tokens. Track billed cost separately using dated rates and each provider's usage field semantics. With no reliable data, report unknown usage or cost.
3. Record expected evidence hits over required evidence, structured parse success, answer correctness, and authorization failures. Compare latency only for cohorts with the same conditions. Ship a change when it meets the task thresholds under both cold and warm runs. Any cross-tenant disclosure or stale authorization reuse blocks the change.

## Offline verification

Run the [paired workflow](examples/paired-workflow.md) and its fixture tests with `python3 -m unittest discover -s tests -p test_context_token_economics.py -v`. The scenario verifies evidence coverage and invalidation. For provider token counts and latency, replace synthetic estimates with captured telemetry for the selected API.

- [OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)
- [Claude prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Gemini context caching](https://ai.google.dev/gemini-api/docs/caching)
