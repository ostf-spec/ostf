<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# OSTF 0.3: phased plan to reach 10 of 10 for coding agents without growing Core

Date: 2026-10-24. Status: Phases 1 to 5 done on 2026-10-24 (sections 4.3, 5.1 to 5.5, 6.1, 7.1 and 8.3) for the [0.3 draft](ostf.md), with two rows lowered in Phase 5. Baseline at the start: design for agents 7 of 10, usable by agents 2 of 10, because no implementation read wire 0.3.

## 1. Definition of done

A model cannot hash a token stream in its head, and OSTF will never standardize dependency analysis or permissions. So 10 of 10 does not mean "no tool needed". It means:

> An agent that has never seen OSTF, given only the repository and one paragraph of instructions, learns why a function exists, which tests to run and which links are stale in at most two calls, writes correct items and links on the first attempt, cannot merge an invented ID, and behaves the same whichever vendor's tool is installed. Verified by trials, not by reading the spec.

The scorecard is the acceptance test. The right-hand columns show the score each phase is expected to reach; only Phase 5 turns an expectation into a measurement.

| Agent need | Now | After P1 | After P2 | After P3 | After P4 | After P5 | Measured by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Find it | 7 | 9 | 9 | 9 | 10 | 10 | Agent locates the root and reads the rules in its first turn, every trial (lowered in Phase 5: every trial but T6, section 8.3). |
| Read intent and tests without a tool | 8 | 8 | 8 | 9 | 9 | 10 | Correct "why does this exist" from files alone in 95 percent of trials. |
| Read freshness | 2 | 2 | 9 | 9 | 9 | 10 | One `check` call returns every link state; two vendors' tools return the same bytes. |
| Write correctly | 7 | 8 | 9 | 9 | 9 | 10 | 95 percent of agent-written items and links pass `check` first time. |
| Fast feedback | 0 | 0 | 9 | 9 | 10 | 10 | `check` in CI and pre-commit, SARIF out, under two seconds on 10 000 files. |
| Few tokens | 8 | 8 | 9 | 9 | 10 | 10 | `context` for one function costs at most 600 tokens; at most two calls before editing (lowered in Phase 5: two per changed function or test, section 8.3). |
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

**4.3 Outcome, 2026-10-24.** Phase 1 is done and the exit gate holds: 35 requirements, no new Core key, both examples validate, and the only example change is dropping `tags: true` from the refund example now that it is the default. [fixtures_test.go](fixtures_test.go) enforces the gate in CI ([fixtures](fixtures/README.md)). An independent review of the text found 14 defects, all fixed within the budget. On paper, the Annex J rendering of `context refund.go#CheckRefundLimit` is about 130 tokens against the 600 target, and Annex I fills its page. The rows above moved as planned, by reading the spec; none is measured until Phase 2. The rulings taken along the way, among them tag scope, the result schema, the normative status of Annex D and the agent paragraph, are in the [decision record](decisions.md#phase-1-fix-the-contract).

## 5. Phase 2: make it real

**Goal.** Freshness, feedback and impact exist as running code, and two code paths agree.

**Work.**

- Port the 0.2 Python prototype to wire 0.3: version, `tags` default, `external` and `sources`, the removed fields, `UNSUPPORTED_LANGUAGE`, the result format with `hint` and `impact`, SARIF output, exit codes, and the three verbs. Keep it independent code with no zztrace import.
- Convert the 0.2 suite to wire 0.3 with a reviewed migration note, add cases for what 0.2 never tested, and map every case to its OSTF identifier so the suite fails when a requirement or Annex C code loses its last case (done in 2b, section 5.2), then `impact` on fixed diffs, `stamp` and SARIF output (done in 2c, section 5.3). `hint` gets no case, because conformance does not compare it (Annex C.2).
- Make [example/expected/](example/expected/) the first passing cases. Note that the 0.2 prototype returns only error codes once any error exists; the port must keep reporting the states of unaffected links, as the Annex C.2 example shows (OSTF-150).
- Give zztrace a code path on wire 0.3 with the command profile, keeping its existing MCP tools as aliases until the trials settle the names (step 2d, section 5.4).

**Exit gate.** The reference checker passes the full suite and still passes the 0.2 fingerprint and lock vectors unchanged; zztrace passes the same suite from its own code path; the two implementations agree on every fingerprint, state and rendering; `check` runs under two seconds on a generated 10 000 file tree.

**Rows moved.** Freshness 2 to 9, Feedback 0 to 9, Reason 6 to 9, Write 8 to 9, Portable 7 to 9, Mark proposed 8 to 10, Few tokens 8 to 9.

**5.1 Outcome, 2026-10-24.** Step 2a is done. [conformance/reader.py](conformance/reader.py) reads wire 0.3 as a Go Analyzer with `check` and `context`, reproduces the expected outputs byte for byte, passes the 39 vectors of 0.2 unchanged, and runs `check` on 10 000 files in about one second, interpreter start included. [check.py](conformance/check.py) runs the cases in [cases.json](conformance/cases.json), 49 check, 11 context and 2 projection at that point, and drives the command line; CI runs it. Writing the port exposed gaps where two readers could disagree, and an independent review found 17 defects, all closed without a new key or requirement ([decision record](decisions.md#step-2a-the-reader)).

**5.2 Outcome, 2026-10-24.** Step 2b is done. The 0.2 suite's 73 repository cases and 24 schema cases are converted: 75 carry on with their 0.2 fingerprints and the reason for any changed expectation, 21 are retired because 0.3 removed what they tested, and one was merged; [conformance/README.md](conformance/README.md#from-02) is the migration note. 31 new cases and two direct checks reach what 0.2 never tested. The suite holds 137 check, 11 context, 18 schema and 2 projection cases, and it fails when a vector file differs from 0.2 or when any of the 35 requirements or 36 Annex C codes loses its last case without a stated reason. Converting, then two independent reviews, found 13 defects, each fixed with a clarified rule and no new key or requirement ([decision record](decisions.md#step-2b-the-suite)).

**5.3 Outcome, 2026-10-24.** Step 2c is done. The reader implements `stamp`, `check --base` with `impact`, and `check --format sarif`. It runs no Git and no subprocess, so `check --base REV` reads the base view from the added option `--base-tree DIR` (Annex I.6) and exits 2 without it. [cases.json](conformance/cases.json) gains 19 stamp, 18 impact and 4 SARIF cases, and 8 more for the reviews' findings; the C.3 example is computed from the example tree, and stamping the example's six links from no lock rebuilds its `trace.lock` byte for byte. A mutation pass found one unpinned rule, an independent review found nine defects and a review of only the fixes found five more, all fixed with a check that fails when the fix is reverted ([decision record](decisions.md#step-2c-stamp-impact-and-sarif)). The last five fixes were not reviewed again.

**5.4 Step 2d, planned 2026-10-24.** Step 2d gives zztrace a code path on wire 0.3, which is the first time two implementations read the same text. Two things come before any zztrace code:

- **Review the unreviewed.** The five fixes from the second 2c review (the [decision record](decisions.md#step-2c-stamp-impact-and-sarif), last paragraph) get a third independent review of only those fixes, so 2d starts from a reviewed reader. It can run while the scoping pass runs.
- **Scope before writing.** A read-only pass over zztrace produces a package layout, which the maintainer approves before any code. The quick look so far: `go/trace` is about 21 700 lines on its own model (`schemaVersion: 1`), carries importers, ReqIF export and GitHub policy code that 2d does not need, and its `ostf_conformance_test.go` reads a 0.2 copy of the suite.

Recommended approach, to be confirmed by the scoping pass: do not convert zztrace's model to 0.3. Add a separate 0.3 reader package in zztrace that reuses its Go locator on `go/parser`, a genuinely different code path from the Python reader's tree-sitter, and that runs this repository's [cases.json](conformance/cases.json) from a checkout given by path, never from a copy, so the two implementations share one suite that cannot drift.

Milestones, each committed on its own and each passing every case it claims:

1. The 39 vectors of 0.2 and the check cases.
2. `context`, with the Annex J text byte for byte.
3. `stamp`, `check --base` with `impact`, and SARIF.
4. The command line, the MCP tools with zztrace's existing ones kept as aliases, and `check` under two seconds on the 10 000-file tree. The generator for that tree is committed under [conformance](conformance/README.md), so both implementations time the same files.

Rules for 2d, learned from 2a to 2c:

- **A disagreement is a specification defect first.** When the two readers differ, the fix is a clarified rule with a case. A reader changes to match the text, never to match the other reader.
- **Agreement is not proof.** Both readers are written from the same text, so they can share a blind spot. The independent review of each milestone reads the Go code against the specification, not against the Python reader, and asks for cases where the text allows two answers.
- **Annex I has no room.** A rule that 2d needs replaces a sentence; the page does not grow (section 2, rule 4).
- **Slower on purpose.** Steps 2a to 2c landed in one day and four reviews found 58 defects. The Phase 2 exit gate is agreement, not throughput: one milestone at a time, and a milestone with a failing case does not land.

Agreement is measured by running the suite in both implementations and by comparing the results of `check`, `context` and `check --base` on the refund example and on the generated tree, result for result. Phase 2 closes when the exit gate above holds; until then the Phase 2 column of the scorecard is an expectation, and the "usable today" score stays where Phase 1 left it, because nothing an agent installs reads 0.3.

**5.5 Outcome, 2026-10-24.** Step 2d is done and the Phase 2 exit gate holds. zztrace has a second reader, the package `go/ostf` with the command `zztrace-ostf` and its MCP tools, written from the text on `go/parser` and run on this repository's suite from a checkout. It passed the suite on its first complete run; a differential run over 542 generated inputs then found 285 differences, which came down to a dozen rules the text left open, each now settled with a case. A third review of the last 2c fixes and a review of the Go reader against the text found 3 and 11 more, all fixed. Both readers pass all cases and the 0.2 vectors, agree on every fingerprint, state and rendering of the example and of the generated 10 000-file tree, and run `check` on it in 0.19 s (Go) and 0.77 s (Python). zztrace's own `trace_*` tools read its own format and stay unchanged ([decision record](decisions.md#step-2d-a-second-reader)).

## 6. Phase 3: make 80 percent honest

**Goal.** The languages most agents edit have normative annexes, so the use-case claim holds outside Go.

**Work.** Write the TypeScript and JavaScript annex and the Python annex under OSTF-164, one page each: files, test files and runner identities, symbols, spans, tokens, algorithm identifiers `ts1` and `py1`, tag comments, vectors. zztrace already has TypeScript locators; the annex turns them into a contract, and the reference checker implements them with tree-sitter as independent code.

**Exit gate.** Fixed vectors pass in both implementations; the TypeScript trial fixture reports every link valid; `UNSUPPORTED_LANGUAGE` still fires for a language with no annex.

**Rows moved.** Read intent 8 to 9. The other rows hold; this phase widens who the scores apply to.

**6.1 Outcome, 2026-10-24.** Phase 3 is done and its exit gate holds. [Annex K](ostf.md#annex-k-normative-typescript-and-javascript-language-annex-algorithm-ts1) (`ts1`) and [Annex L](ostf.md#annex-l-normative-python-language-annex-algorithm-py1) (`py1`) each fill a page; their 55 hand-written vectors pass in both readers, which read TypeScript with tree-sitter and Python with CPython's own parser in one and gotreesitter in the other; the [TypeScript trial fixture](trials/fixtures/ts-shop/) reports all 111 links valid in both; and `UNSUPPORTED_LANGUAGE` still fires for Rust and Java. A differential run of 81 edge inputs found no difference, and an independent review found 27 more points, all settled ([decision record](decisions.md#phase-3-typescript-javascript-and-python)).

## 7. Phase 4: remove friction

**Goal.** Everything an agent or its CI touches exists and installs in minutes.

**Work.** The MCP binding of Annex I in zztrace; a GitHub Action that runs `check`, uploads SARIF and fails on exit code 1; a pre-commit hook; the Annex F paragraph as a copy-paste file; converters from StrictDoc and Doorstop with a published loss report, so existing repositories switch without retyping.

**Exit gate.** An empty repository goes from nothing to a passing `check` in CI with the four-line file in under ten minutes following the README alone; a Doorstop sample converts and round-trips except for the documented losses.

**Rows moved.** Find it 9 to 10, Feedback 9 to 10, Few tokens 9 to 10, Portable 9 to 10, Safe 8 to 9.

**7.1 Outcome, 2026-10-24.** Phase 4 is done and its exit gate holds. The reference reader installs as the `ostf` command from this repository and reads `check --base` from Git; [action.yml](../../action.yml) runs `check`, uploads SARIF and fails on findings, and [.pre-commit-hooks.yaml](../../.pre-commit-hooks.yaml) runs it before a commit, both exercised in CI; zztrace serves the MCP binding; [fixtures/agent-paragraph.txt](fixtures/agent-paragraph.txt) is the copy-paste paragraph; and [tools/](tools/README.md) converts Doorstop both ways and StrictDoc into OSTF, with the losses listed. From an empty repository the README's path takes seconds locally, and the GitHub side was measured in this repository's own CI ([decision record](decisions.md#phase-4-remove-friction)).

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

**Rule.** Where an agent fails because the spec or the paragraph is ambiguous, the spec changes within the simplicity budget and the cell reruns. Where it fails because the task needs dependency analysis or permissions, the failure is recorded as out of scope and the boundary wording in the output is checked for clarity. Where it fails because the model does not manage the task, the failure is recorded as a model limit and the text does not change. A target shown to be unreachable within the budget is lowered publicly, with the reason.

**Exit gate.** The scorecard reads 10 in every row, with two agents and two tools, and the per-cell results, failures and resulting spec changes are published.

**Rows moved.** Everything that is still a 9 becomes a 10 or is publicly lowered.

**8.1 Progress, 2026-10-24.** Phase 5 is under way and its exit gate does not hold yet. The [protocol](trials/protocol.md) was frozen before any scored run: the [Go](trials/fixtures/go-shop/) and [TypeScript](trials/fixtures/ts-shop/) fixtures, three conditions (the reference reader in a shell, zztrace in a shell, zztrace over MCP) and two agents, Claude Code with `sonnet` and Codex CLI with `gpt-6-astra` at medium effort. The two models are not matched: `gpt-6-astra` is Codex's largest model, taken from the maintainer's Codex default rather than chosen to match `sonnet`, so the Codex results may flatter the text. It stays for the rest of the trials so that the rounds compare. [Round 1](trials/results-round1.md), with agent paragraph 1, ran all 288 runs and passed 268; no invented ID reached a file and no run edited `trace.lock` by hand. Every failure was T7, and 18 of the 20 were Codex runs that ran the right tests without naming them, a gap the rule assigns to the text, so Annex F.1 became paragraph 2, which asks agents to also name the items and tests that the impact lists. [Round 2](trials/results-round2.md), with paragraph 2, was stopped at 86 of 288 runs to save credit. All 86 passed, T7 included; they are the first repetition of every task except T8.

Two rows stay below 10 in both rounds, and the trials show why. Find it (95 % in round 1) misses only Claude's T6 runs, which refuse the invented ID after reading `trace.yaml` without calling the tool; the frozen measure counts a miss although the answer is right. Few tokens (73 % in round 1, after a correction of the harness's write detector recorded in the [protocol](trials/protocol.md#harness-corrections); 78 % before it) misses because agents run one `context` per function they change, as the paragraph asks, so at most two calls before the first edit is the wrong target for a task that changes several functions; it is to be lowered publicly with that reason.

**8.2 Next steps, set 2026-10-24.** A review of Phases 1 to 5 on 2026-10-24 confirmed every gate above by running the suite in both readers, the fixture tests and CI, and settled how round 2 ends. Round 2 does not rerun the whole matrix: round 1 was complete, paragraph 2 changed only what T7 measures, and round 2's first repetition passed every task under every condition, so the paragraph regressed nothing. Only the cells that failed in round 1 need their three repetitions, as the Phase 5 rule says.

1. **End round 2 at 86 runs.** The 24 T7 runs that remained, repetitions 2 and 3, were not run: the maintainer chose to spend the credit on the small-model arm (step 5) instead. The cut and its reason are in the Round 2 section of the [protocol](trials/protocol.md), which allows a recorded change; round 2's T7 result rests on 12 runs, one per agent, condition and fixture.
2. **Lower two rows publicly, in the results and here.** Find it: Claude's T6 runs refuse the invented ID after reading `trace.yaml` without a tool call, so the row either excludes T6, whose correct answer needs no tool, or keeps the measure with a lower target; the choice is recorded with its reason when the scorecard is written. Few tokens: agents run one `context` per function they change, as the paragraph asks, so the target becomes at most two OSTF calls per changed function before the first edit.
3. **Write the outcome.** Regenerate the round 2 report, then write section 8.3 here and the Phase 5 entry of the [decision record](decisions.md) with the final scorecard, the small-model arm's scorecard beside it (step 5), the two lowered rows, the unmatched models (Codex's largest against `sonnet`, so Codex's numbers may flatter the text and Claude's are the conservative ones) and MCP use: in the MCP condition only 11 of 28 round 2 runs called an MCP tool, the rest used the shell binary also on PATH, so the portability row rests more on the shell than the heading suggests.
4. **Close Phase 5.** Update the status line at the top of this plan. Completing the five phases does not make OSTF 1.0: section 9 and OSTF-171 still require an independently maintained implementation and two organizations using the format on real changes, and that is the work after this plan.
5. **A small-model arm, before step 3.** The definition of done names an agent that has never seen OSTF, so a small model that passes says more about the text than a large one, and it answers the mismatch above from the other side. Run the matrix with Claude Code on `claude-haiku-5-5`, set through `OSTF_TRIALS_CLAUDE_MODEL`, with paragraph 2 and nothing else changed: one repetition of the eight tasks on both fixtures under the three conditions, 48 runs, then the other two repetitions if the first passes broadly. The arm is recorded in the protocol as an addition and published on its own, `trials/results-haiku.md` with its own scorecard, never pooled into the main matrix: the matrix measures whether two vendors' agents behave the same, the arm whether the paragraph carries a small model. The model never changes inside a round, because a failure could then be the model or the paragraph. Before the arm runs, the Phase 5 rule gains a third category: a failure that comes from the model not managing the task, not from the text and not from dependency analysis or permissions, is recorded as a model limit and changes nothing in the text, so a small model cannot push the paragraph past its budget. Codex does not take part, by the maintainer's choice. The arm and the rule are recorded in the [protocol](trials/protocol.md).

**8.3 Outcome, 2026-10-24.** Phase 5 is done, with two rows lowered and the limits below; the [decision record](decisions.md#phase-5-measure) keeps the rulings. [Round 1](trials/results-round1.md), with paragraph 1, ran all 288 runs and passed 268. [Round 2](trials/results-round2.md), with paragraph 2, stopped at 86 runs by the maintainer's choice and passed all 86, and every row of its scorecard reads 10 once two rows are lowered publicly: Find it leaves out T6, whose correct refusal needs no tool and which was the only task to miss it in either round, and Few tokens allows two OSTF calls per changed function or test, because the paragraph asks for one `context` per function. No run of either round put an invented ID in a file or edited `trace.lock` by hand.

The [small-model arm](trials/results-haiku.md), Claude Code on Haiku 5.5 with paragraph 2, passed 134 of 144. Read intent, Read freshness, Write correctly, lowered Few tokens, Reason about a change and Mark what it proposed read 10; Find it reads 8 even without T6, because Haiku often explains a function from the files without the tool, a right answer, and edited before any OSTF call in 5 runs; Safe reads 9 and Portable workflow 7. Five T6 runs created the nonexistent ID as a draft item, citing the paragraph's rule for new behavior, so paragraph 3 adds that an ID the user refers to but no file defines is reported, not created; with it, [Haiku passed all 18 T6 runs](trials/results-haiku-round3.md). Four T3 runs edited a risk control without asking after `context` had shown it risk-relevant; the rule records a model limit and the text did not change.

Four limits qualify these results. The two agents' models are not matched: Codex ran `gpt-6-astra`, its largest model, against Claude's `sonnet`, so Codex's numbers may flatter the text and Claude's are the conservative ones. Round 2's T7 result rests on 12 runs, not 36. Paragraph 3 was measured on Haiku only. And the MCP condition leaned on the shell: 42 of 96 MCP runs in round 1, 11 of 28 in round 2 and 30 of 48 in the arm called an MCP tool, the rest the binary also on PATH, so Portable workflow rests more on the two shell tools than on the binding. The harness was corrected after scored runs without changing any pass or fail of rounds 1 and 2, and the [protocol](trials/protocol.md#harness-corrections) records the corrections, the cuts and the discarded launches. Completing the five phases does not make OSTF 1.0: section 9 and OSTF-171 still require an independently maintained implementation and two organizations using the format on real changes, and that is the work after this plan.

## 9. What stays out, on purpose

- Dependency analysis, test selection beyond direct links, and ranking. `impact` labels its boundary `direct` and stops.
- Permissions and approvals. The only in-format signal is `controls`; the rest is CODEOWNERS and the tool.
- A link-level review state. The pull request is the review unit.
- Telemetry, evidence records and agent authorship fields. Annexes E and G point to in-toto and Agent Trace.
- Any network dependency: no registry, no schema fetch, no profile download.

Completing all five phases does not make OSTF 1.0. The release gate in OSTF-171 still requires an independently maintained implementation and two organizations using the format on real changes.
