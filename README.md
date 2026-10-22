<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# OSTF: Open Software Traceability Format

OSTF is a working draft of an open interchange format for requirements, risks, code anchors, tests and link freshness. It serializes plain text files against a source tree. Tools may store and serve the same graph in a database. A fresh link means its fingerprinted inputs have not changed since a recorded recheck; it does not establish correctness, approval, test execution or compliance.

**Status:** document revision 0.10, wire version `ostf: "0.1"`, conformance suite 0.1.3. This is a review draft. It is not OSTF 1.0, a certification program or a claim of full Core conformance.

## Read the draft

| Document | Purpose |
| --- | --- |
| [Core contract](draft/core.md) | Normative draft requirements `OSTF-001` through `OSTF-023` |
| [Scope](scope.md) | Core, optional modules, deferred extensions and tool boundaries |
| [Go language annex](draft/go.md) and [Go runner annex](draft/go-tests.md) | Symbol, token and test identities |
| [Schemas](schema/) and [lock grammar](draft/trace-lock.ebnf) | Structural entry points and exact lock syntax |
| [Conformance suite](conformance/README.md) | Fixed vectors, a standalone Python prototype and declared limits |
| [Support map](draft/support.md) | Implemented, proposed and unqualified behavior |
| [White paper](white-paper.md) | Rationale and invitation to review |

The schemas use the `https://ostf.dev/draft/0.1/` identifier namespace. Validation resolves schema references from this repository; the namespace does not require a network fetch. The format's first implementation is zztrace, but its commands, permissions and internal storage are outside OSTF.

## Run the standalone draft checks

With Python 3.10 or newer and Go 1.27.2:

```sh
python3 conformance/run.py
go test ./...
```

The Python script creates an ignored virtual environment, installs exact hash-pinned dependencies and runs 107 non-schema cases through the independent-code prototype. The standalone Go test runs 18 structural schema fixtures with a local-only resolver; it does not import zztrace. The prototype and zztrace reference implementation share project authorship; their agreement is not independent-party qualification. See the [suite details](conformance/README.md) before making a conformance claim.

## Participate

Review the [Core contract](draft/core.md) and try the fixtures with another implementation. Once the repository is public, report ambiguities through GitHub issues. The draft remains 0.x until the [independent implementation and two-organization adoption gates](scope.md#versioning) are met. `ostf.dev` is reserved for the standard; this repository is prepared as the draft's public home.

## License

Specification prose is [CC BY 4.0](LICENSE-CC-BY-4.0.txt). Schemas, grammar, fixtures and executable tools are [Apache 2.0](LICENSE-APACHE-2.0.txt). [License scope](LICENSE.md) gives the file-level rule. Publication does not imply trademark registration or standards-body endorsement.
