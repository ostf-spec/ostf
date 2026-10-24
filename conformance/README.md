<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# OSTF draft conformance fixtures

Suite 0.2.0 targets wire version 0.2 and document revision 0.11. It is a bounded draft suite, not certification or a full Producer, Consumer or Analyzer claim. The [support map](../draft/support.md) applies to every result.

## Run the standalone prototype

From this repository's root, with Python 3.10 or newer and Go 1.27.2:

```sh
python3 conformance/run.py
go test ./...
```

The bootstrap script creates `.venv/`, installs the exact versions and release hashes in [requirements.txt](requirements.txt), then runs the Python checks. PyYAML, tree-sitter, tree-sitter-go and rfc8785 are development dependencies. The script needs PyPI or a prepared wheel cache on first run. It does not call zztrace or use Go modules.

To analyze a directory with the installed environment:

```sh
.venv/bin/python conformance/reader.py PATH_TO_TREE
```

The reader performs no network access, Git invocation or subprocess call. It exits 0 for the bounded common checks passing, 1 for recognized format or semantic errors, and 2 for unsupported constructs. A passing result does not mean the whole Core contract or a product graph check passed.

## Fixture set

| File | Cases | Purpose |
| --- | ---: | --- |
| [item-vectors.json](item-vectors.json) | 6 | `f1` meaning projection and canonical bytes/hashes |
| [code-vectors.json](code-vectors.json) | 21 | Go token streams, signatures, bodies and `go1` hashes |
| [lock-vectors.json](lock-vectors.json) | 12 | Lock grammar, escaping, ordering and rejection cases |
| [repositories.json](repositories.json) | 73 | Small trees with item, document, link, tag and state expectations |
| [schema-cases.json](schema-cases.json) | 24 | Structural root, item, profile and proposed snapshot shape cases |

The standalone Python prototype runs 112 non-schema cases and checks the requirement mappings in [suite.json](suite.json), plus four unsupported-feature guards. It also checks the [minimal example](../examples/minimal/README.md) and [payment retry scenario](../examples/payment-retry/README.md) for two valid links and no diagnostics each. The Go test at the repository root runs all 24 structural schema fixtures with references resolved only from the local `schema/` directory; each example's Go test runs from its own module. Schema shape alone is insufficient for Core conformance.

The fixed token bytes follow the [Go annex](../draft/go.md); their hashes use SHA-256. The initial item and repository expectations were computed with a separate Python projection and RFC 8785 library, then compared with zztrace on the earlier wire draft. The 0.2 observability cases have schema and Python-prototype coverage only. Committed expectations are fixed inputs to this suite. They are not an independent oracle for untested behavior. A changed expectation requires contract review.

## Independence and limits

`reader.py` implements profile and graph checks, alias resolution, risk traversal, lock parsing and state evaluation without importing or calling zztrace. It uses Python/tree-sitter Go rather than the Go reference parser and rfc8785 rather than the reference canonicalizer. Both implementations share project authorship and fixtures, so this is independent code structure, not independent-party qualification.

The prototype supports a bounded default and custom-profile subset, Go package declarations and fixed top-level/subtest source bindings, recursive includes, document headers, YAML/tag links and whole non-Go file hashes. It rejects medical modules, non-Go symbol queries and unsupported Go syntax. External/code.tests/links.keyword settings are reported as skipped. Risk-estimate attributes, recovery records, generic symbol location and full module/profile semantics are not implemented. It is a development probe, not a hardened untrusted-input service.

The suite has partial executable coverage of several `OSTF-` requirements. A complete conformance program, an independently maintained implementation and use by two organizations are open [1.0 gates](../scope.md#versioning).
