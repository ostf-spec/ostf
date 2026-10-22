<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# OSTF: Open Software Traceability Format

OSTF gives tools a shared way to answer three questions about a source tree: why does this code exist, which tests verify a requirement, and which links need another review? It records requirements and their links to code and tests in plain text files. Tools may store and serve the same graph in a database; OSTF specifies the files they exchange.

**Status:** public working draft, document revision 0.10, wire version `ostf: "0.1"`, conformance suite 0.1.3. This is a review draft. It is not OSTF 1.0, a certification program or a claim of full Core conformance.

## What it looks like

A small repository can declare its items and links in `trace.yaml`:

```yaml
ostf: "0.1"
items:
  - id: R-ADD
    text: Add two values.
    code: [math.go#Add]
    tests: [math_test.go#TestAdd]
```

`math.go#Add` names a Go function that implements `R-ADD`; `math_test.go#TestAdd` names a test that verifies it. Paths are relative to the source tree. A separate `trace.lock` records the fingerprints present when each link was rechecked. A matching stamp means those inputs have not changed under the draft's fingerprint rules. It does not establish that the test passed or the code is correct.

The [complete example](examples/minimal/README.md) includes real Go source and a valid lock file. Larger repositories can split items into included files, and tools can declare links with `@req` comments in code. Start with the example and [scope](scope.md) to evaluate the format; use the Core draft and conformance suite when implementing it.

## How the entities connect

This illustrative graph uses the default profile. Each arrow points from a detail to the purpose it serves:

```mermaid
flowchart LR
    subgraph ostfItems["OSTF items"]
        need["Need"]
        requirement["Requirement"]
        design["Design"]
        risk["Risk"]
        verification["Verification item"]
    end
    subgraph sourceAnchors["Source tree anchors"]
        fn["Function"]
        runnerTest["Runner test"]
    end

    requirement -->|refines| need
    design -->|refines| requirement
    requirement -->|controls| risk
    verification -->|verifies| requirement
    fn -->|implements| design
    runnerTest -->|verifies| requirement
```

An item's `code` or `tests` field declares the link in YAML, but the relationship points from the source anchor to the item. `trace.lock` records endpoint fingerprints for stamped links; an Analyzer compares them with the selected source tree to report `valid`, `suspect`, `unstamped` or `broken`. The [Core draft](draft/core.md#relationships-and-identities-in-code) defines the link rules.

## Read the draft

| Document | Purpose |
| --- | --- |
| [Example](examples/minimal/README.md) | A complete source tree with two valid links |
| [Scope](scope.md) | Core, optional modules, deferred extensions and tool boundaries |
| [Core contract](draft/core.md) | Versioned draft rules, deferred proposals and release gates with stable `OSTF-` IDs |
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
(cd examples/minimal && go test ./...)
```

The Python script creates an ignored virtual environment, installs exact hash-pinned dependencies and runs 107 non-schema cases through the independent-code prototype. The standalone Go test runs 18 structural schema fixtures with a local-only resolver; it does not import zztrace. The prototype and zztrace reference implementation share project authorship; their agreement is not independent-party qualification. See the [suite details](conformance/README.md) before making a conformance claim.

## Participate

Review the [Core contract](draft/core.md) and try the fixtures with another implementation. Use the [contribution guide](CONTRIBUTING.md) and [issue templates](https://github.com/ostf-spec/ostf/issues/new/choose) for feedback; [draft governance](GOVERNANCE.md) explains how changes are decided. The draft remains 0.x until the [independent implementation and two-organization adoption gates](scope.md#versioning) are met. `ostf.dev` is reserved for the standard; this repository is the draft's public home. A preliminary trademark search remains separate work; publication is not a claim of name clearance.

For a vulnerability, use the [private security reporting path](SECURITY.md). Community participation follows the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

Specification prose is [CC BY 4.0](LICENSE-CC-BY-4.0.txt). Schemas, grammar, fixtures and executable tools are [Apache 2.0](LICENSE-APACHE-2.0.txt). The [file-level license map](LICENSE.md) gives the exact split. Publication does not imply trademark registration or standards-body endorsement.
