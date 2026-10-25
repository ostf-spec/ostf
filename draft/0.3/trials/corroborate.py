#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The Corroborated row of the agent-first plan (section 2) on 0.3, which has no derived record:
the share of declared `implements` links on tested code that a coverage run confirms.

    python3 corroborate.py root DIR
    python3 corroborate.py trials RESULTS

An `implements` link from a function to an item is on tested code when a test verifies the same
item; it is confirmed when one of those tests, run alone with coverage, executes a statement of
the function. Go runs `go test -run` with `-coverpkg=./...`, TypeScript `node --test` with the
test's name as its pattern and an lcov report. `root` measures the declared links of one root;
`trials` measures the links that agents declared in the T2, T4 and T5 runs of the intent and full
arms, from their final repositories in the work directory, and writes
results/phase1/corroboration.json.
"""
import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse

import harness

READER = None


def reader_module():
    global READER
    READER = READER or harness.load_reader()
    return READER


def result_of(root):
    done = subprocess.run([sys.executable, str(harness.READER), "check", "--format", "json"], cwd=root, capture_output=True, text=True)
    return json.loads(done.stdout)


TS_CALLABLE = re.compile(r"\s*(export\s+)?(default\s+)?(async\s+)?function\b|\s*(export\s+)?(const|let|var)\s+[\w$]+\s*(:[^=]+)?=\s*"
                         r"(async\s+)?(function\b|(\([^)]*\)|[\w$]+)\s*(:\s*[^=]+)?=>)")
TS_METHOD = re.compile(r"\s*((static|private|public|protected|async|readonly|override|get|set)\s+|\*\s*)*[\w$#]+\s*(<[^>]*>)?\s*\(")


def callable_(path, data, d):
    """Whether a definition has statements that a test can execute: a function or a method, not a
    type, an interface, a constant or a field, which coverage cannot confirm."""
    text = data[d["start"]:d["end"]].decode(errors="replace")
    if path.endswith(".go"):
        return d.get("function", False) or (d["member"] and text.lstrip().startswith("func"))
    if path.endswith(".py"):
        return bool(re.match(r"\s*(@.*\n\s*)*(async\s+)?def\b", text))
    return bool(TS_CALLABLE.match(text) or (d["member"] and TS_METHOD.match(text)))


def line_range(root, anchor):
    """The first and last line of the functions and methods an anchor binds to, or None when it
    binds to none."""
    module = reader_module()
    path, _, symbol = anchor.partition("#")
    file = root / path
    if not symbol or not file.exists():
        return None
    annex = module.annex_for(path)
    data = file.read_bytes()
    parsed = annex.parse(data, path) if annex else None
    chosen = annex.select(parsed["definitions"], urllib.parse.unquote(symbol), path) if parsed else []
    chosen = [d for d in chosen if callable_(path, data, d)]
    if not chosen:
        return None
    return (min(data[:d["start"]].count(b"\n") + 1 for d in chosen), max(data[:d["end"]].count(b"\n") + 1 for d in chosen))


def covered_lines(root, test):
    """{path: set of executed lines} when the test anchor runs alone, or None when it cannot run."""
    path, _, name = test.partition("#")
    name = urllib.parse.unquote(name)
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "cover"
        if path.endswith(".go"):
            module = re.search(r"^module\s+(\S+)", (root / "go.mod").read_text(), re.M).group(1)
            pattern = "/".join(f"^{re.escape(part)}$" for part in name.split("/"))
            done = subprocess.run(["go", "test", "./" + str(pathlib.Path(path).parent), "-count=1", "-run", pattern, "-coverpkg=./...",
                                   f"-coverprofile={out}"], cwd=root, capture_output=True, text=True, env=harness.environment(root, root))
            if not out.exists():
                return None
            lines = {}
            for row in out.read_text().splitlines()[1:]:
                where, _, rest = row.partition(":")
                span, _, counts = rest.partition(" ")
                if int(counts.split()[1]) == 0:
                    continue
                start, end = (int(part.split(".")[0]) for part in span.split(","))
                lines.setdefault(where.removeprefix(module + "/"), set()).update(range(start, end + 1))
            return lines if done.returncode == 0 or lines else None
        last = name.split(" > ")[-1]
        subprocess.run(["node", "--test", "--experimental-test-coverage", "--test-reporter=lcov", f"--test-reporter-destination={out}",
                        f"--test-name-pattern=^{re.escape(last)}$", path], cwd=root, capture_output=True, text=True)
        if not out.exists():
            return None
        lines, current = {}, None
        for row in out.read_text().splitlines():
            if row.startswith("SF:"):
                current = str(pathlib.Path(row[3:]).resolve().relative_to(root.resolve())) if row[3:].startswith("/") else row[3:]
            elif row.startswith("DA:") and current:
                number, count = row[3:].split(",")[:2]
                if int(count) > 0:
                    lines.setdefault(current, set()).add(int(number))
        return lines


def measure(root, only=None):
    """Each implements link on tested code with whether a verifying test executes its function;
    `only` limits the links measured to a set of (source, target)."""
    result = result_of(root)
    ids = {i["id"] for i in result["items"]}
    tests = {}
    for l in result["links"]:
        if l["type"] == "verifies" and l["source"] not in ids and "#" in l["source"] and l.get("state") != "broken":
            tests.setdefault(l["target"], set()).add(l["source"])
    cache, out = {}, []
    for l in result["links"]:
        if l["type"] != "implements" or l["source"] in ids or "#" not in l["source"] or l.get("state") == "broken":
            continue
        if only is not None and (l["source"], l["target"]) not in only:
            continue
        span = line_range(root, l["source"])
        if span is None:
            out.append({"link": f"{l['source']} implements {l['target']}", "function": False, "tested": False})
            continue
        verifying = sorted(tests.get(l["target"], ()))
        if not verifying:
            out.append({"link": f"{l['source']} implements {l['target']}", "function": True, "tested": False})
            continue
        path = l["source"].partition("#")[0]
        confirmed, ran = False, False
        for test in verifying:
            if test not in cache:
                cache[test] = covered_lines(root, test)
            lines = cache[test]
            if lines is None or span is None:
                continue
            ran = True
            # A declaration line runs when its module or class loads, in TypeScript and Python;
            # only a line of the body shows that the test called the function.
            first = span[0] if path.endswith(".go") else span[0] + 1
            if lines.get(path, set()) & set(range(first, span[1] + 1)):
                confirmed = True
                break
        out.append({"link": f"{l['source']} implements {l['target']}", "function": True, "tested": True, "ran": ran, "confirmed": confirmed})
    return out


def tally(rows):
    tested = [r for r in rows if r["tested"]]
    return {"implementsLinks": len(rows), "toTypesOrConstants": sum(1 for r in rows if not r["function"]), "onTestedCode": len(tested), "ran": sum(1 for r in tested if r["ran"]),
            "confirmed": sum(1 for r in tested if r["confirmed"])}


def trials(results):
    """Agent-declared links: implements links in a run's final graph that the fixture did not have."""
    fixtures = {f: {(l["source"], l["target"]) for l in result_of(harness.FIXTURES / f)["links"] if l["type"] == "implements"}
                for f in ("go-shop", "ts-shop")}
    runs = []
    for path in sorted(results.glob("*.json")):
        record = json.loads(path.read_text())
        if record.get("arm") not in ("intent", "full") or record.get("task") not in ("T2", "T4", "T5"):
            continue
        repo = harness.WORK / record["run"] / "repo"
        if not (repo / "trace.yaml").exists():
            continue
        final = {(l["source"], l["target"]) for l in result_of(repo)["links"] if l["type"] == "implements"}
        declared = final - fixtures[record["fixture"]]
        rows = measure(repo, declared) if declared else []
        runs.append({"run": record["run"], "arm": record["arm"], "agent": record["agent"], "fixture": record["fixture"],
                     "task": record["task"], **tally(rows), "links": rows})
    fixture_counts = {}
    for f in ("go-shop", "ts-shop"):
        with tempfile.TemporaryDirectory() as tmp:
            copy = pathlib.Path(tmp) / f
            shutil.copytree(harness.FIXTURES / f, copy)
            fixture_counts[f] = tally(measure(copy))
    out = {"fixtures": fixture_counts, "runs": runs,
           "agentDeclared": tally([row for run in runs for row in run["links"]])}
    target = harness.HERE / "results" / "phase1" / "corroboration.json"
    target.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({"fixtures": out["fixtures"], "agentDeclared": out["agentDeclared"]}, indent=1))


def main(argv=None):
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("root")
    one.add_argument("dir", type=pathlib.Path)
    many = commands.add_parser("trials")
    many.add_argument("results", type=pathlib.Path)
    args = parser.parse_args(argv)
    if args.command == "root":
        rows = measure(args.dir.resolve())
        print(json.dumps({**tally(rows), "unconfirmed": [r["link"] for r in rows if r["tested"] and not r["confirmed"]]}, indent=1))
    else:
        trials(args.results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
