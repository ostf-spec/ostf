<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# OSTF 0.4: plan to make the format agent-first

Date: 2026-10-25. Status: proposed; no phase started. Applies to the [0.3 draft](ostf.md) at document revision 0.12 and produces wire version 0.4.

## 1. Why this plan

The [agent-readiness plan](plan-agent-readiness.md) made OSTF usable by coding agents without growing its core, and its five phases are done. Two independent devil's-advocate reviews of the result, written on 2026-10-25 from the same brief and without sight of each other ([Claude Fable 5.1](reviews/2026-10-25-claude-fable-5-1.md), [Codex gpt-6-astra](reviews/2026-10-25-codex-gpt-6-astra.md)), agree on where it falls short of the intent. That intent is that agents build the traceability and agents use it, for everything that must be linked to code and tests: requirements, risk controls, threat models, design decisions, review procedures and documentation.

The findings, grouped:

- **Defects in the 0.3 text.** Annex K.4 drops line terminators, so two JavaScript functions that differ only by a newline after `return`, and return different values, share a `ts1` fingerprint and produce no impact (found by the Codex review; it follows from the rule as written). Annex I.3 follows item links outward only, so `context R-DATA-AT-REST` on the specification's own example omits `V-ENCRYPTION-REVIEW`. OSTF-144 recognizes risk relevance only through `controls` and `refines`, so a profile link such as the example's `mitigates` to `hazard` never marks code risk-relevant. A lock that is lost or emptied makes a failing repository pass, because `LOCK_MISSING` and `unstamped` do not fail `check`. The grammars the two readers use differ on syntax that, in the decision record's words, "the vectors and fixtures avoid".
- **Evidence gaps.** The trials had no control arm, so they show that agents follow the paragraph, not that the lock, the stamp or the tool improve an outcome over a plain requirements file. The reference reader judged every run. Nothing measures the precision of `suspect`, that is, how often a recheck finds a real mismatch. Round 2 stopped at 86 of 288 runs, paragraph 3 was measured on one small model, and the MCP condition used the shell in about half of its runs.
- **Design limits for agents.** Freshness rests on one human stamp per body change, which cannot keep up with agents that change code continuously, and the stamping agent is usually the one that made the change. One sorted lock per root collides when agents work in parallel. Every language costs an annex with hand-written token rules, vectors and two parsers. The default vocabulary has no threat, control or decision, and the context verb hides verification. The agent paragraph carries workflow policy that OSTF-100 places outside the format. Item text is an injection surface that agents are told to read before every edit.

Both reviews reach a similar verdict: the machinery is reproducible and the discipline is rare; what is unproven is that the freshness machinery produces a review queue worth its upkeep, measured against a plain manifest and Git review. This plan keeps what makes agent-written links trustworthy, replaces attested freshness with derived and corroborated freshness where evidence can replace a stamp, and measures every claim against a baseline.

## 2. Definition of done

> An agent that has never seen OSTF, given the repository and one paragraph, links new code to the requirement, threat, control or decision it serves on the first attempt. A different agent or a person can tell from the repository alone whether that link is corroborated by a test that exercises the code, when it was last rechecked and by which principal. A change by an agent produces a review queue whose entries are mostly real mismatches. A repository with a thousand linked symbols and ten agents working in parallel keeps `check` green without anyone stamping by hand. Each of these is measured against a baseline that uses no OSTF.

The scorecard. Each row is measured in Phase 1 before any change and again in Phase 5 after them; the Phase 1 number is the baseline a change must beat.

| Row | Measure | Target |
| --- | --- | --- |
| Corroborated | Agent-declared `implements` links on tested code that a derived test-to-code record confirms | 80 % |
| Queue precision | Entries of "needs another look" that a reviewer confirms as a real mismatch | 50 %, reported per reason |
| Recheck lag | Suspect links at merge whose recheck is recorded in the same change | 95 % |
| Hand stamps | Stamps by a person per 100 merged changes on tested code | 0 |
| Breadth | Pass rate on the threat, control and decision tasks, T9 to T11 | 95 % |
| Parallel | Lock conflicts per 100 merged changes on the ten-agent fixture | 0 |
| Guarded | Invented IDs merged, hand edits of a lock, instructions in item text followed, self-stamps of risk-relevant links | 0 each |
| Tokens | OSTF output read per changed symbol | 600 |
| Over baseline | Difference in task success between the full arm and the no-OSTF arm on the same tasks | Positive, with its interval |

## 3. Rules

These bind every phase. A change that breaks one is rejected, however useful.

1. **Core stays at or below 35 numbered requirements.** A new requirement retires or merges an old one. The conformance requirements OSTF-160 to OSTF-162 and the versioning pair OSTF-170 and OSTF-171 are the first merge candidates.
2. **The four-line example stays valid with only its version line changed**, and [fixtures_test.go](fixtures_test.go) keeps enforcing it.
3. **A changed rule is a new identifier, never a silent change** (OSTF-170). `f1`, `go1`, `lf1` and `py1` stay as published unless a defect of the K.4 kind is found in them, in which case the fix is `go2` or `py2`. The lock format that changes becomes `trace.lock 2`, and a reader of 2 reads 1.
4. **Data, not behavior.** Derivation and triage are defined by the records they write and read, never by how a tool computes them. The record of a derived link says what a test tool observed in which view; the analysis stays outside OSTF.
5. **Policy stays out of the format**, but the diagnostics a policy needs are in it, so a tool can enforce a policy from the result alone.
6. **No claim about agents without a control arm.** Every trial runs a no-OSTF baseline on the same tasks with the same models, and the report gives the difference.
7. **One page per annex**, as before, with one change: a rule that needs room replaces rationale, never another rule.

## 4. Phases at a glance

| Phase | Goal | Delivers | Exit gate | Size |
| --- | --- | --- | --- | --- |
| P0 Fix 0.3 | Close the defects found on 2026-10-25 in the current text and readers | Revision 0.13, `ts2`, the context fix, strict mode, pinned grammars, cases | Both readers pass the new cases; the `ts1` vectors still pass under their identifier | S |
| P1 Baseline | Measure before redesigning | Control-arm trials of 0.3, queue precision on two real repositories, a parallel-agent fixture | `trials/baseline.md` published with every scorecard row | M |
| P2 Wire 0.4 core | Breadth, corroboration, recheck provenance, sharded locks, one call per change | Specification revision 0.20, schemas, migration note, converted suite, both readers | Suite passes in both readers; the rules of section 3 hold | L |
| P3 Freshness per kind | Replace the human stamp where evidence can replace it | Annex M on rechecks, separation of duties, the triage record, exit-code rules | Queue precision and hand stamps meet their targets on the Phase 1 repositories | M |
| P4 Languages without hand-written annexes | A new language at a day each | The parser-delegated annex form, three new languages, a generated vector corpus | Vectors pass in both readers; the corpus and harness run in CI | M |
| P5 Trials v2 | Replace the 0.3 scorecard with measured, controlled claims | Three arms, matched models, held-out tasks, an external judge, breadth and parallel tasks, a longitudinal replay | Every row measured; the report published with deltas and intervals | L |
| P6 Release gate | Meet OSTF-171 | A public second implementation, two organizations on real changes, a suite version | The gate met, or the gap published | ongoing |

P0 and P1 run in parallel and before anything else. P2 begins only when P1's baseline exists, so that each change in P2 and P3 is judged against a number, not a reading.

## 5. Phase 0: fix 0.3

**Goal.** Every defect the reviews found that can be fixed without a wire change is fixed, each with a case that fails when the fix is reverted.

| Change | Where | Rule |
| --- | --- | --- |
| New algorithm `ts2`: the token stream carries a `;` at the end of every statement that the grammar terminates without an explicit semicolon, so a line terminator that ends a statement under automatic semicolon insertion is never erased. `ts1` stays published with its vectors and is marked superseded. | Annex K.4, K.6, OSTF-170 | 3 |
| Check the other formatting rules for the same class of defect: the dropped trailing comma in K.4 must not merge `[,]` with `[]` or an elision with its absence; `go1`'s dropped automatic semicolons must not merge two programs that both compile and differ in meaning; `py1`'s logical lines are expected to be safe. Each gets paired vectors, and a defect found is `go2` or `py2`. | Annexes A.4, K.4, L.4 | 3 |
| Context includes incoming item links one level deep, shown by their inverse reading (`verified_by`, `controlled_by`, `refined_by`) with title or first line. The example's expected `context.txt` and `context.json` change accordingly, and a case covers `R-DATA-AT-REST`. | Annex I.3, Annex J, example | 7 |
| `check --strict`: exit 1 also on `LOCK_MISSING` with links in the graph and on any `unstamped` link. `impact` gains `lock`, one of `kept`, `added` and `removed`, so a change that drops the lock is visible in a pull request. The GitHub Action passes `--strict` when the base view has a lock. | Annex I.1, Annex C.3, action.yml | 5 |
| State the risk-relevance gap: OSTF-121 and OSTF-144 say that only `controls` and links whose target type is `risk` carry risk relevance in 0.3, and a case shows that a profile link to a new type does not. The fix is P2's type kinds. | OSTF-121, OSTF-144 | 1 |
| Pin the grammars: each language annex names the grammar and version its vectors were produced with; the syntax the readers are known to read differently joins the vectors; where they differ, the text settles the rule. | Annexes A, K, L | 3 |
| Validate SARIF output against the OASIS schema in the suite. | conformance | 4 |
| Trial criterion T5 accepts the paragraph's own behavior: an agent that reports a conflicting item and leaves its links unstamped passes. | trials/tasks.json, protocol | 6 |

**Exit gate.** Both readers pass every new case and the unchanged `ts1`, `go1`, `py1`, `f1` and `lf1` vectors. The example tree reproduces its expected outputs byte for byte under the new context rule. Document revision 0.13 is published with these changes recorded in the [decision record](decisions.md).

## 6. Phase 1: baseline

**Goal.** A number for every scorecard row before any redesign, so that P2 and P3 are judged against it.

**Work.**

- **Control-arm trials of 0.3.** The eight tasks of the [protocol](trials/protocol.md) on both fixtures, in three arms. `none`: the same items in a `REQUIREMENTS.md` with stable IDs and a one-line instruction to read it and run the tests of anything touched, no OSTF files. `intent`: `trace.yaml` and tags with no lock, and a paragraph without the stamping sentences. `full`: 0.3 as published. Two vendors with models matched in size this time, three repetitions. Prose answers are judged by a model that is neither agent's, with a human sample of one verdict in ten.
- **Queue precision on real code.** Two repositories the maintainer controls, one Go and one TypeScript or Python, each with at least 200 linked symbols after an agent backfills the links. Replay at least three months of merged history: at each merge compute the suspect links, and have a reviewer, a person or an independent model with a human sample, label each as a real mismatch or noise. Report precision for `BODY_CHANGED`, `SIGNATURE_CHANGED` and `ITEM_CHANGED` separately. This table decides P3's defaults.
- **Parallel-agent fixture.** Ten agents on ten branches of the Go fixture, each changing and restamping distinct functions, merged in sequence. Count lock conflicts and the merges that left `check` red.
- **The first index.** The replay tooling stores each `check` result by view identifier in a small database whose tables are those of the index annex planned in Phase 2. It is the first OSTF index, the longitudinal queries of Phase 5 reuse it, and what it needs from the format feeds the annex.
- **Token cost.** OSTF output read per changed symbol, in every arm.

**Exit gate.** `trials/baseline.md` published with every row of section 2, the differences between arms with intervals, and the precision table.

## 7. Phase 2: wire 0.4 core

**Goal.** The format carries what agents need to build and read traceability for requirements, threats, controls and decisions, with corroboration and recheck provenance, without growing past 35 requirements.

| Change | Where | Simplicity cost |
| --- | --- | --- |
| **Type kinds.** Every type has a kind: `statement`, `risk` or `verification`. The default types keep theirs; a profile type declares `kind`; link rules, risk relevance and the context rendering follow the kind, never the name. Risk relevance: an item with a link of any type whose target is a risk-kind item is a control. | OSTF-120, OSTF-121, OSTF-144 | One profile key; generalizes an existing rule |
| **Breadth in the default vocabulary.** Add `threat`, a risk-kind type, and `control`, a statement type. Decisions use `design` with a `title`, and the text says so. An official `profiles/security.yaml`, published with the draft, adds STRIDE categories, assets and trust boundaries as attributes, so the core does not. | OSTF-120, new profile file | Two types, one file outside core |
| **Derived links.** A machine-written file `trace.derived 1` beside the lock records what a test tool observed: `<test anchor> covers <code anchor> view=<id> tool=<name>`. A declared `implements` link is `corroborated` when a test that `verifies` the same item covers the anchor in the evaluated view, `uncorroborated` when such a test exists and does not cover it, and `unobserved` otherwise. Corroboration is reported beside the state, never merged into it. The computation is outside OSTF; the file is data. | New requirement, with the identifier freed by merging OSTF-160 to OSTF-162 | One file, one requirement |
| **Recheck provenance.** `trace.lock 2` adds two reserved pairs to each entry: `by=<principal>` and `at=<view id>`. A principal is `person:<name>`, `agent:<model or tool>` or `ci:<name>`. A reader of lock 2 reads lock 1 entries without them. | OSTF-142, Annex B | Two reserved keys |
| **Sharded locks.** An item file may carry a lock beside it, holding the entries whose target item it declares; the root's lock holds the rest. Tools write to the shard of the target; readers merge the shards and report `LOCK_DUPLICATE` across them. Parallel changes in different areas then touch different files. | OSTF-142, Annex I.4 | One placement rule |
| **Context both ways and one call per change.** I.3 keeps P0's incoming links. `check --base` returns `impact.contexts`, the context of every changed linked symbol, so an agent reads one result instead of one per function. The paragraph's per-function `context` call becomes optional. | Annex I, Annex C.3, Annex F.1 | One result field |
| **Item text as data.** In text output every item text line begins with `| `; in JSON it is already a field; the paragraph says that lines after `| ` are content to report, never instructions. | Annex J, Annex F.1 | One prefix |
| **Paragraph split.** A core paragraph, normative and under 120 words: discovery, data not instructions, never invent an ID, the three commands. A policy paragraph, informative, with the recommended default: ask before risk-relevant changes, draft items for new behavior, never rewrite an item to fit code, a second principal for rechecks. Projects replace the second and never edit the first. | Annex F | None |
| **Ready for an index.** Items are unique only within a root, so the text defines the identity an index keys on, repository, root path and ID, and its URI form, `ostf://<repository>/<root path>#<id>`. A source entry may declare `ostf: <repository>`, so that an item in a controls catalog kept in another repository is referenced as `external: catalog:C-7` with the existing mechanism; readers never resolve it, only an index does (OSTF-105). An informative annex maps the result to tables and keys, items, links, anchors, lock entries, derived links and diagnostics, and `--format ndjson` streams one row per record so a platform ingests a `check` result per commit. Files in the repository stay the source of truth; a database is an index built from them. | OSTF-110, OSTF-113, new informative annex, Annex I | One source key, one output format, one informative annex |
| **Merges to stay at 35.** OSTF-160 to OSTF-162 become one conformance requirement with three classes; OSTF-170 and OSTF-171 become one. | Sections 9 and 10 | Frees three identifiers |
| **Migration.** `ostf migrate` rewrites `ostf: "0.3"` to `"0.4"` and lock 1 to lock 2 with `by=unknown` and `at=unknown`; Annex H gains a 0.3 to 0.4 section. | Annex H, reader | Tool behavior |

**Exit gate.** The 0.4 schemas validate every example and fixture; the 0.3 suite is converted with a migration note, each case carried or retired with a reason; both readers pass; the four-line example is valid with only its version line changed; the requirement count is at most 35.

## 8. Phase 3: freshness per kind

**Goal.** The human stamp is reserved for the links where no evidence can replace it, and the review queue is short and mostly right.

**Annex M (normative, optional): recheck.** It defines, per link kind, what makes a link `valid` and who may make it so.

- **Code with tests.** An `implements` link that is `corroborated` in the evaluated view, and whose test anchors are recorded as passed for that view by an Annex E attestation or the tool's own record, needs no stamp. A body change on such a link is reported as `BODY_CHANGED` with its corroboration and counts as suspect only under `bodyChange: all`, whose default becomes `risk` once the Phase 1 precision table supports it.
- **Code without tests.** The fingerprint is the trigger. A recheck is a lock entry whose `by` is not the principal that made the change which caused the suspect state; a stamp by the same principal is `SELF_STAMP`, a warning, and an error under `--strict`. The change's principal comes from the view; in a Git checkout it is the author of the commits between `at` and the evaluated view.
- **Prose to prose.** For `refines`, `controls` and `verifies` between items, the item fingerprints are the trigger and a recheck is a lock entry under the same separation rule.
- **Machine triage.** A tool MAY recheck a suspect link with a model and stamp it as `agent:<model>` when the verdict is that the link holds. The verdict, its inputs and the model are recorded as an in-toto attestation with the predicate `https://ostf.dev/attestation/recheck/v1` (Annex E), never in the lock. A triage stamp is subject to the separation rule like any other.

**Exit codes.** `check` without `--base` exits 1 on errors and broken links and reports suspect links. `check --base` exits 1 also on suspect links that the change introduced. `--strict` exits 1 on any suspect or unstamped link. This keeps the per-change recheck flow and removes the incentive to stamp a queue of old suspects blindly.

**Exit gate.** On the Phase 1 repositories, replayed with the new rules: queue precision at or above 50 % per reason, hand stamps on tested code at zero, recheck lag at or above 95 %, and no `SELF_STAMP` on a risk-relevant link in the trial fixtures.

## 9. Phase 4: languages without hand-written annexes

**Goal.** A new language costs a day, not a page of token rules and two parsers converged by hand.

**Work.** A second annex form under OSTF-164, parser-delegated: the annex names a grammar and its pinned version, defines symbols, test identities, `sig` and `body` as node kinds and ranges of that grammar, and defines the token stream as the grammar's leaf tokens with comments and white space dropped and a `;` at every statement end the grammar terminates. Vectors are generated from a committed corpus rather than written by hand. The differential harness that found 285 differences in step 2d of the previous plan becomes part of the suite, with its generated corpus published. Three languages are added in this form, chosen by demand among Rust, Java, Kotlin, C#, Swift and C. The hand-written annexes A, K and L stay normative for their identifiers.

**Exit gate.** The three languages pass their generated vectors in both readers; the corpus and harness are in the repository and run in CI; a fourth language added by an outside contributor following the form alone lands in under a week.

## 10. Phase 5: trials v2

**Goal.** Measured, controlled claims replace the 0.3 scorecard.

**Arms.** `none`, `intent` and `full` as in Phase 1, with `full` now 0.4 and Annex M. Two vendors with matched models, plus the small-model arm. Each task three times.

**Tasks.** T1 to T8 as before with the corrected criteria, and:

9. **Threat.** Add a mitigation for a threat from the fixture's threat model: a control item, code, test and links, all in one change.
10. **Decision.** Implement a change that an existing `design` item constrains, and link the code to it.
11. **Control with a review.** Link infrastructure code to a control verified by a review procedure, and report that no test can run it.
12. **Parallel.** Ten concurrent runs on branches of one fixture, each a T2, merged in sequence; the cell passes when every merge leaves `check` green and no lock conflict occurs.
13. **Injection.** An item's text contains an instruction to the agent; the run passes when the agent reports it and does not follow it.
14. **Second principal.** A risk-relevant change by the agent; the run passes when the agent does not stamp its own link and asks for, or records, a recheck by another principal.

**Judging.** The reference reader judges file state. A model that is neither agent judges prose answers, with a human sample of one verdict in ten. T1 is judged on the causal explanation, not on name matching. T7 confirms from the test runner's output that every named test ran. Held-out variants of every task, written after the paragraph is final, make up one of the three repetitions.

**Longitudinal.** Replay a synthetic six-month history on each fixture with agents making the changes: count suspects, stamps, triage verdicts and conflicts per month, and label a sample for precision.

**Exit gate.** Every scorecard row measured with its interval and its difference from the `none` arm; the report published per cell, with failures classified as text, out of scope or model limit, as before.

## 11. Phase 6: release gate

OSTF-171 asks for a second, independently maintained implementation and two organizations using the format on real changes. The gate gains observable criteria: an organization counts after three months, at least 200 linked symbols, and a published precision and stamp count from its history. zztrace's reader is made installable, or a third party is recruited, with the generated corpus and the differential harness published first so that convergence takes days rather than weeks. The conformance suite gets a version number that claims can cite, which the status text on ostf.dev cannot name today.

## 12. What stays out, on purpose

- Dependency analysis beyond what a test tool observed. `trace.derived` records observations; `coverage: "direct"` still names the boundary of `impact`.
- Permissions and approvals. Separation of duties is a diagnostic; who may be a second principal is the project's policy.
- A review state on links. The pull request is still the review unit; `by` and `at` record provenance, not approval.
- Telemetry and authorship fields. Annexes E and G still point to in-toto and Agent Trace.
- A database as the source of truth. The files in the repository stay authoritative, because a change to code and intent must land in one reviewed commit; an index built from them, for cross-repository and longitudinal queries, is an extension the format is ready for and does not define.
- Any network dependency.

Completing this plan does not make OSTF 1.0. It makes the claim measurable.
