# Hook event protocol v1

`anti-slop-engineering exec hook-event` reads a single UTF-8 JSON object from stdin. The caller launches it from the trusted workspace root. The project owner sets the action contract through the existing `exec parse-prompt` command. The hook reads that contract and has no ticket, prompt, configuration-write, or logging operation.

| Input field | Accepted value |
| --- | --- |
| `schema_version` | Integer `1` |
| `agent`, `tool`, `correlation_id` | Adapter-chosen identifiers with 1–128 ASCII letters, digits, dots, underscores, colons, or hyphens |
| `phase` | `pre_tool` or `post_tool` |
| `operation` | `read`, `write`, or `unknown`. Use a read or write classification only for a known structured file operation |
| `target_paths` | At most 32 nonblank path strings, each at most 1024 characters. Structured file operations need at least one target. Paths may be absolute in the workspace or relative to it |
| `payload_trust` | `untrusted`. Adapters keep native tool content, arguments, and outputs outside the envelope |

The size cap is 64 KiB. Duplicate, missing, and unknown fields are errors. The adapter owns phase and operation classification. Native events and model-supplied arguments do not get to choose how they are classified.

The decision contains `schema_version`, `correlation_id` (or null on invalid input), `decision`, `reason_code`, and `message`. `allow` means this repository policy did not prohibit the action and the host should apply its own permissions. `warn` is advisory. `block` applies before a supported tool action. A post-action policy violation yields `warn` and cannot undo changes. `error` reports invalid input or unavailable local policy. Adapters own host timeouts and report any ability to stop on execution failure separately.

| Exit | Result |
| --- | --- |
| 0 | `allow` or `warn` |
| 1 | `error` |
| 2 | `block` |

The protocol evaluates the existing local contract with a read-only operation. Repeating an event against the same policy and filesystem returns the same decision and does not alter state. This adapter boundary assumes the hook launcher, workspace root, and local contract are controlled by a trusted operator. It does not sandbox tools or monitor file changes outside the registered action. Generic shell and external tool arguments are outside v1's file classification.
