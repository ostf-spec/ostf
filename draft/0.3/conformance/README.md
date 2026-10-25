<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# OSTF 0.3 reader and cases

[reader.py](reader.py) reads wire 0.3: an Analyzer for Go, TypeScript, JavaScript and Python (Annexes A, K and L) with the `check`, `context` and `stamp` commands of [Annex I](../ostf.md#annex-i-normative-optional-command-profile), `impact` for `check --base` (Annex C.3) and SARIF output (Annex D). It is independent code ported from the 0.2 Python prototype; it does not import zztrace or touch the network, and the reader itself starts no subprocess: only the command line's `check --base REV`, without `--base-tree`, runs Git's plumbing commands to read REV. It reads Python with CPython's own tokenizer and parser, and Go, TypeScript and JavaScript with tree-sitter. It is a development probe, not a hardened service: Go syntax comes from tree-sitter-go plus UTF-8 and escape checks, so some files the Go compiler rejects still parse, and reads are not protected against a tree that changes during a run.

From the repository root, with Python 3.12 or newer:

```sh
python3 draft/0.3/conformance/run.py
```

The script creates an ignored `.venv/` at the repository root, installs the exact versions and release hashes in [requirements.txt](requirements.txt), then runs [check.py](check.py). It needs PyPI or a prepared wheel cache on first run. To use the reader directly:

```sh
cd draft/0.3/example
../../../.venv/bin/python ../conformance/reader.py check
../../../.venv/bin/python ../conformance/reader.py context refund.go#CheckRefundLimit
../../../.venv/bin/python ../conformance/reader.py check --format sarif
../../../.venv/bin/python ../conformance/reader.py stamp 'refund.go#CheckRefundLimit implements R-REFUND-LIMIT'
```

`check --base REV` reads the base view from Git with its plumbing commands (`rev-parse`, `ls-tree`, `cat-file`), which run no hooks, filters or repository code; REV is any commit the checkout can name, and a REV without the root's directory is a base with an empty graph (Annex C.3). For the example, against the last commit:

```sh
cd draft/0.3/example
../../../.venv/bin/python ../conformance/reader.py check --base HEAD
```

Outside a Git checkout, the added option `--base-tree DIR` (Annex I.6) supplies the base view instead: DIR is the directory that holds this root in a checkout of REV, and REV is then only the label in `impact.base`. For a root at the top level of a repository, DIR is the checkout itself. A DIR without `trace.yaml` is a base with an empty graph, so adopting OSTF lists every item and link as added; a DIR that does not exist exits 2, so a mistyped path cannot pass for an adoption.

[check.py](check.py) runs:

| Check | What it pins |
| --- | --- |
| [vectors/](vectors/) | The item, Go and lock vectors published with 0.2: f1, go1 and `trace.lock 1` are unchanged (budget rule 5); and the `ts1` and `py1` vectors of Annexes K and L |
| [example/expected/](../example/expected/) | `check` and `context` JSON and the Annex J text, byte for byte |
| [fixtures/minimal/](../fixtures/minimal/) | Two valid links and no diagnostics |
| [cases.json](cases.json) | Small trees with hand-written expected codes, links with attributes, origins, states and reasons, risk relevance, context selections and Annex J text, and f1 projections; its schema cases run in [fixtures_test.go](../fixtures_test.go) |
| `stamps` in cases.json | The stamped links and the exact lock bytes, or no write when a link is refused; then that the named links are valid, no other link changed state and stamping again changes nothing |
| `impacts` in cases.json | A base view and an evaluated view with the expected `impact`, and the evaluated view's codes, read after the impact so it cannot add a diagnostic; [fixtures_test.go](../fixtures_test.go) checks each expected `impact` against the result schema |
| `sarif` in cases.json | Rules, levels, locations, `ostf.link` and `ostf.state` of link-state results, and the mapping of each diagnostic |
| Annex C.3 example | The edit that C.3 describes, applied to the example, yields the JSON printed in the specification; stamping the example's six links from no lock yields its `trace.lock` |
| Coverage | The vector files are byte-identical to 0.2, and every requirement and Annex C code has a case or a reason in `notCovered` |
| The command line | Exit codes 0, 1 and 2 of all three commands, root selection from TARGET, TARGET kept as given, and on an edited copy of the example `check --base`, `--format sarif`, a refused stamp that writes nothing, a stamp that makes `check` pass and leaves no temporary file, no write through a symbolic or hard link, and text `check` naming links that have no state yet |

[generate_tree.py](generate_tree.py) writes the deterministic 10 000-file tree on which both implementations time `check` (plan, section 5.4): `python3 generate_tree.py DIR`.

Each case names the requirements it exercises. Expectations were written from the specification text, not copied from the reader's output; a changed expectation needs a specification reason. The Go tests also check that the schemas accept every file of a case the reader accepts. Not yet covered: Consumer expectations, and the reader is not validated against the OASIS SARIF schema, which is not vendored here.

## From 0.2

Step 2b converted the 0.2 suite's 73 repository cases and 24 schema cases; its 39 vectors run unchanged from [vectors/](vectors/). 75 cases carry on. Each names its 0.2 case in `from02`, and each whose input or expected result changed says why in `note`. The 0.2 expectation was the starting point, including its item and link fingerprints, and every difference is a 0.3 rule:

- `bodyChange` defaults to `all`, so a body change makes a link suspect unless a profile says otherwise.
- `tags` is on by default and tags carry IDs only, so `links: {source: ...}` is gone and a `role=` token is read as a name.
- The default vocabulary declares no attributes, so cases that used `role` declare it in a profile.
- The 0.2 reader stopped at the first error; 0.3 cases keep the states of unaffected links and list `LOCK_MISSING`, `LINK_DUPLICATE` and other warnings and infos.
- A broken link keeps the fingerprints that can still be computed, such as its target's (C.2); 0.2 reported none.
- Codes are more specific: `VERSION_UNSUPPORTED`, `UNKNOWN_KEY` and `PROFILE_INVALID` replace `FORMAT_INVALID` where they apply, and a glob is `INCLUDE_EMPTY` only when it matches nothing.
- The per-link `suspect` setting, `extends`, `derived`, the `document` header and the `date` kind were removed.

21 cases were retired because 0.3 removed what they tested, and one was merged:

| 0.2 cases | Reason |
| --- | --- |
| `document-duplicate-id`, `document-missing-kind`, `document-extension` | The `document` header was removed; `removed-document-header-stops` covers a file that still has one. |
| `attribute-invalid-date`, `attribute-compact-date-rejected` | The `date` kind was removed; a date is a string. |
| `tag-empty-role`, `tag-duplicate-role` | Tags carry no attributes; `tag-attribute-token-is-a-name` covers a `role=` token. |
| `suspect-source-target-changed`, `suspect-target-source-changed` | Without the per-link `suspect` setting, their inputs equal `item-link-target-changed` and `item-link-source-changed`. |
| `observability-refs`, `observability-bad-trace-id`, `observability-log-span-without-trace` and the five `schema-observability`, `schema-otel` and `schema-log` cases | `logs` and `otel` were removed with 0.2's OSTF-024. |
| The four `schema-snapshot` cases | The snapshot schema was replaced by `external` and `sources`. |
| `repository-valid` | Its input equals `minimal-valid`, which now carries its requirements. |

The 0.2 requirement map, `suite.json`, is replaced by the `requirements` of each case and the coverage check. 0.2 identifiers map to 0.3 through [Annex H](../ostf.md#annex-h-informative-changes-from-draft-02).
