<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# OSTF: Open Software Traceability Format

OSTF is a plain-text format that records why code exists. A repository declares its requirements, risks, threats, controls, design decisions and verifications as items with stable IDs, links them to the functions that implement them and the tests that verify them, and keeps a lock file that shows which links were rechecked since either end last changed. Any tool, person or coding agent that can read YAML can then answer three questions from the repository alone: why does this code exist, which tests verify this requirement, and which links need another look.

**Status:** working draft, wire version `ostf: "0.3"`, document revision 0.14. It is candidate text for OSTF 1.0, not 1.0: the release gate needs a second, independently maintained implementation and use by two organizations. It is not a certification program.

## What it looks like

```yaml
ostf: "0.3"
items:
  - id: R-ADD
    text: Add two values.
    code: [math.go#Add]
    tests: [math_test.go#TestAdd]
```

`math.go#Add` implements `R-ADD` and `math_test.go#TestAdd` verifies it. Code can also link itself with a `// @req R-ADD` comment. A tool that rechecks a link writes the fingerprints of both ends to `trace.lock`; when the requirement text or the function body changes, the link becomes `suspect` until someone rechecks it. A valid link means only that its inputs did not change. It does not mean the test passed or the code is correct.

Under the default, every edit to a linked function's body makes its link suspect, a renamed variable or a new log line included, and `check` then fails until someone rechecks and stamps the link. The recheck costs one `context` call, but a team that stamps without reading gets a lock that says nothing. Two things keep that in view: `stamp` takes named links only and has no option to restamp everything, and a profile can set `fingerprints.bodyChange: risk` so that body edits are rechecked only for code that controls a declared risk (OSTF-144).

## Start in ten minutes

1. Next to your code, write `trace.yaml` with your first requirement and the function and test that carry it, as above. Go, TypeScript, JavaScript and Python are read; for other files, link the whole file.
2. Install the reference checker, which needs Python 3.12 or newer:

   ```sh
   pipx install git+https://github.com/ostf-spec/ostf
   ```

3. Run `ostf check`. It lists your links as having no state yet. Stamp each one you have checked by hand, quoting it as `check` prints it and naming yourself with `--by`, and commit the `trace.lock` it writes:

   ```sh
   ostf stamp --by "person:$USER" 'math.go#Add implements R-ADD' 'math_test.go#TestAdd verifies R-ADD'
   ```

4. Paste the [agent paragraph](draft/0.3/fixtures/agent-paragraph.txt) into your `AGENTS.md`, replacing each `<tool>` with `ostf`, and after it your policy for agents, or the [recommended one](draft/0.3/fixtures/agent-policy.txt). Coding agents then run `ostf check --base` before they finish, which also shows what every function they changed serves.
5. Check every push and pull request with `.github/workflows/ostf.yml`; the action fails on an error or a suspect or broken link, and in a pull request whose base branch has a lock file also on an unstamped link or a missing lock (`check --strict`), shows the impact of a pull request in its log and uploads the findings to code scanning:

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
| [Specification](draft/0.3/ostf.md) | The format in 35 numbered requirements, the Go annex, the lock grammar and diagnostics, and optional annexes for SARIF output, the command profile for coding agents and context rendering |
| [Schemas](draft/0.3/schema/) and [lock grammar](draft/0.3/trace-lock.abnf) | JSON Schema 2020-12 for trace, profile and result files, and ABNF for `trace.lock` and `trace.derived` |
| [Example](draft/0.3/example/README.md) | A refund limit that controls a risk, a payment retry owned by an issue tracker, and an encryption rule carried by an infrastructure file and verified by a review, with a real lock file and the expected tool output |
| [Fixtures](draft/0.3/fixtures/README.md) | Files that pin the specification's examples and its size budget |
| [Reader and cases](draft/0.3/conformance/README.md) | The reference reader, installed as `ostf`, with the `check`, `context` and `stamp` commands, and hand-written cases |
| [Converters](draft/0.3/tools/README.md) | Doorstop to OSTF and back, and StrictDoc to OSTF, with what each loses |
| [Agent-readiness plan](draft/0.3/plan-agent-readiness.md) | Five phases that made OSTF work for coding agents without growing its core, all done, with each phase's outcome and the two scorecard rows lowered |
| [Agent-first plan](draft/0.3/plan-agent-first.md) | Seven phases toward wire 0.4 drawn from two independent reviews of 0.3, from fixing the defects they found to trials against a baseline without OSTF; Phase 0, the fixes, is done in revision 0.13, Phase 1, the [baseline](draft/0.3/trials/baseline.md) against a plain requirements file, is published, and Phase 2's pre-work, with the [replay under candidate defaults](draft/0.3/trials/baseline-defaults.md), is done in revision 0.14 |
| [Agent trials](draft/0.3/trials/protocol.md) | The protocol, fixtures, harness and every result of coding agents from two vendors, and a small model, doing eight tasks with only the agent paragraph to go on |
| [Decision record](draft/0.3/decisions.md) | The rulings taken while carrying out the plan: each ambiguity or defect, the rule that settled it and the requirement it touched |

Schemas use the `https://ostf.dev/draft/0.3/` identifier namespace and resolve from this repository; validation never fetches them. zztrace, the project's own tool, reads wire 0.3 with separately written code; both implementations pass the same cases.

## Run the checks

With Python 3.12 or newer and Go 1.27.2, from the repository root:

```sh
python3 draft/0.3/conformance/run.py
go test ./...
(cd draft/0.3/example && go test ./...)
```

The Python script creates an ignored virtual environment, installs hash-pinned dependencies and runs the reader against the published hash vectors, the example's expected output, the fixtures and the cases, then checks the converters on their samples. `go test ./...` validates the examples and expected outputs against the schemas and checks the specification's size budget.

## Participate

Review the [specification](draft/0.3/ostf.md) and try the example with another implementation. Use the [contribution guide](CONTRIBUTING.md) and [issue templates](https://github.com/ostf-spec/ostf/issues/new/choose) for feedback; [draft governance](GOVERNANCE.md) explains how changes are decided. The draft remains 0.x until the [release gate](draft/0.3/ostf.md#10-versioning) is met. `ostf.dev` is reserved for the standard; this repository is the draft's public home. A preliminary trademark search remains separate work; publication is not a claim of name clearance.

For a vulnerability, use the [private security reporting path](SECURITY.md). Community participation follows the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

Specification prose is [CC BY 4.0](LICENSE-CC-BY-4.0.txt). Schemas, grammar, fixtures and executable tools are [Apache 2.0](LICENSE-APACHE-2.0.txt). The [file-level license map](LICENSE.md) gives the exact split. Publication does not imply trademark registration or standards-body endorsement.
