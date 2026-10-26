<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Contributing to OSTF

OSTF is a review draft. Read the [specification](draft/0.3/ostf.md) and [draft governance](GOVERNANCE.md) before proposing a normative change. Use an [issue template](https://github.com/ostf-spec/ostf/issues/new/choose) for ambiguities or reader disagreements. Include the smallest `trace.yaml` or source file example, the expected result and the relevant versions. Discuss a larger extension in an issue before building it.

For a pull request that changes a requirement or annex rule, identify the affected `OSTF-` IDs, update the relevant schemas and fixed conformance cases, and explain wire compatibility and claim impact. Preserve existing IDs, and never reuse one. Keep normative rules in the specification, with examples marked informative. Respect the simplicity budget: no new Core key and at most 35 numbered requirements. Update `CITATION.cff` when the cited draft changes.

Run `python3 draft/0.3/conformance/run.py`, `go test ./...` and `go vet ./...` from the repository root. If the example changes, run `go test ./...` from `draft/0.3/example` too. These checks cover the cases written so far, not complete conformance. Pull requests should explain any failed check or intentionally unqualified case.

Contributions are submitted under the license for the files changed: prose under CC BY 4.0, and schemas, grammar, fixtures and tools under Apache 2.0. The [file-level license map](LICENSE.md) covers files without SPDX comments. Submit only work you have the right to license, keep third-party quotations short and identify their sources. A merged change does not certify an implementation or advance the wire version. Participants follow the [Code of Conduct](CODE_OF_CONDUCT.md); report vulnerabilities through the [security policy](SECURITY.md).
