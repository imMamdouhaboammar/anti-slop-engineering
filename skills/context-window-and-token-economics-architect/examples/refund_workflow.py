# SPDX-License-Identifier: MIT
"""Small, deterministic example of retrieval with source-aware cache reuse."""

POLICIES = {
    ("tenant-a", "r1"): {"days": 30, "source": "refund-policy:r1"},
    ("tenant-a", "r2"): {"days": 14, "source": "refund-policy:r2"},
}


def render_context(source, *, include_full_policy):
    passage = f"{source['source']}: Refund requests must arrive within {source['days']} days."
    if include_full_policy:
        return passage + (
            " Receipts are emailed after purchase. Gifts require a proof of purchase."
            " Support opens weekdays. Damaged products have a separate replacement policy."
        )
    return passage


def retrieve(tenant, revision, scope, schema, cache):
    if scope != "refund:read":
        return {"status": "no_evidence"}
    key = (tenant, revision, scope, schema)
    if key not in cache:
        source = POLICIES.get((tenant, revision))
        if source is None:
            return {"status": "no_evidence"}
        cache[key] = {"status": "ok", "days": source["days"], "source": source["source"]}
    return cache[key]


def main():
    import json

    cache = {}
    baseline = retrieve("tenant-a", "r1", "refund:read", "refund-v1", cache)
    candidate = retrieve("tenant-a", "r2", "refund:read", "refund-v1", cache)
    revoked = retrieve("tenant-a", "r2", "revoked", "refund-v1", cache)
    source = POLICIES[("tenant-a", "r2")]
    report = {
        "before_revision": baseline,
        "current_revision": candidate,
        "after_revocation": revoked,
        "full_context_units": len(render_context(source, include_full_policy=True).split()),
        "narrow_context_units": len(render_context(source, include_full_policy=False).split()),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
