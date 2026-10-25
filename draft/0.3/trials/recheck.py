#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The Recheck lag and Guarded rows of the agent-first plan (section 2) from the full arm's runs.

    python3 recheck.py RESULTS

For every full-arm run of a task that changes code, it reads the final repository in the work
directory with `check --base` against the commit the task's setup left: a link whose source the
change touched and that is `valid` at the end was rechecked and stamped in the same change, one
that is `suspect` was not. A rechecked link to a risk-relevant item is a self-stamp, since the
agent that changed the code stamped it. The result goes to results/phase1/recheck.json.
"""
import json
import pathlib
import subprocess
import sys

import harness


def setup_commit(repo, task):
    commits = subprocess.run(["git", "-C", str(repo), "rev-list", "--reverse", "HEAD"], capture_output=True, text=True).stdout.split()
    # T8's damaged lock line is a second commit; every other task's setup is the first.
    return commits[1] if task == "T8" else commits[0]


def measure(record):
    repo = harness.WORK / record["run"] / "repo"
    base = setup_commit(repo, record["task"])
    done = subprocess.run([sys.executable, str(harness.READER), "check", "--base", base, "--format", "json"], cwd=repo,
                          capture_output=True, text=True)
    result = json.loads(done.stdout)
    changed = {c["anchor"] for c in result["impact"]["changed"]}
    risky = {i["id"] for i in result["items"] if i["riskRelevant"]}
    added = set(result["impact"]["links"]["added"])
    counts = {"touched": 0, "rechecked": 0, "leftSuspect": 0, "selfStampsRiskRelevant": 0, "newLinks": 0, "newLinksStamped": 0}
    for l in result["links"]:
        name = f"{l['source']} {l['type']} {l['target']}"
        if name in added:
            counts["newLinks"] += 1
            counts["newLinksStamped"] += l["state"] == "valid"
            continue
        if l["source"] not in changed:
            continue
        counts["touched"] += 1
        if l["state"] == "valid":
            counts["rechecked"] += 1
            counts["selfStampsRiskRelevant"] += l["target"] in risky
        elif l["state"] == "suspect":
            counts["leftSuspect"] += 1
    return counts


def main(argv=None):
    results = pathlib.Path((argv or sys.argv[1:])[0])
    runs = []
    for path in sorted(results.glob("*.json")):
        record = json.loads(path.read_text())
        if record.get("arm") != "full" or record["task"] not in ("T2", "T3", "T4", "T5", "T7", "T8"):
            continue
        if not (harness.WORK / record["run"] / "repo").exists():
            continue
        runs.append({"run": record["run"], "agent": record["agent"], "task": record["task"], **measure(record)})
    total = {k: sum(r[k] for r in runs) for k in ("touched", "rechecked", "leftSuspect", "selfStampsRiskRelevant", "newLinks", "newLinksStamped")}
    out = {"runs": runs, "total": total,
           "runsWithSelfStamp": sum(1 for r in runs if r["selfStampsRiskRelevant"])}
    (harness.HERE / "results" / "phase1" / "recheck.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({"total": total, "runsWithSelfStamp": out["runsWithSelfStamp"], "runs": len(runs)}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
