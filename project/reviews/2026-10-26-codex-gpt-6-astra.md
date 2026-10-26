<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Second review of draft 0.3: Codex CLI, gpt-6-astra

Produced 2026-10-26 with `codex exec -m gpt-6-astra`, reasoning effort high, read-only sandbox, working directory the repository root, Codex CLI 0.164.0, session `01a1794b-f722-7ea2-9307-e9cb8252dcaf`, after the lock was removed and the record moved under project/. Unlike the [first review](2026-10-25-codex-gpt-6-astra.md), this one was given both 2026-10-25 reviews and asked to read them last, after forming its own view, and to say of each objection whether it is met, moot, still open or sidestepped. Codex also read, as it does by default, the AGENTS.md files on the path and the maintainer's local memory index for the repository. The prompt is reproduced below; the answer follows unedited, except that links were made relative to this directory. The brief wrongly called the suite version 2, from an earlier commit subject; the checkout reads version 1 since the first-revision cleanup, and the answer corrects it. The answer did not run the reader or the suites.

## Prompt

```text
You are reviewing the OSTF specification (Open Software Traceability Format), working draft 0.3 as it stands today, 2026-10-26, in this repository. Read-only: change nothing. You may run `ostf`, `go test` or the conformance script if they need no writes; do not rely on them.

Context. Two independent devil's-advocate reviews of this draft were written on 2026-10-25 from the same brief, blind to each other: `project/reviews/2026-10-25-codex-gpt-6-astra.md` (your own model) and `project/reviews/2026-10-25-claude-fable-5-1.md`. The maintainer says the issues they raised have since been fixed. The draft changed substantially since then: the lock file, fingerprints, stamping and the freshness states were removed from the format; `check --base` now lists what a change touches as information for the review, never a failure; Core is at 26 requirements; the trials gained a baseline arm (Phase 5) and a first field use (Phase 6); the plans, decisions and trials moved from `draft/0.3/` to `project/`. The release gate (a second, independently maintained reader and two organizations) is not claimed as met.

Read in this order. Form your own judgment from the first group before you open the earlier reviews, so that your verdict is yours and not a re-reading of theirs.

Group 1, the draft and its evidence:
- README.md
- draft/0.3/ostf.md (the full specification, every annex)
- draft/0.3/example/ (trace.yaml, trace.derived, README.md, the files, expected/)
- draft/0.3/fixtures/agent-paragraph.txt, draft/0.3/fixtures/agent-policy.txt, draft/0.3/fixtures/README.md
- draft/0.3/conformance/README.md, and cases.json as needed
- draft/0.3/tools/README.md
- project/plan-agent-first.md (at least sections 1, 2, 10, 11 and 12)
- project/decisions.md (at least the sections titled "Agent-first plan")
- project/trials/phase5.md, project/trials/results-phase5.md, project/trials/baseline.md
- project/trials/phase6/zztrace.md
- project/next-revision.md
- project/conformance-history.md

Group 2, after you have written your own view:
- project/reviews/2026-10-25-codex-gpt-6-astra.md
- project/reviews/2026-10-25-claude-fable-5-1.md

Answer these questions, grounded in the actual text. Quote or cite the requirement IDs, annex names, decisions and result tables you rely on.

1. Does OSTF solve a real problem? Name the person, tool or coding agent that has it, the situation in which they have it, what they do today without OSTF, and what OSTF changes for them. Say where the problem is real and where the format creates the work it then solves. Separate what the README claims from what the normative text guarantees.

2. Is this the right approach? Judge the shape the draft now has: YAML items with stable IDs, `code` and `tests` links to symbols, `@req` comments, `check` that fails on errors and broken links only, `check --base` that lists what a change touches, `context`, the agent paragraph and policy, the command profile, the optional annexes. For each of the simpler routes to the same three questions (Markdown with IDs and grep, requirements-as-code, an existing format with a common export, nothing but good commit messages and tests), say what it would reach and what it would lose against OSTF as it is now. Say whether the machinery that remains is earned by the evidence or by taste.

3. Judge the evidence. The conformance suite at version 2, the two readers (the README says zztrace reads wire 0.3 with separately written code; say what that is and is not worth as evidence), the Phase 5 trials with their baseline arm and judge, and the Phase 6 count. State what each shows, what it does not show, and what claim in the README or the specification rests on evidence that does not carry it.

4. The earlier objections. For each major point of the two 2026-10-25 reviews, say whether it is met, moot because the thing it criticized was removed, still open, or sidestepped by a wording change. Answer in particular: was removing the lock the right response, or did it remove the part of the format that justified the rest? Did the Phase 5 baseline settle whether the format beats its own rules written in plain prose, and what did the maintainer conclude from it?

5. If the approach is sound, what concrete changes would most improve it before 1.0, in priority order, and what should be removed rather than fixed?

Be specific and critical. Argue against the draft wherever the text supports it and concede wherever it does not; do not be balanced for its own sake, and do not be contrarian for its own sake. End with a one-paragraph verdict that answers in plain words: does it solve a real issue, and is this the right approach. Write the whole answer in English as Markdown, with links to the files you cite as paths relative to the repository root.
```

## Answer

**OSTF now has a defensible purpose: a portable, checkable record of declared intent and its links to code and verification. The evidence supports that narrower purpose more strongly than it supports an advantage for coding agents.** Removing the lock was a sensible simplification. The remaining question is whether maintaining this graph improves real reviews enough to justify its cost.

I read Group 1 and recorded my provisional judgment before opening either earlier review. This was a read-only examination; I did not run the conformance or test suites.

One correction to the brief matters: **the current checkout calls its conformance suite version 1, not 2.** The history records version 2, and its corrective case remains, but the subsequent publication cleanup reset the number. I discuss the consequence below.

**1. The problem is real, but its boundaries matter.**

The clearest user is a maintainer or coding agent changing unfamiliar code whose obligations are scattered across requirements, tests, design records and issue trackers.

The refund example makes this concrete. Someone editing `CheckRefundLimit` needs to know that it carries both an order-total limit and a daily-limit approval rule, why those rules exist, and which test checks them. Today they inspect callers and tests, search documentation, follow issue references, read Git history, or ask someone who remembers. OSTF gives them an explicit route from the function to `R-REFUND-LIMIT`, its parent need, its controlled risk and `TestRefundLimit`. That is useful retrieval, especially when names alone do not reveal the business constraint. [Example files](../../draft/0.3/example/trace.yaml), [expected context](../../draft/0.3/example/expected/context.txt).

There are three distinct beneficiaries:

| User and situation | What they do without OSTF | What OSTF changes |
| --- | --- | --- |
| Maintainer or agent modifying unfamiliar code | Reconstruct intent from prose, tests, history and people | Retrieves the recorded statement, rationale, related risks and verification through stable links |
| Reviewer assessing a change | Manually connect the diff to requirements and relevant tests | Lists directly changed definitions, linked items, graph changes and directly associated tests |
| Tool author integrating requirements with source analysis | Interpret each repository’s conventions or implement product-specific adapters | Implements a shared vocabulary, symbol-binding contract and result format |

Those benefits arise from **recorded relationships**, not from YAML itself. Stable identity is established by OSTF-110, the graph by OSTF-120 and OSTF-130–135, and direct-change reporting by Annex D.3. [Specification](../../draft/0.3/ostf.md).

The format also creates work. A team must decide which behavior deserves an item, write an accurate statement, choose an identity, maintain links, resolve conflicts and review changes to the record. The recommended policy adds a new draft item for new behavior. That can be valuable discipline, but it can also duplicate an adequate test description or design document. T10 illustrates the distinction: every `full` run followed the existing decision in its implementation, yet none linked the implementation to that decision. The missing graph edge was an OSTF record failure; it was not a failure to implement the decision. [Agent policy](../../draft/0.3/fixtures/agent-policy.txt), [Phase 5 outcome table](../trials/results-phase5.md#outcome-per-cell).

The same applies to malformed `trace.derived` and concurrent additions to an item file. OSTF introduces those artifacts and therefore introduces their maintenance failures. They cannot be counted as pre-existing software problems that adopting OSTF solves.

The README’s opening promise remains too broad:

> “Any tool, person or coding agent that can read YAML” can answer the three questions “from the repository alone.”

The normative contract guarantees less:

- A **Consumer** need not bind symbols or tags. Reading YAML does not recover links written only in source comments. OSTF-133 and OSTF-160 explicitly distinguish that incomplete graph.
- An **Analyzer** supports at least one language annex, not every language. `UNSUPPORTED_LANGUAGE` is a warning, so an unresolved unsupported symbol need not fail `check`.
- External items may omit their text. OSTF-113 explicitly says upstream content changes then do not show.
- Items need not have implementation or verification links. The reference reader’s unlinked-item notice is a tool-specific informational diagnostic.
- A declared verification link does not establish test execution, sufficient assertions or correctness.
- `coverage: "direct"` excludes dependency analysis. The example explicitly shows that breaking `NewService` does not identify `PAY-123` or its test through the unchanged `Service.Charge`.

These are reasonable limits. The headline should say that OSTF answers questions about **the intent and direct relationships recorded in the repository**, using a reader that supports the relevant languages. [README](../../README.md), [OSTF-113, OSTF-160 and Annex D](../../draft/0.3/ostf.md), [reader limitations](../../draft/0.3/conformance/README.md), [example’s dependency counterexample](../../draft/0.3/example/README.md#what-a-change-shows).

**2. The current approach is substantially better proportioned.**

The central design choices now fit together reasonably well.

- **YAML items with stable IDs:** justified for portable declarations and references. OSTF-101’s constrained YAML and OSTF-104’s strict unknown-key handling reduce accidental divergence. YAML over another readable serialization is largely taste; stable identity and defined semantics are the substantive choices.
- **`code` and `tests` symbol links:** justified when function-level navigation matters. They survive surrounding line edits and distinguish different obligations within one file. They still break on renames and moves, and the exact-text repair hint in OSTF-132 is deliberately limited.
- **`@req` comments:** useful because they travel with definitions. Their cost is parser-dependent discovery, test-file conventions and accidental recognition of documentation about tags. OSTF-134 sensibly merges duplicate declarations, but users still need a convention for when to use YAML versus comments.
- **`check` failing on errors and broken links:** a sound, understandable contract. It validates the record. It does not convert a textual change into an assertion that someone owes a semantic review.
- **`check --base`:** probably the strongest practical feature. It provides review material without pretending to decide whether intent still holds. Its limitations should remain visible in ordinary output, including unsupported languages, unlinked changes and nested-root scope.
- **`context`:** a worthwhile common operation. Annex F.3 now includes incoming verification items, which makes the manual-review example work. Its precisely defined traversal is useful, but it is still a selected neighborhood, not the complete consequence of changing an item.
- **Agent paragraph and policy:** separating project policy into K.2 is an improvement. However, K.1 still prescribes when to run a command, how to handle a user-named missing ID and what to put in a summary. Those are workflow rules. Making their exact wording normative remains difficult to reconcile with OSTF-100’s exclusion of change policy.
- **Command profile:** names, arguments, JSON results, exit codes and read-only behavior are worth standardizing if agents and integrations are intended consumers. Annex F.5’s prohibition on writes is particularly useful.
- **Optional annexes:** language binding and diagnostics support the central purpose; optional SARIF is a modest integration layer. Derived coverage and index guidance have a weaker claim to maturity. Making them optional reduces required implementation burden, but does not establish their usefulness or correctness.

Sources: [OSTF-100–135](../../draft/0.3/ostf.md), [command profile](../../draft/0.3/ostf.md#Annex-F), [agent guidance](../../draft/0.3/ostf.md#Annex-K).

The simpler alternatives remain credible:

| Route | How far it reaches the three questions | What it loses against current OSTF |
| --- | --- | --- |
| **Markdown, stable IDs and grep** | Can record the same explanations and code/test references. A person or agent can inspect the diff and search the relevant IDs. Phase 5’s `rules` arm demonstrates this route on the fixtures. | Standardized symbol resolution, graph validation, deterministic direct-impact output and a shared machine interface. Adding those gradually recreates much of OSTF. |
| **An existing requirements-as-code system** | Keeps requirements, relationships and source references in the team’s existing authoring workflow. Can answer the questions through that system’s conventions and tooling. | OSTF’s particular portable anchor, tag and result contract. Migration may also lose existing semantics: the published converters preserve Doorstop review stamps without interpreting them and drop StrictDoc function selectors. |
| **An existing format with a common context export** | Could provide the same read-side answers and change summaries while retaining the established source of truth. This directly serves agents that primarily consume intent. | Portable authoring across backends; exporters must define binding and completeness consistently. OSTF has not demonstrated that these users need to migrate their authoritative files. |
| **Good commit messages and tests** | Explains the reasons recorded when changes landed and checks executable expectations. Often sufficient for a small, well-understood repository. | A maintained current map from obligations to implementations, explicit manual verifications and risk relationships, and a reliable reverse lookup independent of historical commit boundaries. |
| **Executable requirements with IDs, plus design records** | Makes tested behavior directly discoverable and executable; design records explain choices that tests cannot. | Untestable requirements, review procedures, explicit implementation links and broader typed relationships need another representation. |

The existing-format comparison is supported by the project’s own [converter loss report](../../draft/0.3/tools/README.md) and [Annex L](../../draft/0.3/ostf.md#Annex-L); it is not evidence that every named product supplies an equivalent workflow.

**The basic graph and shared reader interface are earned as implementable mechanisms. Their maintenance economics are not yet earned.** The elaborate profile merging rules, global URI scheme, fixed agent wording and historical annotations are mostly design judgments awaiting independent users. The count of 26 Core requirements does not resolve that question: OSTF-121 alone contains numerous independent obligations, and numbered Core requirements exclude substantial normative annex text.

**3. The evidence is useful, but supports different claims at different strengths.**

**Conformance demonstrates reproducibility on specified cases.**

The suite has meaningful strengths: expectations written from the text, language span vectors, exact example outputs, scripted histories, impact cases, command-line behavior and SARIF schema validation. The current `cases.json` contains 191 checks, 28 contexts, 25 impacts, eight histories, three SARIF cases and 28 schema cases. These are much stronger evidence than schema validation alone. [Conformance README](../../draft/0.3/conformance/README.md), [cases](../../draft/0.3/conformance/cases.json).

The historical version-2 correction is especially valuable evidence. The readers disagreed about a malformed `revision` without `external`; OSTF-151 settled the question against the reference reader, which was corrected. This shows the process can treat the text as authoritative rather than merely forcing another implementation to copy Python. [Conformance history, “From suite version 1”](../conformance-history.md#from-suite-version-1).

But the present publication resets the suite to version 1 while retaining that case. The [current claim](../../draft/0.3/conformance/README.md#suite-version), [case metadata](../../draft/0.3/conformance/cases.json) and historical account therefore cannot be understood through the version number alone. This was a deliberate cleanup, not an omitted fix, but it weakens the purpose of OSTF-163’s reproducible conformance identity. The publication needs an explicit mapping or a new, unambiguous suite identifier.

Other limits remain:

- Requirement-to-case coverage is not coverage of every clause or combination.
- Consumer expectations are still absent.
- The reference reader admits accepting some Go syntax that the normative parser rejects.
- Attribute value-type semantics and diagnostic subjects remain unsettled in the text.
- The 476-tree differential corpus is correctly described as a convergence aid, **not conformance evidence against an independent oracle**.

These are stated in the [conformance README](../../draft/0.3/conformance/README.md) and [next-revision questions](../next-revision.md).

**The second reader is real implementation evidence, not independent adoption evidence.**

zztrace’s wire-0.3 reader is a separately written `go/ostf` package with a `zztrace-ostf` command. It is distinct from zztrace’s older trace format and its existing `trace_*` MCP tools. Its Go parsing uses Go’s own parser; the reference reader uses tree-sitter for Go. That separation has exposed real ambiguities and bugs. [Decision record, “Step 2d: a second reader”](../decisions.md#step-2d-a-second-reader).

It is nevertheless the maintainer’s own tool, developed within the same effort and converged against shared cases. Shared grammar ancestry also limits parser independence for some languages. It demonstrates that another implementation can be written and made to agree. It does not demonstrate independent maintenance incentives, outside implementer experience or an interoperability ecosystem. The README is right not to claim OSTF-170’s release gate is met.

**Phase 5 answers the missing baseline question, with an unfavorable result for a broad agent-benefit claim.**

The decisive table is:

| Arm | Task outcomes on the primary comparison tasks |
| --- | --- |
| Plain requirements with a minimal instruction, `none` | 88/144, **61%** |
| Plain requirements with the workflow rules, `rules` | 131/144, **91%** |
| OSTF declarations and rules without the tool, `intent` | 131/144, **91%** |
| Full OSTF workflow, `full` | 122/144, **85%** |

`full − none` is **+24 percentage points**, with the reported interval +13 to +33. `full − rules` is **−6 points**, with the reported interval −14 to +1. [Phase 5 verdict and arms tables](../trials/results-phase5.md).

This supports **no demonstrated task-outcome advantage over equivalent prose rules**. It does not prove universal equivalence or that OSTF makes agents worse. The maintainer draws the appropriate narrower conclusion:

> “the format is not shown to improve task outcomes beyond the same rules on a plain requirements file.”

The record then attributes the observed gain over `none` to the rules and retains the claim about maintaining a checkable record. [Decision record, “What the format shows”](../decisions.md#agent-first-plan-phase-5-trials-v2).

The other results deserve equally specific readings:

- **106/110 corroborated links:** agents usually linked tested code that a verifying test actually exercised. It does not establish that the test checked the requirement, that every necessary implementation was linked, or that a stored observation remains current. `intent` achieved 113/117 without the tool.
- **Zero broken links in 69 merged changes:** encouraging evidence of record maintenance in a synthetic replay. The comparison is two stale references in 67 `none` changes. There is no `rules` replay, so this does not isolate the format from maintenance instructions.
- **107 items listed, 1.6 per change:** demonstrates manageable output on this workload. It does not measure whether reviewers found the list useful or whether consequential indirect impacts were omitted.
- **82/85 “still holds” claims judged correct:** encouraging, but conditioned on claims made and items listed. It does not measure recall over all obligations affected by the changes.
- **Breadth, 24/36:** threats and review-verified controls passed; decision linking failed in all 12 `full` cells, despite correct implementation of the decision.
- **Parallel work:** `full` passed only 1/12 cells, with 18 conflicting merges. The other recording arms also performed poorly. The problem was concurrent editing of the shared record file, not YAML specifically.
- **Guarded:** zero invented IDs and zero followed injected instructions are positive observations. Fourteen derived-file edits remain a failure. They are not eliminated by moving the file into an optional annex.
- **Tokens:** the measured median was 1,365 per changed symbol versus 826 for `rules`. Annex G’s approximately 600-token single-context aspiration is a different measure, so this is not a literal contradiction, but it does defeat an inference of low total interaction cost.

Sources: [verdict](../trials/results-phase5.md#verdict), [parallel merges](../trials/results-phase5.md#t12-merges), [longitudinal replay](../trials/results-phase5.md#longitudinal-replay).

The study is materially stronger than its predecessors: four arms, held-out variants, an external prose judge, clearer outcome criteria and published corrections. Its limits still matter:

- Two language versions of one shop are few independent situations.
- The reported intervals treat cells as independent despite repeated tasks and shared fixtures.
- Only the designated small models ran.
- The 149-verdict human sample remains unlabelled.
- The judge was not reliably blinded because answers could reveal their arm.
- The prose instructions are adapted across arms, not identical interventions differing only in serialization.
- T12 left the primary gate after nine scored T1 cells, before T12 ran. This favored the primary comparison, but was disclosed, and the result including T12 still appears.
- The tested `full` configuration included derived links; moving them out of Core was not followed by a fresh measurement of a configuration without them.

These qualifications appear in the [pre-registration](../trials/phase5.md) and [results](../trials/results-phase5.md). They limit generalization without nullifying the experiment.

**Phase 6 is an adoption starting point, not a field result.**

Its table reports **zero changes**, **0.0 months**, and **516 linked symbols: 108 code definitions and 408 test anchors**. The size threshold is met under the chosen counting rule. There is no observed maintenance rate yet. [Phase 6 count](../trials/phase6/zztrace.md).

The first deployment has already supplied useful qualitative evidence: frozen older-format fixtures make a top-level `check --base` fail; documentation of tag syntax was read as tags; ignored source copies caused local-only diagnostics. The chosen workaround was a package-level root. These are actual adoption costs, not hypothetical objections. [Plan §11](../plan-agent-first.md#11-phase-6-release-gate).

The current README does **not** claim superior agent outcomes or a completed release gate. That restraint deserves credit. Its unsupported implications are narrower: universal YAML-only answers, automatic compliance after pasting the paragraph, and the suggestion that every changed function’s purpose will be shown. The normative limits and trial failures do not support those implications.

**4. The earlier objections are not all “fixed.” Some were fixed, some removed, and some remain unanswered.**

The following covers the major points of the [Codex review](../reviews/2026-10-25-codex-gpt-6-astra.md) and [Claude review](../reviews/2026-10-25-claude-fable-5-1.md). Requirement and annex references below are to the current [specification](../../draft/0.3/ostf.md).

| Earlier objection | Assessment today |
| --- | --- |
| **Fingerprint normalization erased meaningful JavaScript line breaks.** Codex. | **Moot through removal, with the surviving behavior fixed.** Fingerprints are gone; Annex D.3 compares span text, and `impact-line-break-after-return` covers the remaining impact obligation. |
| **Noisy `suspect` states created repeated stamping work.** Both. | **Moot as a failure mechanism.** Changes are informational. Review noise remains possible because formatting and comments inside spans now count, but it no longer forces stamps or fails CI. |
| **Blind/self-stamping and deleting the lock could turn failure into success.** Both, especially Codex. | **Moot through removal.** There is no lock or freshness state to manipulate. Whether an independent semantic review occurs remains outside the format. |
| **Helper changes could break behavior without flagging the traced requirement.** Both. | **Still open as a deliberate boundary.** The example retains the `NewService` counterexample. Renaming the third question to “which items a change touches” reduces the claim; it does not supply dependency analysis. |
| **Incoming manual verification and controls were absent from context.** Both. | **Met.** Annex F.3 includes incoming item links; `context-incoming-verification` and related cases pin the behavior. |
| **A profile’s `mitigates`/`hazard` relationship escaped risk relevance.** Codex. | **Met.** OSTF-120 uses type kinds and recognizes a statement linked to a risk through any link type. `risk-relevance-follows-kind` tests precisely that example. |
| **Readers accepted different language syntax while vectors avoided it.** Both. | **Partly met; residual limits remain.** Pinned grammars, explicit exclusions and new vectors address known examples. The reference reader still admits Go parser differences. Shared TypeScript grammar behavior remains a correlated limitation. |
| **The immutable agent paragraph embedded project policy.** Both. | **Partly met.** Approval, drafting and requirement-editing policy moved into replaceable K.2. K.1 still mandates workflow and response behavior verbatim. |
| **A context call before every edit would scale badly.** Claude. | **Met structurally, not economically.** K.1 no longer demands that call; `check --base` supplies contexts together. Phase 5 nevertheless missed its token target. |
| **External items could lack local intent; rationale changes were ignored.** Codex. | **Split.** Annex F.3 now includes rationale in item-change comparison. External text remains optional, so the repository-only completeness objection remains. |
| **No control arm; trials measured obedience to the supplied workflow.** Both. | **Met experimentally.** Phase 5 supplies `rules` and `intent`. Its result does not show a format advantage beyond the rules. The claim is narrowed, not vindicated. |
| **The reader judged its own workflow and weak string matching overstated success.** Both. | **Partly met.** A different model now judges prose, T1 checks explanation, and T7 checks test execution more carefully. The reader still judges graph state; the human audit remains pending. |
| **Final wording was insufficiently retested; task diversity and MCP evidence were weak.** Codex. | **Partly met.** The paragraph’s wording was exercised across the new small-model matrix and held-out variants. Broad task diversity, large-model validation and isolated MCP portability remain unestablished. “First attempt” is still stronger than a final-state pass. |
| **Parallel agents collide in a shared lock.** Claude. | **Moot for the lock; still open for authoring.** T12 found conflicts in the item file. Phase 6’s one-item-per-file convention is sensible, but its field count has no changes yet. |
| **Threat/control breadth and trust in agent-authored links were weak.** Claude. | **Partly met.** Default types and a security profile exist; threat/control tasks passed. Decision linking failed. Coverage observations support execution relationships, not semantic truth. |
| **Prompt injection and self-attestation were insufficiently guarded.** Claude. | **Partly addressed, not established as safe.** Item text is marked as data and no trial injection was followed. Codex did not report injected instructions, and second-principal behavior failed in its `full` cells. Moving review into a PR does not prove it happens. |
| **Core complexity, implementation independence and real maintenance value were unearned.** Both. | **Reduced, but still open.** Removing hashes and locks is a substantial cut. Profiles and annexes remain significant. Separately written readers are useful; independent maintenance and longitudinal outside use remain release work. |
| **SARIF lacked schema validation.** Codex. | **Met.** The conformance documentation now specifies validation against the OASIS schema. |

The fixes and removals are recorded in the [Agent-first decision sections](../decisions.md#agent-first-plan-phase-0-fix-03); the remaining experimental failures are in [Phase 5](../trials/results-phase5.md).

**Removing the lock was the right response.** Phase 1 measured real mismatches in only 18/204 body-change alerts and 1/96 signature-change alerts. Those estimates depend on backfilled items and model labels, but they give a concrete reason to question mandatory freshness work. The proposed quieter system then missed its pre-registered recall gate: 17/20 rather than 90%. That small, model-labelled result is not a universal disproof of freshness tracking. It was nevertheless a reasonable stopping point for this draft. [Baseline scorecard](../trials/baseline.md#scorecard), [Phase 3 verdict and fallback](../plan-agent-first.md#8-phase-3-the-graph-without-the-lock).

The lock did not justify stable IDs, graph validation, symbol binding or portable context. Those have independent value. What disappeared was the claim that OSTF maintains a reproducible queue of relationships awaiting recheck. The replacement is an explicit trade: review material and Git change information, with semantic judgment left to the reviewing process.

I also reject two overstatements in the Claude review. Passing tests do not establish that a requirement remains satisfied; the decision record reports four labelled mismatches whose linked tests still passed. And an agent backfilling a repository does not make authoring cost disappear: verification of that backfill and subsequent maintenance remain work. [Decision record, “Passing tests do not clear a link”](../decisions.md#agent-first-plan-phase-2-wire-04-core).

The Phase 5 baseline therefore **settled what can currently be claimed**, not which approach wins universally. The maintainer correctly concluded that the rules carry the measured task-outcome gain, while retaining the narrower record-maintenance case. Optionalizing derived links and restating breadth/token claims are honest reductions in scope. They should not be described as demonstrated repairs to the failed behaviors.

**5. Before 1.0, prioritize the following changes.**

1. **Publish one precise contract and one reproducible conformance identity.**  
   Narrow the README’s opening to recorded intent and direct relationships. Explain what a green check does and what unsupported or unlinked content leaves unknown. Resolve the suite-number reset explicitly. Keep historical records, but provide a clear mapping to the current document, annexes and suite.

2. **Measure the remaining value proposition in real reviews.**  
   Continue Phase 6 and recruit an independently maintained reader and an outside organization. Measure reviewer time, useful findings, missed affected obligations, incorrect-but-resolving links, record-editing effort and merge conflicts. Include the `rules` baseline in a maintenance comparison. Broken-link counts and items listed measure activity and structural health; they do not establish benefit. Finish the human judge sample before leaning heavily on judged outcomes.

3. **Fix repository scope before widening language support.**  
   The first deployment already required avoiding the recommended top-level root. Define how readers distinguish active roots from archived examples and fixtures, and make local versus CI file selection predictable. Preserve explicit reporting of excluded roots. Do not make agents repair frozen historical fixtures merely because they contain `trace.yaml`. [Plan §11](../plan-agent-first.md#11-phase-6-release-gate).

4. **Close the text’s interoperability gaps.**  
   Specify profile attribute value types, settle diagnostic subjects, add Consumer expectations and align parser acceptance with the claimed annexes. Treat grammar updates as explicit compatibility decisions. The unanswered questions in [next-revision.md](../next-revision.md) belong ahead of more types, languages or integrations.

5. **Make the agent text optional guidance rather than an immutable normative prompt.**  
   Preserve the command and result contract. Keep project policy visibly separate. Clarify the apparent conflict between “Never invent an ID” and creating a legitimate new item, and address decision linking in a later, separately measured revision. Do not keep appending sentences solely to make each benchmark failure pass.

6. **Defer derived corroboration from the 1.0 promise unless its evidence semantics improve.**  
   Annex E.1 explicitly leaves the relationship between the observed and evaluated views outside OSTF. Consequently, `corroborated` can describe a stored observation from an unchecked older view. The example even uses manually supplied `view=unknown` observations. Keep this experimental or call it a recorded coverage observation; do not let it imply current validation. A credible producer and view-binding story matters more than preserving three attractive result labels. [Annex E](../../draft/0.3/ostf.md#Annex-E), [example explanation](../../draft/0.3/example/README.md).

7. **Narrow the index annex to what its output actually supplies.**  
   Annex I’s table expects item text and external identity from results, but ordinary `check` output need not include them. The published example demonstrates their absence. Source-to-root mappings needed for the proposed cross-root join are also not in the standard result envelope. Either specify the additional inputs an index needs or defer the ingestion recipe until an independent consumer implements it. This is an incomplete informative recipe, rather than a violation of the normative NDJSON framing. [Annex I](../../draft/0.3/ostf.md#Annex-I), [expected check result](../../draft/0.3/example/expected/check.json).

What should stay removed is the lock, stamping, fingerprint normalization and automatic freshness states. What should be removed from the standard’s obligations is the exact agent prompt. What should be deferred is a claim that optional coverage observations provide current corroboration, and an index-export promise whose payload is incomplete. The small-file and requirement-count budgets can remain editorial aids, but should stop substituting for measurements of implementation and maintenance burden.

**Verdict:** OSTF solves a real issue: maintainers, reviewers and coding agents need a dependable way to find the intent attached to code and the verification attached to that intent. Its current combination of stable items, symbol links, strict validation, context and informational change summaries is a reasonable approach for repositories that need an explicit traceability graph. Removing the lock improved that approach by dropping expensive, weakly justified freshness machinery. The evidence does not show that OSTF makes agents more successful than equivalent rules over plain requirements, and it does not yet show that real teams recover its maintenance cost. Continue it as a focused interoperability draft, finish the contract and obtain independent field evidence before calling it a broadly justified standard.