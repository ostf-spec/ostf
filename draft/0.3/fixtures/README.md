<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# OSTF 0.3 draft fixtures

These files pin the draft to its examples and to the simplicity budget of the [agent-readiness plan](../plan-agent-readiness.md). [fixtures_test.go](../fixtures_test.go) checks them, and the repository's `go test ./...` runs it.

| Fixture | Pinned to | Fails when |
| --- | --- | --- |
| [minimal/](minimal/) | The `trace.yaml` block of section 2 | The section 2 example drifts from these bytes, stops validating, or grows past six lines |
| [agent-paragraph.txt](agent-paragraph.txt) | The paragraph of Annex F.1 | The paragraph in the specification changes without this file, loses its version line, or reaches 120 words |
| [agent-policy.txt](agent-policy.txt) | The recommended policy paragraph of Annex F.2 | The paragraph in the specification changes without this file |
| [../example/expected/](../example/expected/) | Annex C.2, Annex I.3 and Annex J | An expected output fails the result schema, or the Annex J block drifts from `context.txt` |

The same test validates the profile example of OSTF-121, the published [security profile](../profiles/security.yaml) and the result examples of Annex C against the schemas, and fails when Core has more than 35 numbered requirements. `minimal/` is its own Go module, like the examples, so the code it links builds and tests on its own.
