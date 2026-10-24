<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# OSTF draft refactoring plan

Date: 2026-10-24. Status: superseded by the from-scratch [0.3 draft](0.3/ostf.md) and its [agent-readiness plan](0.3/plan-agent-readiness.md); kept as a record of the direction considered. Planning baseline: OSTF wire 0.2, document revision 0.11, and the current zztrace implementation. Proposed next wire version: 0.3, assigned when its contract and fixtures are ready.

Refactor OSTF into a portable contract that lets an agent start from a task, requirement, function, PR diff, or runtime incident and retrieve relevant engineering context with an explanation of each connection. Context can include requirements, design decisions, tests, risk controls, logs, traces, configuration, and resources supplied by other systems.

The draft may change substantially before publication. Existing serialization, field names, schemas, and module boundaries are open to replacement. Preserve useful semantics and executable examples; use a documented conversion for existing development fixtures instead of committing to permanent support for earlier drafts. Existing specification requirement IDs keep their historical meaning: retain, revise explicitly, or retire them, and allocate new IDs for new obligations.

The design adopts OpenTelemetry semantic conventions where their meanings fit. Running an OpenTelemetry SDK, Collector, exporter, or backend remains optional. The first implementation milestone is an executable PR review workflow in zztrace, including an indirect code change, an external requirement, and evidence tied to known source revisions.

## 1. Outcomes and design decisions

| Decision | Planned direction |
| --- | --- |
| Primary purpose | Give agents relevant, explainable context throughout planning, coding, review, and maintenance. |
| General model | Typed resources and directed relationships, with explicit identity, revision, selectors, provenance, and applicability. Requirements remain a supported resource kind. |
| Flexibility | A common reference envelope and versioned profiles support different data sources without a new top-level field for every integration. |
| OpenTelemetry | Reuse selected vocabulary, attribute definitions, identifier representations, and naming conventions. Publish an optional telemetry mapping profile. |
| Interoperability | Standardize portable data and the meaning of context/impact results. Provide an optional agent query profile and an initial MCP binding. |
| Discovery | Tools choose their indexing, dependency analysis, retrieval, and ranking algorithms. Their results carry methods, supporting references, and limits. |
| Authoring | Keep a small repository usable offline with a short YAML file. Define one normalized graph representation; any compact authoring shorthand expands to it deterministically. |
| Runtime data | Reference retained artifacts or bounded queries. Keep high-volume telemetry in its source system. |
| Freshness | Report link freshness, execution outcomes, review decisions, and impact completeness separately. |
| Adoption | Prove the deterministic workflow in Go first. Add semantic retrieval and further languages against measured gaps. |

Policy enforcement, reviewer authentication, source write protection, and release decisions remain responsibilities of tools and organizations. OSTF carries references to their results when useful. No graph database, embedding model, network service, or telemetry installation is required to read the Core graph.

## 2. Starting point and concrete gaps

The current [Core](core.md) already supplies stable local IDs, typed relationships, configurable profiles, source anchors, fingerprints, and separate origins. zztrace exposes these through [agent tools](../../zztrace/go/trace/mcp.go), including queries before editing and impact analysis afterward.

The next design needs to address these gaps:

| Current behavior | Required change |
| --- | --- |
| External snapshots are deferred and unresolved by current readers. | Make external resource identity, captured revisions, resolution results, and capture completeness part of the supported reference contract. |
| `logs` and `otel` entries are item attachments without graph edges or source-baseline binding. | Represent observations and artifacts through common references and typed relationships; add the telemetry mapping profile. |
| Profile attribute names exclude dots and underscores. | Revise the registry grammar, schemas, and readers to admit the selected OpenTelemetry names and extension namespaces. |
| Code anchors identify repository paths and symbols without an exchanged repository/view envelope. | Define repository identity, selected source views, selectors, and historical lookup together. |
| Agent answers and their completeness are entirely tool-specific. | Specify a portable result envelope and optional query semantics. |
| Direct links dominate impact analysis; discovery of production dependencies is incomplete. | Add dependency-based candidate impact with supporting paths and explicit unresolved boundaries. |
| Link origin does not fully describe a machine-inferred candidate or its review disposition. | Exchange provenance, derivation method, and review status independently. |

The [constructor scenario](../examples/change-impact.md) supplies a regression target. During the 2026-10-24 review, a temporary copy of the payment example was converted to zztrace's supported wire 0.1, with the 0.2 observability attachments omitted. Removing the receipts-map initialization from `NewService` caused `TestSameKey` to panic. zztrace reported the constructor as untraced and out of scope, but returned no affected requirements or selected tests; both existing link stamps remained valid. This is consistent with the current fingerprint boundary and demonstrates the missing impact connection. Seven focused zztrace query/impact tests passed during the review.

## 3. Refactored data contract

### 3.1 Resources, references, and source views

Use a common resource model for local items and externally owned information. A resource has a kind, identity within an identified source, optional content, and profile-defined attributes. Source ownership is explicit. An imported copy owned by the repository and a captured observation of an externally owned record have different ownership semantics.

Define references using separate fields rather than requiring callers to concatenate opaque identifiers:

| Part | Meaning |
| --- | --- |
| Source identity | The repository, document collection, issue system, telemetry store, or other owning namespace. Display aliases resolve to this identity. |
| Native resource ID | The stable identifier assigned by that source. A display URL is a retrieval location and may change. |
| Revision or observation | A source-native revision when available; otherwise an identified capture with time and digest. Preserve both when both exist. |
| Selector | A typed selection within the resource, such as a symbol, test case, document section, JSON Pointer, or span. |
| Retrieval information | Artifact location or resolver descriptor, media type, and availability/retention metadata. Credentials stay with the resolver. |

Core defines the envelope and selector dispatch. Language, document, test-runner, and telemetry profiles define selector semantics. Unknown selector types remain visible as unsupported; they cannot produce a successful exact match. A piece of a resource and the whole resource use the same reference mechanism.

For code, combine repository identity, a selected source view, a clean repository-relative path, and a language-aware selector. Lines are locations within that view. A function's display name is insufficient as a global identity. A rename or move is an explicit correspondence between views, with provenance when inferred; ambiguity remains visible.

Source views must describe coherent bytes, including the selected worktree changes when applicable. Record their identity and how it was obtained. Define how a Git commit identifies a tree, how a materialized tree is digested, and how graph inputs are bound to that view. PR results identify both base and head views. External captures have their own revisions and times; their association with a source view is recorded rather than assuming simultaneous capture across systems.

### 3.2 Relationships and provenance

Represent relationships explicitly with source and target references, a registered predicate, applicable revisions, and declared attributes. A relationship can connect code, tests, intent, controls, observations, and other registered resource kinds. Keep the existing `implements`, `verifies`, `refines`, and `controls` meanings where applicable; define endpoint constraints, inverse names, and cycle rules in the registry.

Introduce only the additional predicates the pilot needs, such as an observation referring to a source view or a derived dependency between definitions. For each, state exactly what can be inferred. A test's declared `verifies` relationship identifies its purpose; its execution outcome is a separate observation. A static dependency indicates potential impact within the analyzer's scope.

Store independently:

- How the connection entered the graph, such as declaration, tag, import, static derivation, runtime correlation, or semantic suggestion.
- The producer and method/version, supporting references, and captured inputs.
- Its review disposition and any reference to a review record. A disposition alone does not authenticate the reviewer.
- Its applicability to selected revisions and its freshness result.
- An optional tool-local ranking score with its method. Scores are not assumed to be calibrated probabilities or comparable across tools.

Keep candidate relationships separate from accepted assertions in query results. Acceptance preserves the original derivation and evidence. Rejection is scoped to the evaluated inputs so identical suggestions can be suppressed without permanently suppressing a connection after its inputs change.

### 3.3 Profiles, attributes, and extension handling

Create a versioned registry with entries for resource kinds, selectors, relationship types, and attributes. Each entry declares its owner, definition, value type, applicability, requiredness, stability, and replacement/deprecation information. Attribute definitions also declare whether they affect identity, semantic fingerprints, or display only.

Retain structured fields for identity, references, and relationships. Use namespaced attributes for additional descriptors. Register domain-specific structured data through profiles when simple attributes are insufficient. A profile must identify its version and dependencies, and its definitions must be available to an offline reader.

Readers preserve opaque extensions and report unsupported capabilities. Unknown required semantics prevent a complete interpretation claim; they cannot be silently treated as implemented. Arbitrary unrecognized attributes do not acquire identity or freshness meaning just because they were preserved.

### 3.4 Fingerprints, freshness, and evidence

Retain canonical projections and explicit algorithm versions. Reassess the lock serialization after the reference and relationship model is fixed. Define which endpoint revisions, selectors, relationship attributes, and semantic fields are bound by a recheck. Canonicalization must distinguish absent values from explicit values, define array ordering, and specify text and number handling.

Preserve the separation between stable identity and changing content. Retain the four existing freshness meanings where useful, exposing them explicitly as freshness. For the agent review profile, count body changes for all linked code by default; specialized profiles can declare different projections with visible limits. Dependency impact remains a separate result even when endpoint fingerprints are unchanged.

Promote the portable parts of the [evidence proposal](evidence.md): execution identity, exact source and graph inputs, environment/configuration, test identity, outcome, and retained artifact reference/digest. Record retries and partial execution without collapsing skipped or unexecuted tests into passes. A mutable query is a retrieval recipe; a captured result has its own identity, capture time, and integrity information.

## 4. OpenTelemetry semantics and notation

Use OpenTelemetry as a vocabulary dependency for selected fields. Publish the exact convention version and definitions adopted by each OSTF profile, including any mapping. A named profile can require these field meanings when the fields are present while remaining usable with exported files and offline fixtures.

| Area | Reuse or mapping decision |
| --- | --- |
| Attribute notation | Adopt lowercase dot-separated namespaces and underscore-separated words within a component. Keep OSTF structural keys distinct from this attribute registry. |
| Service | Reuse `service.name`, `service.namespace`, and `service.version` with their documented meanings. Record exact build/source binding separately because a service version string does not guarantee it. |
| Source code | Map `code.function.name`, `code.file.path`, `code.line.number`, and `code.column.number` into a source view and language selector. Preserve the original values. Runtime function names and filesystem paths may need translation. |
| Trace and span identity | Reuse the specified trace/span identifier representation in the telemetry profile. Add the owning source/store and execution context needed to locate and interpret the record. Trace and span IDs keep their role as execution identifiers. |
| CI and source control | Evaluate the relevant CI/VCS conventions against the pilot. Pin adopted versions and maturity; require immutable source selection for OSTF applicability even when an upstream field permits a moving reference. |
| OSTF concepts | Define OSTF-owned resource and relationship semantics. Use an owned namespace for any new exported telemetry attributes, initially `dev.ostf.*`; these would be OSTF extensions, not official OpenTelemetry conventions. |

OpenTelemetry's [naming rules](https://opentelemetry.io/docs/specs/semconv/general/naming/) supply the notation and namespace guidance. Its [code attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/code/) and [service conventions](https://opentelemetry.io/docs/specs/semconv/resource/service/) supply the corresponding field meanings. The [logs data model](https://opentelemetry.io/docs/specs/otel/logs/data-model/) supports optional trace/span correlation. OSTF should not assume those fields or function-level instrumentation exist in every observation.

For the first telemetry adapter, resolve this chain with evidence at each step:

```text
log or span -> deployment/build -> source view -> code selector -> linked intent/control
```

When code-level metadata is absent, return a supported service/operation-level association with its lower precision. Sampling, missing instrumentation, and expired data limit coverage. Lack of an observed execution cannot establish lack of impact. Production observations from an older deployment remain useful historical context, with their applicability distinguished from candidate verification.

## 5. Agent query contract and lifecycle

Add an optional, transport-neutral agent profile with five conceptual operations. Exact operation names and wire shapes are settled with the first client fixture; an MCP binding initially reuses zztrace's existing workflow where it fits.

| Operation | Inputs and result |
| --- | --- |
| Discover capabilities | Supported profiles, languages, selectors, resolvers, analysis methods, and result limits. |
| Resolve a reference | A resource reference plus evaluation context; resolved identity/content or a typed unavailable, missing, ambiguous, or unsupported result. |
| Find relevant context | A task, resource, or code selector; ranked context with supporting relationship paths and separate suggestions. |
| Assess a change | Base/head source views and optional task scope; direct and potential indirect impact, affected intent/controls, test candidates, evidence, and gaps. |
| Export a context bundle | A bounded, revision-bound subset with its required registry definitions, provenance, and missing-reference manifest, suitable for another reader. |

Every response identifies its inputs, evaluated source views, profile versions, producer/methods, and capture time. Results include the supporting references and path explaining relevance. Report direct links, derived potential impact, and semantic candidates distinctly. Distinguish no match from inaccessible, expired, unsupported, untraced, ambiguous, or unevaluated information.

Completeness is relative to a declared source and analysis scope. Responses name that scope, exclusions, unresolved boundaries, limits reached, and pagination/truncation. A bounded dependency walk cannot imply whole-program completeness. Empty test selection with incomplete analysis must remain distinguishable from a complete selection with no applicable tests. The implementation can recommend a broader package or suite fallback.

Use incremental retrieval: a compact initial answer with explanation paths and references, followed by expansion as needed. Carry content as source data, with provenance; retrieved documents cannot grant tool permissions or become agent instructions merely by appearing in context. Retrieval authorization stays with the client and source adapter.

| Lifecycle stage | Expected behavior |
| --- | --- |
| Planning | Retrieve intent, existing implementation, constraints, controls, and unresolved questions. Capture new intent with ownership and provenance before linking implementation. |
| Coding | Resolve context for planned edits, expose shared dependencies, propose new connections, and update anchors as code changes. |
| PR review | Evaluate both source views, retain base-side links for deleted/moved code, explain direct and potential impact, and separate historical context from candidate evidence. |
| Merge and deployment | Retain the reviewed graph/source association and bind execution observations to the build that produced them. |
| Maintenance | Start from an incident or changed external record, resolve the relevant source view, follow connections, refresh captures, and identify links/evidence needing reassessment. |

## 6. Linkage algorithm implementation plan

The standard defines result semantics and interoperability fixtures. zztrace implements a reference pipeline whose algorithmic quality is measured separately from format conformance.

1. **Normalize and index identities.** Load selected repository views, declared links, profile registries, external captures, and evidence references. Maintain indexes from anchors/resources to relationships and from source revisions to observations. Reject conflicting identities and report unresolved references.
2. **Map the diff on both sides.** Resolve removed lines against base definitions and added lines against head definitions. Preserve changes outside definitions and changes to configuration or dependency manifests. Use both graph versions so unlinking or moving code does not erase its earlier context.
3. **Expand potential impact.** Build a Go reference index using parser/type information across production code and tests. Walk reverse dependencies to callers, affected tests, and linked resources. Include data/type/global dependencies where supported. The constructor regression can be reached through `TestSameKey` calling `NewService`, then the test's `verifies` link. Record the whole path. Unsupported dynamic calls or configuration dependencies produce explicit boundaries and a conservative test fallback.
4. **Join runtime observations.** Use deployment/build/source mappings, then exact code selectors or a documented service/operation fallback. Return the observations' actual revisions and time bounds. Preserve unmatched telemetry as an unresolved association rather than manufacturing a function link.
5. **Retrieve semantic candidates.** Begin with exact IDs and lexical retrieval. Add embedding retrieval and optional model-assisted reranking only when the benchmark demonstrates a useful gap. Require supporting excerpts/references and keep inferred suggestions distinguishable. Evaluate acceptance and false associations against held-out cases.
6. **Assemble and maintain context.** Rank by supported relevance, applicability, freshness, and task scope. Return bounded graph paths, evidence, and missing coverage. Recompute derived results when their inputs change; cache by source-view and method versions. Preserve historical captures and decisions.

Evaluate [SCIP](https://github.com/scip-code/scip) as an optional source of definitions and references for later language adapters. Its indexing protocol supports code navigation; the impact engine still needs propagation rules and explicit analysis boundaries. Go can start with its native parser/type tooling.

## 7. Work packages and completion gates

Execute these packages in order. Each package closes its fixtures and documentation before the next expands the surface. Work in zztrace follows the standard contract from this repository.

### P1. Fix the model and semantic registry

- Rewrite the capability statement and scope around lifecycle context. Define the Core/reference boundary and the optional agent and telemetry profiles.
- Draft resource/reference, relation/provenance, source-view, and registry contracts. Resolve the existing attribute-name restriction before introducing borrowed names.
- Create minimal examples for local requirements, an external document section, a code/test relationship, and a runtime observation using the same reference model.
- Set draft version and compatibility policy. Map every current `OSTF-` requirement to retained, revised, or retired status.

Deliverables: revised `scope.md` and `draft/core.md`; new `draft/semantic-conventions.md`, `draft/references.md`, and a small machine-readable registry under `registry/`; an ID/change mapping in `draft/migration.md`.

Gate: the examples can be explained without tool-specific identity rules; a local requirement/code/test example remains short and needs no external service. Each borrowed name has an exact definition/version or an explicit mapping.

### P2. Implement references and offline interchange

- Update schemas, strict parsing, profiles, canonicalization, and freshness evaluation for the new model. Resolve the lock format and bind stamps to the relevant inputs.
- Implement external snapshot resolution, mapped-content digests, source ownership, capture manifests, and incomplete-capture diagnostics in the Python reader and zztrace.
- Support typed selectors and revision-bound bundles. Preserve unknown optional payloads and report unsupported required semantics.
- Convert existing fixtures and examples with a reviewed migration report. New readers reject unsupported old wire versions clearly; permanent dual readers are unnecessary for the unpublished draft.

Deliverables: updated `schema/`, `conformance/reader.py`, vectors and suite mappings; refreshed minimal/payment examples; corresponding zztrace `go/trace` reader/model/export changes.

Gate: both code paths agree on fixed identities, resolution results, canonical bytes, and freshness fixtures. External references work from committed captures while offline, including partial and altered snapshots.

### P3. Implement agent context and explainable impact

- Specify capability discovery, reference resolution, context, impact, and bundle response schemas.
- Add source-view-bound responses, completeness reporting, explanation paths, and bounded expansion to zztrace's queries and MCP tools.
- Extend diff analysis with the Go dependency index over production and test code. Preserve base-side associations and handle renames/deletions explicitly.
- Include package/suite fallback advice for incomplete test selection.

Deliverables: new `draft/agent.md`, `draft/linkage.md`, and query fixtures; zztrace changes centered on `go/trace/impact.go`, `query.go`, `mcp.go`, and a separate dependency-analysis component.

Gate: an agent starting with the constructor-only diff discovers `R-PAY-RETRY` and `TestSameKey` through an explanation path. Unresolved dependencies and untraced changes stay visible. No previously linked deleted/moved code loses its base context.

### P4. Complete one lifecycle pilot with external and runtime evidence

- Implement the telemetry profile and baseline-bound evidence records.
- Add one resolver for a captured external requirement and one adapter for retained OTel trace/log data. Start with deterministic exported fixtures; then exercise authorized real sources without making live services a conformance prerequisite.
- Bind build/deployment identity to source and graph inputs. Distinguish historical production evidence from a run against the proposed change.
- Turn `examples/change-impact.md` into an executable scenario with a runner and expected context/impact results.
- Exercise planning, implementation, PR review, and an incident lookup against the same resource identities.

Deliverables: new `draft/otel.md`; revised `draft/external.md` and `draft/evidence.md`; executable lifecycle fixtures and a recorded zztrace pilot.

Gate: the agent retrieves the external requirement revision, risk-control relationship, affected test, and applicable observation. It reports an expired artifact and rejects a wrong-revision observation as candidate verification. The same Core graph remains usable without OTel data.

### P5. Measure discovery quality and add semantic retrieval

- Establish labeled evaluation cases containing missing links, distractors, ambiguous names, indirect dependencies, and external sources with different terminology.
- Compare declared-link lookup, structural analysis, lexical retrieval, and the combined pipeline. Add embeddings/reranking as separately measured candidates.
- Freeze test labels and evaluation conditions before tuning. Use a held-out set and preserve rejected candidates with their input context.
- Measure relevant-context recall, irrelevant-result rate, explanation support, unknown/unresolved reporting, response size, latency, and reviewer effort.

Deliverables: a reproducible evaluation corpus and report, plus any justified retrieval component in zztrace. Keep algorithm quality scores separate from OSTF conformance results.

Gate: every fixed critical-impact case is found or explicitly reported as unresolved, and every returned established relationship has a supporting source or derivation. Set quantitative retrieval targets from the recorded baseline before accepting a new ranking method. Hold an actual human review of the workflow; agent-only trials do not establish reviewer benefit.

### P6. Consolidate the next draft

- Reconcile Core, registry, profiles, schemas, examples, support claims, and documentation. Remove superseded field definitions and duplicated proposal text.
- Update the README, white paper, contribution/governance text, citation metadata, and support map for the unpublished draft and its actual capabilities.
- Publish the development migration procedure with explicit losses, including unsupported selectors and changes to fingerprint meaning. Synchronize zztrace's embedded `standard/` snapshot from this repository.
- Assign and test conformance claims for Core reading/writing, source analysis, agent results, and optional profiles independently.

Gate: the new draft passes its declared suite in both code paths and the lifecycle pilot passes. A future 1.0 still needs independently maintained implementation and real adoption evidence; completing this refactor does not itself trigger publication or a 1.0 claim.

The first end-to-end milestone is completion of P1 through P4. Semantic retrieval, additional languages, and more vendor adapters follow the measured gaps from that milestone.

## 8. Acceptance scenarios

These cases test distinct failure modes. The suite must state whether each asserts format semantics, a named analyzer capability, or an end-to-end workflow result.

| Scenario | Required result |
| --- | --- |
| Local requirement, function, and test; no OTel installation | Resolve the graph and answer code-to-intent queries offline. |
| Custom resource kind and document-section selector | Preserve the data and resolve through its declared profile; report an unsupported selector when that capability is absent. |
| Constructor-only change from the payment example | Return the affected test and requirement through dependency evidence, while keeping link freshness separate. |
| Deleted or moved function and changed links | Retain base-side context; report correspondence or ambiguity explicitly. |
| Shared helper used by unrelated features | Return all supported impact paths, including effects outside the task's declared scope. |
| Configuration or dependency-manifest change | Resolve declared/derived consumers or expose an analysis gap with a test fallback. |
| Changed external requirement, unchanged source | Identify the new captured revision and affected relationships without rewriting historical evidence. |
| Partial external export or access failure | Report incomplete/unavailable context rather than an absent requirement. |
| Trace from a different build or environment | Return it with its real applicability; exclude it from candidate verification. |
| Same function name in two repositories | Keep identities separate through repository/view/selector context. |
| Expired log or altered retained artifact | Distinguish retrieval failure from integrity failure and from successful evidence resolution. |
| Similar wording in an unrelated requirement | Keep any semantic match a candidate and measure it as a false association when the label rejects it. |
| Truncated graph walk or paginated search | Report bounds and continuation information; no whole-scope completeness claim. |
| Non-risk function body changes | Agent review profile reports freshness change even when its signature is unchanged. |
| Unknown required profile or malformed borrowed attribute | Report unsupported semantics or a typed validation error, according to the contract. |

## 9. File changes and verification

| Location | Planned changes |
| --- | --- |
| `README.md`, `scope.md`, `white-paper.md` | Lifecycle purpose, architecture, short onboarding example, and draft status. |
| `draft/core.md`, `draft/go.md`, `draft/go-tests.md`, `draft/trace-lock.ebnf` | Refactored contracts, bindings, fingerprints, and requirement mappings. |
| `draft/external.md`, `draft/evidence.md` | Supported capture/evidence contracts with explicit profile boundaries. |
| New `draft/references.md`, `draft/semantic-conventions.md`, `draft/agent.md`, `draft/otel.md`, `draft/linkage.md`, `draft/migration.md` | Reference identity, vocabulary, agent results, OTel mapping, informative algorithm, and draft conversion. |
| New `registry/`; `schema/` | Versioned semantic definitions and structural schemas; local resolution. Extend `LICENSE.md` for new registry file types if needed. |
| `conformance/`, `schema_test.go` | Fixed projections, reference/selector/state fixtures, query-envelope fixtures, explicit capability coverage. |
| `examples/` | Minimal authoring, mixed-source context, and executable lifecycle scenario. |
| `draft/support.md`, `CITATION.cff`, `CONTRIBUTING.md`, `GOVERNANCE.md` | Accurate versions, implementation limits, and unpublished-draft process. |
| Sibling zztrace `go/trace`, `standard/`, and relevant docs | Reader, resolvers, indexes, query/MCP results, evidence adapters, and consumer usage examples. Changes follow its existing verification requirements. |

For implementation changes, run the repository's declared checks:

```sh
python3 conformance/run.py
go test ./...
go vet ./...
(cd examples/minimal && go test ./...)
(cd examples/payment-retry && go test ./...)
```

Add the lifecycle runner to these checks once implemented. Run `npm run verify` in zztrace for product changes, with focused dependency/query tests during development. Separate offline conformance, deterministic integration fixtures, and optional live-adapter trials in results. Update support claims only for capabilities actually exercised.

## 10. Decisions to close during P1

These are bounded design tasks with a preferred starting point. They do not block writing the first examples.

| Question | Starting point and decision evidence |
| --- | --- |
| Canonical graph versus compact authoring syntax | One normalized resource/relation representation; retain compact declarations only if their expansion is unambiguous and demonstrably improves the minimal example. |
| Reference identity syntax | Structured source/native-ID/revision/selector fields, with local short IDs resolved through a source manifest. Test opaque external IDs and repository collisions. |
| Source-view digest | Canonical sorted path/content manifest with an explicit algorithm; preserve Git identities as provenance and selectors. Define included files, symlinks, submodules, and external artifact boundaries before publishing vectors. |
| Relationship identity and rechecks | Define the immutable identity tuple separately from revision bindings and review records. Compare compact lock entries with a structured recheck file using the pilot cases. |
| Semantic convention version | Select and pin the smallest stable OTel subset needed by the examples. Define deprecated-name mappings and conversion diagnostics; evaluate CI/VCS fields individually. |
| External snapshots in Core | Put common identity/reference and capture-result semantics in Core; source-specific mapping and synchronization behavior live in adapters/profiles. |

Start implementation with P1's minimal examples and definitions, followed by fixed reference-resolution vectors. This makes each broader capability depend on an executable shared contract.
