<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Example: a refund limit, a payment retry and encryption at rest, traced with OSTF 0.3

A small Go package that shows the constructs most teams need:

- a need, a risk, and the requirement that controls the risk (`N-REFUNDS`, `RISK-REFUND-ABUSE`, `R-REFUND-LIMIT`), with links declared in [trace.yaml](trace.yaml);
- a requirement owned by an issue tracker (`PAY-123`, declared `external: jira:PAY-123` with the observed text and revision), linked from [charge.go](charge.go) and [charge_test.go](charge_test.go) by `@req` comments, which are read unless the root sets `tags: false`;
- a requirement that no function carries (`R-DATA-AT-REST`, encryption at rest): it links the whole infrastructure file [deploy/database.tf](deploy/database.tf), which no language annex covers, and is verified by a review procedure, `V-ENCRYPTION-REVIEW`, an item of type `verification` rather than an automated test;
- [trace.derived](trace.derived), the coverage a test tool records under Annex E, an optional annex: `TestRefundLimit` covers `CheckRefundLimit` and `TestChargeRetry` covers `Service.Charge`, so both `implements` links are `corroborated`, while `deploy/database.tf`, whose item no test verifies, is `unobserved`. Its lines carry `view=unknown` because they were written for this example, not observed in a commit.

Run the tests from this directory:

```sh
go test ./...
```

## What a change shows

The tree has eight links: three between items, four from Go code and tests, and one from a whole file. The two `R-REFUND-LIMIT` code and test links are declared in YAML (`code` and `tests`); the two `PAY-123` links come from tags, so an Analyzer reports them with origin `tagged`. `check --base` against the commit before a change lists every definition whose text the change altered, with the items each one serves and their text, the items and links the change adds or removes, and the tests to run (Annex D.3); `context` and `check --base` give each link they show the last commits that changed its two sides (Annex F.3). None of it fails `check`: the pull request that shows a changed definition beside its items is where someone says whether they still match.

- Change the body of `CheckRefundLimit` and `check --base` lists `refund.go#CheckRefundLimit` with `R-REFUND-LIMIT`, which controls `RISK-REFUND-ABUSE`, and `refund_test.go#TestRefundLimit` as the test to run.
- Refresh the Jira item's copy to a new `revision` with different `text`, and `PAY-123` is listed as a changed item with the test that verifies it (OSTF-113).
- Change any byte of `deploy/database.tf`, a comment included, and it is listed as a changed file with `R-DATA-AT-REST`: without an annex, the text of the whole file is what changes.
- `V-ENCRYPTION-REVIEW` names no test, so no tool can run it; whether the review happened is evidence kept outside OSTF (Annex J).
- Remove the receipts map initialization from `NewService` and `check --base` lists `charge.go#NewService` with no item: `Service.Charge`, which `PAY-123` traces, did not change. Finding that `TestChargeRetry` must run is a dependency analysis a tool performs on top of the format (OSTF-100).

## Expected outputs

[expected/](expected/) holds what a tool that claims the command profile (Annex F) returns for this tree: [check.json](expected/check.json) for `check --format json`, and [context.json](expected/context.json) and [context.txt](expected/context.txt) for `context refund.go#CheckRefundLimit` in both formats. The outputs follow the specification text and the result schema; the [0.3 reader](../conformance/README.md) reproduces every file byte for byte. Their corroborations are Annex E's: a tool that does not implement that annex reads no `trace.derived` and gives the same outputs without them, so this tree is also the annex's worked example.

## Status

The [0.3 reader](../conformance/README.md) reads this tree directly and reproduces [expected/](expected/) byte for byte. zztrace's second reader, written separately on Go's own parser, agrees with it on every result and rendering of this tree.
