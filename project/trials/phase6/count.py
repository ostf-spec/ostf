#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Phase 6's counts for a real repository (agent-first plan, section 11), from its Git history alone.

    python3 count.py REPO [START] [--root go/ostf] [--branch main] [--reader ostf] [--as-of YYYY-MM-DD] [--name zztrace]

Each commit on the first-parent history of BRANCH after START is a merged change; those that touch
ROOT are counted, in commit order. For each, from trees that `git archive` writes outside the
checkout, so the checkout is never touched: the links the change broke and left broken, the
BROKEN_LINK diagnostics of the commit less those of its parent, one per diagnostic as Phase 5's
replay counted them; the items and tests that `check --base` lists for it against its parent, the
items of its changed definitions and those added or changed; and the item files it edited, ROOT's
trace.yaml and trace/*.yaml, every edit counting as a hand edit while no command writes them. The
gate's three criteria are reported beside the totals: months of use from START to the as-of date,
linked symbols at the head as code definitions and test anchors, and the counts this file publishes.
The reader is the installed `ostf`, the reference reader at the pin; no model or agent is called.
Writes NAME.md, a table to paste into the plan, and NAME.json beside this script.
"""
import argparse
import collections
import datetime
import io
import json
import pathlib
import subprocess
import tarfile
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
# zztrace's counts start after the merge of its pull request #2, which moved its items to working draft 0.3:
# a script rewrote every item, ID and link there, so the changes before it say nothing about real use.
START = "a983df5a299779a2418d50e63918c20cfbabe983"
GATE_MONTHS = 3
GATE_SYMBOLS = 200


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def tree(repo, sha, root, into):
    """ROOT as it is at SHA, written under INTO; an empty directory when SHA has no ROOT."""
    target = into / root
    target.mkdir(parents=True, exist_ok=True)
    done = subprocess.run(["git", "-C", str(repo), "archive", sha, root], capture_output=True)
    if done.returncode == 0:
        with tarfile.open(fileobj=io.BytesIO(done.stdout)) as archive:
            archive.extractall(into, filter="data")
    return target


def check(reader, root, *args):
    done = subprocess.run([reader, "check", "--root", str(root), "--format", "json", *args], capture_output=True, text=True)
    if done.returncode == 2:
        raise SystemExit(f"{reader} check could not run on {root}: {done.stderr.strip()}")
    return json.loads(done.stdout)


def broken(result):
    return collections.Counter(d.get("subject") for d in result["diagnostics"] if d["code"] == "BROKEN_LINK")


def reader_pin(reader):
    """The package the installed reader came from, as pipx recorded it."""
    try:
        venvs = json.loads(subprocess.run(["pipx", "list", "--json"], capture_output=True, text=True).stdout)["venvs"]
        return venvs["ostf-reader"]["metadata"]["main_package"]["package_or_url"]
    except (OSError, KeyError, ValueError):
        return f"{reader}, pin unknown"


def count(repo, start, root, branch, reader):
    start = git(repo, "rev-parse", start).strip()
    head = git(repo, "rev-parse", branch).strip()
    changes = []
    for sha in git(repo, "rev-list", "--first-parent", "--reverse", f"{start}..{head}").split():
        parent = git(repo, "rev-parse", f"{sha}^1").strip()
        files = git(repo, "diff", "--name-only", parent, sha, "--", root).split()
        if not files:
            continue
        with tempfile.TemporaryDirectory() as work:
            work = pathlib.Path(work)
            after, before = tree(repo, sha, root, work / "after"), tree(repo, parent, root, work / "before")
            now = check(reader, after)
            impact = check(reader, after, "--base", parent, "--base-tree", str(before)).get("impact") or {}
            was = check(reader, before)
        items = {i for c in impact.get("changed", []) for i in c["items"]} | set(impact.get("items", {}).get("added", [])) \
            | set(impact.get("items", {}).get("changed", []))
        item_files = [f for f in files if f == f"{root}/trace.yaml" or (f.startswith(f"{root}/trace/") and f.endswith(".yaml") and f.count("/") == root.count("/") + 2)]
        changes.append({"commit": sha, "date": git(repo, "show", "-s", "--format=%cs", sha).strip(),
                        "brokenLeftBroken": sorted((broken(now) - broken(was)).elements()), "itemsListed": sorted(items),
                        "testsListed": impact.get("tests", []), "itemFilesEdited": item_files})
    with tempfile.TemporaryDirectory() as work:
        result = check(reader, tree(repo, head, root, pathlib.Path(work)))
    ids = {i["id"] for i in result["items"]}
    code = {l["source"] for l in result["links"] if l["type"] == "implements"}
    tests = {l["source"] for l in result["links"] if l["type"] == "verifies" and l["source"] not in ids}
    return start, head, changes, {"codeDefinitions": len(code), "testAnchors": len(tests), "items": len(ids), "links": len(result["links"])}


def report(name, repo_root, start, head, changes, symbols, as_of, pin):
    started = datetime.date.fromisoformat(git(repo_root, "show", "-s", "--format=%cs", start).strip())
    months = round((as_of - started).days / 30.44, 1)
    total = lambda key: sum(len(c[key]) for c in changes)
    plural = lambda n, word: f"{n} {word}{'' if n == 1 else 's'}"
    per100 = lambda key: f"{100 * total(key) / len(changes):.1f}" if changes else "n/a"
    lines = [f"Counts of {name}'s OSTF root, from {start[:7]} to {head[:7]}, read on {as_of} with {pin}, by `trials/phase6/count.py`.", "",
             "| Merged change | Date | Links broken and left broken | Items listed | Tests listed | Item files edited by hand |",
             "| --- | --- | --- | --- | --- | --- |"]
    lines += [f"| {c['commit'][:7]} | {c['date']} | {len(c['brokenLeftBroken'])} | {len(c['itemsListed'])} | {len(c['testsListed'])} | {len(c['itemFilesEdited'])} |"
              for c in changes]
    lines += [f"| {plural(len(changes), 'change')} | | {total('brokenLeftBroken')}, {per100('brokenLeftBroken')} per 100 | {total('itemsListed')}, {per100('itemsListed')} per 100 "
              f"| {total('testsListed')}, {per100('testsListed')} per 100 | {total('itemFilesEdited')}, {per100('itemFilesEdited')} per 100 |", "",
              "| Gate criterion | Gate | Measured | Met so far |", "| --- | --- | --- | --- |",
              f"| Months of use | {GATE_MONTHS} | {months} | {'yes' if months >= GATE_MONTHS else 'no'} |",
              f"| Linked symbols | {GATE_SYMBOLS} | {symbols['codeDefinitions'] + symbols['testAnchors']}: {symbols['codeDefinitions']} code definitions, "
              f"{symbols['testAnchors']} test anchors | {'yes' if symbols['codeDefinitions'] + symbols['testAnchors'] >= GATE_SYMBOLS else 'no'} |",
              f"| Published counts | broken links and items listed | {plural(total('brokenLeftBroken'), 'link')} broken, {plural(total('itemsListed'), 'item')} listed, in this table | yes |"]
    data = {"name": name, "start": start, "head": head, "asOf": str(as_of), "reader": pin, "monthsOfUse": months, "linkedSymbols": symbols, "changes": changes}
    return "\n".join(lines) + "\n", data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("repo", type=pathlib.Path)
    parser.add_argument("start", nargs="?", default=START)
    parser.add_argument("--root", default="go/ostf")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--reader", default="ostf")
    parser.add_argument("--as-of", type=datetime.date.fromisoformat, default=datetime.date.today())
    parser.add_argument("--name", default="zztrace")
    args = parser.parse_args(argv)
    start, head, changes, symbols = count(args.repo, args.start, args.root, args.branch, args.reader)
    text, data = report(args.name, args.repo, start, head, changes, symbols, args.as_of, reader_pin(args.reader))
    (HERE / f"{args.name}.md").write_text(text)
    (HERE / f"{args.name}.json").write_text(json.dumps(data, indent=1) + "\n")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
