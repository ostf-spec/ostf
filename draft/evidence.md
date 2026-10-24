<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Evidence references: design proposal

Status: exploratory optional module outside OSTF Core 0.2 and every current conformance claim. Core can name tests, logs and OpenTelemetry traces and check link freshness; those references do not say that a test ran or passed. This proposal addresses portable, baseline-bound execution evidence. It does not standardize CI behavior, approval or release authority.

## Interchange problem

A second tool should be able to discover which run observed a named test on a particular source and trace baseline, locate its retained log and check that the retrieved artifact matches the recorded digest. A changing build URL or a green badge does not identify the evidence used for a reviewed change.

## Candidate data contract

| Data | Interoperability purpose |
| --- | --- |
| Run identity, producer and production time | Distinguish one execution from another and identify the reporting tool |
| Repository and exact source-tree identity | Bind observations to a commit or equivalent immutable source view, not to a moving branch name |
| OSTF file and lock identity | Show which graph and recheck stamps the run evaluated |
| Runner test identity and outcome | Distinguish passed, failed, skipped and not-run observations for the named test |
| Environment identity | Record the material runner, configuration and dependency baseline needed to interpret the result |
| Artifact reference, digest and media type | Locate a retained log or report and check its bytes after retrieval |
| Access and retention information | Tell a consumer whether evidence can be retrieved and how long it is expected to remain available |

An evidence digest checks bytes, not the producer's identity or the quality of a test oracle. A passing result does not make an OSTF link valid, and a valid link does not establish a passing result. Reviewer decisions and signatures would need their own separately specified records or tool controls.

## Decisions before a schema and conformance cases

1. Choose the record identity and module version independently of Core's `ostf: "0.2"` wire version.
2. Define source-view and trace-input digests so producers using Git SHA-1, Git SHA-256 or a materialized tree can report equivalent evidence without ambiguity.
3. Define outcome vocabulary and aggregation for retries, parameterized tests and partially executed suites.
4. Define which artifact digests are required, how restricted URLs are represented, and what an offline consumer can validate.
5. Add fixed positive and negative vectors for wrong source revision, altered log bytes, skipped tests, missing artifacts and conflicting run identities.

The synthetic [change workflow](../examples/change-impact.md) supplies a candidate pilot. A schema and executable conformance cases should follow the decisions above, rather than presenting a structural placeholder as working evidence support.
