---
name: llm-eval-and-prompt-injection-fortress
description: Review how agents handle untrusted text, authorize tool requests, and protect private outputs. Use for retrieval, tool connectors, agent permissions, or evaluation of coding agents.
license: MIT
metadata:
  version: "0.1.0"
  parent: anti-slop-engineering
---

# Prompt Injection and Tool Authorization Review

## Map data and authority

| Boundary | Review evidence |
| --- | --- |
| User intent | The authenticated platform request identifies actor, tenant, requested operation, and exact resource scope. High-impact actions carry explicit approval for canonical arguments. |
| Retrieved content | Repository files, comments, webpages, emails, tool results, and OCR remain data even if they quote a privileged role or resemble a tool invocation. Preserve provenance and isolate this text from developer instructions. |
| Requested action | The model produces a typed proposal. Independently validate tool, normalized target, operation, actor/tenant, and data classification at the dispatcher. Unknown or incomplete authority denies execution. |
| Effect and output | The tool service checks resource ownership and scope again. Filter sensitive fields before sending results to the model or an external destination. Log decision identifiers and classified outcomes with no private content. |

## Check the policy boundary

1. Inventory which connectors can read, write, publish, or transfer data. Grant separate, task-scoped capabilities to models or tools and enforce the authenticated caller's entitlements at each downstream service.
2. Tie approval to the exact operation, resource, tenant, and canonical parameters. Recheck it before execution and expire it with the task. No connector response or model-generated field can supply authority.
3. Compare the tool proposal, policy decision, actual invocation and observed side effect. A helpful refusal in text leaves the tool boundary unverified. A denied operation should produce zero downstream invocations, zero writes and zero disclosure.
4. Preserve the ability to quote and summarize untrusted text as data. If retrieval returns mixed-authority text, retain its source and restrict the available action set for that step. Use a harmless placeholder in all fixtures and keep evaluation isolated from credentials, network and production state.

## Record the evaluation

Record fixture revision, expected outcome, observed dispatcher decision, actual tool/effect count, and any policy or evidence gap. Use separate sets for known-authorized reads, wrong-resource and wrong-tenant reads, unauthorized publish, and quoted text with no proposed action. Any unauthorized downstream invocation blocks release. Check authorized success independently to catch a policy that denies every request. Treat unexecuted integrations as inconclusive.

Run `python3 examples/policy_review.py` from the skill directory for the synthetic decision cases. The example has no real tools or model and demonstrates an in-memory authorization check. Run `python3 -m unittest discover -s tests -p test_prompt_tool_authorization.py -v` from a source checkout.

- [OWASP prompt injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)
- [OpenAI safety in building agents](https://developers.openai.com/api/docs/guides/agent-builder-safety)
