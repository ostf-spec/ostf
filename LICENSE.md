<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# OSTF licensing

OSTF uses two licenses by file, rather than offering every file under both licenses. GitHub may label this repository's license "Other" because a single license badge cannot express the file-level split.

| Files | License |
| --- | --- |
| `README.md`, `scope.md`, `white-paper.md`, `CONTRIBUTING.md`, `GOVERNANCE.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CITATION.cff`, this page, other Markdown prose under `draft/`, `conformance/` and `examples/`, and GitHub issue or pull request templates | [CC BY 4.0](LICENSE-CC-BY-4.0.txt), SPDX `CC-BY-4.0` |
| JSON schemas and conformance fixtures, EBNF grammar, Python and Go code, example source and serialized data, dependency manifests and sums, GitHub configuration YAML, `.gitattributes` and `.gitignore` | [Apache 2.0](LICENSE-APACHE-2.0.txt), SPDX `Apache-2.0` |

SPDX identifiers in individual files take precedence. JSON fixtures, Go module files and other formats without an SPDX comment follow the table. The initial OSTF specification prose is credited to Medoya LLC. When reusing that prose, give appropriate credit, link to [CC BY 4.0](LICENSE-CC-BY-4.0.txt), and indicate changes as the license requires. The [NOTICE](NOTICE) preserves the initial Apache attribution. Dependencies retain their own licenses. These licenses do not grant rights to an OSTF trademark or imply standards-body endorsement or certification.
