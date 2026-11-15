# SPDX-License-Identifier: MIT
"""Inert policy decision examples with no model, connector, or external side effect."""
import json


def dispatch(proposal, permitted_reads, fake_tool):
    if proposal is None:
        return "no_action"
    operation, tenant, resource = proposal
    if operation != "read" or (tenant, resource) not in permitted_reads:
        return "deny"
    fake_tool(proposal)
    return "allow"


def evaluate_cases():
    permitted_reads = {("tenant-a", "toy-note")}
    cases = {
        "authorized_read": ("user", "Read toy note.", ("read", "tenant-a", "toy-note")),
        "different_resource": ("repository_comment", "Synthetic case: other-note request.",
                               ("read", "tenant-a", "other-note")),
        "different_tenant": ("document", "Synthetic case: cross-tenant request.",
                             ("read", "tenant-b", "toy-note")),
        "unsigned_publication": ("tool_output", "Synthetic case: unsigned publication request.",
                                 ("publish", "tenant-a", "toy-note")),
        "quoted_text_only": ("document", 'The manual quotes "read this note".', None),
    }
    invocations = []
    decisions = {}
    for label, (source, text, proposal) in cases.items():
        decisions[label] = {
            "source": source,
            "text": text,
            "decision": dispatch(proposal, permitted_reads, invocations.append),
        }
    return {"decisions": decisions, "downstream_invocations": invocations}


if __name__ == "__main__":
    print(json.dumps(evaluate_cases(), indent=2))
