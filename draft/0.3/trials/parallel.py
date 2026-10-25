#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The parallel-agent fixture of the agent-first plan's Phase 1 (section 6): ten agents on ten
branches of the Go fixture, each refactoring one linked function and restamping its links, then
the branches merged into main in sequence.

    python3 parallel.py run --roots 1|2 [--jobs 10]
    python3 parallel.py layout --roots 1|2 DIR
    python3 parallel.py selftest

With --roots 2 the same code is split into two roots: the top-level root and a nested root in
inventory/ (OSTF-102). Each run counts the merges that conflict, and the clean merges after which
`check` fails in a root. Results go to results/phase1/parallel-ROOTSroot.json; the agents' work
stays in the work directory.
"""
import argparse
import concurrent.futures
import datetime
import json
import os
import pathlib
import shutil
import subprocess
import sys

import harness

NESTED = "inventory"
# The ten functions, one per agent: five beneath the nested root of the split layout and five
# outside it, none of them risk-relevant, so that the paragraph lets each agent go ahead.
FUNCTIONS = [
    "inventory/inventory.go#Stock.Reserve", "cart/cart.go#Cart.Add", "inventory/inventory.go#Stock.Release",
    "pricing/discount.go#ApplyDiscount", "inventory/inventory.go#Stock.Confirm", "pricing/tax.go#Tax",
    "inventory/inventory.go#Stock.Available", "cart/cart.go#Cart.Subtotal", "inventory/inventory.go#NewStock",
    "accounts/session.go#Sessions.Register",
]
PROMPT = "Refactor {symbol} in {path} so that it is easier to read, without changing what it does. Keep the tests passing."
RESULTS = harness.HERE / "results" / "phase1"
GIT = harness.GIT


def git(repo, *args, check=True):
    return subprocess.run(GIT + ["-C", str(repo), *args], capture_output=True, text=True, check=check)


def reader(root, *args):
    return subprocess.run([sys.executable, str(harness.READER), *args], cwd=root, capture_output=True, text=True)


def roots(repo):
    return sorted(p.parent for p in repo.rglob("trace.yaml") if ".cache" not in p.parts)


def stamp_all(root):
    """Stamp every link of a root, as a first adoption would, and return the check exit code."""
    (root / "trace.lock").unlink(missing_ok=True)
    result = json.loads(reader(root, "check", "--format", "json").stdout)
    names = [f"{l['source']} {l['type']} {l['target']}" for l in result["links"]]
    done = reader(root, "stamp", *names)
    if done.returncode:
        raise RuntimeError(f"stamp failed in {root}: {done.stdout}{done.stderr}")
    return reader(root, "check").returncode


def split(repo):
    """The fixture as two roots. A link goes to the root that covers its anchor, and each root holds
    the items its links name with the items they refine, control or verify, so an item linked from
    both roots is written in both; 0.3 has no link between roots."""
    import yaml
    items, top = harness.fixture_items(repo)
    by_id = {i["id"]: i for i in items}
    links = json.loads(reader(repo, "check", "--format", "json").stdout)["links"]
    prefix = NESTED + "/"
    named = {"top": set(), "nested": set()}
    for link in links:
        if link["source"] not in by_id:
            named["nested" if link["source"].startswith(prefix) else "top"].add(link["target"])
    unanchored = set(by_id) - named["top"] - named["nested"]

    def closure(ids):
        ids, grown = set(ids), True
        while grown:
            more = {t for i in ids for field in ("refines", "controls", "verifies") for t in by_id[i].get(field, [])}
            grown = not more <= ids
            ids |= more
        return ids

    members = {"top": closure(named["top"] | unanchored), "nested": closure(named["nested"])}
    for side, directory in (("top", repo), ("nested", repo / NESTED)):
        written = []
        for item in items:
            if item["id"] not in members[side]:
                continue
            item = dict(item)
            for field in ("code", "tests"):
                kept = [a for a in item.get(field, []) if a.startswith(prefix) == (side == "nested")]
                kept = [a[len(prefix):] for a in kept] if side == "nested" else kept
                if kept:
                    item[field] = kept
                else:
                    item.pop(field, None)
            written.append(item)
        document = {"ostf": "0.3"}
        if any(i.get("external") for i in written):
            document["sources"] = top["sources"]
        document["items"] = written
        (directory / "trace.yaml").write_text(yaml.safe_dump(document, sort_keys=False, width=1000, allow_unicode=True))
    shutil.rmtree(repo / "trace")
    for root in roots(repo):
        if stamp_all(root):
            raise RuntimeError(f"check fails in {root} after the split")


def layout(directory, count):
    shutil.copytree(harness.FIXTURES / "go-shop", directory)
    if count == 2:
        split(directory)


def run_agent(n, base, work):
    """One agent on its own clone and branch; its committed work is pushed back as branch agent-N."""
    agent = "claude" if n % 2 == 0 else "codex"
    path, _, symbol = FUNCTIONS[n].partition("#")
    run_dir = work / f"agent-{n + 1:02d}"
    shutil.rmtree(run_dir, ignore_errors=True)
    run_dir.mkdir(parents=True)
    repo = run_dir / "repo"
    subprocess.run(["git", "clone", "-q", str(base), str(repo)], check=True)
    (repo / ".git" / "info" / "exclude").write_text(".cache/\n")
    bin_dir = run_dir / "bin"
    bin_dir.mkdir()
    (bin_dir / "ostf").symlink_to(harness.TOOLS["python"])
    timing = harness.AGENTS[agent](repo, bin_dir, PROMPT.format(symbol=symbol, path=path), False, run_dir / "transcript.jsonl")
    found, final, _, usage = harness.calls(agent, run_dir / "transcript.jsonl")
    m = harness.metrics(found)
    checks = {str(r.relative_to(repo)): reader(r, "check").returncode for r in roots(repo)}
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", f"Agent {n + 1}: refactor {symbol}", check=False)
    git(repo, "push", "-q", "origin", f"HEAD:refs/heads/agent-{n + 1:02d}")
    changed = git(repo, "diff", "--name-only", "origin/main", "HEAD").stdout.split()
    return {"agent": agent, "model": harness.CLAUDE_MODEL if agent == "claude" else harness.CODEX_MODEL, "function": FUNCTIONS[n],
            "branch": f"agent-{n + 1:02d}", "timing": timing, "checks": checks, "changedFiles": changed,
            "stampCalls": m["stampCalls"], "lockHandEdits": m["lockHandEdits"], "usage": usage, "finalMessage": final[-2000:]}


def merge_all(base, agents):
    """Merge the branches into main in agent order. A conflicting merge is aborted and counted, and
    the next branch merges onto main without it; after a clean merge every root is checked."""
    merges = []
    for record in agents:
        done = git(base, "merge", "--no-ff", "-q", "-m", f"Merge {record['branch']}", record["branch"], check=False)
        if done.returncode:
            conflicted = git(base, "diff", "--name-only", "--diff-filter=U").stdout.split()
            git(base, "merge", "--abort", check=False)
            merges.append({"branch": record["branch"], "conflict": conflicted})
            continue
        checks = {str(r.relative_to(base)): reader(r, "check").returncode for r in roots(base)}
        tests = subprocess.run(["go", "test", "./..."], cwd=base, capture_output=True, text=True,
                               env=harness.environment(base, base)).returncode == 0
        merges.append({"branch": record["branch"], "conflict": [], "checks": checks, "testsPass": tests})
    return merges


def run(count, jobs):
    work = harness.WORK.parent / f"parallel-{count}root"
    shutil.rmtree(work, ignore_errors=True)
    base = work / "main"
    layout(base, count)
    subprocess.run(["git", "init", "-q", "-b", "main", str(base)], check=True)
    (base / ".git" / "info" / "exclude").write_text(".cache/\n")
    git(base, "add", "-A")
    git(base, "commit", "-q", "-m", "Shop at main")
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        agents = list(pool.map(lambda n: run_agent(n, base, work), range(len(FUNCTIONS))))
    merges = merge_all(base, agents)
    record = {"roots": count, "date": datetime.date.today().isoformat(), "agents": agents, "merges": merges,
              "conflicts": sum(1 for m in merges if m["conflict"]),
              "lockConflicts": sum(1 for m in merges if any(f.endswith("trace.lock") for f in m["conflict"])),
              "redMerges": sum(1 for m in merges if not m["conflict"] and any(m["checks"].values()))}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"parallel-{count}root.json").write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n")
    print(f"{count} root(s): {record['conflicts']} conflicting merges ({record['lockConflicts']} in trace.lock), "
          f"{record['redMerges']} clean merges with a failing check, of {len(merges)}")


def selftest():
    """Both layouts check clean with every link valid, the split keeps every link and adds none
    but the copies of items that both roots link, and every function exists and is linked."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        one, two = pathlib.Path(tmp) / "one", pathlib.Path(tmp) / "two"
        layout(one, 1)
        layout(two, 2)
        links = {}
        for directory in (one, two):
            found = set()
            for root in roots(directory):
                result = json.loads(reader(root, "check", "--format", "json").stdout)
                assert all(l["state"] == "valid" for l in result["links"]), root
                assert not [d for d in result["diagnostics"] if d["severity"] != "info"], (root, result["diagnostics"])
                prefix = "" if root == directory else str(root.relative_to(directory)) + "/"
                found |= {(prefix + l["source"] if "#" in l["source"] or "/" in l["source"] or l["source"].endswith(".go") else l["source"],
                           l["type"], l["target"]) for l in result["links"]}
            links[directory] = found
        assert links[one] <= links[two], sorted(links[one] - links[two])
        assert [r.relative_to(two) for r in roots(two)] == [pathlib.Path("."), pathlib.Path(NESTED)]
        for function in FUNCTIONS:
            assert any(l[0] == function for l in links[one]), function
    print("parallel selftest passed")


def main(argv=None):
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    go = commands.add_parser("run")
    go.add_argument("--roots", type=int, choices=(1, 2), required=True)
    go.add_argument("--jobs", type=int, default=10)
    show = commands.add_parser("layout")
    show.add_argument("--roots", type=int, choices=(1, 2), required=True)
    show.add_argument("dir", type=pathlib.Path)
    commands.add_parser("selftest")
    args = parser.parse_args(argv)
    if args.command == "selftest":
        selftest()
    elif args.command == "layout":
        layout(args.dir, args.roots)
    else:
        run(args.roots, args.jobs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
