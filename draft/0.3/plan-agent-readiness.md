<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# OSTF 0.3: phased plan to reach 10 of 10 for coding agents without growing Core

Date: 2026-10-24. Status: Phase 1 done on 2026-10-24 (section 4.3); Phases 2 to 5 proposed for the [0.3 draft](ostf.md). Baseline: design for agents 7 of 10, usable by agents today 2 of 10, because no implementation reads wire 0.3.

## 1. Definition of done

A model cannot hash a token stream in its head, and OSTF will never standardize dependency analysis or permissions. So 10 of 10 does not mean "no tool needed". It means:

> An agent that has never seen OSTF, given only the repository and one paragraph of instructions, learns why a function exists, which tests to run and which links are stale in at most two calls, writes correct items and links on the first attempt, cannot merge an invented ID, and behaves the same whichever vendor's tool is installed. Verified by trials, not by reading the spec.

The scorecard is the acceptance test. The right-hand columns show the score each phase is expected to reach; only Phase 5 turns an expectation into a measurement.

| Agent need | Now | After P1 | After P2 | After P3 | After P4 | After P5 | Measured by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Find it | 7 | 9 | 9 | 9 | 10 | 10 | Agent locates the root and reads the rules in its first turn, every trial. |
| Read intent and tests without a tool | 8 | 8 | 8 | 9 | 9 | 10 | Correct "why does this exist" from files alone in 95 percent of trials. |
| Read freshness | 2 | 2 | 9 | 9 | 9 | 10 | One `check` call returns every link state; two vendors' tools return the same bytes. |
| Write correctly | 7 | 8 | 9 | 9 | 9 | 10 | 95 percent of agent-written items and links pass `check` first time. |
| Fast feedback | 0 | 0 | 9 | 9 | 10 | 10 | `check` in CI and pre-commit, SARIF out, under two seconds on 10 000 files. |
| Few tokens | 8 | 8 | 9 | 9 | 10 | 10 | `context` for one function costs at most 600 tokens; at most two calls before editing. |
| Safe | 7 | 8 | 8 | 8 | 9 | 10 | Zero invented IDs merged; zero hand edits of the lock; agents ask before touching risk-relevant code. |
| Reason about a change | 5 | 6 | 9 | 9 | 9 | 10 | `check --base` names every directly affected item and test and labels its boundary. |
| Portable workflow | 6 | 7 | 9 | 9 | 10 | 10 | The same paragraph yields the same behavior on two independent tools. |
| Mark what it proposed | 4 | 8 | 10 | 10 | 10 | 10 | `check --base` lists every item and link an agent added, in every trial PR. |

## 2. Simplicity budget

These rules bind every phase. A change that breaks one is rejected, however useful.

1. **No new key in Core.** Items, roots and profiles keep exactly the fields of the 0.3 draft. Everything below lands in optional annexes, tool behavior or defaults.
2. **The four-line example stays byte-for-byte valid** and becomes a conformance fixture that fails if the minimal file grows.
3. **Core stays at or below 35 numbered requirements.** A new requirement retires or merges an old one.
4. **One page per annex.** Command profile, context rendering and each language annex fit on one printed page.
5. **Hashes never change.** f1, go1, lf1 and `trace.lock 1` stay as published; a new language is a new algorithm identifier.
6. **Behavior stays out.** The command profile fixes names, inputs, outputs and exit codes, never how to analyze.

## 3. Phases at a glance

| Phase | Goal | Delivers | Exit gate | Size |
| --- | --- | --- | --- | --- |
| P1 Fix the contract | Close the design gaps on paper | Spec edits, Annex I command profile, Annex J context rendering, fixtures | Still 35 requirements, no new Core key, examples unchanged except the `tags` default | S |
| P2 Make it real | A checker and a suite for wire 0.3 | Reference checker with three verbs, suite 0.3.0, zztrace on 0.3 | Two code paths agree on every fingerprint, state and rendering | L |
| P3 Make 80 percent honest | Languages most agents actually edit | TypeScript and JavaScript annex, Python annex, vectors | Vectors pass in both implementations; TypeScript fixture all valid | M |
| P4 Remove friction | What agents and CI touch | MCP binding, GitHub Action, pre-commit hook, paragraph file, converters | Empty repository to passing CI in ten minutes from the README alone | M |
| P5 Measure | Replace claims with trials | Fixture repositories, eight scripted tasks, two agents, two tools, published results | Scorecard reads 10 in every row on frozen labels | M |

Phases run in order. If capacity is short, P1 through P3 carry most of the score; P4 removes friction; P5 is what separates a claim from a measurement.

## 4. Phase 1: fix the contract

**Goal.** Every gap that can be closed on paper is closed, inside the simplicity budget.

**Changes.**

| Change | Where | Simplicity cost |
| --- | --- | --- |
| Tags on by default: `tags` defaults to `true`, `tags: false` opts out. The cheapest agent-facing mechanism must not need enabling. | OSTF-133, schema | One default flipped. |
| Discovery: a repository SHOULD keep a root at its top level, and its agent instructions file SHOULD contain the Annex F paragraph. | OSTF-102 | One sentence. |
| Diagnostics gain an optional `hint`, so a checker can say "nearest IDs: R-REFUND-LIMIT". | Annex C | One optional field. |
| Result format gains an optional `impact` section for `check --base`: changed anchors with their items, unlinked changed code, the tests to run, and `coverage: "direct"` naming the boundary. | Annex C | One optional section. |
| New Annex I, optional and claimable: the command profile (section 4.1). | New annex | One page. |
| New Annex J, informative: the context rendering (section 4.2). | New annex | Half a page. |
| Recorded decision: links have no proposed state. The pull request is the review unit, `check --base` lists added items and links, attribution belongs to Git and Agent Trace. | Annex F, Annex G | None; removes a temptation to add fields. |
| Annex F becomes a fixed, versioned paragraph that projects paste verbatim, with the tool name as the only variable. | Annex F | None. |

**4.1 Annex I, command profile.** The profile standardizes what an agent types and what comes back. Tools implement it under any binary name; the Annex F paragraph refers to verbs only.

| Verb | Writes | Input | Output | Exit code |
| --- | --- | --- | --- | --- |
| `check [--base REV] [--format json\|sarif\|text]` | nothing | optional base revision for impact | Annex C result, SARIF or text | 0 no errors and no suspect or broken link; 1 findings; 2 could not run |
| `context <anchor\|ID> [--format json\|text]` | nothing | one anchor or item ID | Annex J rendering, or the same data as JSON | 0 found; 1 not found; 2 could not run |
| `stamp <link identity>...` | `trace.lock` only | link identities as printed by `check` | the stamped entries | 0 stamped; 1 a named link is broken or unknown; 2 could not run |

`check` and `context` MUST NOT modify any file, so an agent may call them freely. `stamp` is the only writer and accepts only named links; the profile defines no bulk option, because blind restamping is the failure the lock exists to prevent. An MCP binding exposes the same three operations as `ostf_check`, `ostf_context` and `ostf_stamp` with identical JSON, so an agent with MCP and an agent with a shell see the same data.

**4.2 Annex J, context rendering.** One anchor or ID in, one screen out, risk first:

```text
refund.go#CheckRefundLimit
  implements R-REFUND-LIMIT [accepted] Refund limit
    A refund must not exceed the original order, and refunds above the daily
    limit for an account need a second approval.
    controls RISK-REFUND-ABUSE  (risk-relevant: ask before changing)
    refines  N-REFUNDS
    tests    refund_test.go#TestRefundLimit
    links    implements valid, verifies valid
```

Risk-relevant items come first and carry the marker; the direct item shows its whole text, ancestors a title or first line; every link state appears once; the rendering is deterministic for a source view; a tool MAY append an `x-` block after the standard one. Target: 600 tokens for a function with two items.

**Exit gate.** The spec has at most 35 requirements and no new Core key; the schemas validate every existing example unchanged except for the `tags` default; the four-line example, the refund example and the Annex F paragraph are fixtures.

**Rows moved.** Find it 7 to 9, Write 7 to 8, Safe 7 to 8, Reason 5 to 6, Portable 6 to 7, Mark proposed 4 to 8. Freshness and feedback stay where they are: nothing runs yet.

**4.3 Outcome, 2026-10-24.** Phase 1 is done and the exit gate holds: 35 requirements, no new Core key, both examples validate, and the only example change is dropping `tags: true` from the refund example now that it is the default. [fixtures_test.go](fixtures_test.go) enforces the gate in CI ([fixtures](fixtures/README.md)).

Decisions taken while writing it that this plan did not spell out:

- **Tag scope.** With tags on by default, a top-level root would also have read the tags of nested roots. OSTF-102 now says a root covers the files beneath it except those beneath a nested root, and OSTF-133 reads tags only there.
- **Result schema.** [schema/result.schema.json](schema/result.schema.json) defines the result format, since three commands now return it. Every result item carries `riskRelevant`. `context` and `stamp` return the same format, restricted, rather than new shapes. One code was added, `STAMP_REFUSED`.
- **SARIF.** Annex D became normative for tools that emit SARIF, because Annex I offers `--format sarif` and a normative annex should not rest on an informative one.
- **Agent paragraph.** F.1 is the only normative part of Annex F. The paragraph is version 1, 190 words, and [fixtures/agent-paragraph.txt](fixtures/agent-paragraph.txt) holds the same bytes, which also delivers the copy-paste file planned for Phase 4.
- **`unstamped` does not fail `check`.** A new link is reviewed in its pull request before anyone stamps it; a team that wants a stricter gate uses a tool option.
- **Independent review.** A second model reviewed the Phase 1 text cold and found 14 defects, all fixed within the budget. The two that mattered most for agents: the paragraph allowed stamping only `suspect` links, so no first lock entry could ever be written, and `context` run from the top level missed a nested root. The others closed determinism gaps: impact on a failed graph or an absent base root, deletions, anchor spellings that bind the same definition, alias versus anchor precedence, which diagnostics a context keeps, unsupported languages in `context`, the origin of a link declared twice, current versus recorded fingerprints, reason order, shell quoting of identities, repeated items in the rendering, and several reasons in SARIF.
- **Expected outputs.** [example/expected/](example/expected/) holds the `check` and `context` results for the refund example, written from the spec text and cross-checked against the lock with the 0.2 prototype's f1 and go1 code. They are the first Phase 2 targets.

Measured on paper: the Annex J rendering of `context refund.go#CheckRefundLimit` is about 130 tokens against the 600 target, and Annex I runs to about 760 words with its table, which fills one dense page and leaves no room: the next rule it needs must replace a sentence. The rows above moved as planned, by reading the spec; none is measured until Phase 2.

## 5. Phase 2: make it real

**Goal.** Freshness, feedback and impact exist as running code, and two code paths agree.

**Work.**

- Port `conformance/reader.py` to wire 0.3: version, `tags` default, `external` and `sources`, the removed fields, `UNSUPPORTED_LANGUAGE`, the result format with `hint` and `impact`, SARIF output, exit codes, and the three verbs. Keep it independent code with no zztrace import.
- Convert the 112 suite cases to wire 0.3 with a reviewed migration note. Add cases for external items, duplicate externals, tags by default, tags in a language without an annex, `revision` without `external`, the result format, `hint`, `impact` on a fixed diff, each verb's exit codes, and the context rendering as golden text. Map every case to its OSTF identifier so `suite.json` fails when a requirement loses its cases.
- Make [example/expected/](example/expected/) the first passing cases. Note that the 0.2 prototype returns only error codes once any error exists; the port must keep reporting the states of unaffected links, as the Annex C.2 example shows (OSTF-150).
- Adopt wire 0.3 and the command profile in zztrace `go/trace`, keeping its existing MCP tools as aliases until the trials settle the names.

**Exit gate.** The reference checker passes the full suite and still passes the 0.2 fingerprint and lock vectors unchanged; zztrace passes the same suite from its own code path; the two implementations agree on every fingerprint, state and rendering; `check` runs under two seconds on a generated 10 000 file tree.

**Rows moved.** Freshness 2 to 9, Feedback 0 to 9, Reason 6 to 9, Write 8 to 9, Portable 7 to 9, Mark proposed 8 to 10, Few tokens 8 to 9.

## 6. Phase 3: make 80 percent honest

**Goal.** The languages most agents edit have normative annexes, so the use-case claim holds outside Go.

**Work.** Write the TypeScript and JavaScript annex and the Python annex under OSTF-164, one page each: files, test files and runner identities, symbols, spans, tokens, algorithm identifiers `ts1` and `py1`, tag comments, vectors. zztrace already has TypeScript locators; the annex turns them into a contract, and the reference checker implements them with tree-sitter as independent code.

**Exit gate.** Fixed vectors pass in both implementations; the TypeScript trial fixture reports every link valid; `UNSUPPORTED_LANGUAGE` still fires for a language with no annex.

**Rows moved.** Read intent 8 to 9. The other rows hold; this phase widens who the scores apply to.

## 7. Phase 4: remove friction

**Goal.** Everything an agent or its CI touches exists and installs in minutes.

**Work.** The MCP binding of Annex I in zztrace; a GitHub Action that runs `check`, uploads SARIF and fails on exit code 1; a pre-commit hook; the Annex F paragraph as a copy-paste file; converters from StrictDoc and Doorstop with a published loss report, so existing repositories switch without retyping.

**Exit gate.** An empty repository goes from nothing to a passing `check` in CI with the four-line file in under ten minutes following the README alone; a Doorstop sample converts and round-trips except for the documented losses.

**Rows moved.** Find it 9 to 10, Feedback 9 to 10, Few tokens 9 to 10, Portable 9 to 10, Safe 8 to 9.

## 8. Phase 5: measure

**Goal.** Every 10 on the scorecard is a measurement on frozen labels, not a reading of the spec.

**Fixtures.** Two small repositories, one Go and one TypeScript, each with about 40 items, a Jira-owned item, a risk control, tags, a lock file and the Annex F paragraph in its agent instructions file. Nothing else about OSTF is in the agent's context.

**Tasks, scripted, scored pass or fail.**

1. Explain why a named function exists and which tests cover it, from files alone.
2. Implement a new requirement: item, code, test and links in one change.
3. Change a risk control: ask before editing, recheck the suspect link afterwards.
4. Rename and move a linked function: fix the anchors and the tags.
5. Link new code to a Jira-owned item that already exists in `trace.yaml`.
6. Refuse a prompt that supplies a plausible but nonexistent ID: report it, do not tag it.
7. Summarize the impact of a given diff with `check --base` and run the named tests.
8. Recover from a deliberately broken lock line that `check` reports.

**Conditions.** At least two agents from different vendors. Each task runs with a shell-only tool and with the MCP binding. Three runs per cell. Labels frozen before any tuning of the spec or the paragraph.

**Metrics.** Task success rate; invented IDs that reach a commit; hand edits of `trace.lock`; calls before the first edit; tokens spent on OSTF content; identical behavior across the two tools with the same paragraph.

**Rule.** Where an agent fails because the spec or the paragraph is ambiguous, the spec changes within the simplicity budget and the cell reruns. Where it fails because the task needs dependency analysis or permissions, the failure is recorded as out of scope and the boundary wording in the output is checked for clarity. A target shown to be unreachable within the budget is lowered publicly, with the reason.

**Exit gate.** The scorecard reads 10 in every row, with two agents and two tools, and the per-cell results, failures and resulting spec changes are published.

**Rows moved.** Everything that is still a 9 becomes a 10 or is publicly lowered.

## 9. What stays out, on purpose

- Dependency analysis, test selection beyond direct links, and ranking. `impact` labels its boundary `direct` and stops.
- Permissions and approvals. The only in-format signal is `controls`; the rest is CODEOWNERS and the tool.
- A link-level review state. The pull request is the review unit.
- Telemetry, evidence records and agent authorship fields. Annexes E and G point to in-toto and Agent Trace.
- Any network dependency: no registry, no schema fetch, no profile download.

Completing all five phases does not make OSTF 1.0. The release gate in OSTF-171 still requires an independently maintained implementation and two organizations using the format on real changes.
