<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# OSTF 0.3 reader and cases

[reader.py](reader.py) reads wire 0.3: an Analyzer for Go, TypeScript, JavaScript and Python (Annexes A, K and L) with the `check` and `context` commands of [Annex I](../ostf.md#annex-i-normative-optional-command-profile), `impact` for `check --base` (Annex C.3) and SARIF output (Annex D). It is independent code ported from the 0.2 Python prototype; it does not import zztrace or touch the network, and the reader itself starts no subprocess: only the command line runs Git's plumbing commands, for `check --base REV` without `--base-tree` to read REV, and for `context` and `check --base` to read change information (Annex I.3). It reads Python with CPython's own tokenizer and parser, and Go, TypeScript and JavaScript with tree-sitter. It is a development probe, not a hardened service: Go syntax comes from tree-sitter-go plus UTF-8 and escape checks, so some files the Go compiler rejects still parse, and reads are not protected against a tree that changes during a run.

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

`check --base REV` reads the base view from Git with its plumbing commands (`rev-parse`, `ls-tree`, `cat-file`), which run no hooks, filters or repository code; REV is any commit the checkout can name, and a REV without the root's directory is a base with an empty graph (Annex C.3). `context` and `check --base` read the change information of Annex I.3 from the first-parent history of `HEAD` with `log`, `ls-tree` and `cat-file`, and give none outside a Git checkout. For the example, against the last commit:

```sh
cd draft/0.3/example
../../../.venv/bin/python ../conformance/reader.py check --base HEAD
```

Outside a Git checkout, the added option `--base-tree DIR` (Annex I.5) supplies the base view instead: DIR is the directory that holds this root in a checkout of REV, and REV is then only the label in `impact.base`. For a root at the top level of a repository, DIR is the checkout itself. A DIR without `trace.yaml` is a base with an empty graph, so adopting OSTF lists every item and link as added; a DIR that does not exist exits 2, so a mistyped path cannot pass for an adoption.

The reader adds one code of its own, outside Annex C as OSTF-151 allows: `ostf-reader.UNLINKED`, an info that counts the statements, other than obsolete ones, that no link targets, and names the first ten. `check` reports broken links, not whether statements are covered, so without it a requirement with no code, test or verification passes in silence; whether it must be covered is a policy for the team or a tool on top. The info never fails `check`, and the cases compare Annex C codes only. When `context` is given a path that does not resolve, its hint names the covered files whose paths end with that path, spelled from the working directory, which is where Annex I.3 reads TARGET from:

```sh
cd draft/0.3/example/deploy
../../../../.venv/bin/python ../../conformance/reader.py context deploy/database.tf
# error BROKEN_LINK deploy/database.tf: deploy/database.tf does not resolve (paths are relative to the working directory: try database.tf)
```

[check.py](check.py) runs:

| Check | What it pins |
| --- | --- |
| [vectors/](vectors/) | The span vectors of Annexes A, K and L: every definition of each source by full symbol and span text, and the definitions each symbol binds to, or no parse; the item, Go and lock vectors published with 0.2 stay byte for byte as history and are not run |
| [example/expected/](../example/expected/) | `check` and `context` JSON and the Annex J text, byte for byte |
| [fixtures/minimal/](../fixtures/minimal/) | Two links and no diagnostics |
| [cases.json](cases.json) | Small trees with hand-written expected codes, links with attributes and origins, corroboration by link identity, risk relevance, context selections and Annex J text; a file that a case names in `padTo` is extended with line feeds to that size in bytes, so that a case at the size limit need not carry it; its schema cases run in [fixtures_test.go](../fixtures_test.go) |
| `impacts` in cases.json | A base view and an evaluated view with the expected `impact`, and the evaluated view's codes, read after the impact so it cannot add a diagnostic; [fixtures_test.go](../fixtures_test.go) checks each expected `impact` against the result schema |
| `histories` in cases.json | A scripted Git history, built with Git's plumbing, a merge and a shallow clone among them, run through the command line; every commit identifier in the output, whole or cut to 12 characters, is replaced by its commit's subject before the change information and the Annex J text are compared, so a case holds whatever object format, names and dates Git uses |
| `sarif` in cases.json | Rules, levels, locations and messages of each diagnostic; every SARIF log the suite produces is also validated against the OASIS SARIF 2.1.0 schema |
| Annex C.3 example | The edit that C.3 describes, applied to the example, yields the JSON printed in the specification |
| Coverage | The vector files of 0.2 are unchanged byte for byte, Annex B reproduces [trace-lock.abnf](../trace-lock.abnf), a retired requirement is defined nowhere and named by no case, the cases that use [profiles/security.yaml](../profiles/security.yaml) carry it byte for byte, and every requirement and Annex C code has a case or a reason in `notCovered` |
| The command line | Exit codes 0, 1 and 2 of both commands, root selection from TARGET, TARGET kept as given, the hint for a path given from another directory, text `check` counting items and links, and on an edited copy of the example `check --base`, which lists the change and passes, and `--format sarif` |

[generate_tree.py](generate_tree.py) writes the deterministic 10 000-file tree on which both implementations time `check` (plan, section 5.4): `python3 generate_tree.py DIR`.

Each case names the requirements it exercises. Expectations were written from the specification text, not copied from the reader's output; a changed expectation needs a specification reason. The Go tests also check that the schemas accept every file of a case the reader accepts. Not yet covered: Consumer expectations. The SARIF schema is fetched rather than kept here, since it is OASIS's.

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

The 0.2 requirement map, `suite.json`, is replaced by the `requirements` of each case and the coverage check. 0.2 identifiers map to 0.3 through [Annex H](../ostf.md#annex-h-informative-changes-from-draft-02-and-revision-014).

## From revision 0.14

Phase 2 of the [agent-first plan](../plan-agent-first.md) changed rules under the same wire string, and the suite with them; the [decision record](../decisions.md#agent-first-plan-phase-2-wire-04-core) gives each rule. Every case carried on, and none was retired. The converted ones, by rule:

- **Type kinds.** `risk-relevance-follows-controls-only`, which pinned the 0.3 gap, became `risk-relevance-follows-kind` and expects the opposite; `risk-relevance-through-extended-controls` declares the kind of its new type.
- **Merges.** The four cases that named OSTF-162 name OSTF-160.
- **Recheck provenance.** The 15 stamped lines that the stamp cases expect end with `by=unknown at=unknown`; a stamp case may give `by` and `at`.
- **Sharded locks.** A stamp case may expect `locks`, every lock file written by path, in place of `lock`.
- **One call per change and roots that know each other.** Every impact case gained `impact.contexts`, and impact cases compare the result of `check --base`, which evaluates nested roots.
- **Item text as data.** Eleven context cases gained the `| ` marker in their Annex J text, and nothing else.

New expectations: `corroboration` and `hints` in check cases, and `migrations`, the lock files that `migrate` writes (Annex H). The example gained `trace.derived`, and its lock and the minimal fixture's were brought to the current revision with the reader's `migrate`, so each entry ends with `by=unknown at=unknown`.

## From revision 0.15

Phase 3 of the [agent-first plan](../plan-agent-first.md) missed its pre-registered gate, so its fallback removed the lock and the fingerprints in revision 0.16; the [decision record](../decisions.md#agent-first-plan-phase-3-the-fallback) gives each ruling. Of the 363 cases of revision 0.15, 92 are retired, 271 carry on, 209 of them changed, and 13 are new, 284 in all. The vectors of 0.2 stay byte for byte and are no longer run; the `go2`, `ts1`, `ts2` and `py1` vectors are deleted, and their sources and symbols became the span vectors of Annexes A, K and L.

Retired, by reason:

- **Lock files** (OSTF-142, 17): `lock-at-size-limit`, `lock-above-size-limit`, `lock-entry-malformed`, `lock-header-unknown`, `lock-duplicate-uses-neither`, `lock-values-not-validated`, `lock-provenance-read`, `lock-provenance-any-order`, `lock-provenance-invalid`, `lock-provenance-not-identity`, `lock-shards-merge`, `lock-shard-only`, `lock-shard-entry-elsewhere-is-read`, `lock-shards-duplicate`, `lock-shard-invalid-line`, `lock-shard-too-large`, `lock-shard-of-unread-file-ignored`.
- **Suspect rules** (OSTF-144, 16), whose observable was a state: `body-change-suspect`, `reasons-sorted`, `lock-key-on-one-side-differs`, `body-change-none`, `external-revision-only-stays-valid`, `external-refresh-is-item-changed`, `item-changed`, `body-change-counts-by-default`, `signature-changed`, `reasons-for-what-has-no-body`, `reasons-quieted-on-their-own`, `reasons-quieted-unless-risk-relevant`, `item-link-source-changed`, `item-link-target-changed`, `ts2-line-break-after-return-is-suspect`, `ts2-omitted-semicolon-stays-valid`.
- **Link states** (OSTF-143, 8): `unstamped-without-entry`, `lock-missing-reports-no-states`, `unknown-algorithm-is-unstamped`, `broken-before-unknown-algorithm`, `no-lock`, `unstamped`, `unknown-algorithm`, `ts1-lock-entry-is-unstamped`.
- **The meaning of a valid link** (OSTF-145, 1): `helper-change-keeps-valid`.
- **The hint without a base** (OSTF-132, 2), which read the lock entry; `impact-broken-link-hint-by-text` pins the hint by text: `broken-link-hint-names-the-move`, `broken-link-hint-needs-a-lock-entry`.
- **The lock-file rules of OSTF-102 and OSTF-132** (6), the glob exclusion and the anchor ban: `lock-shard-not-an-item-file`, `anchor-names-trace-lock`, `anchor-trace-lock-any-case`, `lock-shard-anchor-invalid`, and the contexts `context-trace-lock-does-not-bind` and `context-trace-lock-any-case`.
- **The profile's fingerprints keys** (OSTF-121, 2): `reasons-setting-invalid` and the schema case `schema-fingerprints-reason-settings`.
- **`impact.lock`** (Annex C.3, 4): `impact-lock-removed`, `impact-lock-added`, `impact-lock-absent`, `impact-lock-kept-in-another-lock-file`.
- **Link-state results in SARIF** (Annex D, 1): `sarif-link-states`.
- **`stamp`** (Annex I.4, 26): every stamp case, from `stamp-creates-lock` to `stamp-root-item-stays-in-trace-lock`, and the list `stamps` with them.
- **`migrate`** (Annex H, 4): every migration case, and the list `migrations`.
- **The fingerprints** (OSTF-140, OSTF-141, 4): `formatting-and-comments`, `whole-file-lf1-normalizes-crlf`, and both projections, `string-kept-text-normalized-empty-omitted` and `all-empty-attributes-omitted`, with the list `projections`.
- **`meaning`** (OSTF-114, 1): `external-without-text-keeps-meaning-attributes`.

Carried, with what changed:

- Every case with a lock file lost it, its states and reasons and the lock codes; a link tuple is now source, link type, target, attributes and origin.
- Cases that pin risk relevance name OSTF-120, and those without a lock no longer name OSTF-144. The profiles of five cases lost their `fingerprints` keys.
- Item and link fingerprint expectations are gone; cases that named OSTF-141 for `PARSE_ERROR` name OSTF-132, OSTF-140 is dropped, and the annex sections follow their new numbers.
- `meaning` left two profiles, three schema inputs and the cases that carry [profiles/security.yaml](../profiles/security.yaml).
- `impact-items-and-links` counts a new rationale as a changed item; `impact-nested-roots-each-evaluated` fails its nested root with a broken link; `sarif-locations` checks the locations of diagnostics, a tag naming `R{0}` among them; `sarif-info-is-note` uses `NESTED_ROOT`; the Annex J texts lose their states; `context-item-text-marked` forges a corroboration in its title, since a state no longer appears; and SARIF cases no longer list link results.

New: `histories`, eight scripted Git histories run through the command line (Annex I.3); three impact cases, a comment inside a definition, CRLF alone and the hint by text; `leftover-lock-files-are-ordinary-files`; and `attribute-meaning-rejected`.
