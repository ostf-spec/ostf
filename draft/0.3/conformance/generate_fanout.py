#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Write a generated tree whose items link one, ten and a hundred anchors (agent-first plan, section 6).

    python3 generate_fanout.py DIR [--fanout 1,10,100] [--items 60] [--packages 40]

The tree is deterministic: the same arguments write the same bytes. It holds one root with
`--items` requirements for each fan-out, each linking that many distinct Go functions and one test,
the functions of an item spread across the packages as one requirement spreads across the modules
of a large code base. One item in ten controls one of six risks, so `bodyChange: risk` has links
to count. There is no lock; trials/fanout.py stamps one and times the commands on the tree.
"""
import argparse
import pathlib

PER_FILE = 50


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dir")
    parser.add_argument("--fanout", default="1,10,100")
    parser.add_argument("--items", type=int, default=60)
    parser.add_argument("--packages", type=int, default=40)
    args = parser.parse_args()
    root = pathlib.Path(args.dir)
    root.mkdir(parents=True, exist_ok=True)
    lines = ['ostf: "0.3"', "items:"]
    lines += [f"  - id: RISK-{r}\n    type: risk\n    text: Generated risk {r}." for r in range(6)]
    functions, tests, number = [], [], 0
    for fanout in (int(f) for f in args.fanout.split(",")):
        for n in range(args.items):
            ident = f"R-F{fanout}-{n:03d}"
            code = []
            for _ in range(fanout):
                package = number % args.packages
                functions.append((package, number))
                code.append(f"p{package:02d}/f{number // (PER_FILE * args.packages):03d}.go#F{number}")
                number += 1
            # The test sits in the package of the item's last function and calls it.
            test, package = len(tests), functions[-1][0]
            tests.append((package, test, number - 1))
            lines += [f"  - id: {ident}", f"    text: Generated requirement {n} with {fanout} linked functions.",
                      f"    code: [{', '.join(code)}]", f"    tests: [p{package:02d}/t{test:04d}_test.go#TestR{test}]"]
            if n % 10 == 0:
                lines.append(f"    controls: [RISK-{n % 6}]")
    (root / "trace.yaml").write_text("\n".join(lines) + "\n")
    files = {}
    for package, n in functions:
        files.setdefault((package, n // (PER_FILE * args.packages)), []).append(n)
    for (package, index), numbers in sorted(files.items()):
        body = "".join(f"\n// F{n} is linked from trace.yaml.\nfunc F{n}(a, b int) int {{\n\tif a > b {{\n\t\treturn a - b\n\t}}\n"
                       f"\treturn a + b + {n % 7}\n}}\n" for n in numbers)
        path = root / f"p{package:02d}" / f"f{index:03d}.go"
        path.parent.mkdir(exist_ok=True)
        path.write_text(f"package p{package:02d}\n{body}")
    for package, n, last in tests:
        text = (f'package p{package:02d}\n\nimport "testing"\n\nfunc TestR{n}(t *testing.T) {{\n\tif F{last}(1, 2) == 0 {{\n'
                f'\t\tt.Fatal("zero")\n\t}}\n}}\n')
        (root / f"p{package:02d}" / f"t{n:04d}_test.go").write_text(text)


if __name__ == "__main__":
    main()
