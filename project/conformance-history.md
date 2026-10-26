<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Conversion notes of the conformance suite

The notes that the conformance README carried while the draft was worked on, as they stood when the work was published as working draft 0.3.

## From 0.2

Applies to the first suite of draft 0.3, before suite versions. Step 2b converted the 0.2 suite's 73 repository cases and 24 schema cases; its 39 vectors run unchanged from [vectors/](../draft/0.3/conformance/vectors/). 75 cases carry on. Each names its 0.2 case in `from02`, and each whose input or expected result changed says why in `note`. The 0.2 expectation was the starting point, including its item and link fingerprints, and every difference is a 0.3 rule:

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

The 0.2 requirement map, `suite.json`, is replaced by the `requirements` of each case and the coverage check. 0.2 identifiers map to 0.3 through [Annex H](../draft/0.3/ostf.md#Annex-H).

## From revision 0.14

Applies to the suite of revision 0.15, before suite versions. Phase 2 of the [agent-first plan](plan-agent-first.md) changed rules under the same wire string, and the suite with them; the [decision record](decisions.md#agent-first-plan-phase-2-wire-04-core) gives each rule. Every case carried on, and none was retired. The converted ones, by rule:

- **Type kinds.** `risk-relevance-follows-controls-only`, which pinned the 0.3 gap, became `risk-relevance-follows-kind` and expects the opposite; `risk-relevance-through-extended-controls` declares the kind of its new type.
- **Merges.** The four cases that named OSTF-162 name OSTF-160.
- **Recheck provenance.** The 15 stamped lines that the stamp cases expect end with `by=unknown at=unknown`; a stamp case may give `by` and `at`.
- **Sharded locks.** A stamp case may expect `locks`, every lock file written by path, in place of `lock`.
- **One call per change and roots that know each other.** Every impact case gained `impact.contexts`, and impact cases compare the result of `check --base`, which evaluates nested roots.
- **Item text as data.** Eleven context cases gained the `| ` marker in their Annex J text, and nothing else.

New expectations: `corroboration` and `hints` in check cases, and `migrations`, the lock files that `migrate` writes (Annex H). The example gained `trace.derived`, and its lock and the minimal fixture's were brought to the current revision with the reader's `migrate`, so each entry ends with `by=unknown at=unknown`.

## From revision 0.15

Applies to the suite of revision 0.16, before suite versions. Phase 3 of the [agent-first plan](plan-agent-first.md) missed its pre-registered gate, so its fallback removed the lock and the fingerprints in revision 0.16; the [decision record](decisions.md#agent-first-plan-phase-3-the-fallback) gives each ruling. Of the 363 cases of revision 0.15, 95 are retired, 268 carry on, 207 of them changed, and 15 are new, 283 in all. The vectors of 0.2 stay byte for byte and are no longer run; the `go2`, `ts1`, `ts2` and `py1` vectors are deleted, and their sources and symbols became the span vectors of Annexes A, K and L.

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
- **Reserved link attribute names** (OSTF-121, 3), by the maintainer's ruling after the rows: `link-attribute-named-by-rejected`, `profile-reserved-attribute-name` and the schema case `schema-link-attribute-reserved-provenance`.

Carried, with what changed:

- Every case with a lock file lost it, its states and reasons and the lock codes; a link tuple is now source, link type, target, attributes and origin.
- Cases that pin risk relevance name OSTF-120, and those without a lock no longer name OSTF-144. The profiles of five cases lost their `fingerprints` keys.
- Item and link fingerprint expectations are gone; cases that named OSTF-141 for `PARSE_ERROR` name OSTF-132, OSTF-140 is dropped, and the annex sections follow their new numbers.
- `meaning` left two profiles, three schema inputs and the cases that carry [profiles/security.yaml](../draft/0.3/profiles/security.yaml).
- `impact-items-and-links` counts a new rationale as a changed item; `impact-nested-roots-each-evaluated` fails its nested root with a broken link; `sarif-locations` checks the locations of diagnostics, a tag naming `R{0}` among them; `sarif-info-is-note` uses `NESTED_ROOT`; the Annex J texts lose their states; `context-item-text-marked` forges a corroboration in its title, since a state no longer appears; and SARIF cases no longer list link results.

New: `histories`, eight scripted Git histories run through the command line (Annex I.3); three impact cases, a comment inside a definition, CRLF alone and the hint by text; `leftover-lock-files-are-ordinary-files`; `attribute-meaning-rejected`; and `link-attributes-named-source-target-by-at` and the schema case `schema-link-attribute-named-at`, which accept `source`, `target`, `by` and `at` as link attribute names.

## From revision 0.16

Gives suite version 1, the suite of revision 0.17, which revision 0.18 numbered. Phase 5 of the [agent-first plan](plan-agent-first.md) missed the row that counts hand edits of `trace.derived`, so revision 0.17 moves derived links out of Core into Annex B, an optional annex; the [decision record](decisions.md#agent-first-plan-phase-5-trials-v2) gives the rulings. No case is retired or added, and no expectation changed. The cases that named OSTF-146 name the annex's sections instead, as the command profile's cases name Annex I, and like them they hold for a reader that claims the annex: `derived-corroboration`, `derived-absent`, `derived-header-only`, `derived-invalid-lines`, `derived-header-invalid`, `derived-broken-test`, `derived-too-large`, which no longer names OSTF-105 since that limit no longer names the file, and the contexts `context-corroboration-without-lock` and `context-corroboration-after-state`. `derived-not-an-anchor` names OSTF-132 alone, which still makes an anchor that names the file `ANCHOR_INVALID`. OSTF-146 joins the retired requirements that no case may name, and the coverage check reads the codes of Annex C.1 and of Annex B.4 apart.

## From suite version 1

Gives suite version 2, on 2026-10-26, under revision 0.18; no rule changed. One case is added, `revision-wrong-type-without-external`: items whose `revision` is an integer, a boolean, an empty string or a list, and that have no `external`, are each `INVALID_EXTERNAL` alone. The differential harness found the reference reader reporting `FORMAT_INVALID` beside `INVALID_EXTERNAL` for such an item, where zztrace's reader reported `INVALID_EXTERNAL` alone. By the maintainer's ruling OSTF-151 settles it, a value that breaks a rule with its own code getting that code whatever its type, as the reference reader already applied it to `status`, `type` and `external`; the reference reader is fixed. Beside `external`, a `revision` that is not a nonempty string stays `FORMAT_INVALID`, as `yaml-leading-zero-is-an-integer` and `revision-empty` pin.
