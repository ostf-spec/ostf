<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# OSTF: Open Software Traceability Format

OSTF is a plain-text format that records why code exists. A repository declares its requirements, risks, threats, controls, design decisions and verifications as items with stable IDs, links them to the functions that implement them and the tests that verify them. A person, tool or coding agent can then answer three questions from the repository alone, for the items it declares and the links a reader of its languages binds: why does this code exist, which tests verify this requirement, and which items a change touches.

**Status:** working draft 0.3, wire version `ostf: "0.3"`. It is candidate text for OSTF 1.0, not 1.0: the release gate needs a second, independently maintained implementation and use by two organizations. It is not a certification program.

## What it looks like

```yaml
ostf: "0.3"
items:
  - id: R-ADD
    text: Add two values.
    code: [math.go#Add]
    tests: [math_test.go#TestAdd]
```

`math.go#Add` implements `R-ADD` and `math_test.go#TestAdd` verifies it. Code can also link itself with a `// @req R-ADD` comment. When a change edits `Add`, `ostf check --base` lists the function beside the text of `R-ADD`, the test to run, and the last commits that changed each side; the pull request that shows them is where someone confirms that the two still match. A link says that the code serves the item, not that the test passed or the code is correct.

A changed definition fails nothing: `check` fails on errors and broken links, and what a change touches is information for the review.

## Start in ten minutes

1. Next to your code, write `trace.yaml` with your first requirement and the function and test that carry it, as above. Go, TypeScript, JavaScript and Python are read; for other files, link the whole file.
2. Install the reference checker, which needs Python 3.12 or newer:

   ```sh
   pipx install git+https://github.com/ostf-spec/ostf
   ```

3. Run `ostf check`. It reports any error, such as an unknown ID or a function that does not exist, and counts your items and links; `ostf check --base main` also lists what your branch changed and the items each change serves.
4. Paste the [agent paragraph](draft/0.3/fixtures/agent-paragraph.txt) into your `AGENTS.md`, replacing each `<tool>` with `ostf`, and after it your policy for agents, or the [recommended one](draft/0.3/fixtures/agent-policy.txt). Coding agents then run `ostf check --base` before they finish, which also shows what every function they changed serves.
5. Check every push and pull request with `.github/workflows/ostf.yml`; the action fails on an error or a broken link, prints in a pull request's log what the change touches, which never fails it, and uploads the findings to code scanning:

   ```yaml
   name: OSTF
   on: [push, pull_request]
   permissions:
     contents: read
     security-events: write
   jobs:
     check:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v5
         - uses: ostf-spec/ostf@main
   ```

6. Optionally, check before each commit with [pre-commit](https://pre-commit.com):

   ```yaml
   repos:
     - repo: https://github.com/ostf-spec/ostf
       rev: main
       hooks:
         - id: ostf-check
   ```

`ostf context FILE#FUNCTION` shows why a function exists, what it controls and which tests verify it. Requirements kept in Doorstop or StrictDoc can be [converted](draft/0.3/tools/README.md). Pin `@main` and `rev: main` to a commit in production use.

## Read the draft

| Document | Purpose |
| --- | --- |
| [Specification](draft/0.3/ostf.md) | The format in 26 numbered requirements, the Go, TypeScript and Python annexes and the diagnostics, and optional annexes for derived links, SARIF output, the command profile for coding agents, context rendering and results for an index |
| [Schemas](draft/0.3/schema/) and [derived-link grammar](draft/0.3/trace-derived.abnf) | JSON Schema 2020-12 for trace, profile and result files, and ABNF for `trace.derived`, the file of the optional Annex E |
| [Example](draft/0.3/example/README.md) | A refund limit that controls a risk, a payment retry owned by an issue tracker, and an encryption rule carried by an infrastructure file and verified by a review, with derived links and the expected tool output |
| [Fixtures](draft/0.3/fixtures/README.md) | Files that pin the specification's examples and its size budget |
| [Reader and cases](draft/0.3/conformance/README.md) | The reference reader, installed as `ostf`, with the `check` and `context` commands, and hand-written cases, conformance suite version 2 |
| [Converters](draft/0.3/tools/README.md) | Doorstop to OSTF and back, and StrictDoc to OSTF, with what each loses |

The trials and the records behind this draft are under [project/](project/).

Schemas use the `https://ostf.dev/draft/0.3/` identifier namespace and resolve from this repository; validation never fetches them. zztrace, the project's own tool, reads wire 0.3 with separately written code; both implementations pass the same cases.

## Run the checks

With Python 3.12 or newer and Go 1.27.2, from the repository root:

```sh
python3 draft/0.3/conformance/run.py
go test ./...
(cd draft/0.3/example && go test ./...)
```

The Python script creates an ignored virtual environment, installs hash-pinned dependencies and runs the reader against the span vectors, the example's expected output, the fixtures and the cases, then checks the converters on their samples. `go test ./...` validates the examples and expected outputs against the schemas and checks the specification's size budget.

## Participate

Review the [specification](draft/0.3/ostf.md) and try the example with another implementation. Use the [contribution guide](CONTRIBUTING.md) and [issue templates](https://github.com/ostf-spec/ostf/issues/new/choose) for feedback; [draft governance](GOVERNANCE.md) explains how changes are decided. The draft remains 0.x until the [release gate](draft/0.3/ostf.md#9-versioning) is met. `ostf.dev` is reserved for the standard; this repository is the draft's public home. A preliminary trademark search remains separate work; publication is not a claim of name clearance.

For a vulnerability, use the [private security reporting path](SECURITY.md). Community participation follows the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

Specification prose is [CC BY 4.0](LICENSE-CC-BY-4.0.txt). Schemas, grammar, fixtures and executable tools are [Apache 2.0](LICENSE-APACHE-2.0.txt). The [file-level license map](LICENSE.md) gives the exact split. Publication does not imply trademark registration or standards-body endorsement.
