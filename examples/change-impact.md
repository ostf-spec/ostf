<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# A change outside the linked function

This is an informative follow-on to the runnable [payment retry example](payment-retry/README.md). It is a proposed workflow, not another executable OSTF fixture. It shows what the current format can say and where other tools must contribute.

For a real multi-file Git diff and its direct line-to-anchor-to-item mapping, see the [PR #2 impact example](pr-impact.md).

In the runnable tree, `R-PAY-RETRY` links to `pay/charge.go#Service.Charge` and `pay/retry_test.go#TestSameKey`. Now imagine a later pull request changes `NewService` so that it no longer initializes the receipts map. `Service.Charge` and `TestSameKey` remain byte-for-byte unchanged. A charge can panic when it tries to store a receipt.

The existing `trace.lock` entries can still report **valid** for those two links. Their endpoint fingerprints do not cover `NewService`. Under [OSTF-019](../draft/core.md#meaning-and-freshness), valid means scoped link freshness, not unchanged behavior, a passing test or release approval.

| Step | What happens | Boundary |
| --- | --- | --- |
| Agent opens a pull request | The PR names the requirement and includes the constructor edit | PR creation and permissions are tool behavior. OSTF supplies the stable requirement and code/test identities |
| Impact is assessed | A dependency analyzer or a reviewer notices that `Service.Charge` depends on initialization in `NewService` | Transitive dependency discovery is tool behavior. The existing OSTF links identify the requirement and test to revisit once the impact is found |
| Verification runs | CI runs `TestSameKey` against the exact candidate revision and retains the result and log | Core names a runner test but does not record execution. A proposed [evidence reference](../draft/evidence.md) could make the result portable |
| A decision is made | Reviewers decide whether the fix, tests and risk assessment justify merging | Approval and merge gates belong to the organization's tools and process |
| A source requirement lives in Jira | A read-only adapter captures the exact approved revision used for the change | The [external-item proposal](../draft/external.md) is not implemented by current Core readers |

The same boundary applies in safety work: a helper or configuration can change without changing a tracked function's fingerprint. A future medical profile may add domain vocabulary and validation rules, but it cannot turn a valid Core stamp into a safety or compliance claim.

This example is a useful pilot challenge. Change only the constructor, keep the tracked anchors unchanged, and require the workflow to find the affected requirement, run verification against the candidate revision and obtain a separate human decision. The current OSTF conformance suite does not claim to test that complete workflow.
