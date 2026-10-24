<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# OSTF 0.3 reader and cases

[reader.py](reader.py) reads wire 0.3: a Go Analyzer with the `check` and `context` commands of [Annex I](../ostf.md#annex-i-normative-optional-command-profile). It is independent code ported from the 0.2 Python prototype; it does not import zztrace, call Git, start a subprocess or touch the network. It is a development probe, not a hardened service: Go syntax comes from tree-sitter-go plus UTF-8 and escape checks, so some files the Go compiler rejects still parse, and reads are not protected against a tree that changes during a run. It does not yet implement `stamp`, `check --base` or SARIF output.

From the repository root, with Python 3.10 or newer:

```sh
python3 draft/0.3/conformance/run.py
```

The script creates an ignored `.venv/` at the repository root, installs the exact versions and release hashes in [requirements.txt](requirements.txt), then runs [check.py](check.py). It needs PyPI or a prepared wheel cache on first run. To use the reader directly:

```sh
cd draft/0.3/example
../../../.venv/bin/python ../conformance/reader.py check
../../../.venv/bin/python ../conformance/reader.py context refund.go#CheckRefundLimit
```

[check.py](check.py) runs:

| Check | What it pins |
| --- | --- |
| [vectors/](vectors/) | The item, Go and lock vectors published with 0.2: f1, go1 and `trace.lock 1` are unchanged (budget rule 5) |
| [example/expected/](../example/expected/) | `check` and `context` JSON and the Annex J text, byte for byte |
| [fixtures/minimal/](../fixtures/minimal/) | Two valid links and no diagnostics |
| [cases.json](cases.json) | Small trees with hand-written expected codes, links with attributes, origins, states and reasons, risk relevance, context selections and Annex J text, and f1 projections |
| The command line | Exit codes 0, 1 and 2, root selection from TARGET, and TARGET kept as given |

Each case names the requirements it exercises. Expectations were written from the specification text, not copied from the reader's output; a changed expectation needs a specification reason. The cases are a first slice of the 0.3 suite, not the suite: converting the 73 repository cases of 0.2, kept in [from-0.2/](from-0.2/README.md), is the next step of Phase 2 in the [plan](../plan-agent-readiness.md).
