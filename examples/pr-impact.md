<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# From a pull request diff to OSTF items

This informative example uses the real [PR #2](https://github.com/ostf-spec/ostf/pull/2) in this repository. Its recorded merge result introduced the [payment retry example](payment-retry/README.md) across 11 files. This document compares that result with its parent; the two commits are reproducible views of the merged change, not a claim about the PR branch refs before merge. It describes an impact analysis a Git-aware tool could produce. OSTF Core 0.2 does not serialize PRs or perform diff-to-anchor or dependency analysis.

## Keep the identities separate

| Identity | Example | Role |
| --- | --- | --- |
| PR | `ostf-spec/ostf#2` | Review container. Its branch and displayed diff can change before merge. |
| Compared Git views | before `8649b7f3c25a754dd2b5336008842beb6974203e`, after `063986cf2d1ed992495e7842ef88ecf68e5c96b1` | Reproduce the merged change's diff. In a live PR, record the exact base tip, head and merge base used for the analysis; PR number alone is insufficient. |
| Changed location | `examples/payment-retry/pay/charge.go`, head line 52 | A line in that diff. It is a locator for the recorded head, not a durable OSTF key. |
| Code anchor | `pay/charge.go#Service.Charge` | Definition within the OSTF root `examples/payment-retry/`. Its path and symbol form the link source. |
| OSTF item | `R-PAY-RETRY` | Stable requirement ID within this repository's OSTF namespace. |
| OSTF link | `pay/charge.go#Service.Charge implements R-PAY-RETRY` | Typed relationship. `trace.lock` fingerprints its endpoints after a recheck. |

The repository path in a Git diff includes `examples/payment-retry/`. The anchor in `trace.yaml` is relative to the example's OSTF root, so it starts at `pay/`. An analyzer must know that root before joining Git paths to anchors.

## Map every changed location

The PR added an entire Go file, so one Git hunk covers multiple definitions. A tool must split the hunk by symbol spans. The rows below select representative changed lines at the recorded head:

| Changed location in PR #2 | Resolved anchor | Direct OSTF links | Impact result |
| --- | --- | --- | --- |
| `pay/charge.go:52`, stores the receipt | `pay/charge.go#Service.Charge` | `implements R-PAY-RETRY` | Directly reaches `R-PAY-RETRY` and its verifying test. |
| `pay/retry_test.go:27`, checks the retry | `pay/retry_test.go#TestSameKey` | `verifies R-PAY-RETRY` | Directly reaches the same item. |
| `pay/charge.go:29`, initializes the map | `pay/charge.go#NewService` | None in this example | Unmapped as a direct OSTF link. It still affects the retry path; dependency analysis or review must find that relationship. |
| Documentation and CI files | File or no applicable source anchor | None in this example | Report as changed and unlinked, with an explicit scope or review disposition. |

The first row is a single source line inside a linked method. The OSTF node remains the requirement; the source line is an observed location beneath an anchor. A definition can have two `implements` links. For example, the following **hypothetical addition** to the payment example would be valid Core YAML; it was not part of PR #2:

```yaml
ostf: "0.2"
items:
  - id: R-PAY-RETRY
    text: A retry with the same key returns the first result without a second charge.
    code: [pay/charge.go#Service.Charge]
  - id: R-PAY-AMOUNT
    text: Reusing an idempotency key with a different amount is rejected.
    code: [pay/charge.go#Service.Charge]
```

This creates two separate links because their target IDs differ. A changed line inside `Service.Charge` reaches both items through the symbol anchor; a reviewer still decides which behaviors the line could affect. A PR can also change many definitions in many files, each reaching different items. The result is a many-to-many mapping, not a single PR-to-item key.

## Proposed impact procedure

1. Capture the repository and PR locator, exact base and head Git object IDs, and the merge base used for the PR diff. GitHub presents a three-dot PR comparison from merge base to head; a later push or base change requires a new analysis. Do not use a moving branch name or PR number as the source revision.
2. Diff the recorded views. Preserve each file's old and new path, change kind, and old/new line ranges. For additions use the head side; for deletions inspect the base side; for edits inspect both. Resolve each changed line against language-defined symbol spans. A hunk can cross more than one symbol. Preserve unresolved locations instead of assigning the whole hunk to a convenient nearby symbol.
3. Join resolved anchors to all OSTF links in the corresponding source-tree view. Report direct item IDs and linked tests. Preserve the path from changed location to anchor to link to item, including zero-link and multi-link results. Apply repository root mapping before comparing paths.
4. Separately analyze calls, configuration, generated code and other dependencies that can affect linked anchors without editing them. Mark these as inferred or reviewer-confirmed impact, never as a direct Core link. The [constructor-change example](change-impact.md) shows why this step matters.
5. Recheck relevant links and run selected tests against the exact candidate source and OSTF view. A `trace.lock` state is scoped freshness, not proof that a test ran. Baseline-bound results belong to the [evidence proposal](../draft/evidence.md) or the tool's CI records.

This procedure is a proposed tool workflow. Core supplies item IDs, anchors and links; it neither defines a portable PR impact report nor guarantees completeness of inferred dependencies. A useful report should expose every changed location's disposition, including unresolved and unlinked code, so that a reviewer can see what was actually covered.
