<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Go runner annex: identities

Document revision 0.5, wire version 0.1, 2026-10-19. Draft annex for OSTF-012. Go test identity is the runner's reported test name, including slash-separated subtest components. See the official [testing package](https://pkg.go.dev/testing#hdr-Subtests_and_Sub_benchmarks).

An anchor `path/pump_test.go#TestLimit` names the top-level declaration. `TestLimit/over_max` names the Go runner identity below that declaration. The reference locator binds a subtest identity to the top-level function for source location/fingerprinting; it does not infer that a dynamically named subtest executed. A freshness check of that anchor therefore fingerprints the declaration, while report binding requires the exact runner identity.

This annex defines stored identity and source binding, not command syntax or a standardized evidence-report format. A suite/file selection or successful process exit is not proof that an individual case passed. The retained report must distinguish executed, absent, failed and skipped identities under the tool's separate evidence contract.

Both readers qualify the stored identity and source fingerprint binding of a fixed subtest anchor, including a missing parent declaration. The source locator binds the slash-suffixed runner identity to the top-level declaration; it does not prove that a dynamically or nested named subtest executed. Execution remains a separate evidence question.
