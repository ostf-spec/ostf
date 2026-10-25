<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Example: a refund limit, a payment retry and encryption at rest, traced with OSTF 0.3

A small Go package that shows the constructs most teams need:

- a need, a risk, and the requirement that controls the risk (`N-REFUNDS`, `RISK-REFUND-ABUSE`, `R-REFUND-LIMIT`), with links declared in [trace.yaml](trace.yaml);
- a requirement owned by an issue tracker (`PAY-123`, declared `external: jira:PAY-123` with the observed text and revision), linked from [charge.go](charge.go) and [charge_test.go](charge_test.go) by `@req` comments, which are read unless the root sets `tags: false`;
- a requirement that no function carries (`R-DATA-AT-REST`, encryption at rest): it links the whole infrastructure file [deploy/database.tf](deploy/database.tf), which no language annex covers, and is verified by a review procedure, `V-ENCRYPTION-REVIEW`, an item of type `verification` rather than an automated test;
- [trace.lock](trace.lock) with eight rechecked links, three between items, four from Go code and tests and one from a whole file, and real `go2`, `f1` and `lf1` fingerprints.

Run the tests from this directory:

```sh
go test ./...
```

## What the stamps say

Each lock line names a link and the fingerprints of both ends at the last recheck. The `refines`, `controls` and `verifies` lines between items carry two item fingerprints. The two `R-REFUND-LIMIT` code and test links are declared in YAML (`code` and `tests`); the two `PAY-123` links come from tags, so an Analyzer reports them with origin `tagged`. The `deploy/database.tf` line carries `source.sig` alone: a whole-file anchor in a language without an annex is fingerprinted with `lf1` over the file's bytes (OSTF-141). All eight are `valid` for these exact bytes.

- Change the body of `CheckRefundLimit` and its `implements` link becomes `suspect` with reason `BODY_CHANGED`, because `bodyChange` defaults to `all` (OSTF-144).
- Refresh the Jira item's copy to a new `revision` with different `text` and both `PAY-123` links become `suspect` with reason `ITEM_CHANGED`: the observed copy enters the item fingerprint (OSTF-113).
- Change any byte of `deploy/database.tf`, a comment included, and its `implements` link becomes `suspect` with reason `SIGNATURE_CHANGED`. Without an annex there are no comments or whitespace to drop, so a whole-file link is rechecked more often than a symbol link; that is the price of tracing a file OSTF cannot parse.
- `V-ENCRYPTION-REVIEW` names no test, so no tool can run it. `check` reports only whether the procedure's text or its requirement's text changed since the two were last confirmed to match; whether the review happened is evidence kept outside OSTF (Annex E).
- Remove the receipts map initialization from `NewService` and every link stays `valid`. `Service.Charge` did not change. That is the boundary OSTF-145 states: a valid link is unchanged inputs, not correct behavior. Finding that `TestChargeRetry` must run is a dependency analysis a tool performs on top of the format.

## Expected outputs

[expected/](expected/) holds what a tool that claims the command profile (Annex I) returns for this tree: [check.json](expected/check.json) for `check --format json`, and [context.json](expected/context.json) and [context.txt](expected/context.txt) for `context refund.go#CheckRefundLimit` in both formats. The outputs for the first six links were written from the specification text and checked against `trace.lock` and the result schema before any tool produced them. The two `R-DATA-AT-REST` links were added with the [0.3 reader](../conformance/README.md) after their `f1` and `lf1` fingerprints had been computed separately with a hash library alone; the reader reproduces every file byte for byte.

## Status

The `f1` fingerprints were first computed with the code of the 0.2 Python prototype, since this draft keeps that algorithm unchanged; the Go fingerprints were recomputed when `go2` replaced 0.2's `go1` (Annex A.6). The [0.3 reader](../conformance/README.md) reads this tree directly, reports all eight links `valid` and reproduces [expected/](expected/) byte for byte. zztrace's second reader, written separately on Go's own parser, agrees with it on every fingerprint, state and rendering of this tree ([agent-readiness plan](../plan-agent-readiness.md), step 2d).
