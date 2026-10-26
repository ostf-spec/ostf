<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Independent review of draft 0.3: Codex CLI, gpt-6-astra

Produced 2026-10-25 with `codex exec -m gpt-6-astra`, reasoning effort high, read-only sandbox, working directory the repository root, Codex CLI 0.164.0. The reviewer had not seen the [Claude review](2026-10-25-claude-fable-5-1.md) written from the same brief. The prompt is reproduced below; the answer follows unedited, except that absolute paths were made relative to this directory and line numbers were removed from links. Where the answer says it ran the reader, the maintainer has not rerun that command; the two defects it reports in Annex K.4 and Annex I.3 follow from the rule text as written.

## Prompt

```text
You are reviewing the OSTF specification (Open Software Traceability Format), working draft 0.3, in this repository. Read-only: change nothing.

Read at least these before answering:
- README.md
- draft/0.3/ostf.md (the full specification, including all annexes)
- draft/0.3/decisions.md
- draft/0.3/plan-agent-readiness.md
- draft/0.3/example/ (trace.yaml, trace.lock, README.md)
- draft/0.3/fixtures/agent-paragraph.txt
- draft/0.3/trials/protocol.md and the results files beside it

Then play devil's advocate. Several reviewers have agreed that this specification fills a gap. Your job is to argue the other side as strongly and concretely as you can, grounded in the actual text:

1. Is the gap real, and is this the right approach to it? Where is the design over-built, under-evidenced, or solving the wrong problem? Name specific requirements, annexes or decisions.
2. What other approaches would reach the same goal (a person, tool or coding agent answering from the repository alone: why does this code exist, which tests verify this requirement, which links need another look) with less machinery? For each alternative, say what it would lose compared with OSTF.
3. Judge the evidence: the conformance work, the two readers, and the agent trials. What do they show and what do they not show?
4. If the approach is sound, what concrete changes would most improve it before 1.0? Prioritize.

Be specific and critical rather than balanced for its own sake. Quote or cite the requirement IDs and annex names you are talking about. End with a one-paragraph verdict. Write the whole answer in English as Markdown.
```

## Answer

**OSTF demonstrates that its machinery can work. It has not yet demonstrated that the machinery is worth maintaining.** The strongest case against it is that the difficult problem is keeping intent accurate and reviewing meaningful changes, while OSTF primarily standardizes declarations and detects changes to selected representations. Those are useful capabilities, but the evidence does not establish that this particular combination beats simpler repository conventions.

I read all the requested material, including every annex and all four trial reports, and inspected the conformance documentation and trial scorer. I also ran two narrow, read-only checks. Nothing was changed.

**1. The gap is plausible; the proposed solution is not yet justified.**

**The opening claim is broader than the contract.** The README promises answers to “why does this code exist,” “which tests verify this requirement,” and “which links need another look.” The actual guarantees are narrower:

- OSTF records what someone *declared* the code implements.
- It records which tests someone *declared* verify a statement.
- It detects changes to particular fingerprinted inputs.

OSTF-145 correctly disclaims correctness, test success and dependency coverage. But that leaves the central adoption question unanswered: how often do those declarations and fingerprints improve a real maintenance decision enough to pay for their upkeep? Annex G already identifies several requirements-as-code systems. The unproven gap is therefore interoperable, worthwhile freshness tracking, not the existence of repository-local traceability itself. [Specification, OSTF-145 and Annex G](../../draft/0.3/ostf.md)

**The freshness model can be noisy and blind at the same time.** Under OSTF-144, a local-variable rename or logging change can require restamping. Conversely, the example explicitly demonstrates that removing the receipts-map initialization from `NewService` leaves every link valid even though payment behavior breaks. Linking the whole file catches more changes but increases irrelevant alerts; the Terraform example makes even comments significant.

This is not an argument that OSTF should standardize dependency analysis. It is an argument that its central product hypothesis remains untested: **does this particular approximation produce a useful review queue?** The trials measure whether agents complete stamping workflows, not whether the queue catches consequential drift with acceptable noise. [Example: “What the stamps say”](../../draft/0.3/example/README.md)

**There is also a fingerprint defect inside the declared boundary.** Annex K.4, “Tokens,” drops line terminators. Consider these two JavaScript functions:

```javascript
function f() { return 1 }
```

```javascript
function f() { return
1 }
```

The first returns `1`; the second returns `undefined`. I confirmed that with Node. The reference reader produces identical signature and body token streams for them. Using an in-memory repository and a lock generated for the first version, the second version produces:

```json
{
  "state": "valid",
  "checkFails": false,
  "impact": {
    "changed": [],
    "tests": []
  }
}
```

This is not the helper-dependency limitation acknowledged by OSTF-145. Behavior changed **inside the linked function**, and the normalization erased it. Annex C.3 also uses the body token stream to determine impact, so both freshness and change reporting miss it. The rule in the specification needs correction. [Annex K.4](../../draft/0.3/ostf.md)

**The lock records a claim of rechecking, without establishing that a recheck occurred.** Annex I.4 merely writes current fingerprints. It does not require evidence that the item was read, the relationship assessed, or tests executed. That separation is legitimate for a format, but the stated safeguard against blind restamping is weak: accepting only named links prevents an accidental `--all`, yet an agent can enumerate every identity and pass them all to `stamp LINK...`.

The README’s statement that a recheck “costs one `context` call” substantially understates the cost. Retrieving the context costs one call. Deciding whether the code and tests still satisfy the requirement is the expensive part.

The decision that **unstamped links do not fail `check`** further weakens what a green check communicates. Under OSTF-143 and Annex I.1, an absent lock produces no states and need not fail; an empty lock leaves links unstamped and need not fail. Thus losing freshness history can make a previously failing repository pass. This need not be malicious: a mistaken merge or reset is enough. [Phase 1 decision](../decisions.md), [Annex I](../../draft/0.3/ostf.md)

**The “simplicity budget” measures document shape rather than complexity.** Thirty-five requirement IDs, four lines to start, and one page per annex do not constrain the number of concepts an implementer must support. OSTF-121 alone introduces vocabulary merging, endpoint rules, custom attributes, inverse names and cycle policies. Add language-specific symbol binding, canonical hashes, a bespoke lock grammar, diagnostics, result JSON and command semantics, and this is a substantial protocol.

The decision record explicitly describes deleting explanatory material to keep Annex I on one page. That optimizes a page count at the expense of explanation. Likewise, preserving old hashes is a compatibility decision, not evidence that their design is minimal or correct. [Plan §2](../plan-agent-readiness.md), [Decision record, step 2c](../decisions.md)

**Profiles promise more semantic flexibility than the common workflow understands.** OSTF-121 permits custom links, and the example profile defines `mitigates` targeting `hazard`. But OSTF-144’s risk relevance recognizes specifically `controls` and propagation through `refines`. A custom `mitigates` relationship alone does not trigger the risk-relevant marker or `bodyChange: risk` treatment.

Two readers can agree perfectly while a domain profile silently defeats the workflow’s intended protection. Extensible syntax does not automatically provide interoperable semantics.

**The command profile misses a verification already present in the example.** Annex I.3 follows item-to-item links outward and includes incoming anchor links. It does not include incoming verification-item links. I ran:

```sh
ostf context R-DATA-AT-REST --root draft/0.3/example --format json
```

The result contains the requirement and `deploy/database.tf`, but omits `V-ENCRYPTION-REVIEW`. Both the relationship and its purpose are explicitly declared in `trace.yaml`. The omission follows the specification, not just the implementation. A format claiming to expose verification should not hide the manual verification in its own demonstration. [Annex I.3](../../draft/0.3/ostf.md)

**The agent paragraph embeds workflow policy despite OSTF-100 excluding it.** Annex F.1 requires verbatim wording that includes asking before risk-relevant changes, creating draft items for new behavior, refusing to revise requirements to fit code, running tests and stamping. Those are consequential process choices, not serialization conventions.

The small-model T5 failure exposes the mismatch: the agent identified a conflicting requirement and followed the paragraph, yet failed the task criterion. There is also no natural “run its tests” path for the example’s manual verification. A common command interface is defensible; a universal, immutable working policy is much harder to justify. [Annex F](../../draft/0.3/ostf.md), [Trial protocol](../trials/protocol.md)

Finally, **repository-only answers are conditional on repository completeness**. OSTF-113 permits external items without text, and explicitly cannot detect upstream content changes in that case. OSTF-140 excludes `rationale` from fingerprints even though rationale can be the most direct explanation of *why* code exists. Those are defensible tradeoffs, but the headline needs to distinguish recorded local intent from complete, current intent.

**2. Several simpler approaches deserve comparison before committing to this architecture.**

These are alternative designs, not claims that a particular current product already supplies every detail.

| Alternative | How it answers the three questions | What it loses compared with OSTF |
|---|---|---|
| **Markdown requirements and decisions, stable IDs, code/test comments, a small link checker** | Search an ID to find its explanation and references. CI detects unknown IDs and missing files. A Git diff identifies touched linked files for review. | Standardized symbol binding, portable per-link freshness, typed graph semantics and consistent cross-tool results. |
| **A small YAML traceability table plus Git review baselines** | Store `id`, statement, rationale, code paths and test paths. Compare linked paths and statements against a reviewed commit to produce a review list. | Function-level precision and independent recheck baselines for each link; file-level diffs create more noise. It also depends on retained Git history. |
| **Executable acceptance specifications with requirement IDs, plus decision records** | Requirements are connected directly to tests; decisions explain why they exist. Test execution and changed specifications identify work needing attention. | Manual verifications, risk/refinement graphs and explicit implementation links remain weaker. Passing tests still do not establish complete requirement coverage. |
| **Keep an existing requirements format and generate a common context export** | Preserve the team’s current source of truth; expose a small `context` result containing intent, code, tests and review candidates. | Portable editing and lock semantics remain tool-specific. Exporters must disclose differing freshness meanings. |

The last option is especially relevant to Annex G and the converters. Existing users may need a common **reading interface**, not another authoritative authoring format. The Doorstop converter preserves review stamps as uninterpreted extensions, and the StrictDoc importer drops function selectors. That demonstrates migration feasibility, but also shows that adopting OSTF can discard useful semantics before its replacements have proven their value. [Converter loss report](../../draft/0.3/tools/README.md)

OSTF should earn its additional machinery against the first two baselines. Without that comparison, successful adoption exercises show that it is usable, not that it is preferable.

**3. The evidence supports implementability much more strongly than utility.**

**Conformance work:** the hand-written expectations, fixed vectors, mutation checks and differential tests are meaningful. They show that a substantial subset of the contract can be implemented reproducibly. The decision record’s account of a reader passing the suite and then encountering **285 differences across 542 generated inputs** is particularly instructive: passing the published suite did not establish broad agreement. [Decision record, step 2d](../decisions.md)

Requirement-to-case coverage is not coverage of every semantic clause. Consumer expectations remain untested, and the conformance README says the SARIF output is not validated against the OASIS schema. More fundamentally, a suite can faithfully enforce an inadequate rule, as the JavaScript newline example illustrates. [Conformance README](../../draft/0.3/conformance/README.md)

**The two readers:** separate implementations, especially Go’s parser versus tree-sitter for Go, are valuable evidence against implementation-specific assumptions. They are not an independent adoption ecosystem. The project correctly leaves OSTF-171 unmet.

There is also a known interoperability defect, not merely hypothetical residual risk: the decision record says the language grammars accept different syntax and can yield `lf1` in one reader and token fingerprints in the other; “the vectors and fixtures avoid it.” That qualification materially narrows claims of agreement. Both TypeScript implementations also share a grammar, so they share some failure modes. [Known limits](../decisions.md)

**Performance:** subsecond checks on the generated 10,000-file tree demonstrate feasibility on that workload. The generator uses repetitive small Go files, 500 requirements and an empty lock. It does not establish performance on a large mixed-language repository, large generated files, complex syntax or a mature trace graph.

**Agent trials:** the results show agents can discover and operate the supplied workflow in small, pre-traced repositories:

| Trial | Observed result | Defensible interpretation |
|---|---|---|
| Paragraph 1 | 268/288 passed; all failures were T7 | The workflow was broadly usable; output instructions strongly affected scoring. |
| Paragraph 2 | 86/86 passed; stopped early | The revised wording helped on the same fixtures, with limited repetitions. |
| Haiku, paragraph 2 | 134/144 passed; five invented IDs and four premature risk edits | The paragraph was neither a reliable identity safeguard nor an approval mechanism. |
| Haiku, paragraph 3 | 18/18 T6 passed | The specific wording repair worked on that task and those fixtures. |

Sources: [round 1](../trials/results-round1.md), [round 2](../trials/results-round2.md), [Haiku](../trials/results-haiku.md), [Haiku round 3](../trials/results-haiku-round3.md).

The principal weaknesses are:

- **No baseline or ablation.** There is no comparison with good Markdown, ID comments, a simple manifest, or OSTF without the lock. The trials cannot attribute benefit to the expensive parts.
- **Very little task diversity.** Two language versions of the same shop and eight repeated tasks are not hundreds of independent maintenance situations. There is no longitudinal measurement of graph decay or stamping fatigue.
- **The score labels overstate the measurements.** The plan promises correct writing on the first attempt; the scorer checks the final state. T1 checks that expected item and test names appear, not that the causal explanation is correct or obtained without a tool. T7’s automated test-execution criterion detects a test command, not that every named test actually ran. “Mark what it proposed” checks that T2 names an added item, not every added link. [Scorer](../trials/harness.py)
- **“Few tokens” measures calls.** The reports’ approximate OSTF-output medians are 4,185, 4,592.5 and 6,380 tokens for the main rounds and Haiku arm. Those totals do not disprove the 600-token single-context target, but a call-count score of 10 does not establish low total cost. The token estimate itself is character count divided by four. [Metrics implementation](../trials/harness.py)
- **MCP was not isolated.** Only 42/96, 11/28 and 30/48 MCP-condition runs actually called MCP. A shell fallback makes this a weak test of binding portability.
- **The final wording lacks a full validation run.** Paragraph 3 was tested only on Haiku T6. Reusing the same tasks after tuning is useful regression work, but is not held-out validation.

The lowered targets and discarded runs are disclosed, which makes the record auditable. That does not make “10 of 10” a useful conclusion. Classifying premature risk edits as a model limit can justify leaving the specification unchanged; it cannot remove those failures from the practical reliability of the workflow.

**4. Before 1.0, prioritize correctness and evidence over more surface area.**

1. **Fix fingerprint normalization that erases behavior changes.** Address Annex K.4’s line-terminator handling first. Add paired cases where superficially minor changes alter parsing or execution, alongside formatting-equivalence cases. Follow OSTF-170: change the algorithm identifier when its rules change. Published hash compatibility must not preserve a defective projection.

2. **Close the known interoperability and context gaps.** Test the syntax cases currently avoided by the fixtures and settle parser-version behavior. Fix Annex I.3 to expose incoming verification items, including the encryption example. Add explicit cases for custom profile links and risk relevance.

3. **Run comparative, longitudinal field trials.** Use real changes over several weeks, with a simple manifest or Markdown-plus-IDs baseline. Measure missed intent changes, irrelevant suspect alerts, recheck time, blind restamps, missing links and reviewer effort. Extend OSTF-171’s “two organizations” requirement with observable success criteria; two organizations merely trying the format is too weak.

4. **Make freshness completeness visible and enforceable without changing basic adoption behavior.** Keep an easy initial path, but provide a clearly documented strict CI policy for missing locks, unstamped links and unsupported anchors. Distinguish a passing structural check from a fully evaluated freshness check. Make blind-restamping behavior part of the evaluation.

5. **Replace the universal agent paragraph with a portable core and explicit project policy.** Keep discovery, data-versus-instructions boundaries and command usage common. Let projects define approval rules, legitimate requirement changes, manual verification and acceptance. The current verbatim rule binds adoption to a particular workflow without proving that workflow generalizes.

6. **Replace the 10/10 scorecard with claims matched to measurements.** Measure first-attempt validity directly, separate file-only from tool-assisted reading, isolate MCP, independently assess answer quality and use held-out tasks. Report task-specific failures and uncertainty instead of combining unrelated observations into a perfect-looking score.

7. **Reconsider the complexity budget.** Measure implementation burden and recurring author effort. Explore whether a small declaration format plus optional freshness and vocabulary layers preserves most value. Do not add more language annexes or integration mappings until the existing ones and the maintenance economics hold up.

**Verdict:** OSTF is a credible experiment in portable declarations and link freshness, but the repository does not yet establish a compelling case for it as a general standard. Its strongest evidence concerns reproducible machinery; its weakest evidence concerns the human and agent behavior that gives that machinery meaning. The verified fingerprint blind spot, omitted manual verification, permissive freshness gate and admitted parser differences should be resolved before 1.0. After that, the decisive test is whether real teams make better maintenance decisions with less total effort than they do using a small traceability manifest and disciplined Git review. Until that comparison exists, another successful agent demonstration would add less value than one honest field study.