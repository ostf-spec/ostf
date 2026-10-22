<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Contributing to OSTF

OSTF is a review draft. Open an issue for an ambiguity, incompatible interpretation, missing conformance case or proposed extension. When reporting a reader disagreement, include the smallest `trace.yaml` or `trace.lock` example, the expected result and the tool versions.

For a pull request that changes a requirement or annex rule, update the affected schemas and fixed conformance cases, and describe any wire compatibility impact. Requirement IDs are permanent: retire an ID rather than reusing it. Run `python3 conformance/run.py` before submitting. The standalone runner covers its declared Python subset; schema and complete Core checks still need separate implementation review.

Prose contributions are submitted under CC BY 4.0. Schema, grammar, fixture and tool contributions are submitted under Apache 2.0, as described in [LICENSE.md](LICENSE.md). Keep third-party quotations short and identify their sources. A merged change does not by itself certify an implementation or advance the wire version.
