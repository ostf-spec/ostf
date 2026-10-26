#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Write the generated tree that both implementations time `check` on.

    python3 generate_tree.py DIR [--files 10000]

The tree is deterministic: the same arguments write the same bytes. It holds one root with
500 requirements, 40 percent Go source files (one in four tags an item), 20 percent Go test
files and 40 percent other files.
"""
import argparse
import pathlib


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dir")
    parser.add_argument("--files", type=int, default=10000)
    args = parser.parse_args()
    root = pathlib.Path(args.dir)
    root.mkdir(parents=True, exist_ok=True)
    sources, tests = args.files * 4 // 10, args.files * 2 // 10
    others = args.files - sources - tests - 1  # trace.yaml counts as a file
    items = ['ostf: "0.3"', "items:"]
    for n in range(500):
        package = n % 50
        items += [f"  - id: R-{n:04d}", f"    text: Requirement {n} of the generated tree.",
                  f"    code: [p{package:02d}/s{n:05d}.go#F{n}]", f"    tests: [p{package:02d}/t{n:05d}_test.go#TestF{n}]"]
        if n % 10 == 1:
            items.append(f"    refines: [R-{n - 1:04d}]")
    (root / "trace.yaml").write_text("\n".join(items) + "\n")
    for n in range(sources):
        package = n % 50
        tag = f"// @req R-{n % 500:04d}\n" if n % 4 == 0 and n >= 500 else ""
        body = "".join(f"\n// F{n}x{k} does step {k}.\nfunc F{n}x{k}(a, b int) int {{\n\tif a > b {{\n\t\treturn a - b\n\t}}\n\treturn a + b + {k}\n}}\n" for k in range(3))
        text = f"package p{package:02d}\n\n// F{n} is linked from trace.yaml.\n{tag}func F{n}(values []int) (total int) {{\n\tfor _, v := range values {{\n\t\ttotal += v\n\t}}\n\treturn total\n}}\n{body}"
        path = root / f"p{package:02d}" / f"s{n:05d}.go"
        path.parent.mkdir(exist_ok=True)
        path.write_text(text)
    for n in range(tests):
        package = n % 50
        text = f'package p{package:02d}\n\nimport "testing"\n\nfunc TestF{n}(t *testing.T) {{\n\tif F{n}([]int{{1, 2}}) != 3 {{\n\t\tt.Fatal("sum")\n\t}}\n}}\n'
        (root / f"p{package:02d}" / f"t{n:05d}_test.go").write_text(text)
    for n in range(others):
        folder = root / "docs" / f"d{n % 40:02d}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"note{n:05d}.md").write_text(f"# Note {n}\n\nGenerated text that mentions no tag.\n")


if __name__ == "__main__":
    main()
