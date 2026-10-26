<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Independent review of draft 0.3: Claude Fable 5.1

Written 2026-10-25 in Claude Code, from the specification at document revision 0.12, the decision record, the agent-readiness plan, the example, the agent paragraph, and the trial protocol and results. The brief was to play devil's advocate: is the gap real, is this the right approach, is there a simpler one, and what would improve it. A second review by Codex with `gpt-6-astra` ran from the same brief without sight of this one ([review](2026-10-25-codex-gpt-6-astra.md)). Section 3 was written after the maintainer stated the intent: agents build the traceability and agents use it, for risk controls, threat models and every document that must link to code and tests.

## 1. The case against

The gap is real but narrower than the specification claims, and the design pays for interop and determinism it does not yet have. The data model is sound. The lock mechanism and the language annexes are where the cost sits, and the trials do not show that they earn it.

- **The novel part is the weakest part.** Items with IDs, tags in code and coverage reports exist in Doorstop, StrictDoc, OpenFastTrace and Sphinx-Needs; Doorstop has review hashes and suspect links. What OSTF adds is token-normalized code fingerprints plus an agent workflow. The fingerprints are the single biggest source of complexity: three normative language annexes, hand-written vectors, and two parsers that a differential harness had to force into agreement across hundreds of inputs. They buy formatting-insensitive drift detection, a modest improvement over "the function changed since you last looked".
- **`suspect` is a low-precision signal, and low-precision signals get ignored.** Under the default every body edit of a linked function fails CI until someone stamps, and most body edits do not break the requirement. Every typo fix in an item's text flips all of its links, with no way to mark an edit cosmetic. The README names the failure mode itself: teams that stamp without reading. Taking named links only is friction, not prevention; an agent will pipe the JSON into a stamp loop within a week, as happened with snapshot tests, lockfile updates and lint suppressions.
- **A valid link proves very little.** OSTF-145 is honest about it. But what people want, "is the refund limit still enforced", is answered by the test passing in CI, which they already have. The marginal value is the index from function to intent, and that part needs none of the lock, the stamp verb, the ABNF grammar or the annexes.
- **The trials test obedience, not value.** All three conditions have OSTF installed; there is no control arm with a plain requirements file and an instruction to run related tests. The tasks were written around the specification's own verbs, and the reference reader is the judge. The result shows that agents follow a clear paragraph, not that the lock, the stamp or the tool improved an outcome. The cuts, the unmatched models and the half-used MCP binding are disclosed, which is to the authors' credit, but "10 in every row" overstates what was learned. Every phase landed on one day, so nothing has been used for a month.
- **The agent paragraph does not scale as written.** It asks for a context call before changing any function. The fixtures link most functions; real repositories link a few percent, so most calls return empty and agents will stop making them. The Few tokens row already had to be lowered, and paragraph 3 was measured on Haiku only. Making prompt text normative ties specification revisions to model behavior that changes monthly.
- **The core carries features with no user yet.** Profiles with typed attributes and meaning flags, external items with sources and revisions, aliases, include globs, nested roots, link attributes, acyclic checks, a verification type, and the SARIF, MCP and in-toto annexes. Each is a place where a second implementer must match behavior. "Four lines to start" is true; "simple" is not, with a reader of about two thousand lines and thirty-six diagnostic codes.
- **"Many agents agreed" is weak evidence.** Models agree with specifications this well written. A better test is to ask an agent, without showing it OSTF, to design the smallest thing that answers the three questions, and compare.

What is good: the honest boundaries in OSTF-145 and `coverage: "direct"`; the security posture of no network, a YAML subset and strict paths; the determinism discipline of differential testing, vectors and a decision record; symbol anchors rather than lines; the strict unknown-ID rule against an agent's plausible IDs; and the risk-relevant marker as a cheap safety cue.

## 2. Simpler routes to the same three questions

Three that keep OSTF's shape:

1. **Items, tags, context, and freshness from Git. No lock.** The checker validates IDs and prints, for a symbol, the linked items and tests with the date and commit of the last change to each side. Freshness is information the agent reads, not a state CI enforces. Drops the lock grammar, the stamp verb, the states table and all token rules. Loses cross-tool byte agreement and a CI gate on drift, whose value is the unproven part.
2. **Keep the lock, key it on commits instead of token hashes.** A lock entry records the commit at which the link was rechecked; suspect means the item or the function's span has a later commit, from `git log -L`. Drops the three language annexes, keeps the workflow. Loses VCS independence, which almost no target user needs, and some formatting insensitivity.
3. **Make the test the carrier.** Name or annotate tests with the requirement ID and text; runners already report per-name results and coverage data answers which code a requirement exercises. Freshness is "the test passes". Loses untestable items such as needs, risks and review-verified rules.

Five that change who does the work, which is what decides scale:

1. **Tag tests, derive the rest from coverage.** Per-test coverage exists in every mainstream toolchain, so CI derives test to function and therefore requirement to function, and commits the map so the repository still answers from files alone. No annexes, no per-function authoring, no stamps. Loses untestable items and precision on shared helpers.
2. **Stamp equals merge.** CI shows the reviewer each item's text beside the diff of the linked symbols it touched; approving the pull request is the recheck, recorded in Git. Removes the stamp verb, the lock grammar, the merge conflicts and the blind-stamp incentive. Loses offline evaluation and byte-identical results across tools.
3. **Let the machine recheck, let people see exceptions.** An agent reads the requirement, the diff and the test result and returns "still holds", "no longer holds" or "cannot tell", with its model recorded; humans review the last two. Scales with change rate. Loses determinism and clean auditability, and a wrong verdict is a quiet failure.
4. **Tracker plus commit trailers plus a thin context tool.** The de facto practice: `git log -L` on the symbol, the referenced issues and their cached text. Loses repository-only answers, symbol-level precision and inherits tracker rot.
5. **Standardize the query, not the storage.** Annex I and the result shape as an intent protocol with three operations, why, tests-for and stale, over any backend. Loses byte-identical interop on one repository, and freshness semantics vary per backend.

## 3. Comparison for an agent-first format

When agents both build and consume the graph, authoring cost stops being the constraint, because an agent backfills a repository in an afternoon. The constraints become trust and rate: can anyone trust links an agent wrote, and who rechecks them when agents change code faster than people read. Breadth matters, since threats, controls, decisions and runbooks are not tests.

Six questions. Agent writes: can an agent produce links reliably and can a checker catch its mistakes. Agent reads: tokens and calls to get why, tests and risk for a symbol. Breadth: requirements, risks, threats, controls, decisions, non-code artifacts. Guards: invented IDs, stale text, self-attestation, prompt injection. Freshness: does rechecking keep up with agent change rates. Scale: languages, repository size, parallel agents, cross-repository.

| Approach | Agent writes | Agent reads | Breadth | Guards | Freshness | Scale |
| --- | --- | --- | --- | --- | --- | --- |
| OSTF 0.3 as drafted | Strong | Strong | Fair | Fair | Weak | Fair |
| Markdown, IDs, checker | Strong | Fair | Strong | Weak | Weak | Strong |
| Tests tagged, links derived from coverage | Strong | Fair | Weak | Strong | Strong | Strong |
| Stamp at merge, freshness from Git | Strong | Fair | Fair | Fair | Fair | Strong |
| Agent recheck with recorded verdict | Layer | Strong | Strong | Fair | Strong | Fair |
| Tracker plus commit trailers | Fair | Weak | Fair | Weak | Weak | Strong |
| Interface standard over backends | Backend | Strong | Backend | Backend | Backend | Strong |
| OSCAL or threat-model-as-code, plus anchors | Weak | Weak | Strong | Fair | Weak | Fair |

- **OSTF 0.3 as drafted.** Pros: strict IDs and a typed graph are the best defense against plausible-but-wrong links; symbol anchors survive edits; repository-only answers suit sandboxed agents; profiles can add threat and control types; the risk-relevant marker works. Cons: freshness rests on a human stamp per body change; the stamping agent is usually the one that made the change; threat modeling needs a profile nobody has published; the context verb hides incoming verification and control items; one sorted lock per root collides under parallel agents; each language needs an annex; item text is an injection surface read before every edit.
- **Markdown, IDs, checker.** Pros: agents read and write it best; any artifact fits; zero machinery. Cons: nothing binds an ID to a symbol; no freshness; silent drift, the failure agents notice least.
- **Tests tagged, links derived from coverage.** Pros: the test-to-code leg is computed, so no agent can hallucinate it; CI recomputes freshness; any language with a coverage tool. Cons: tested behavior only; shared helpers show every requirement through them.
- **Stamp at merge.** Pros: the recheck rides an act that already happens; no lock, no blind-stamp incentive, no annexes. Cons: when agents open and merge most pull requests the gate is only as good as what reviews it; evidence lives in the forge and history.
- **Agent recheck with a recorded verdict.** Pros: scales with change rate; judges prose artifacts no hash can; humans see only exceptions. Cons: nondeterministic; needs separation of duties and a record of model, inputs and verdict; tokens per change; quiet wrong verdicts.
- **Tracker plus commit trailers.** Pros: universal, no files, every language. Cons: depends on a system outside the repository; commit granularity; threat models do not live in tickets; weak on every guard.
- **Interface standard over backends.** Pros: agents learn one surface; organizations keep their source of truth. Cons: no portable authoring, and the intent is that agents author; half a standard on its own.
- **OSCAL or threat-model-as-code, plus anchors.** Pros: controls and threats already have machine-readable formats with regulator recognition; the widest breadth. Cons: verbose for an agent; nothing anchors to a code symbol or detects drift; the layer above, not the answer to this gap.

**Synthesis.** No single row wins. The combination that scores strongly everywhere is OSTF's data model with its freshness replaced by derivation and machine triage: keep stable IDs, strict validation, the typed graph, symbol anchors, repository-only reading, the context verb and the result JSON; make agent-declared links corroborated by derived test-to-code links, with disagreement as the review queue; define freshness per artifact kind, tests for tested behavior, fingerprint plus a second agent's triage for untested code and prose; require that the rechecking principal differ from the changing one; add threat, control and decision to the default vocabulary or an official security profile; return the context of every changed linked symbol in one call; shard or drop the lock; render item text as marked data. The trade is determinism: no promise that two tools produce the same lock bytes. For a standard whose builders and readers are agents, that is the better bargain.

## 4. Verdict

The thinking is unusually disciplined for a draft, the security posture is right, and symbol anchors, strict IDs and the risk-relevant marker are good calls. The open question is whether the lock is worth its weight, and nothing published yet answers it. The two experiments that would settle it quickly: run a coverage-derived map on the TypeScript trial fixture and compare its links with the hand-declared ones; and run the eight trial tasks with the intent layer only, no lock, and see which rows move.
