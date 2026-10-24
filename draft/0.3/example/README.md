<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Example: a refund limit and a payment retry, traced with OSTF 0.3

A small Go package that shows the constructs most teams need:

- a need, a risk, and the requirement that controls the risk (`N-REFUNDS`, `RISK-REFUND-ABUSE`, `R-REFUND-LIMIT`), with links declared in [trace.yaml](trace.yaml);
- a requirement owned by an issue tracker (`PAY-123`, declared `external: jira:PAY-123` with the observed text and revision), linked from [charge.go](charge.go) and [charge_test.go](charge_test.go) by `@req` comments, which are read unless the root sets `tags: false`;
- [trace.lock](trace.lock) with six rechecked links, two between items and four from code and tests, and real `go1` and `f1` fingerprints.

Run the tests from this directory:

```sh
go test ./...
```

## What the stamps say

Each lock line names a link and the fingerprints of both ends at the last recheck. The `refines` and `controls` lines carry two item fingerprints. The two `R-REFUND-LIMIT` code and test links are declared in YAML (`code` and `tests`); the two `PAY-123` links come from tags, so an Analyzer reports them with origin `tagged`. All six are `valid` for these exact bytes.

- Change the body of `CheckRefundLimit` and its `implements` link becomes `suspect` with reason `BODY_CHANGED`, because `bodyChange` defaults to `all` (OSTF-144).
- Refresh the Jira item's copy to a new `revision` with different `text` and both `PAY-123` links become `suspect` with reason `ITEM_CHANGED`: the observed copy enters the item fingerprint (OSTF-113).
- Remove the receipts map initialization from `NewService` and every link stays `valid`. `Service.Charge` did not change. That is the boundary OSTF-145 states: a valid link is unchanged inputs, not correct behavior. Finding that `TestChargeRetry` must run is a dependency analysis a tool performs on top of the format.

## Expected outputs

[expected/](expected/) holds what a tool that claims the command profile (Annex I) returns for this tree: [check.json](expected/check.json) for `check --format json`, and [context.json](expected/context.json) and [context.txt](expected/context.txt) for `context refund.go#CheckRefundLimit` in both formats. They were written from the specification text and checked against `trace.lock` and the result schema; no tool produces them yet, so they are targets for Phase 2 of the [plan](../plan-agent-readiness.md).

## Status

The fingerprints were computed with the `go1` and `f1` implementation of the 0.2 Python prototype in `conformance/`; this draft keeps both algorithms unchanged. Neither that prototype nor zztrace reads wire 0.3 yet. A wire 0.2 rendering of this tree, with the `external` fields removed, reports the same six links `valid` through the prototype, which is how the lock file was cross-checked.
