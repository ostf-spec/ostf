#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The replay of the replay (agent-first plan, section 7, pre-work item 1): the suspect queue of
the Phase 1 replay and its precision per reason under candidate defaults, recomputed from the
Phase 1 index and labels alone. No agent runs and no link is labelled again (plan, rule 8).

    python3 defaults.py collect
    python3 defaults.py report

`collect` reads each repository's index in OSTF_REPLAY_DATA and writes
results/phase1/replay-defaults.json, counts only, as replay.py's `publish` does; `report` writes
baseline-defaults.md from it. Both check first that the counts give back the Phase 1 numbers in
results/phase1/replay-summary.json.
"""
import collections
import itertools
import json
import sqlite3
import sys

import baseline
import harness
import replay

COUNTS = baseline.PHASE1 / "replay-defaults.json"
OUT = harness.HERE / "baseline-defaults.md"
# The reasons of wire 0.4 (plan, section 7): a whole-file anchor's change is FILE_CHANGED and a
# definition without a body, whose sig and body token streams Annexes A, K and L make identical,
# DEFINITION_CHANGED; SIGNATURE_CHANGED is kept for a signature.
REASONS = ("BODY_CHANGED", "SIGNATURE_CHANGED", "DEFINITION_CHANGED", "FILE_CHANGED")
LINKS = ("code, tested", "code, untested", "test")
# The candidates of the pre-work, each a test of whether a cell still counts. No backfilled item
# controls a risk, so `risk` counts no body change, and a reason quieted to `risk` counts nothing.
CANDIDATES = {
    "quiet": ("whole files and bodyless definitions quieted", lambda c: c["reason"] not in ("FILE_CHANGED", "DEFINITION_CHANGED")),
    "risk": ("`bodyChange: risk`", lambda c: c["reason"] != "BODY_CHANGED"),
    "tested": ("tested code exempt", lambda c: c["link"] != "code, tested"),
}


def cells(name):
    """The suspect links of one repository, counted by 0.3 reason, 0.4 reason and kind of link,
    with their labels. A code link is on tested code when its item has a test link that is not
    broken in the same view; the records hold no test result, so nothing says the test passed."""
    db = sqlite3.connect(f"file:{replay.DATA / name / 'index.sqlite'}?mode=ro", uri=True)
    rows = db.execute("select root, view, link, source, type, target, reasons from suspects where repository=? and state='suspect'",
                      (name,)).fetchall()
    keys = {(root, view, link) for root, view, link, *_ in rows}
    views = {(root, view) for root, view, *_ in rows}
    fingerprints = {(root, view, link): json.loads(value) for root, view, link, value in
                    db.execute("select root, view, link, fingerprints from lock_entries where repository=?", (name,))
                    if (root, view, link) in keys}
    verdicts = {(root, view, link): verdict for root, view, link, verdict in
                db.execute("select root, view, link, verdict from labels where repository=?", (name,))}
    items = collections.defaultdict(set)
    for root, view, ident in db.execute("select root, view, id from items where repository=?", (name,)):
        if (root, view) in views:
            items[(root, view)].add(ident)
    tested = collections.defaultdict(set)
    for root, view, source, target, state in db.execute("select root, view, source, target, state from links where repository=? "
                                                        "and type='verifies'", (name,)):
        if (root, view) in views and state != "broken" and source not in items[(root, view)]:
            tested[(root, view)].add(target)
    counted = collections.Counter()
    for root, view, link, source, kind, target, was in rows:
        current = fingerprints[(root, view, link)]
        if "#" not in source:
            reason = "FILE_CHANGED"
        elif current.get("source.sig") == current.get("source.body"):
            reason = "DEFINITION_CHANGED"
        else:
            reason = was
        if kind == "verifies":
            what = "test"
        elif kind == "implements":
            what = "code, tested" if target in tested[(root, view)] else "code, untested"
        else:
            raise SystemExit(f"{name}: a suspect {kind} link, which a replay whose items never change cannot have")
        counted[(was, reason, what, verdicts.get((root, view, link)))] += 1
    out = {}
    for (was, reason, what, verdict), n in counted.items():
        cell = out.setdefault((was, reason, what), {"was": was, "reason": reason, "link": what, "suspect": 0, "labelled": 0,
                                                    "mismatch": 0, "relevant": 0, "noise": 0})
        cell["suspect"] += n
        if verdict:
            cell["labelled"] += n
            cell[verdict] += n
    return [out[k] for k in sorted(out, key=lambda k: (REASONS.index(k[1]), LINKS.index(k[2]), k[0]))]


def verify(counts):
    """The counts give back what Phase 1 published: the suspect links and the labelled mismatches
    per reason, and the whole-file anchors, in replay-summary.json; and no body change on a source
    without a body, which OSTF-144 rules out."""
    summary = {r["name"]: r for r in baseline.load("replay-summary.json")["repositories"]}
    for repo in counts["repositories"]:
        published = summary[repo["name"]]
        for was in published["suspect"]:
            mine = [c for c in repo["cells"] if c["was"] == was]
            got = {"suspect": sum(c["suspect"] for c in mine),
                   "precision": [sum(c["mismatch"] for c in mine), sum(c["labelled"] for c in mine)],
                   "whole file": sum(c["suspect"] for c in mine if c["reason"] == "FILE_CHANGED")}
            want = {"suspect": published["suspect"][was], "precision": published["precision"].get(was, [0, 0]),
                    "whole file": published["kinds"].get(was, {}).get("whole file", 0)}
            if got != want:
                raise SystemExit(f"{repo['name']} {was}: {got} where Phase 1 published {want}")
        if any(c["was"] == "BODY_CHANGED" and c["reason"] != "BODY_CHANGED" for c in repo["cells"]):
            raise SystemExit(f"{repo['name']}: a body change on a source without a body")


def collect():
    summary = {r["name"]: r for r in baseline.load("replay-summary.json")["repositories"]}
    counts = {"repositories": [{"name": name, "changes": summary[name]["changes"], "broken": summary[name]["broken"], "cells": cells(name)}
                               for name in replay.REPOS if name in summary]}
    verify(counts)
    COUNTS.write_text(json.dumps(counts, indent=1) + "\n")
    print(f"wrote {COUNTS}")


def queue(repo, chosen):
    return [c for c in repo["cells"] if all(CANDIDATES[k][1](c) for k in chosen)]


def total(rows, field):
    return sum(c[field] for c in rows)


def report():
    counts = json.loads(COUNTS.read_text())
    verify(counts)
    repos = counts["repositories"]
    every = [c for r in repos for c in r["cells"]]
    names = ", ".join(r["name"] for r in repos)
    lines = ["<!-- SPDX-License-Identifier: CC-BY-4.0 -->", "# Phase 1 replay under candidate defaults", "",
             "Pre-work item 1 of Phase 2 in the [agent-first plan](../plan-agent-first.md), section 7: the suspect queue of the "
             "[Phase 1 replay](baseline.md#replay-of-real-repositories) and its precision, recomputed under the candidate defaults "
             "from which Phase 3 sets its own. Nothing ran again and no link was labelled again (rule 8): the counts come from the "
             "Phase 1 index and labels, through `defaults.py collect`, into [results/phase1/replay-defaults.json]"
             "(results/phase1/replay-defaults.json), and this report from `defaults.py report`. Both check first that the counts give "
             "back the published Phase 1 numbers.", "",
             "## What the records allow", "",
             "- **Reasons.** Wire 0.4 splits `SIGNATURE_CHANGED` (plan, section 7): a change to a whole-file anchor becomes "
             "`FILE_CHANGED`, and to a definition without a body, whose `sig` and `body` token streams Annexes A, K and L make "
             "identical, `DEFINITION_CHANGED`. The index keeps both fingerprints of every suspect link, so the split is exact.",
             "- **Risk.** No backfilled item controls a risk, so here `bodyChange: risk` counts no body change and a reason quieted to "
             "`risk` counts nothing. The table shows what each default removes from a queue without risk-relevant links; what it keeps "
             "on risk-relevant code is not measured.",
             "- **Tested code.** A code link is on tested code when its item has a test link that is not broken in the same view. The "
             "records hold no test result and no coverage, so the exemption assumes that each such test ran, reached the code and "
             "passed: it bounds what Annex M would exempt from above. py-repo's backfill linked no test, so the exemption changes "
             "nothing there.",
             "- **Precision.** Labelled links are pooled across the three repositories as in `baseline.md`, so each repository weighs "
             "by its sample of 100, not by its queue. 95 % Wilson intervals in parentheses. A link Phase 1 did not label is counted in "
             "the queue and not in its precision.", ""]

    lines += ["## Precision by reason", "",
              "Each suspect link of the replay, by the reason 0.4 would report and the kind of link. Mismatch: after the change the "
              "item no longer holds of the code, or the link needs an update. Relevant: the change touched the stated behavior and the "
              "statement still held.", "",
              f"| Reason in 0.4 | Link | Suspect links | Labelled | Mismatch | Mismatch or relevant | Mismatch per repository, {names} |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for reason in REASONS:
        for what in LINKS:
            group = [c for c in every if c["reason"] == reason and c["link"] == what]
            if not group:
                continue
            labelled, mismatch = total(group, "labelled"), total(group, "mismatch")
            per = ", ".join(f"{total(g, 'mismatch')}/{total(g, 'labelled')}"
                            for g in ([c for c in r["cells"] if c["reason"] == reason and c["link"] == what] for r in repos))
            lines.append(f"| `{reason}` | {what} | {total(group, 'suspect')} | {labelled} | {baseline.pct(mismatch, labelled)} | "
                         f"{baseline.pct(mismatch + total(group, 'relevant'), labelled, interval=False)} | {per} |")

    lines += ["", "## Candidate defaults", "",
              "The queue under each combination of the three candidates of the pre-work, beside 0.3 as published. Per 100 merged "
              "changes is the Hand stamps row of the scorecard, the stamps the queue asks for; labelled mismatches left out are those "
              f"of the {total(every, 'mismatch')} that the default removes from the queue.", "",
              f"| Defaults | Suspect links | Per 100 merged changes, {names} | Labelled | Mismatch | Mismatch or relevant | "
              "Labelled mismatches left out |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for size in range(len(CANDIDATES) + 1):
        for chosen in itertools.combinations(CANDIDATES, size):
            rows = [queue(r, chosen) for r in repos]
            kept = [c for group in rows for c in group]
            name = "; ".join(CANDIDATES[k][0] for k in chosen) if chosen else "0.3 as published, `bodyChange: all`"
            per = ", ".join(f"{100 * total(group, 'suspect') / r['changes']:.0f}" for r, group in zip(repos, rows))
            labelled, mismatch = total(kept, "labelled"), total(kept, "mismatch")
            lines.append(f"| {name[0].upper() + name[1:]} | {total(kept, 'suspect')} | {per} | {labelled} | "
                         f"{baseline.pct(mismatch, labelled)} | "
                         f"{baseline.pct(mismatch + total(kept, 'relevant'), labelled, interval=False)} | "
                         f"{total(every, 'mismatch') - mismatch} |")

    lines += ["", "## Link churn", "",
              "The scorecard's Link churn row, added after Phase 1, counts links broken by a merged change and neither re-anchored nor "
              "retired in it. In the replay no item changed, so no broken link was ever re-anchored, and its Phase 1 value is every "
              "link newly broken, per 100 merged changes: " +
              ", ".join(f"{r['name']} {100 * r['broken'] / r['changes']:.0f} ({r['broken']} in {r['changes']})" for r in repos) + ".", ""]
    OUT.write_text("\n".join(lines))
    print(f"wrote {OUT}")


def main(argv=None):
    command = (argv or sys.argv[1:] or ["report"])[0]
    {"collect": collect, "report": report}[command]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
