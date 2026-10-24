<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# OSTF 0.3 reader and cases

[reader.py](reader.py) reads wire 0.3: a Go Analyzer with the `check` and `context` commands of [Annex I](../ostf.md#annex-i-normative-optional-command-profile). It is independent code ported from the [0.2 prototype](../../../conformance/README.md); it does not import zztrace, call Git, start a subprocess or touch the network. It is a development probe, not a hardened service: Go syntax comes from tree-sitter-go plus UTF-8 and escape checks, so some files the Go compiler rejects still parse, and reads are not protected against a tree that changes during a run. It does not yet implement `stamp`, `check --base` or SARIF output.

From the repository root, after `python3 conformance/run.py` has prepared `.venv/`:

```sh
.venv/bin/python draft/0.3/conformance/check.py
```

```sh
cd draft/0.3/example
../../../.venv/bin/python ../conformance/reader.py check
../../../.venv/bin/python ../conformance/reader.py context refund.go#CheckRefundLimit
```

[check.py](check.py) runs:

| Check | What it pins |
| --- | --- |
| The 0.2 item, Go and lock vectors | f1, go1 and `trace.lock 1` are unchanged (budget rule 5) |
| [example/expected/](../example/expected/) | `check` and `context` JSON and the Annex J text, byte for byte |
| [fixtures/minimal/](../fixtures/minimal/) | Two valid links and no diagnostics |
| [cases.json](cases.json) | Small trees with hand-written expected codes, links with attributes, origins, states and reasons, risk relevance, context selections and Annex J text, and f1 projections |
| The command line | Exit codes 0, 1 and 2, root selection from TARGET, and TARGET kept as given |

Each case names the requirements it exercises. Expectations were written from the specification text, not copied from the reader's output; a changed expectation needs a specification reason. The cases are a first slice of the 0.3 suite, not the suite: converting the 112 cases of 0.2 is the next step of Phase 2 in the [plan](../plan-agent-readiness.md).
