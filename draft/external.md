<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# External-item interchange: design proposal

Status: exploratory extension outside OSTF Core 0.2 and every current conformance claim. This page identifies the data that a Jira, Jama or similar adapter would need to exchange. It does not authorize a reader to resolve external items or claim that a snapshot is approved.

## Interchange problem

A team may keep an approved requirement in another system while its code and tests live in Git. An OSTF reader needs a stable external identity and the exact content the team used for a particular source-tree view. A live issue URL alone can change, become inaccessible or show different fields to different readers.

The existing [snapshot entry schema](../schema/snapshot.schema.json) checks a proposed structural shape. It does not define the item's hash projection, prove the export was complete, resolve external links or validate source-system approval. The [support map](support.md) records these limits.

## Candidate data contract

| Data | Interoperability purpose |
| --- | --- |
| Source alias and permanent native ID | Preserve identity even when a display key or URL changes; detect collisions across sources |
| Source revision, if available, and mapped-content digest | Identify the exact observed content. A digest without a source revision identifies an observation, not a retrievable source version |
| Selected item fields and mapping version | Let readers interpret the same requirement text and attributes without depending on a live API response |
| Snapshot capture time, adapter identity and source baseline | Explain where the observation came from and which controlled export produced it |
| Capture scope and completeness result | Prevent an inaccessible field, truncated query or missing linked item from being silently interpreted as an absent requirement |
| Snapshot integrity check | Detect accidental edits to committed content. A self-reported digest alone does not prove who exported or approved it |

The source system continues to own the requirement. An adapter may use credentials to read it, but credentials do not enter OSTF files. The adapter's API calls, retries, synchronization schedule, authorization checks and approval interpretation remain tool behavior.

## Decisions before a normative extension

1. Define the canonical byte projection for an external item's mapped fields, including text normalization and profile attributes, before assigning meaning to `hash`.
2. Define how a manifest records capture scope, missing or inaccessible records, and mixed-revision exports. A partial capture must have an explicit incomplete result.
3. Decide whether snapshot integrity is per item, per file or both, and what a reader reports for a changed digest. Integrity does not establish authenticity or approval.
4. Define link resolution and suspect behavior when a newer reviewed snapshot changes a referenced item's meaning. The older snapshot remains a valid historical observation.
5. Specify conformance vectors for duplicate identities, an edited snapshot, missing content, incomplete capture and a changed external requirement.

The current schema and its structural fixtures remain review material. Semantic reader support, fixed hash vectors and positive and negative conformance cases are required before this extension can make an implementation claim. The synthetic [change workflow](../examples/change-impact.md) is an informative stress test for the contract.
