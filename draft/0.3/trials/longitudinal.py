#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The longitudinal replay of the agent-first plan's Phase 5 (section 10), on document revision 0.16:
a synthetic six-month history on each fixture, with agents making the changes.

    python3 longitudinal.py run [--fixtures go-shop,ts-shop] [--arms full,none] [--agents claude,codex] [--months 6] [--jobs 6] [--cap USD]

phase5/longitudinal.json freezes the history: six changes a month, each a prompt a user would type.
Each month's changes start on branches of the month's first commit, the agents alternating by
change, and merge into main in the order listed; a conflicting merge is aborted and counted, and
the next one merges without it. After each clean merge the replay counts the links that the merge
broke and left broken, the Link churn row of plan section 2, and the items that `check --base`
lists for the change; in the none arm it counts instead the references of REQUIREMENTS.md that the
merge left stale. In the full arm the judge labels, for each item listed, whether the agent's
summary says the change keeps it true and whether, from the diff, it still holds, for the precision
of those claims. Results go to RESULTS/longitudinal-FIXTURE-ARM.json.
"""
import argparse
import collections
import concurrent.futures
import datetime
import json
import pathlib
import shutil
import subprocess
import sys

import harness

HISTORY = json.loads((harness.PHASE5 / "longitudinal.json").read_text())


def graph(repo, arm):
    """What the replay compares across a merge: the broken links and invented IDs (trace.yaml), or
    the stale references of REQUIREMENTS.md."""
    if arm in harness.RECORD_ARMS:
        _, result = harness.reader_json(repo, "check")
        result = result or {"diagnostics": [], "items": [], "links": []}
        # One diagnostic per broken link, so a source that breaks two links counts twice.
        broken = collections.Counter(d.get("subject") for d in result["diagnostics"] if d["code"] == "BROKEN_LINK")
        invented = collections.Counter(d.get("subject") for d in result["diagnostics"] if d["code"] in ("UNKNOWN_TARGET", "TAG_UNKNOWN_ID"))
        return {"broken": broken, "invented": invented, "result": result}
    text = (repo / "REQUIREMENTS.md").read_text() if (repo / "REQUIREMENTS.md").exists() else ""
    stale = collections.Counter(f"{i} {p}#{s or ''}" for i, p, s in harness.manifest_refs(text) if not harness.resolves(repo, p, s))
    return {"broken": stale, "invented": collections.Counter(), "result": None}


def label(change, prompt, summary, diff, listed, texts, log):
    """The judge's labels of one summary's claims (judge.json, longitudinal)."""
    questions = []
    for ident in listed:
        values = {"id": ident, "title": texts.get(ident, {}).get("title") or ident, "text": texts.get(ident, {}).get("text", "")}
        questions += [(key.format(**values), q.format(**values)) for key, q in harness.JUDGE["questions"]["longitudinal"].items()]
    labels = harness.JUDGE["material"]
    if len(diff) > harness.JUDGE["diffLimit"]:
        diff = diff[:harness.JUDGE["diffLimit"]] + f"\n[diff cut at {harness.JUDGE['diffLimit']} characters]"
    material = [(labels["request"], prompt), (labels["summary"], summary), (labels["diff"], diff or "(no change)"),
                (labels["items"], "\n".join(f"{i}: {texts.get(i, {}).get('text', '')}" for i in listed))]
    return harness.ask_judge(material, questions, log)


def run(fixture, arm, agents, months, jobs):
    name = f"longitudinal-{fixture}-{arm}"
    target = harness.RESULTS / f"{name}.json"
    if target.exists():
        return json.loads(target.read_text())
    work = harness.WORK / name
    shutil.rmtree(work, ignore_errors=True)
    repo, _ = harness.prepare(work / "main", fixture, {}, arm)
    shutil.rmtree(work / "main" / "bin")
    history = [c for c in HISTORY["history"][fixture] if c["month"] <= months]
    records = []
    for month in range(1, months + 1):
        harness.check_cap()
        changes = [c for c in history if c["month"] == month]
        context = {"task": None, "task_id": None, "arm": arm, "fixture": fixture}
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
            runs = list(pool.map(lambda c: harness.branch_run(agents[(int(c["id"].split(".")[1]) - 1) % len(agents)], repo, work / c["id"],
                                                              c["prompt"], f"m{c['id'].replace('.', '-')}", {**context, "change": c["id"]}),
                                 changes))
        for change, branch in zip(changes, runs):
            before_sha = harness.git(repo, "rev-parse", "HEAD").stdout.strip()
            before = graph(repo, arm)
            done = harness.git(repo, "merge", "--no-ff", "-q", "-m", f"Merge {change['id']}", branch["branch"], check=False)
            entry = {**change, "agent": branch["agent"], "model": branch["model"], "cost": branch["cost"], "timing": branch["timing"],
                     "derivedHandEdits": branch["metrics"]["derivedHandEdits"], "summary": branch["finalMessage"],
                     "changedFiles": branch["changedFiles"]}
            if done.returncode:
                entry["conflict"] = harness.git(repo, "diff", "--name-only", "--diff-filter=U").stdout.split() or ["(merge failed)"]
                harness.git(repo, "merge", "--abort", check=False)
                entry["merged"] = False
                records.append(entry)
                continue
            after = graph(repo, arm)
            state = harness.merge_state(repo, arm)
            diff = harness.git(repo, "diff", before_sha, "HEAD").stdout
            entry.update({"merged": True, "conflict": [], "newlyBroken": sorted((after["broken"] - before["broken"]).elements()),
                          "inventedIds": sorted((after["invented"] - before["invented"]).elements()), "check": state["check"], "testsPass": state["testsPass"],
                          "derivedChanged": "trace.derived" in harness.git(repo, "diff", "--name-only", before_sha, "HEAD").stdout.split()})
            if arm in harness.RECORD_ARMS:
                impact = (harness.reader_json(repo, "check", "--base", before_sha)[1] or {}).get("impact") or {}
                listed = sorted({i for c in impact.get("changed", []) for i in c["items"]} | set(impact.get("items", {}).get("added", []))
                                | set(impact.get("items", {}).get("changed", [])))
                entry["listedItems"] = listed
                entry["listedTests"] = impact.get("tests", [])
                if arm == "full" and listed:
                    items, _ = harness.fixture_items(repo)
                    texts = {i["id"]: {"title": i.get("title"), "text": " ".join(i.get("text", "").split())} for i in items}
                    verdict = label(change["id"], change["prompt"], branch["finalMessage"], diff, listed, texts, work / change["id"] / "judge.json")
                    entry["labels"] = verdict["answers"]
                    entry["judgeCost"] = verdict.get("cost")
            records.append(entry)
    merged = [r for r in records if r["merged"]]
    claims = [(r, i) for r in merged for i in r.get("listedItems", []) if r.get("labels", {}).get(f"claim:{i}") is True]
    out = {"fixture": fixture, "arm": arm, "agents": agents, "months": months, "date": datetime.date.today().isoformat(), "changes": records,
           "merged": len(merged), "conflicts": len(records) - len(merged),
           "linksBroken": sum(len(r["newlyBroken"]) for r in merged),
           "brokenPer100": round(100 * sum(len(r["newlyBroken"]) for r in merged) / len(merged), 1) if merged else None,
           "byMonth": [{"month": m, "merged": sum(1 for r in merged if r["month"] == m),
                        "conflicts": sum(1 for r in records if r["month"] == m and not r["merged"]),
                        "linksBroken": sum(len(r["newlyBroken"]) for r in merged if r["month"] == m),
                        "itemsListed": sum(len(r.get("listedItems", [])) for r in merged if r["month"] == m)} for m in range(1, months + 1)],
           "claimsHold": sum(1 for r, i in claims if r["labels"].get(f"holds:{i}") is True), "claims": len(claims),
           "inventedIds": sum(len(r["inventedIds"]) for r in merged),
           "derivedHandEdits": sum(1 for r in records if r["derivedHandEdits"] or r.get("derivedChanged")),
           "cost": round(sum(r["cost"] for r in records) + sum(r.get("judgeCost") or 0 for r in records), 6)}
    harness.RESULTS.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    return out


def main(argv=None):
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    go = commands.add_parser("run")
    go.add_argument("--fixtures", default="go-shop,ts-shop")
    go.add_argument("--arms", default="full,none")
    go.add_argument("--agents", default="claude,codex")
    go.add_argument("--months", type=int, default=HISTORY["months"])
    go.add_argument("--jobs", type=int, default=HISTORY["changesPerMonth"])
    go.add_argument("--cap", type=float, default=None)
    args = parser.parse_args(argv)
    if subprocess.run([sys.executable, str(harness.READER), "--help"], capture_output=True).returncode:
        sys.exit(f"{sys.executable} cannot run {harness.READER}; run the replay with the trial venv's python")
    if args.cap is not None:
        harness.CAP = args.cap
    agents = args.agents.split(",")
    if "fake" not in agents and harness.JUDGE_MODE == "model" and not harness.CAP:
        sys.exit("a scored replay needs a cap: --cap USD or OSTF_TRIALS_CAP_USD (phase5.md, Budget)")
    for fixture in args.fixtures.split(","):
        for arm in args.arms.split(","):
            try:
                out = run(fixture, arm, agents, args.months, args.jobs)
                print(f"{fixture} {arm}: {out['merged']} merged, {out['conflicts']} conflicts, {out['linksBroken']} links broken "
                      f"({out['brokenPer100']} per 100), claims holding {out['claimsHold']}/{out['claims']}", flush=True)
            except harness.Capped as error:
                print(f"CAPPED {fixture} {arm}: {error}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
