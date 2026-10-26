<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# OSTF 0.3 draft fixtures

These files pin the draft to its examples and to its simplicity budget. [fixtures_test.go](../fixtures_test.go) checks them, and the repository's `go test ./...` runs it.

| Fixture | Pinned to | Fails when |
| --- | --- | --- |
| [minimal/](minimal/) | The `trace.yaml` block of section 2 | The section 2 example drifts from these bytes, stops validating, or grows past six lines |
| [agent-paragraph.txt](agent-paragraph.txt) | The paragraph of Annex K.1 | The paragraph in the specification changes without this file, loses its version line, or reaches 120 words |
| [agent-policy.txt](agent-policy.txt) | The recommended policy paragraph of Annex K.2 | The paragraph in the specification changes without this file |
| [../example/expected/](../example/expected/) | Annex D.2, Annex F.3 and Annex G | An expected output fails the result schema, or the Annex G block drifts from `context.txt` |

The same test validates the profile example of OSTF-121, the published [security profile](../profiles/security.yaml) and the result examples of Annex D against the schemas, and fails when Core has more than 35 numbered requirements. `minimal/` is its own Go module, like the examples, so the code it links builds and tests on its own.
