#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Scale on a generated tree (agent-first plan, section 6): items that link one, ten and a hundred
anchors, from conformance/generate_fanout.py, measured with the reference reader.

    python3 fanout.py [--items 60] [--sweep 0.05] [--repeat 3]

It stamps every link, times `check`, `context` on an item of each fan-out and on a function, then
edits the bodies of a share of the functions, commits the sweep and times `check --base`, and
counts the suspect queue under `bodyChange: all` and `bodyChange: risk`. Times are the median of
`--repeat` runs. The result goes to results/phase1/fanout-ITEMS.json.
"""
import argparse
import datetime
import json
import pathlib
import random
import re
import statistics
import subprocess
import sys
import tempfile
import time

import harness

GENERATOR = harness.DRAFT / "conformance" / "generate_fanout.py"


def reader(root, *args):
    return subprocess.run([sys.executable, str(harness.READER), *args], cwd=root, capture_output=True, text=True)


def timed(root, repeat, *args):
    times, done = [], None
    for _ in range(repeat):
        began = time.perf_counter()
        done = reader(root, *args)
        times.append(time.perf_counter() - began)
    return round(statistics.median(times), 3), done


def git(root, *args):
    subprocess.run(harness.GIT + ["-C", str(root), *args], check=True, capture_output=True)


def queue(result):
    suspect = [l for l in result["links"] if l["state"] == "suspect"]
    by_fanout = {}
    for l in suspect:
        group = re.match(r"R-F(\d+)-", l["target"])
        key = group.group(1) if group else "other"
        by_fanout.setdefault(key, set()).add(l["target"])
    return {"suspectLinks": len(suspect), "suspectItems": len({l["target"] for l in suspect}),
            "itemsByFanout": {k: len(v) for k, v in sorted(by_fanout.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 1e9)}}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", type=int, default=60)
    parser.add_argument("--sweep", type=float, default=0.05)
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp) / "tree"
        subprocess.run([sys.executable, str(GENERATOR), str(root), "--items", str(args.items)], check=True)
        git(root.parent, "init", "-q", "-b", "main", str(root))
        result = json.loads(reader(root, "check", "--format", "json").stdout)
        names = [f"{l['source']} {l['type']} {l['target']}" for l in result["links"]]
        began = time.perf_counter()
        for n in range(0, len(names), 500):
            reader(root, "stamp", *names[n:n + 500])
        stamp_time = time.perf_counter() - began
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "tree")
        lock = root / "trace.lock"
        out = {"date": datetime.date.today().isoformat(), "reader": "reference reader (Python)", "itemsPerFanout": args.items,
               "items": len(result["items"]), "links": len(result["links"]),
               "functions": sum(1 for l in result["links"] if l["type"] == "implements"),
               "lockLines": len(lock.read_text().splitlines()), "lockBytes": lock.stat().st_size,
               "stampAllSeconds": round(stamp_time, 2)}
        out["checkSeconds"], _ = timed(root, args.repeat, "check", "--format", "json")
        contexts = {}
        for fanout in (1, 10, 100):
            seconds, done = timed(root, args.repeat, "context", f"R-F{fanout}-000")
            contexts[f"item linking {fanout}"] = {"seconds": seconds, "bytes": len(done.stdout), "tokens": round(len(done.stdout) / 4)}
        seconds, done = timed(root, args.repeat, "context", "p00/f000.go#F0")
        contexts["function"] = {"seconds": seconds, "bytes": len(done.stdout), "tokens": round(len(done.stdout) / 4)}
        out["context"] = contexts
        # The sweep: a share of the functions change a constant in their body, as edits across a code base would.
        functions = sorted(root.glob("p*/f*.go"))
        bodies = [(path, m.group(0)) for path in functions for m in re.finditer(r"func F\d+\(a, b int\) int \{.*?\n\}", path.read_text(), re.S)]
        chosen = random.Random(1).sample(bodies, max(1, round(len(bodies) * args.sweep)))
        for path, body in chosen:
            path.write_text(path.read_text().replace(body, body.replace("return a + b + ", "return a + b + 1 + ")))
        git(root, "commit", "-q", "-a", "-m", "sweep")
        out["sweep"] = {"share": args.sweep, "functionsEdited": len(chosen)}
        out["checkBaseSeconds"], done = timed(root, args.repeat, "check", "--base", "HEAD~1", "--format", "json")
        result_all = json.loads(done.stdout)
        out["sweep"]["impactChanged"] = len(result_all["impact"]["changed"])
        out["sweep"]["bodyChangeAll"] = queue(result_all)
        (root / "profile.yaml").write_text('ostf: "0.3"\nfingerprints:\n  bodyChange: risk\n')
        (root / "trace.yaml").write_text((root / "trace.yaml").read_text().replace('ostf: "0.3"\n', 'ostf: "0.3"\nprofile: profile.yaml\n', 1))
        out["sweep"]["bodyChangeRisk"] = queue(json.loads(reader(root, "check", "--format", "json").stdout))
    target = harness.HERE / "results" / "phase1" / f"fanout-{args.items}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
