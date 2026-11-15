# Refund policy retrieval comparison

Return the current refund deadline as an integer and cite the policy passage by source ID. If current evidence is absent or unauthorized, return `no_evidence`.

| Input | Baseline | Candidate |
| --- | --- | --- |
| Retrieval | Entire authorized policy and receipt guide | Authorized refund passage with source ID and revision |
| Cache identity | Tenant and query | Tenant, document revision, authorization scope, and output schema revision |
| Offline rendered input | Refund passage, receipt instructions, and unrelated policy | Refund passage with its provenance |
| Offline budget | 20 whitespace-delimited units | The same 20-unit budget |

The fixture checks the answer against the authorized source, then exercises a revision change from 30 to 14 days, access revocation, a second tenant without evidence, and a schema revision. It reports input size with a whitespace counter for reproducibility. Use the selected API's tokenizer or returned usage for real token counts and billing.

For a live comparison, fix the model and schema and stream both variants over the same sanitized, labeled task set. Compare cold and warm runs separately. Set the latency budget against the service objective and require every refund deadline in this example to match its cited revision.
