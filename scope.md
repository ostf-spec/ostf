# OSTF scope: the common capability

Status: public working draft for review, document revision 0.10, reviewed 2026-10-22. Wire version 0.1, conformance suite 0.1.3. OSTF was drawn from version 2 of the zztrace trace format. This page decides which parts become Core, optional modules or tools. The [draft contract](draft/core.md), [annexes](draft/go.md), [schemas](schema/) and [suite](conformance/README.md) now exist; the [support map](draft/support.md) explicitly limits their executable coverage. This is not full Core conformance or a 1.0 standard.

## The capability

Any person, agent or tool can read a repository and learn which requirements, risks and verification exist, how they link to each other and to the functions and tests that implement and verify them, and which of those links were rechecked since either end last changed.

Core data supports the first five questions from the repository alone, offline and with the same answer every time. The sixth is a deferred extension goal:

1. **Why does this code exist?** From a function or test to the items it implements or verifies.
2. **What carries this requirement?** From an item to its parents, children, code and tests.
3. **What does this change touch?** From changed symbols to the items linked to them and the tests linked to those items. The analysis is a tool's job; the data that makes it possible is OSTF's.
4. **Which links are stale?** Whether each link was rechecked after its requirement or its code changed.
5. **Where did this link come from?** Declared with an item, tagged in code, or imported. A deferred recovery extension would distinguish later reconstruction.
6. **What lives elsewhere?** A deferred external-item extension would identify items owned by another system, such as Jama, DOORS or a risk spreadsheet, and the revision the repository last saw.

## Scope layers

| Layer | What it is | Status |
| --- | --- | --- |
| **OSTF Core** | Files, local identity, items, profiles, links, code anchors and tags, declared/tagged/imported origins, fingerprints and the lock file | Draft common contract. Producers write it; Consumers and Analyzers read it |
| **Modules** | Planned optional parts, each versioned on its own: Risk, Architecture and integrity | Separate specifications and conformance claims are planned; none are qualified in this draft |
| **Deferred extensions** | Referenced items and snapshots, recovered links and records, `@req-none` exclusions | Proposals outside Core 1.0 and its conformance claims |
| **Tools** | Analyses, commands, MCP tools, import and sync adapters, documents, change policy, approvals, signatures and baselines | Not standardized. This is where tools compete |

The split follows one rule: **OSTF standardizes data that more than one tool must read the same way. It does not standardize behavior.** Two tools must agree on what `payments/refund.go#checkRefundLimit implements R-REFUND-LIMIT` means and whether that link is suspect. They need not agree on how they present it, which tests they choose to run, or what an agent is allowed to do about it.

Conformance is at the serialized file boundary. A tool backed by a database may import, export or both, according to the conformance class it claims. Using Git files as the primary graph store is a zztrace product choice, not an OSTF requirement.

A second rule follows from the first: **Core has no industry in it.** The `default` profile serves any team that lets an agent change code. Domain profiles, such as one for IEC 62304, add types, links and rules on top, and the vocabulary they need lives in the modules.

## OSTF Core

The TRF IDs below record zztrace provenance only. The rules needed to implement this draft are in the OSTF documents here.

| Part | Content | Original zztrace IDs |
| --- | --- | --- |
| C1. Files | Root file, included item files, the `ostf` version key, the safe YAML subset, strict reading with reserved keys and `x-` extensions, size bounds | TRF-001, TRF-002, TRF-004, TRF-006 to TRF-008 |
| C2. Identity | Local ID grammar, aliases preserving original identifiers (including numeric IDs), no reuse | TRF-010, TRF-012, TRF-013 |
| C3. Items | Core fields, `draft`, `accepted` and `obsolete` status, text, derived items, documents and sections | TRF-020 to TRF-024 |
| C4. Profiles | Type, attribute and link registries with endpoint rules; extending a profile; the `default` profile | TRF-030 to TRF-034, TRF-035 (`default` only) |
| C5. Links | Declared on the source item, direction from detail to purpose, computed inverses, acyclic link types, duplicates | TRF-040 to TRF-044 |
| C6. Code anchors and tags | `path#symbol` anchors, symbol paths, test identities in the runner's syntax, `@req` tags and their binding, where links live | TRF-050 to TRF-056 |
| C7. Origins | `declared`, `tagged` and `imported`, reported separately from freshness | TRF-045 (those origins) |
| C8. Fingerprints and the lock file | Item fingerprints with their JSON projection, code signature and body fingerprints over tokens, the `trace.lock` line format with its escaping, the four link states and their order, suspect rules, risk relevance. A valid link has unchanged inputs; it is not a claim that the code is correct | TRF-064, TRF-090 to TRF-095 |
| C11. Verification | `verifies` roles (implementation, effectiveness) and methods (test, inspection, analysis, review), verification items | TRF-070, TRF-071 |

The C9 and C10 labels are retained below for traceability to earlier scope drafts; they are outside Core 1.0.

Risk relevance (TRF-064) sits in Core, not in the Risk module, because the `default` profile already has `risk` and `controls`, and the suspect rules depend on it. In the `default` profile a risk is anything that can cause harm or loss: a security breach or a financial loss as much as an injury. The Risk module's `hazard` keeps its ISO 14971 meaning, the potential source of harm.

## Modules

| Module | Content | Original zztrace IDs |
| --- | --- | --- |
| **Risk** | Risks and the controls that address them: hazard, hazardous situation, harm, cause and risk-control types; risk estimates and the risk matrix. The `iec62304` profile adds that standard's chain, experimental until its clause mapping is reviewed against the licensed texts | TRF-060 to TRF-063, TRF-035 (`iec62304`) |
| **Architecture and integrity** | Software items, code membership by path, integrity schemes as declared data (for example IEC 62304 class, ISO 26262 ASIL, DO-178C DAL), segregation rationale | TRF-072 to TRF-074 |

Verification is in Core: the `default` profile's `verifies` link already carries `role` and `method`, so a reader that resolves links must read them.

The following deferred proposals do not add obligations to a Core 1.0 Producer, Consumer or Analyzer:

| Proposal | Content | Original zztrace IDs |
| --- | --- | --- |
| C9. External and onboarding | Referenced-item ownership, `alias:native` identities, external declarations, read-only snapshots, links into snapshots and integrity checks | TRF-011, TRF-080, TRF-084 to TRF-087 |
| Recovery | `asserted`/`recovered` origins and accepted recovery records, including link, origin, decision, evidence and rejected proposals | TRF-045, TRF-046 |
| Tag exclusions and formats | `@req-none` and alternative tag keywords | TRF-057, TRF-058 |
| Coverage rules | Declared rules per type, the link path language, built-in checks, justifications | TRF-100 to TRF-104 |
| Adoption | Import records, item provenance, candidate items from documents, repeat import and cutover | TRF-081 to TRF-083 |

**C10. Interchange** is informative, outside Core conformance. Standalone ReqIF and OSLC mapping annexes remain planned.

## Left to tools

- **Analyses:** check, scope, impact and test selection, beyond the link-state definitions in C8.
- **Interfaces:** command names, CLI options, MCP tool names and their answers.
- **Adapters:** sync with Jama, Polarion, DOORS, codebeamer or Jira, and import mapping files. A future external-item extension may standardize the snapshots and provenance they write.
- **Documents:** generated specifications, trace matrices and design history files.
- **Change policy:** locks, owner groups and allow, warn, approve or deny decisions (TRF-140 to TRF-149). Not in OSTF 1.0. The `policy` key is reserved so zztrace can keep its policy in the same files. Revisit once the T3 model has real use. Publishing the policy file format would not give away the engine that decides, much as CODEOWNERS is a public format read by many tools.
- **Evidence:** test results, baselines, approvals and signatures (plan phase T6). A later module may define how results bind to a test identity, a commit and a fingerprint.

## Conformance

A tool claims a conformance class for Core, then each module it supports, for example "OSTF Core 1.0 Analyzer (Go, Python), Risk 1.0".

| Class | A conforming tool |
| --- | --- |
| **Producer** | Writes Core files that satisfy the entry schemas and applicable semantic rules for their declared profile; schema validation alone is insufficient |
| **Consumer** | Reads serialized Core constructs, validates the lock grammar, resolves local IDs, aliases and file-declared links, and reports their origins. It does not claim source binding or freshness states |
| **Analyzer** | Is a Consumer that also binds anchors and tags for at least one named language and runner, computes fingerprints and reports the four link states. It names the languages, test runners and fingerprint algorithms it supports |

A Consumer of a tree with enabled tags does not claim its file-declared links are the complete graph until an Analyzer binds those tags. Each link-state result uses one selected source-tree view for the OSTF files, lock and referenced source bytes. A public conformance suite makes the classes testable: fixture repositories with expected results, covering valid and invalid files with their error codes, anchors and tags with their bindings, and lock files with their link states. Core codes include `TAG_UNKNOWN_ID`, `TAG_UNBOUND` and `ITEM_CHANGED`. `SNAPSHOT_EDITED` belongs to the deferred external-item proposal.

The current [suite 0.1.3](conformance/suite.json) is a bounded draft subset. It exercises the current Go common contract with fixed expected bytes/hashes and two separately structured implementations. Schema-shape tests for proposed snapshots do not implement snapshot reading or integrity. The Python prototype shares this project's authorship, so it is independent code rather than independent-party qualification. The [support map](draft/support.md) is part of every result's claim boundary.

## Document set

"OSTF 1.0" names a set of documents, not one file. Each is versioned and listed here with its status.

| Document | Status | Holds |
| --- | --- | --- |
| **OSTF Core specification** | Draft contract with permanent IDs now present | [Core draft](draft/core.md): conventions, data, identity, links, origins, fingerprints/states, proposed areas and claim limits. Referenced-item and module contracts remain separate drafts |
| **Schemas** | Draft structural schemas and grammar now present | [Root, item, profile and proposed snapshot schemas](schema/), with shared definitions; [lock grammar](draft/trace-lock.ebnf). Text/schema agreement is fixture-checked. Single-source publication generation remains a 1.0 preparation task |
| **Language annexes** | Draft Go annex now present | [Go symbols, tags and go1](draft/go.md), with fixed token/hash vectors. 1.0 still targets Go first; zztrace's broader language support is not automatically an OSTF annex |
| **Runner annexes** | Draft Go identity annex now present | [Go runner identities](draft/go-tests.md). The independent prototype qualifies fixed top-level and subtest source-binding cases |
| **Module specifications** | Planned normative drafts, claimed separately when qualified | Risk, Architecture and integrity; each with its own terms, model, schema fragment and error codes |
| **Profiles** | Normative data | `default` ships with Core. Domain profiles such as `iec62304` ship with their module and name the standard editions they follow |
| **Conformance suite** | Initial bounded draft subset now present | [Suite 0.1.3](conformance/README.md), with requirement mappings and fixed positive/negative expectations. Complete error-code/construct coverage and independent-party qualification remain 1.0 gates |
| **Mappings** | Informative, outside Core conformance | ReqIF and OSLC mappings, each link marked exact, conditional or unsupported, with what is lost in each direction. Assurance-case mappings come later |
| **Rationale and examples** | Informative | Why the decisions were made, worked examples, migration from other tools' formats |

Rules the set follows:

- **Precedence.** Schemas define structural constraints, while Core text controls semantics. Where the schema and text disagree, the text wins, and the disagreement is a defect to fix in the next patch release.
- **Normative language.** "Shall", "should" and "may" follow [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) and ISO/IEC Directives, Part 2. Examples and notes are never normative.
- **Normative references** are limited to what the text depends on: YAML 1.2, RFC 8785 (JSON Canonicalization Scheme), SHA-256 (FIPS 180-4), base64url (RFC 4648), Semantic Versioning 2.0.0, and the terms vocabulary below.
- **Every requirement carries an `OSTF-` ID** that is never reused, and every test in the conformance suite names the IDs it exercises.

## Terms and definitions

Borrow before inventing. This working vocabulary distinguishes existing engineering terms from OSTF-specific terms. Exact source citations and definitions for borrowed terms remain terms-annex work before 1.0.

**Existing engineering terms (sources noted where applicable):**

| Term | Note |
| --- | --- |
| requirement | |
| verification | Confirmation, through objective evidence, that specified requirements have been fulfilled |
| traceability | 24765's software sense: the degree to which a relationship can be established between two or more products of the development process. OSTF states this explicitly because the healthcare standards family defines traceability of a *product* (IEC 60050-880), not of work products |
| configuration item | |
| software item, software unit | From IEC 62304, cited there, used only in the Architecture module |
| hazard, hazardous situation, harm, risk, risk control, residual risk | From ISO/IEC Guide 63 and ISO 14971, used in the Risk module. The `default` profile's `risk` item type is defined by OSTF as anything that can cause harm or loss, as a risk register records it |

**Defined by OSTF:**

| Term | Meaning |
| --- | --- |
| item | A unit of intent or evidence with a stable ID: a need, requirement, design element, risk, control or verification |
| profile | A declaration of the item types, link types, attributes and rules a project uses |
| module | An optional, separately versioned part of the standard |
| link | A typed, directed relationship from a source item or code anchor to a target item |
| inverse | The computed reading of a link from its target |
| source-tree view | One coherent set of repository-relative file contents and absences selected for an evaluation, such as a commit, a worktree snapshot or an equivalent materialized view |
| code anchor | A `path` or `path#symbol` reference to a file or a definition in the repository |
| tag | An `@req` comment that declares a link from the definition it binds to |
| test identity | The name a test runner gives a test, as the runner itself reports it |
| origin | How a Core link came to exist: declared, tagged or imported. Asserted and recovered are deferred proposals |
| prospective, retrospective | Links written with the work, and links reconstructed after it; the recovery contract is deferred |
| fingerprint | A hash over the fields or code that carry an item's or anchor's meaning |
| lock entry | The recorded fingerprints of both ends of a link when it was last rechecked |
| stamp | The act of rewriting a link's lock entry after rechecking it |
| link state | valid, suspect, unstamped or broken |
| risk-relevant | An item that is a control or refines one, and the code and tests linked to it. Earlier drafts said safety-relevant |
| referenced item | Proposed extension term: an item owned by another system and held read-only in a snapshot |
| snapshot | Proposed extension term: the committed, read-only copy of referenced items, with their revisions and hashes |
| adopted item | An item imported once and owned by the repository from then on |
| document | An ordered set of items with sections, as one item file presents them |
| conformance class | Producer, Consumer or Analyzer |

Decided 2026-10-17: the Core term is `risk`, and `hazard` is used only in its ISO 14971 sense, in the Risk module (a term inherited from the original zztrace format).

## Origin and open work

OSTF was extracted from the zztrace format. The items below record completed separation work and remaining interoperability work; the Core contract and schemas in this repository define the draft.

1. **Self-identification.** Done in TRF-007. A file says which standard it follows, as `openapi: 3.1.0` does: `ostf: "0.1"` while the format is a draft, `ostf: "1.0"` once it is published, in place of `schemaVersion: 2`. zztrace keeps reading `schemaVersion: 1`.
2. **Modules a reader does not implement.** Done in TRF-004. Strict reading still rejects unknown keys, so typos fail, but module keys, at the top level and on items, are reserved: a reader accepts them, may ignore them, and says it did.
3. **Tool extensions.** Done in TRF-004. Keys starting with `x-` (for example `x-zztrace`) hold tool-specific data. Other tools keep them and ignore them, and they never enter a fingerprint.
4. **Symbol paths per language.** A [Go draft annex](draft/go.md) now exists. Later annexes must settle other languages independently; product locator support alone does not make an interoperable annex.
5. **Test identity per runner.** A [Go identity draft](draft/go-tests.md) now exists. Broader runner annexes and dynamic subtest execution evidence remain open.
6. **Code fingerprint algorithms.** Fixed [token/hash vectors](conformance/code-vectors.json) now exercise go1 through the Go reference and independent-code Python parser. Unknown algorithms remain unstamped with UNKNOWN_ALGORITHM. Full independent-party and grammar-wide qualification remains open; ts1 is still product behavior without a normative draft annex.
7. **JSON Schema and lock grammar.** Draft root/item/profile/snapshot [schemas](schema/) and the [grammar](draft/trace-lock.ebnf) now exist. Snapshot shape is proposed, not working external-system semantics.
8. **Its own IDs.** [OSTF-001 through OSTF-023](draft/core.md) now map to the TRF areas. The [suite index](conformance/suite.json) maps executable cases and records non-executable/proposed gates. The original zztrace working specification remains separate from this draft.

## Versioning

- OSTF versions follow semantic versioning. A 1.x release only adds; a reader for 1.0 reads a 1.1 file and reports the constructs it skipped (TRF-007).
- 1.0 is frozen only after a second, independent implementation that computes fingerprints and link states itself passes the conformance suite, and two organizations have used the format on real changes. Until then, drafts are 0.x.
- Each module has its own version.
- IDs are never reused. A retired requirement of the standard keeps its ID, to preserve citation stability.
