<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Phase 1 replay under candidate defaults

Pre-work item 1 of Phase 2 in the [agent-first plan](../plan-agent-first.md), section 7: the suspect queue of the [Phase 1 replay](baseline.md#replay-of-real-repositories) and its precision, recomputed under the candidate defaults from which Phase 3 sets its own. Nothing ran again and no link was labelled again (rule 8): the counts come from the Phase 1 index and labels, through `defaults.py collect`, into [results/phase1/replay-defaults.json](results/phase1/replay-defaults.json), and this report from `defaults.py report`. Both check first that the counts give back the published Phase 1 numbers.

## What the records allow

- **Reasons.** Wire 0.4 splits `SIGNATURE_CHANGED` (plan, section 7): a change to a whole-file anchor becomes `FILE_CHANGED`, and to a definition without a body, whose `sig` and `body` token streams Annexes A, K and L make identical, `DEFINITION_CHANGED`. The index keeps both fingerprints of every suspect link, so the split is exact.
- **Risk.** No backfilled item controls a risk, so here `bodyChange: risk` counts no body change and a reason quieted to `risk` counts nothing. The table shows what each default removes from a queue without risk-relevant links; what it keeps on risk-relevant code is not measured.
- **Tested code.** A code link is on tested code when its item has a test link that is not broken in the same view. The records hold no test result and no coverage, so the exemption assumes that each such test ran, reached the code and passed: it bounds what Annex M would exempt from above. py-repo's backfill linked no test, so the exemption changes nothing there.
- **Precision.** Labelled links are pooled across the three repositories as in `baseline.md`, so each repository weighs by its sample of 100, not by its queue. 95 % Wilson intervals in parentheses. A link Phase 1 did not label is counted in the queue and not in its precision.

## Precision by reason

Each suspect link of the replay, by the reason 0.4 would report and the kind of link. Mismatch: after the change the item no longer holds of the code, or the link needs an update. Relevant: the change touched the stated behavior and the statement still held.

| Reason in 0.4 | Link | Suspect links | Labelled | Mismatch | Mismatch or relevant | Mismatch per repository, go-repo, py-repo, ts-repo |
| --- | --- | --- | --- | --- | --- | --- |
| `BODY_CHANGED` | code, tested | 875 | 57 | 3/57 (5 %, 2 to 14) | 26/57 (46 %) | 2/35, 0/0, 1/22 |
| `BODY_CHANGED` | code, untested | 710 | 108 | 15/108 (14 %, 9 to 22) | 47/108 (44 %) | 1/14, 13/86, 1/8 |
| `BODY_CHANGED` | test | 320 | 39 | 0/39 (0 %, 0 to 9) | 10/39 (26 %) | 0/28, 0/0, 0/11 |
| `SIGNATURE_CHANGED` | code, tested | 148 | 7 | 0/7 (0 %, 0 to 35) | 4/7 (57 %) | 0/2, 0/0, 0/5 |
| `SIGNATURE_CHANGED` | code, untested | 71 | 5 | 0/5 (0 %, 0 to 43) | 3/5 (60 %) | 0/1, 0/2, 0/2 |
| `DEFINITION_CHANGED` | code, tested | 580 | 23 | 1/23 (4 %, 1 to 21) | 6/23 (26 %) | 1/1, 0/0, 0/22 |
| `DEFINITION_CHANGED` | code, untested | 158 | 4 | 0/4 (0 %, 0 to 49) | 0/4 (0 %) | 0/2, 0/0, 0/2 |
| `FILE_CHANGED` | code, tested | 56 | 14 | 0/14 (0 %, 0 to 22) | 10/14 (71 %) | 0/14, 0/0, 0/0 |
| `FILE_CHANGED` | code, untested | 53 | 15 | 0/15 (0 %, 0 to 20) | 4/15 (27 %) | 0/3, 0/12, 0/0 |
| `FILE_CHANGED` | test | 781 | 28 | 0/28 (0 %, 0 to 12) | 4/28 (14 %) | 0/0, 0/0, 0/28 |

## Candidate defaults

The queue under each combination of the three candidates of the pre-work, beside 0.3 as published. Per 100 merged changes is the Hand stamps row of the scorecard, the stamps the queue asks for; labelled mismatches left out are those of the 19 that the default removes from the queue.

| Defaults | Suspect links | Per 100 merged changes, go-repo, py-repo, ts-repo | Labelled | Mismatch | Mismatch or relevant | Labelled mismatches left out |
| --- | --- | --- | --- | --- | --- | --- |
| 0.3 as published, `bodyChange: all` | 3752 | 511, 119, 87 | 300 | 19/300 (6 %, 4 to 10) | 114/300 (38 %) | 0 |
| Whole files and bodyless definitions quieted | 2124 | 430, 107, 41 | 216 | 18/216 (8 %, 5 to 13) | 90/216 (42 %) | 1 |
| `bodyChange: risk` | 1847 | 120, 16, 51 | 96 | 1/96 (1 %, 0 to 6) | 31/96 (32 %) | 18 |
| Tested code exempt | 2093 | 244, 119, 45 | 199 | 15/199 (8 %, 5 to 12) | 68/199 (34 %) | 4 |
| Whole files and bodyless definitions quieted; `bodyChange: risk` | 219 | 39, 4, 5 | 12 | 0/12 (0 %, 0 to 24) | 7/12 (58 %) | 19 |
| Whole files and bodyless definitions quieted; tested code exempt | 1101 | 215, 107, 17 | 152 | 15/152 (10 %, 6 to 16) | 60/152 (39 %) | 4 |
| `bodyChange: risk`; tested code exempt | 1063 | 36, 16, 30 | 52 | 0/52 (0 %, 0 to 7) | 11/52 (21 %) | 19 |
| Whole files and bodyless definitions quieted; `bodyChange: risk`; tested code exempt | 71 | 7, 4, 2 | 5 | 0/5 (0 %, 0 to 43) | 3/5 (60 %) | 19 |

## Link churn

The scorecard's Link churn row, added after Phase 1, counts links broken by a merged change and neither re-anchored nor retired in it. In the replay no item changed, so no broken link was ever re-anchored, and its Phase 1 value is every link newly broken, per 100 merged changes: go-repo 54 (61 in 112), py-repo 9 (25 in 291), ts-repo 17 (548 in 3259).
