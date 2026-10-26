<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# OSTF 0.3 reader and cases

[reader.py](reader.py) reads wire 0.3: an Analyzer for Go, TypeScript, JavaScript and Python (Annexes A, B and C) with the `check` and `context` commands of [Annex F](../ostf.md#Annex-F), `impact` for `check --base` (Annex D.3) and SARIF output (Annex H). It is independent code; it does not import the second reader, zztrace, or touch the network, and the reader itself starts no subprocess: only the command line runs Git's plumbing commands, for `check --base REV` without `--base-tree` to read REV, and for `context` and `check --base` to read change information (Annex F.3). It reads Python with CPython's own tokenizer and parser, and Go, TypeScript and JavaScript with tree-sitter. It is a development probe, not a hardened service: Go syntax comes from tree-sitter-go plus UTF-8 and escape checks, so some files the Go compiler rejects still parse, and reads are not protected against a tree that changes during a run.

**Claim (OSTF-163).** An Analyzer for Annexes A, B and C, of working draft 0.3 of 2026-10-26, wire version 0.3 and the schema identifiers under `https://ostf.dev/draft/0.3/`, that passes suite version 1; and, as separate claims, Annexes E, F, H and I.

From the repository root, with Python 3.12 or newer:

```sh
python3 draft/0.3/conformance/run.py
```

The script creates an ignored `.venv/` at the repository root, installs the exact versions and release hashes in [requirements.txt](requirements.txt), fetches the OASIS SARIF 2.1.0 schema into `.venv/` and checks its SHA-256, then runs [check.py](check.py). It needs PyPI and docs.oasis-open.org, or a prepared `.venv/`, on first run. To use the reader directly:

```sh
cd draft/0.3/example
../../../.venv/bin/python ../conformance/reader.py check
../../../.venv/bin/python ../conformance/reader.py context refund.go#CheckRefundLimit
../../../.venv/bin/python ../conformance/reader.py check --format sarif
```

`check --base REV` reads the base view from Git with its plumbing commands (`rev-parse`, `ls-tree`, `cat-file`), which run no hooks, filters or repository code; REV is any commit the checkout can name, and a REV without the root's directory is a base with an empty graph (Annex D.3). `context` and `check --base` read the change information of Annex F.3 from the first-parent history of `HEAD` with `log`, `ls-tree` and `cat-file`, and give none outside a Git checkout. For the example, against the last commit:

```sh
cd draft/0.3/example
../../../.venv/bin/python ../conformance/reader.py check --base HEAD
```

Outside a Git checkout, the added option `--base-tree DIR` (Annex F.5) supplies the base view instead: DIR is the directory that holds this root in a checkout of REV, and REV is then only the label in `impact.base`. For a root at the top level of a repository, DIR is the checkout itself. A DIR without `trace.yaml` is a base with an empty graph, so adopting OSTF lists every item and link as added; a DIR that does not exist exits 2, so a mistyped path cannot pass for an adoption.

The reader adds one code of its own, outside Annex D as OSTF-151 allows: `ostf-reader.UNLINKED`, an info that counts the statements, other than obsolete ones, that no link targets, and names the first ten. `check` reports broken links, not whether statements are covered, so without it a requirement with no code, test or verification passes in silence; whether it must be covered is a policy for the team or a tool on top. The info never fails `check`, and the cases compare Annex D codes only. When `context` is given a path that does not resolve, its hint names the covered files whose paths end with that path, spelled from the working directory, which is where Annex F.3 reads TARGET from:

```sh
cd draft/0.3/example/deploy
../../../../.venv/bin/python ../../conformance/reader.py context deploy/database.tf
# error BROKEN_LINK deploy/database.tf: deploy/database.tf does not resolve (paths are relative to the working directory: try database.tf)
```

[check.py](check.py) runs:

| Check | What it pins |
| --- | --- |
| [vectors/](vectors/) | The span vectors of Annexes A, B and C: every definition of each source by full symbol and span text, and the definitions each symbol binds to, or no parse |
| [example/expected/](../example/expected/) | `check` and `context` JSON and the Annex G text, byte for byte |
| [fixtures/minimal/](../fixtures/minimal/) | Two links and no diagnostics |
| [cases.json](cases.json) | Small trees with hand-written expected codes, links with attributes and origins, corroboration by link identity, risk relevance, context selections and Annex G text; a file that a case names in `padTo` is extended with line feeds to that size in bytes, so that a case at the size limit need not carry it; its schema cases run in [fixtures_test.go](../fixtures_test.go) |
| `impacts` in cases.json | A base view and an evaluated view with the expected `impact`, and the evaluated view's codes, read after the impact so it cannot add a diagnostic; [fixtures_test.go](../fixtures_test.go) checks each expected `impact` against the result schema |
| `histories` in cases.json | A scripted Git history, built with Git's plumbing, a merge and a shallow clone among them, run through the command line; every commit identifier in the output, whole or cut to 12 characters, is replaced by its commit's subject before the change information and the Annex G text are compared, so a case holds whatever object format, names and dates Git uses |
| `sarif` in cases.json | Rules, levels, locations and messages of each diagnostic; every SARIF log the suite produces is also validated against the OASIS SARIF 2.1.0 schema |
| Annex D.3 example | The edit that D.3 describes, applied to the example, yields the JSON printed in the specification |
| Coverage | Annex E reproduces [trace-derived.abnf](../trace-derived.abnf), the cases that use [profiles/security.yaml](../profiles/security.yaml) carry it byte for byte, and every requirement and Annex D code has a case or a reason in `notCovered` |
| The command line | Exit codes 0, 1 and 2 of both commands, root selection from TARGET, TARGET kept as given, the hint for a path given from another directory, text `check` counting items and links, and on an edited copy of the example `check --base`, which lists the change and passes, and `--format sarif` |

[generate_tree.py](generate_tree.py) writes the deterministic 10 000-file tree on which both implementations time `check`: `python3 generate_tree.py DIR`.

Each case names the requirements it exercises. Expectations were written from the specification text, not copied from the reader's output; a changed expectation needs a specification reason. The Go tests also check that the schemas accept every file of a case the reader accepts. Not yet covered: Consumer expectations. The SARIF schema is fetched rather than kept here, since it is OASIS's.

## Suite version

The suite is suite version 1, which `suite.version` in [cases.json](cases.json) records and a claim cites (OSTF-163): the cases, the span vectors, the example's expected outputs and the checks of check.py. Any case or expectation added, removed or changed, in cases.json, a span vector, an expected output of the example or a check of check.py, gives the suite the next version, and this file records what each version changed. `suite.sha256` is a digest of cases.json without that entry, the span vectors and the expected outputs, and check.py fails when they change and the digest does not, so no such change ships without a decision on the version.

## Differential harness

[differential.py](differential.py) runs any reader that claims the command profile (Annex F) over 476 small trees at the edges of the text, [differential/corpus.json](differential/corpus.json), and compares what it reports with [differential/reference.json](differential/reference.json), the reference reader's summaries. It is a convergence aid for a new reader and no part of the suite: agreement with the reference summaries supports no conformance claim, since the reference reader is not the oracle; the text is. A difference is a question for the text. Settled there with a case, it is fixed in whichever reader read it the other way, and the case, not the corpus, enters the suite.

```sh
python3 draft/0.3/conformance/differential.py run --reader "my-reader" --out mine.json
python3 draft/0.3/conformance/differential.py compare draft/0.3/conformance/differential/reference.json mine.json
```

The script needs Python 3 and Git and nothing of this repository's reader. For each tree it writes the files to a temporary directory and runs `check` as json and as sarif, `context` as json and text for the tree's targets, and, for a tree with a base, `check --base HEAD` in a Git repository whose one commit is the base. A summary keeps what Annex D.2 compares, the codes, items, link tuples and `impact`, with the file of each diagnostic, the SARIF rules, levels and files, the exit codes and the Annex G text of a context that resolves. It leaves out what Annex D.2 does not compare: the order of diagnostics, messages, hints and subjects, SARIF logical locations among them, codes of a tool's own, and change information, which the `histories` cases pin. The corpus covers scalar types in every item field, wire versions in each kind of file, keys and extensions, paths and anchors, link entries, tags in Go, TypeScript and Python, profiles, external items, includes and nested roots, derived lines, contexts and impacts. Its generator is deterministic and committed with its output, so a third party and CI see the same inputs: `differential.py check`, which CI runs, fails when the corpus is not what `differential.py generate` writes or the reference reader no longer gives the committed summaries.
