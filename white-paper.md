<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# OSTF: The Open Software Traceability Format

**Why coding agents need to know why code exists, and a proposal for a shared format that tells them**

White paper, draft 0.8, project status reconciled 2026-10-22. For public review. OSTF remains a 0.x proposal; its bounded executable draft and current limits are in the [support map](draft/support.md).

## Summary

Coding agents now write and change a growing share of software. They are quick and capable, but they cannot see why a function exists: which requirement it implements, which risk it controls, which test checks it. That knowledge lives elsewhere, in a ticket, a design document, a wiki page or someone's head, and it drifts away from the code. Every team has such rules: a refund limit, an access check, a retention period, a rate limit. Agents change the code that carries them without knowing it.

Open-source requirements-as-code tools showed years ago that requirements belong in the repository, next to the code and reviewed in the same pull requests, but each tool invented its own format. Spec-driven agent tools such as GitHub Spec Kit, Kiro and OpenSpec give agents written intent to work from, each in its own form. Industries that must prove traceability, in health, automotive and avionics software, have required it for decades, and none of their standards says how to record it.

The Open Software Traceability Format (OSTF) proposes one small, open format for that layer:

- requirements, the risks they address and the verification that provides evidence for them, with typed links between them;
- links to code at the level of functions and tests;
- a proposed later extension for references to items kept in other systems, such as Jira, Jama or a spreadsheet;
- a lock file of fingerprints that shows which links were rechecked after either end changed;
- an origin on every Core link, distinguishing declarations, code tags and imports. A later recovery extension would identify reconstructed links.

OSTF serializes to plain text files against a source tree, typically versioned in Git; tools may use databases internally. A small core serves any team that lets an agent change code. Planned modules would add what regulated industries need. Mappings to ReqIF and OSLC are planned, each stating what it loses. A link that the lock file shows as rechecked has unchanged inputs; that does not make the code correct, approved, tested or compliant. This paper explains the problem, what OSTF standardizes and what it leaves to tools, how it serves coding agents, how the same format could carry a safety standard's trace, and how we propose to take it from draft to standard.

## 1. Agents change code faster than anyone can trace it

When a person changes a function, the hard questions are rarely about how. They are about whether. May I touch this? What else depends on it? Which tests matter? Does this function exist because of a rule someone agreed on? People answer from memory, from documents, or by asking a colleague.

An agent answers from what it can read: the repository and the context it is given. If the rule is not there in a form it can read, the agent guesses. It cannot tell a helper function from the one that enforces a refund limit or an access check. It cannot know that the test it is about to rewrite is the only evidence that the rule holds.

In most teams, the record of why code exists is reconstructed after the fact: when something breaks, when a customer asks, or before an audit. It is late and costly, and it records what the team believes the code does rather than what the code does. Agents make the gap wider. They produce changes faster than anyone updates the record.

Industries where software can hurt people have lived with this requirement for decades. IEC 62304 for health software, ISO 26262 for road vehicles and DO-178C for airborne software all require traceability from requirements through code to tests, and the medical standards add the trace from each hazard to the control that addresses it and to the verification that shows the control works [1][2][3]. None of them prescribes a format. Each team, and each tool, picks its own.

The same agents that widen the gap can close it. An agent can update a requirement and its links in the same change as the code, if it has a format it can read and write, and a check that fails when it gets them wrong.

## 2. What exists today

**Open-source requirements-as-code tools.** OpenFastTrace, StrictDoc, Sphinx-Needs, LOBSTER with TRLC, and Doorstop all keep requirements and links as text in the repository and review them in pull requests [8][9][10][11][12]. Most link code by tags in comments; some keep links in sidecar files; StrictDoc supports both. Several also track change. Doorstop fingerprints items and their links and can store a SHA-256 of each referenced file [12]. Eclipse TSF's trudag reports suspect links when a linked item changes, and its STPA extension records losses, hazards and constraints as linked items [24]. reqstool reads source annotations and test results and serves them to agents over MCP and to editors over LSP [25]. They agree on the approach, and that agreement is what makes a standard possible now. They do not agree on syntax: LOBSTER writes `lobster-trace:`, and OpenFastTrace and StrictDoc each have their own tag grammar.

**Spec-driven agent tools.** A newer family of tools gives coding agents written intent to work from. GitHub Spec Kit writes a specification, a plan and a task list for each feature before the agent codes, in a `specs/<feature>/` folder [21]. Kiro, from AWS, does the same in `.kiro/specs/<feature>/`, with requirements written as user stories and EARS acceptance criteria, and keeps a link from each requirement to the tests that validate it [22]. OpenSpec updates lasting specifications when a change is archived [26]. Trellis keeps team conventions, a requirements document for each task and a memory for each developer in a `.trellis/` folder, and has an agent review each diff against the conventions [23].

These tools share OSTF's premise: agents need intent in the repository, in a form they can read. Each keeps it in its own form, written per feature or per change, and in the documentation we read we found no shared record of which functions carry each requirement, nor a rule for when such a link must be rechecked after the code changes. OSTF could be that shared layer: the requirements meant to outlive a feature become OSTF items, linked to the code and tests that carry them, which any of these tools could read. The two kinds of tool complement each other.

**Commercial requirements tools.** Jama, Polarion, codebeamer and IBM DOORS manage requirements in their own databases and mark links as suspect when an item at either end changes [13][14][15][16]. Ketryx, the closest commercial product for agents in regulated development, reads Git-based items and links tests through `@tests:` annotations [17]. Jama and Ketryx both announced MCP servers in 2026, so agents can query them [18][19]. Each still holds its data in its own model.

**Standards.** Three recognized standards come close. OSTF should reuse their vocabulary rather than compete with it.

| Standard | What it does | What it leaves open |
| --- | --- | --- |
| ReqIF (OMG) [4] | XML format for exchanging requirements between requirements tools | Exchange between tools. Code and tests can be carried only as proxy objects, and it prescribes no repository authoring, symbol resolution or rule for when a link to code is stale. Each exporting tool has its own dialect, and some overwrite the `ForeignID` attribute meant to identify items [5] |
| OSLC Requirements Management (OASIS) [6] | Linked-data vocabulary and API for connecting live tools | Its vocabulary can be written in files without a server, but it prescribes no repository layout, symbol resolution or freshness rule. Its main use is connecting live tools |
| SysML v2 (OMG) | Systems modeling language with a textual notation that includes requirements | Built for model-based systems engineering. Heavy for a software team, and its textual form lacks the stable element identifiers needed for round trips [7] |

**What we found missing.** In our review of the tools above in October 2026:

- risks and their controls are modeled by a few tools, Eclipse TSF's STPA extension among them, each in its own schema;
- several tools fingerprint items, links or whole referenced files, but we found none that fingerprints a function or test by symbol, with rules that keep formatting changes from making a link suspect;
- there is no shared way to point from the repository to an item in Jira, Jama or DOORS with the revision last seen. LOBSTER's pinned codebeamer references (`12345@42`) are the closest [11].

For teams, the result is lock-in to one tool's syntax. For agents, it is one convention per tool. For vendors, it is one importer per competitor.

## 3. OSTF in one example

A payments service must not refund more than the original order, and refunds above a daily limit per account need a second approval. The team keeps the rule in its repository, linked to the risk it controls. The excerpts below illustrate the relationships; they are not a complete runnable repository. For exact files and stamps, see the [worked example](examples/minimal/README.md).

The items, in `trace.yaml`:

```yaml
ostf: "0.1"
include: [trace/*.yaml]
links: {source: both}   # read the @req tags below as well as YAML
items:
  - id: N-REFUNDS
    type: need
    text: Customers get refunds quickly without the business losing money to abuse.
  - id: RISK-REFUND-ABUSE
    type: risk
    text: A compromised account or a mistaken operator drains funds through refunds.
  - id: R-REFUND-LIMIT
    title: Refund limit
    text: A refund must not exceed the original order, and refunds above the daily limit for an account need a second approval.
    refines: [N-REFUNDS]
    controls: [RISK-REFUND-ABUSE]
    code: [config/limits.yaml]
```

In the `default` profile, a risk is anything that can cause harm or loss: a security breach or a financial loss as much as an injury. Profiles for safety work add hazards, hazardous situations and harms in their ISO 14971 sense. An abbreviated code excerpt shows how the function and test carry a tag with the requirement ID, never its text:

```go
// checkRefundLimit rejects a refund above the order total or the daily limit.
// @req R-REFUND-LIMIT
func checkRefundLimit(r Refund, acct Account) error {

// @req R-REFUND-LIMIT
func TestRefundLimit(t *testing.T) {
```

The lock file records what both ends of each link looked like when someone last rechecked it. This abbreviated line illustrates the fields; its short hashes are not valid stamps:

```
trace.lock 1
payments/refund.go#checkRefundLimit implements R-REFUND-LIMIT source.sig=go1:Q2xi source.body=go1:8b1c target=f1:3f9a
```

In this scenario, a conforming Analyzer could tell an agent or a reviewer:

- `checkRefundLimit` implements `R-REFUND-LIMIT`, which controls `RISK-REFUND-ABUSE`, so the function carries a risk control and deserves more care than a helper.
- If someone edits the body of `checkRefundLimit`, the risk-relevant link becomes suspect until someone rechecks it and updates the lock file. A tool can use the linked test to plan verification.
- If an agent writes `@req R-REFUND-LIMT`, the check fails: the ID does not exist. A made-up citation becomes a failing build instead of a silent error.
- Nothing here is specific to payments or to any industry. The same files describe a rate limit, an access check or a retention rule.

## 4. Design principles

1. **In the repository, reviewed with the code.** Requirements, links and fingerprints are plain text in Git. A change to code and a change to its requirement appear in the same pull request, in front of the same reviewer.
2. **Links name symbols, not lines.** A link points to `payments/refund.go#checkRefundLimit`, not to line 42 or to a file version. Editing inside a function keeps its links. When a tool cannot place a symbol, the whole file counts, so uncertainty flags more, never less.
3. **A declared vocabulary, open through profiles.** Item types, link types and attributes are declared in a profile, not invented per file. A typo is an error, not a new item. Teams extend the vocabulary by extending a profile, and the extension shows in review.
4. **Change is visible.** Every link is valid, suspect, unstamped or broken. Rechecking a link is a deliberate act that updates one line in a lock file, and the pull request shows which links were reconfirmed. Comments, whitespace and formatting never make a link suspect, and a body change does so only when the item is risk-relevant. A valid link means its inputs did not change since the recheck, not that the code is correct or tested: a change to a helper it calls leaves the link valid.
5. **Honest origins.** Every Core link says whether it was declared in an item file, tagged in code or imported. The proposed recovery extension would record links reconstructed from earlier evidence or confirmed after an agent proposal, keeping those origins distinct.
6. **Keep the systems you have.** The proposed external-item extension would hold read-only snapshots of items owned by Jira, Jama, DOORS or a quality system, including their revision and content hash. Core 1.0 does not yet standardize that contract.
7. **A small core, optional modules, data not behavior.** OSTF fixes what two tools must read the same way. How tools analyze, present and enforce it is theirs to decide.

## 5. What OSTF standardizes

**OSTF Core** defines the files that Producers write and Consumers and Analyzers read. It has no industry in it:

- **Files:** a root file, included item files, strict reading of unknown fields.
- **Identity:** local IDs, aliases, and IDs that are never reused.
- **Items:** a small set of fields (ID, type, title, text, status, rationale, attributes) and documents with sections.
- **Profiles:** registries of item types, link types with allowed endpoints, and typed attributes. The `default` profile serves any team; domain profiles add types and rules on top.
- **Links:** declared on the more detailed item and pointing to what it serves, with inverses computed.
- **Code anchors and tags:** `path#symbol` anchors, test identities in each test runner's own syntax, and `@req` tags in comments that bind to the definition below them.
- **Origins** of links declared in item files, tagged in code or imported.
- **Verification:** a role (implementation or effectiveness) and a method (test, inspection, analysis, review) on each `verifies` link, and verification items for checks that are not automated tests.
- **Fingerprints and the lock file:** item fingerprints over the fields that carry meaning, code fingerprints for a definition's signature and body, the lock file line format, and the four link states.

Mappings to ReqIF and OSLC are informative, outside Core: each says which links map exactly, which only under conditions, and which are lost.

**Planned modules** would be optional, separately versioned and claimed only when qualified:

| Module | Covers |
| --- | --- |
| Risk | Risks and the controls that address them: hazards, hazardous situations, harms, causes and risk controls; risk estimates and a declared risk matrix. A profile adds a standard's chain, such as the IEC 62304 one |
| Architecture and integrity | Software items, code membership by path, integrity levels as declared schemes (for example IEC 62304 class, ISO 26262 ASIL, DO-178C DAL), segregation rationale |

Referenced items and snapshots, recovered links and records, `@req-none` exclusions, coverage rules and adoption provenance remain proposals outside Core 1.0. The snapshot schema checks shape for review but does not qualify external-item behavior.

**OSTF leaves to tools:**

- analyses such as impact and test selection;
- commands, user interfaces and MCP tools;
- sync adapters for other systems;
- generated documents;
- change policy: deciding what an agent may change, and who must approve;
- evidence: test results, baselines, approvals and signatures.

Tools compete on all of these, and should.

**Conformance** has three classes. A **Producer** writes files that satisfy both schema and Core semantic rules. A **Consumer** reads the serialized graph, validates lock syntax and reports file-declared links with their origins. An **Analyzer** also binds code anchors and tags for the languages it names, computes fingerprints and reports link states against one selected source-tree view. A public conformance suite of fixture repositories with expected results makes each claim testable.

## 6. Why agents need a format, not only an API

MCP gives agents a standard way to ask tools questions. OSTF is the shared answer to what those questions are about. The two complement each other, but a format adds things an API cannot:

- **The requirement is where the agent is already reading.** Agents read the files they change. A tag above a function puts the requirement ID in front of the agent without a lookup.
- **The same data for every tool.** An API, even a local MCP server, answers for the tool behind it. A shared format lets tools that implement the same version and annexes evaluate the same commit offline, in CI, on a laptop or in an air-gapped environment.
- **Mistakes fail loudly.** An unknown ID in a tag is an error. With an OSTF check in CI, an agent that invents a requirement ID fails the check.
- **Trace changes travel with code changes.** The agent edits the requirement, its links and the code in one pull request, and the reviewer sees all of it together.
- **Recovered links need an explicit record.** In existing code, agents can propose links for a person to confirm. Research shows why confirmation matters: one 2025 study measured LLM recovery of requirement-to-code links at an F1 score between 0.24 and 0.53 [20]. The proposed recovery extension would label confirmed links `recovered`; it is not part of Core 1.0.
- **One convention for every agent.** An agent that learns OSTF once can work in any repository that uses it, whichever tool the team runs.

## 7. The same format under a safety standard

Future Risk and Architecture modules would let teams express an industry-specific trace through a profile. The following infusion-pump sketch shows the intended shape. Those modules are not qualified in the current draft, and this excerpt is not valid Core 0.1 input:

```yaml
profile: iec62304
items:
  - id: HS-07
    type: hazardous-situation
    text: A dose above the prescribed maximum is programmed and the pump starts delivering it.
  - id: SI-DELIVERY
    type: software-item
    text: Dose programming and delivery control.
    attributes: {safetyClass: C, paths: [pump/pump.go, pump/limits.go]}
  - id: CAUSE-07-1
    type: cause
    text: The dose programming code accepts a value above the configured limit.
    leads_to: [HS-07]
    occurs_in: [SI-DELIVERY]
  - id: RC-07-1
    type: risk-control
    text: Software rejects a programmed dose above the configured maximum before delivery starts.
    controls: [CAUSE-07-1]
  - id: R-DOSE-LIMIT
    text: The pump refuses a dose above the configured maximum.
    refines: [RC-07-1]
  - id: VER-USE-4
    type: verification
    text: Nurses try to program a dose above the limit. Every attempt is blocked.
    attributes: {method: test}
    verifies: [{to: RC-07-1, role: effectiveness}]
```

With code and tests tagged `@req R-DOSE-LIMIT` as in section 3, such a future module could express relationships relevant to IEC 62304 clause 7.3.3 and FDA software submissions [1][3]:

| Element | In the proposed modules |
| --- | --- |
| Hazardous situation | A `hazardous-situation` item, with the hazard it arises from and the harm it results in |
| Software item | A `software-item` with its paths and safety class |
| Software cause | A `cause` item that leads to the hazardous situation and occurs in the software item |
| Risk control | A `risk-control` item that controls the cause |
| Requirement | A requirement that refines the risk control |
| Code | Functions linked by tag or by anchor |
| Verification of implementation | Tests that verify the requirement or the control |
| Verification of effectiveness | Verification with role `effectiveness`, as ISO 14971 separates it [2] |

Records in regulated industries must stay readable for many years. Plain text under an open specification outlives any tool vendor and any version of zztrace.

**What a format does not do.** OSTF does not make a product compliant. The Risk module's mapping to IEC 62304 and ISO 14971 clauses comes from secondary sources until it is reviewed against the licensed texts. Approvals, signatures, baselines and tool validation remain the job of the quality system and the tools that implement it.

## 8. Why a standard, and why now

The open-source field has converged on requirements as text in Git, and coding agents raise the cost of every team using a different syntax. A format is easier to agree on before many tools ship incompatible versions of it.

Data formats for engineering tools have become standards this way before:

- **SARIF**, for static analysis results, was developed at Microsoft and became an OASIS standard.
- **SPDX** and **CycloneDX**, for software bills of materials, became ISO/IEC 5962 and ECMA-424.
- **OpenAPI** grew out of Swagger, a single company's format, before moving to a Linux Foundation project.

Each began as a working format with an open specification and a reference implementation, and found a neutral home once others had adopted it. OSTF should follow the same path. A standards body cannot bless a draft into adoption; tools and teams that use it can.

## 9. From draft to standard

| Stage | What happens |
| --- | --- |
| 0. Draft | This paper, [scope](scope.md) and draft contract were prepared for review. Name and publication checks are tracked separately from the technical contract |
| 1. Working format, bounded internal increment present | zztrace has real-project evidence, and the draft has structural schemas, a lock grammar, Go annexes and suite 0.1.3. A separately structured Python prototype agrees on the exercised cases; shared authorship and incomplete Core coverage remain explicit. Comparative agent trials are optional research, not performed results |
| 2. Public draft (0.x) | This specification is published under open licenses for review. A converter to and from StrictDoc or Doorstop, with a loss report, remains planned |
| 3. Second implementation and 1.0 | At least one independent tool that computes fingerprints and link states itself passes the conformance suite, and two organizations have used the format on real changes. Only then is 1.0 frozen. The specification changes only through public review |
| 4. Neutral home | A foundation holds the name and the specification. Candidates include the Linux Foundation's ELISA project, which already works on requirements for safety-critical Linux, the Eclipse Foundation, and OASIS |

## 10. Call for reviewers

We are looking for people who will tell us what is wrong with OSTF before it is fixed in place:

- people who build coding agents and the tools they call;
- engineering teams that already let agents change production code;
- authors of requirements-as-code tools and spec-driven agent tools;
- quality, regulatory and safety engineers who prepare trace evidence for audits;
- ALM and QMS vendors who would read or write OSTF at their boundary.

The questions we most want answered:

1. Is OSTF Core small enough for one tool author to implement, and complete enough to be worth it?
2. Should links live in code tags by default, or in item files?
3. Can code fingerprints be specified per language precisely enough that two tools always agree?
4. Which link vocabulary do your reviewers or auditors expect to see?
5. What would stop your team or your tool from adopting it?

## References

1. IEC 62304 clauses, secondary sources: LDRA, IEC 62304 white paper, https://ldra.com/wp-content/uploads/2023/08/IEC_62304-1-2006_White_Paper_v3.pdf; Johner Institute, https://blog.johner-institute.com/iec-62304-medical-software/iec-62304-2nd-edition-all-areas-of-application-and-changes/
2. ISO 14971 risk control verification, secondary source: https://meddeviceguide.com/blog/iso-14971-risk-control-traceability-gap-analysis-guide
3. FDA, Content of Premarket Submissions for Device Software Functions (2023): https://www.fda.gov/media/153781/download
4. OMG, Requirements Interchange Format (ReqIF) 1.2: https://www.omg.org/spec/ReqIF/1.2/About-ReqIF
5. ReqIF ForeignID behavior: https://hub.requisis.com/en/kb/wissenswertes-zu-reqif
6. OASIS, OSLC Requirements Management 2.1 vocabulary: https://docs.oasis-open.org/oslc-domains/oslc-rm/v2.1/cs01/part2-requirements-management-vocab/oslc-rm-v2.1-cs01-part2-requirements-management-vocab.html
7. Sodius Willert, A Practical Guide for SysML v2 Adoption: https://www.sodiuswillert.com/en/blog/a-practical-guide-for-sysml-v2-adoption
8. OpenFastTrace concepts and tags: https://github.com/itsallcode/openfasttrace/blob/main/doc/user_guide/introduction/concepts_and_terms.md
9. StrictDoc user guide: https://github.com/strictdoc-project/strictdoc/blob/main/docs/strictdoc_01_user_guide.sdoc
10. Sphinx-Needs configuration: https://github.com/useblocks/sphinx-needs/blob/master/packages/sphinx-needs/docs/configuration.rst
11. LOBSTER user manual and codebeamer importer: https://github.com/bmw-software-engineering/lobster/blob/main/documentation/user-manual.md, https://github.com/bmw-software-engineering/lobster/blob/main/documentation/manual-lobster_codebeamer.md
12. Doorstop item reference: https://doorstop.readthedocs.io/en/latest/reference/item.html
13. Jama relationship rules and suspect links: https://help.jamasoftware.com/en/manage-content/coverage-and-traceability/relationships/clear-suspect-links.html
14. Polarion link roles and suspect flags: https://blogs.sw.siemens.com/polarion/links-between-work-items-and-their-intended-meaning/
15. codebeamer suspect propagation: https://support.ptc.com/help/codebeamer/r3.3/en/codebeamer/user_guide/ug_tracker_ref_fields.html
16. IBM ELM link validity: https://www.ibm.com/docs/SSYMRC_7.2/com.ibm.jazz.vvc.doc/topics/c_linkval.html
17. Ketryx, traceability to automated tests and Git-based risks: https://llm.ketryx.com/content/capabilities/traceability-to-automated-tests/index.html, https://llm.ketryx.com/content/support/hc/en-us/articles/41955656286861-does-ketryx-support-git-based-risks/index.html
18. Jama Software, MCP server announcement: https://www.jamasoftware.com/press/jama-software-launches-model-context-protocol-mcp-server/
19. Ketryx, MCP announcement: https://www.ketryx.com/press-release/ketryx-announces-mcp
20. LiSSA, retrieval-augmented traceability link recovery (ICSE 2025): https://publikationen.bibliothek.kit.edu/1000179816/164563088
21. GitHub Spec Kit: https://github.com/github/spec-kit; Microsoft for Developers, Diving into spec-driven development with GitHub Spec Kit (2025): https://devblogs.microsoft.com/blog/spec-driven-development-spec-kit
22. Kiro, feature specs, requirements-first workflow and correctness: https://kiro.dev/docs/specs/feature-specs/, https://kiro.dev/docs/specs/feature-specs/requirements-first/, https://kiro.dev/docs/specs/correctness/
23. Mindfold, Trellis: https://github.com/mindfold-ai/Trellis
24. Eclipse TSF, trudag usage and STPA schema: https://pages.eclipse.dev/eclipse/tsf/tsf/tools/usage.html, https://pages.eclipse.dev/eclipse/tsf/tsf/extensions/stpa/schema.html
25. reqstool client: https://github.com/reqstool/reqstool-client
26. OpenSpec: https://github.com/Fission-AI/OpenSpec
