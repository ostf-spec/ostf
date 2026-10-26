#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""A differential harness for OSTF 0.3 readers: a convergence aid, not part of the conformance suite.

    python3 differential.py generate                        write differential/corpus.json
    python3 differential.py run [--reader CMD] [--out FILE]  run a reader on the corpus, write its summaries
    python3 differential.py compare EXPECTED ACTUAL          list every difference, exit 1 when there is one
    python3 differential.py check                            the corpus regenerates, the reference reader matches

The corpus is a deterministic list of small trees at the edges of the text: scalar types, versions,
keys, paths and anchors, link entries, tags in Go, TypeScript and Python, profiles, external items,
includes and nested roots, derived lines, contexts and impacts. `run` drives a reader only through
the command line of Annex F, so any tool that claims it can take part: for each tree, `check` as
json and as sarif, `context` as json and text for its targets, and, when the tree has a base, `check
--base HEAD` in a Git repository whose one commit is the base. CMD is the command, split as a shell
would, that runs the reader, such as `ostf` or `zztrace-ostf`; by default it is this directory's
reader.py. A summary keeps what Annex D.2 compares, the codes, items, link tuples and impact, with
the files of the diagnostics, the SARIF rules, levels and files, the exit codes and the Annex G text
of a context that resolves, and leaves out what it does not compare: the order of diagnostics,
messages, hints and subjects, SARIF logical locations among them, codes of a tool's own, and the
change information of a history.

Agreement with the reference summaries supports no conformance claim. The reference reader is not
the oracle; the text is. A difference is a question for the text: settled there with a case, it is
fixed in whichever reader read it the other way.
"""
import argparse
import concurrent.futures
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
CORPUS = HERE / "differential" / "corpus.json"
REFERENCE = HERE / "differential" / "reference.json"
ANNEX_CODE = re.compile(r"[A-Z][A-Z_]*")  # a tool's own codes carry a prefix with a dot (OSTF-151)


# --- the corpus ----------------------------------------------------------------

def root(items="", head=""):
    return f'ostf: "0.3"\n{head}items:\n{items}' if items else f'ostf: "0.3"\n{head}'


GO = ('package a\n\n// F doubles.\nfunc F(x int) int { return 2 * x }\n\nfunc G() int { return 3 }\n\n'
      'type S struct{}\n\nfunc (s *S) M() {}\n')
GO_TEST = 'package a\n\nimport "testing"\n\nfunc TestF(t *testing.T) { F(1) }\n'
ITEM_A = "  - id: R-A\n    text: A.\n"
ITEM_B = "  - id: R-B\n    text: B.\n"


def corpus():
    inputs = []

    def add(category, label, files, contexts=None, base=None):
        entry = {"id": f"{category}-{len([i for i in inputs if i['id'].startswith(category + '-')]) + 1:03d}-{label}", "files": files}
        if contexts:
            entry["contexts"] = contexts
        if base is not None:
            entry["base"] = base
        inputs.append(entry)

    # Scalars in item fields (OSTF-101, OSTF-110 to OSTF-113, OSTF-150, OSTF-151).
    values = ["true", "True", "'true'", "1", "1.5", "0x10", "null", "~", "''", "' a '", "[]", "{}", '"a\\nb"', "é",
              "9007199254740993", "'R-B'", "R B", "-R", "r-a"]
    for field in ["id", "type", "status", "title", "text", "rationale", "section", "aliases", "revision", "external"]:
        for value in values:
            item = f"  - id: R-A\n    text: A.\n    {field}: {value}\n" if field != "id" else f"  - id: {value}\n    text: A.\n"
            add("scalar", field, {"trace.yaml": root(item)})
    # Wire versions in each kind of file (OSTF-103).
    for version in ['"0.3"', '"0.3.0"', "0.3", '"0.4"', '"1.0"', '"0.1"', '"3"', '""', '"v0.3"', '" 0.3"']:
        add("version", "root", {"trace.yaml": f"ostf: {version}\nitems:\n{ITEM_A}"})
        add("version", "item-file", {"trace.yaml": root(head='include: ["reqs/*.yaml"]\n'), "reqs/a.yaml": f"ostf: {version}\nitems:\n{ITEM_A}"})
        add("version", "profile", {"trace.yaml": root(ITEM_A, "profile: p.yaml\n"), "p.yaml": f"ostf: {version}\n"})
    # Keys and extensions (OSTF-102, OSTF-104).
    for where, files in [
        ("root", {"trace.yaml": root(ITEM_A, "colour: red\n")}),
        ("root-x", {"trace.yaml": root(ITEM_A, "x-colour: red\n")}),
        ("item", {"trace.yaml": root(ITEM_A + "    colour: red\n")}),
        ("item-x", {"trace.yaml": root(ITEM_A + "    x-colour: red\n")}),
        ("item-x-nested", {"trace.yaml": root(ITEM_A + "    attributes: {x-colour: red}\n")}),
        ("item-file-profile", {"trace.yaml": root(head='include: ["reqs/*.yaml"]\n'), "reqs/a.yaml": f'ostf: "0.3"\nprofile: p.yaml\nitems:\n{ITEM_A}'}),
        ("item-file-tags", {"trace.yaml": root(head='include: ["reqs/*.yaml"]\n'), "reqs/a.yaml": f'ostf: "0.3"\ntags: false\nitems:\n{ITEM_A}'}),
        ("item-file-no-items", {"trace.yaml": root(head='include: ["reqs/*.yaml"]\n'), "reqs/a.yaml": 'ostf: "0.3"\n'}),
        ("source-key", {"trace.yaml": root(ITEM_A, "sources:\n  jira: {url: 'https://x/{id}', colour: red}\n")}),
        ("source-x", {"trace.yaml": root(ITEM_A, "sources:\n  jira: {url: 'https://x/{id}', x-colour: red}\n")}),
        ("profile-key", {"trace.yaml": root(ITEM_A, "profile: p.yaml\n"), "p.yaml": 'ostf: "0.3"\ncolour: red\n'}),
        ("profile-x", {"trace.yaml": root(ITEM_A, "profile: p.yaml\n"), "p.yaml": 'ostf: "0.3"\nx-colour: red\n'}),
        ("yaml-anchor", {"trace.yaml": 'ostf: "0.3"\nitems:\n  - &a {id: R-A, text: A.}\n  - *a\n'}),
        ("yaml-tag", {"trace.yaml": 'ostf: "0.3"\nitems:\n  - id: !!str R-A\n    text: A.\n'}),
        ("yaml-duplicate-key", {"trace.yaml": 'ostf: "0.3"\nitems:\n  - id: R-A\n    id: R-B\n    text: A.\n'}),
        ("yaml-two-documents", {"trace.yaml": f'ostf: "0.3"\nitems:\n{ITEM_A}---\nostf: "0.3"\n'}),
        ("bom", {"trace.yaml": "\ufeff" + root(ITEM_A)}),
        ("nel", {"trace.yaml": root("  - id: R-A\n    text: \"a\\u0085b\"\n")}),
        ("crlf", {"trace.yaml": root(ITEM_A).replace("\n", "\r\n")}),
    ]:
        add("keys", where, files)
    # Anchors in code and tests (OSTF-105, OSTF-131, OSTF-132, Annexes A.1 and A.2).
    anchors = ["a.go", "a.go#F", "./a.go#F", "../a.go#F", "/a.go#F", "a\\\\b.go#F", "a.go#", "#F", "a.go#F#G", "dir/", "a.go#Missing",
               "missing.go#F", "a.go#f", "A.go#F", "trace.derived", "TRACE.DERIVED", "R-A", "a b.go#F", "a.go #F", "a.go#F/sub",
               "a_test.go#TestF/sub", "a_test.go#TestF", "a_test.go#TestF/", "x.rs#F", "x.rs", "deploy/x.tf", "a.go#S.M", "a.go#M",
               "a.go#S", "a.go#(*S).M"]
    for field in ["code", "tests"]:
        for anchor in anchors:
            add("anchor", field, {"trace.yaml": root(f'  - id: R-A\n    text: A.\n    {field}: ["{anchor}"]\n'), "a.go": GO,
                                  "a_test.go": GO_TEST, "x.rs": "fn f() {}\n", "deploy/x.tf": "x = 1\n", "dir/b.go": "package dir\n"})
    # Link entries (OSTF-120, OSTF-121, OSTF-130, OSTF-131, OSTF-134).
    for label, link in [("string", "refines: [R-B]"), ("mapping", "refines: [{to: R-B}]"), ("ref-key", "refines: [{ref: R-B}]"),
                        ("attribute", "refines: [{to: R-B, role: x}]"), ("number", "refines: [1]"), ("nested", "refines: [[R-B]]"),
                        ("scalar", "refines: R-B"), ("self", "refines: [R-A]"), ("unknown", "refines: [R-MISSING]"),
                        ("case", "refines: [r-b]"), ("alias", "refines: [B-ALIAS]"), ("twice", "refines: [R-B, R-B]"),
                        ("controls-statement", "controls: [R-B]"), ("verifies-statement", "verifies: [R-B]"),
                        ("unknown-type", "mitigates: [R-B]"), ("empty", "refines: []"), ("null", "refines: null"),
                        ("to-and-ref", "refines: [{to: R-B, ref: R-B}]"), ("to-number", "refines: [{to: 1}]")]:
        add("link", label, {"trace.yaml": root(f"  - id: R-A\n    text: A.\n    {link}\n  - id: R-B\n    text: B.\n    aliases: [B-ALIAS]\n")})
    add("link", "cycle", {"trace.yaml": root("  - id: R-A\n    text: A.\n    refines: [R-B]\n  - id: R-B\n    text: B.\n    refines: [R-A]\n"
                                             "  - id: R-C\n    text: C.\n    refines: [R-A]\n")})
    add("link", "obsolete", {"trace.yaml": root("  - id: R-A\n    text: A.\n    refines: [R-B]\n  - id: R-B\n    text: B.\n    status: obsolete\n")})
    add("link", "risk", {"trace.yaml": root("  - id: RISK-A\n    type: risk\n    text: A.\n  - id: R-A\n    text: B.\n    controls: [RISK-A]\n"
                                            "    code: [a.go#F]\n  - id: R-B\n    text: C.\n    refines: [R-A]\n"), "a.go": GO})
    add("link", "threat", {"trace.yaml": root("  - id: T-A\n    type: threat\n    text: A.\n  - id: C-A\n    type: control\n    text: B.\n    controls: [T-A]\n")})
    add("link", "verification", {"trace.yaml": root("  - id: V-A\n    type: verification\n    text: V.\n    verifies: [R-A]\n" + ITEM_A)})
    add("link", "duplicate-id", {"trace.yaml": root(ITEM_A + "  - id: r-a\n    text: B.\n")})
    add("link", "alias-collides", {"trace.yaml": root(ITEM_A + "  - id: R-B\n    text: B.\n    aliases: [r-a]\n")})
    # Tags in Go (OSTF-133, Annex A.4).
    for label, source in [
        ("line", "// @req R-A\nfunc F() {}\n"), ("no-space", "//@req R-A\nfunc F() {}\n"), ("commas", "// @req R-A,R-B\nfunc F() {}\n"),
        ("spaces", "// @req   R-A  R-B\nfunc F() {}\n"), ("tab", "// @req\tR-A\nfunc F() {}\n"), ("unknown", "// @req R-A R-MISSING\nfunc F() {}\n"),
        ("block", "/* @req R-A */\nfunc F() {}\n"), ("block-lines", "/*\n@req R-A\n*/\nfunc F() {}\n"), ("file", "// @req-file R-A\n"),
        ("bare", "// @req\nfunc F() {}\n"), ("glued", "// @reqR-A\nfunc F() {}\n"), ("mid-line", "// see @req R-A\nfunc F() {}\n"),
        ("trailing", "func F() {} // @req R-A\n"), ("blank-line", "// @req R-A\n\nfunc F() {}\n"), ("inside", "func F() {\n\t// @req R-A\n}\n"),
        ("grouped-keyword", "// @req R-A\nconst (\n\tX = 1\n\tY = 2\n)\n"), ("grouped-spec", "const (\n\t// @req R-A\n\tX = 1\n\tY = 2\n)\n"),
        ("multi-name", "// @req R-A\nvar X, Y = 1, 2\n"), ("method", "type S struct{}\n\n// @req R-A\nfunc (s *S) M() {}\n"),
        ("generic", "type L[T any] struct{}\n\n// @req R-A\nfunc (l *L[T]) M() {}\n"), ("string", 'var s = "// @req R-A"\n'),
        ("raw-string", "var s = `\n// @req R-A\n`\n"), ("crlf", "// @req R-A\r\nfunc F() {}\r\n"), ("alias", "// @req A-ALIAS\nfunc F() {}\n"),
        ("type", "// @req R-A\ntype T struct{}\n"), ("unparseable", "// @req R-A\nfunc F( {\n"), ("doc-and-tag", "// F does.\n// @req R-A\nfunc F() {}\n"),
        ("two-tags", "// @req R-A\n// @req R-B\nfunc F() {}\n"), ("backticks", "// `@req` R-A\nfunc F() {}\n"),
    ]:
        add("go-tag", label, {"trace.yaml": root("  - id: R-A\n    text: A.\n    aliases: [A-ALIAS]\n" + ITEM_B), "a.go": "package a\n\n" + source})
    for label, source in [("test", 'import "testing"\n\n// @req R-A\nfunc TestF(t *testing.T) {}\n'),
                          ("helper", "// @req R-A\nfunc helper() {}\n"), ("benchmark", 'import "testing"\n\n// @req R-A\nfunc BenchmarkF(b *testing.B) {}\n'),
                          ("lowercase", 'import "testing"\n\n// @req R-A\nfunc Testf(t *testing.T) {}\n'),
                          ("fuzz", 'import "testing"\n\n// @req R-A\nfunc FuzzF(f *testing.F) {}\n')]:
        add("go-tag", f"test-file-{label}", {"trace.yaml": root(ITEM_A), "a_test.go": "package a\n\n" + source})
    add("go-tag", "tags-off", {"trace.yaml": root(ITEM_A, "tags: false\n"), "a.go": "package a\n\n// @req R-MISSING\nfunc F() {}\n"})
    # Tags and definitions in TypeScript and JavaScript (Annex B).
    for label, path, source in [
        ("function", "a.ts", "// @req R-A\nexport function f() {}\n"), ("class-method", "a.ts", "export class C {\n  // @req R-A\n  m() {}\n}\n"),
        ("arrow", "a.ts", "// @req R-A\nexport const f = () => 1;\n"), ("namespace", "a.ts", "namespace N {\n  // @req R-A\n  export function f() {}\n}\n"),
        ("interface", "a.ts", "// @req R-A\ninterface I { x: number }\n"), ("enum", "a.ts", "// @req R-A\nenum E { A }\n"),
        ("default", "a.ts", "// @req R-A\nexport default function f() {}\n"), ("jsx", "a.tsx", "const x = <div>{/* @req R-A */}</div>;\n"),
        ("template", "a.ts", "const s = `\n// @req R-A\n`;\n"), ("block", "a.js", "/** @req R-A */\nfunction f() {}\n"),
        ("member-assign", "a.js", "const o = {};\n// @req R-A\no.f = function () {};\n"), ("destructure", "a.ts", "// @req R-A\nconst { a, b } = o;\n"),
        ("private", "a.ts", "class C {\n  // @req R-A\n  #m() {}\n}\n"), ("computed", "a.ts", "class C {\n  // @req R-A\n  ['m']() {}\n}\n"),
        ("decorated", "a.ts", "class C {\n  // @req R-A\n  @d m() {}\n}\n"), ("unparseable", "a.ts", "// @req R-A\nfunction f( {\n"),
        ("jest", "a.test.ts", "describe('suite', () => {\n  // @req R-A\n  it('works', () => {});\n});\n"),
        ("vitest-each", "a.test.ts", "// @req R-A\ntest.each([1])('case %s', () => {});\n"),
        ("tests-dir", "__tests__/a.ts", "// @req R-A\ntest('works', () => {});\n"), ("mjs", "a.mjs", "// @req R-A\nexport function f() {}\n"),
    ]:
        add("ts-tag", label, {"trace.yaml": root(ITEM_A), path: source})
    for anchor in ["a.ts#f", "a.ts#C.m", "a.ts#m", "a.ts#N.f", "a.ts#C", "a.ts#I", "a.test.ts#suite > works", "a.test.ts#suite", "a.ts#missing"]:
        add("ts-anchor", re.sub(r"[^a-z]+", "-", anchor.split("#")[1].lower()).strip("-") or "x",
            {"trace.yaml": root(f'  - id: R-A\n    text: A.\n    code: ["{anchor}"]\n'),
             "a.ts": "export function f() {}\nexport class C {\n  m() {}\n}\nnamespace N {\n  export function f() {}\n}\ninterface I { x: number }\n",
             "a.test.ts": "describe('suite', () => {\n  it('works', () => {});\n});\n"})
    # Tags and definitions in Python (Annex C).
    for label, path, source in [
        ("def", "a.py", "# @req R-A\ndef f():\n    pass\n"), ("method", "a.py", "class C:\n    # @req R-A\n    def m(self):\n        pass\n"),
        ("decorator", "a.py", "# @req R-A\n@d\ndef f():\n    pass\n"), ("async", "a.py", "# @req R-A\nasync def f():\n    pass\n"),
        ("nested-class", "a.py", "class C:\n    class D:\n        # @req R-A\n        def m(self):\n            pass\n"),
        ("variable", "a.py", "# @req R-A\nX = 1\n"), ("docstring", "a.py", 'def f():\n    """@req R-A"""\n'),
        ("test", "test_a.py", "# @req R-A\ndef test_f():\n    pass\n"), ("test-class", "test_a.py", "class TestC:\n    # @req R-A\n    def test_m(self):\n        pass\n"),
        ("tabs", "a.py", "def f():\n\t# @req R-A\n\tpass\n"), ("unparseable", "a.py", "# @req R-A\ndef f(:\n"),
        ("template-string", "a.py", "# @req R-A\nx = t'{y}'\n"), ("one-line", "a.py", "# @req R-A\ndef f(): pass\n"),
    ]:
        add("py-tag", label, {"trace.yaml": root(ITEM_A), path: source})
    for anchor in ["a.py#f", "a.py#C.m", "a.py#m", "test_a.py#test_f[1-2]", "test_a.py#TestC.test_m", "test_a.py#TestC::test_m", "a.py#X"]:
        add("py-anchor", re.sub(r"[^a-z0-9]+", "-", anchor.split("#")[1].lower()).strip("-"),
            {"trace.yaml": root(f'  - id: R-A\n    text: A.\n    tests: ["{anchor}"]\n'), "a.py": "def f():\n    pass\n\nclass C:\n    def m(self):\n        pass\n\nX = 1\n",
             "test_a.py": "def test_f():\n    pass\n\nclass TestC:\n    def test_m(self):\n        pass\n"})
    # Profiles (OSTF-114, OSTF-120, OSTF-121).
    for label, profile, item in [
        ("type-kind", "types:\n  hazard: {kind: risk}\n", "  - id: H-A\n    type: hazard\n    text: H.\n"),
        ("type-no-kind", "types:\n  hazard: {}\n", "  - id: H-A\n    type: hazard\n    text: H.\n"),
        ("type-bad-kind", "types:\n  hazard: {kind: danger}\n", ITEM_A),
        ("link-new", "types:\n  hazard: {kind: risk}\nlinks:\n  mitigates: {from: [requirement], to: [hazard]}\n",
         "  - id: H-A\n    type: hazard\n    text: H.\n  - id: R-A\n    text: A.\n    mitigates: [H-A]\n"),
        ("link-no-to", "links:\n  mitigates: {from: [requirement]}\n", ITEM_A),
        ("link-anchor-from", "links:\n  covers: {from: [code], to: [requirement]}\n", ITEM_A),
        ("attribute-values", "types:\n  requirement:\n    attributes:\n      level: {type: string, values: [a, b]}\n", ITEM_A + "    attributes: {level: c}\n"),
        ("attribute-required", "types:\n  requirement:\n    attributes:\n      level: {type: string, required: true}\n", ITEM_A),
        ("attribute-type", "types:\n  requirement:\n    attributes:\n      n: {type: number}\n", ITEM_A + "    attributes: {n: '1'}\n"),
        ("link-attribute", "links:\n  refines:\n    attributes:\n      role: {values: [x]}\n", "  - id: R-A\n    text: A.\n    refines: [{to: R-B, role: y}]\n" + ITEM_B),
        ("reserved-to", "links:\n  refines:\n    attributes:\n      to: {}\n", ITEM_A),
        ("not-mapping", "[]\n", ITEM_A), ("meaning", "types:\n  requirement:\n    attributes:\n      a: {type: string, meaning: true}\n", ITEM_A),
    ]:
        add("profile", label, {"trace.yaml": root(item, "profile: p.yaml\n"), "p.yaml": 'ostf: "0.3"\n' + profile if not profile.startswith("[") else profile})
    add("profile", "missing", {"trace.yaml": root(ITEM_A, "profile: p.yaml\n")})
    # External items and sources (OSTF-110, OSTF-113).
    for label, head, item in [
        ("plain", "sources:\n  jira: {url: 'https://x/{id}'}\n", "  - id: R-A\n    external: jira:X-1\n"),
        ("text", "sources:\n  jira: {}\n", "  - id: R-A\n    external: jira:X-1\n    revision: '3'\n    text: A.\n"),
        ("undeclared", "", "  - id: R-A\n    external: jira:X-1\n"), ("bad-alias", "sources:\n  Jira: {}\n", "  - id: R-A\n    external: Jira:X-1\n"),
        ("no-native", "sources:\n  jira: {}\n", "  - id: R-A\n    external: 'jira:'\n"), ("space", "sources:\n  jira: {}\n", "  - id: R-A\n    external: jira:X 1\n"),
        ("duplicate", "sources:\n  jira: {}\n", "  - id: R-A\n    external: jira:X-1\n  - id: R-B\n    external: jira:X-1\n"),
        ("revision-alone", "", "  - id: R-A\n    text: A.\n    revision: '3'\n"),
        ("root-same-repo", "sources:\n  cat: {ostf: services/catalog}\n", "  - id: R-A\n    external: cat:C-1\n"),
        ("root-other-repo", "sources:\n  cat: {ostf: 'ostf://github.com/acme/controls#security/'}\n", "  - id: R-A\n    external: cat:C-1\n"),
        ("root-invalid", "sources:\n  cat: {ostf: '../up'}\n", "  - id: R-A\n    external: cat:C-1\n"),
    ]:
        add("external", label, {"trace.yaml": root(item, head)})
    # Includes and nested roots (OSTF-102).
    for label, files in [
        ("glob-star", {"trace.yaml": root(head='include: ["reqs/*.yaml"]\n'), "reqs/a.yaml": f'ostf: "0.3"\nitems:\n{ITEM_A}', "reqs/sub/b.yaml": f'ostf: "0.3"\nitems:\n{ITEM_B}'}),
        ("glob-double-star", {"trace.yaml": root(head='include: ["reqs/**/*.yaml"]\n'), "reqs/a.yaml": f'ostf: "0.3"\nitems:\n{ITEM_A}', "reqs/sub/b.yaml": f'ostf: "0.3"\nitems:\n{ITEM_B}'}),
        ("glob-empty", {"trace.yaml": root(ITEM_A, 'include: ["none/*.yaml"]\n')}),
        ("glob-class", {"trace.yaml": root(head='include: ["reqs/[ab].yaml"]\n'), "reqs/a.yaml": f'ostf: "0.3"\nitems:\n{ITEM_A}'}),
        ("glob-order", {"trace.yaml": root(head='include: ["b/*.yaml", "a/*.yaml"]\n'), "a/x.yaml": f'ostf: "0.3"\nitems:\n{ITEM_A}', "b/x.yaml": f'ostf: "0.3"\nitems:\n  - id: r-a\n    text: B.\n'}),
        ("glob-twice", {"trace.yaml": root(head='include: ["reqs/*.yaml", "reqs/a.yaml"]\n'), "reqs/a.yaml": f'ostf: "0.3"\nitems:\n{ITEM_A}'}),
        ("nested", {"trace.yaml": root(ITEM_A), "sub/trace.yaml": root(ITEM_B), "sub/a.go": "package sub\n\n// @req R-B\nfunc F() {}\n"}),
        ("nested-include", {"trace.yaml": root(head='include: ["**/*.yaml"]\n'), "sub/trace.yaml": root(ITEM_B), "sub/x.yaml": f'ostf: "0.3"\nitems:\n{ITEM_A}'}),
        ("nested-anchor", {"trace.yaml": root('  - id: R-A\n    text: A.\n    code: ["sub/a.go#F"]\n'), "sub/trace.yaml": root(ITEM_B), "sub/a.go": "package sub\n\nfunc F() {}\n"}),
        ("include-root", {"trace.yaml": root(ITEM_A, 'include: ["trace.yaml"]\n')}),
        ("include-path", {"trace.yaml": root(ITEM_A, 'include: ["../x/*.yaml"]\n')}),
    ]:
        add("include", label, files)
    # Derived lines (Annex E).
    derived = {"trace.yaml": root('  - id: R-A\n    text: A.\n    code: [a.go#F, a.go#G]\n    tests: [a_test.go#TestF]\n'), "a.go": GO, "a_test.go": GO_TEST}
    for label, text in [
        ("covers", "trace.derived 1\na_test.go#TestF covers a.go#F view=1 tool=t\n"), ("none", "trace.derived 1\n"),
        ("header", "trace.derived 2\na_test.go#TestF covers a.go#F view=1 tool=t\n"), ("no-tool", "trace.derived 1\na_test.go#TestF covers a.go#F view=1\n"),
        ("pair-twice", "trace.derived 1\na_test.go#TestF covers a.go#F view=1 view=2\n"), ("escape", "trace.derived 1\na_test.go#TestF covers a.go%23F view=1 tool=t\n"),
        ("bad-escape", "trace.derived 1\na_test.go#TestF covers a.go#F view=%zz tool=t\n"), ("crlf", "trace.derived 1\r\na_test.go#TestF covers a.go#F view=1 tool=t\r\n"),
        ("not-anchor", "trace.derived 1\n../x covers a.go#F view=1 tool=t\n"), ("word", "trace.derived 1\na_test.go#TestF calls a.go#F view=1 tool=t\n"),
        ("unsorted", "trace.derived 1\na_test.go#TestF covers a.go#G view=1 tool=t\na_test.go#TestF covers a.go#F view=1 tool=t\n"),
        ("lowercase-hex", "trace.derived 1\na_test.go#TestF covers a.go#F view=%2a tool=t\n"),
    ]:
        add("derived", label, {**derived, "trace.derived": text})
    # Contexts (Annex F.3, Annex G).
    tree = {"trace.yaml": root("  - id: N-A\n    type: need\n    text: Need.\n  - id: RISK-A\n    type: risk\n    title: Risk\n    text: |\n      Line one.\n      Line two.\n"
                               "  - id: R-A\n    title: Req\n    text: A.\n    rationale: Because.\n    aliases: [A-ALIAS]\n    refines: [N-A]\n    controls: [RISK-A]\n"
                               "    code: [a.go#F, deploy/x.tf]\n    tests: [a_test.go#TestF]\n  - id: V-A\n    type: verification\n    text: Review.\n    verifies: [R-A]\n"
                               "  - id: R-B\n    text: B.\n    status: draft\n    code: [a.go#S.M]\n"),
            "a.go": GO, "a_test.go": GO_TEST, "deploy/x.tf": "x = 1\n", "x.rs": "fn f() {}\n"}
    add("context", "targets", tree, contexts=["R-A", "A-ALIAS", "r-a", "N-A", "RISK-A", "V-A", "R-B", "R-MISSING", "a.go#F", "a.go#G", "a.go",
                                              "a.go#M", "a.go#S.M", "a_test.go#TestF", "deploy/x.tf", "x.rs#f", "missing.go#F", "a.go#Missing",
                                              "../a.go", "a.go#", "trace.yaml"])
    # Impacts (Annex D.3).
    item = '  - id: R-A\n    text: A.\n    code: [a.go#F, a.go#S.M]\n    tests: [a_test.go#TestF]\n'
    base = {"trace.yaml": root(item), "a.go": GO, "a_test.go": GO_TEST}
    for label, files in [
        ("none", dict(base)), ("body", {**base, "a.go": GO.replace("2 * x", "3 * x")}), ("comment-inside", {**base, "a.go": GO.replace("{ return 2 * x }", "{ /* c */ return 2 * x }")}),
        ("comment-above", {**base, "a.go": GO.replace("// F doubles.", "// F doubles x.")}), ("crlf", {**base, "a.go": GO.replace("\n", "\r\n")}),
        ("rename", {**base, "a.go": GO.replace("func F(", "func H(")}), ("move", {**base, "a.go": GO.replace("// F doubles.\nfunc F(x int) int { return 2 * x }\n\n", ""),
                                                                             "b.go": "package a\n\n// F doubles.\nfunc F(x int) int { return 2 * x }\n"}),
        ("delete-file", {k: v for k, v in base.items() if k != "a.go"}), ("item-text", {**base, "trace.yaml": root(item.replace("text: A.", "text: A2."))}),
        ("item-rationale", {**base, "trace.yaml": root(item + "    rationale: R.\n")}), ("item-added", {**base, "trace.yaml": root(item + ITEM_B)}),
        ("link-added", {**base, "trace.yaml": root(item.replace("a.go#S.M]", "a.go#S.M, a.go#G]"))}), ("test-body", {**base, "a_test.go": GO_TEST.replace("F(1)", "F(2)")}),
        ("method", {**base, "a.go": GO.replace("func (s *S) M() {}", "func (s *S) M() { _ = s }")}), ("type-field", {**base, "a.go": GO.replace("type S struct{}", "type S struct{ n int }")}),
        ("new-test", {**base, "b_test.go": 'package a\n\nimport "testing"\n\nfunc TestG(t *testing.T) { G() }\n'}),
        ("root-removed", {k: v for k, v in base.items() if k != "trace.yaml"}),
    ]:
        add("impact", label, files, base=base)
    add("impact", "adopt", base, base={"a.go": GO, "a_test.go": GO_TEST})
    return inputs


def corpus_text():
    return json.dumps(corpus(), indent=1, ensure_ascii=True) + "\n"


# --- running a reader ------------------------------------------------------------

def write(directory, files):
    for path, text in files.items():
        target = directory / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode())


def call(reader, cwd, *args):
    done = subprocess.run([*reader, *args], cwd=cwd, capture_output=True, timeout=120)
    return done.returncode, done.stdout.decode("utf-8", "replace")


def annex(diagnostics):
    return [d for d in diagnostics if ANNEX_CODE.fullmatch(d["code"])]


def tuples(links):
    return sorted([l["source"], l["type"], l["target"], l.get("attributes", {}), l.get("origin"), l.get("corroboration")] for l in links)


def summarize_result(code, out):
    if code == 2:
        return {"exit": 2}
    result = json.loads(out)
    diagnostics = annex(result["diagnostics"])
    return {"exit": code, "codes": sorted({d["code"] for d in diagnostics}), "diagnosticFiles": sorted([d["code"], d.get("file", "")] for d in diagnostics),
            "items": sorted([i["id"], i["type"], i["status"], i["riskRelevant"]] for i in result["items"]), "links": tuples(result["links"])}


def summarize(reader, entry):
    summary = {}
    with tempfile.TemporaryDirectory() as work:
        tree = pathlib.Path(work)
        write(tree, entry["files"])
        summary["check"] = summarize_result(*call(reader, tree, "check", "--root", ".", "--format", "json"))
        code, out = call(reader, tree, "check", "--root", ".", "--format", "sarif")
        if code == 2:
            summary["sarif"] = {"exit": 2}
        else:
            run_ = json.loads(out)["runs"][0]
            results = []
            for row in run_["results"]:
                location = (row.get("locations") or [{}])[0]
                # The logical location is the subject (Annex H), which Annex D.2 does not compare.
                results.append([row["ruleId"], row["level"], ((location.get("physicalLocation") or {}).get("artifactLocation") or {}).get("uri", "")])
            summary["sarif"] = {"exit": code, "rules": sorted(r["id"] for r in run_["tool"]["driver"]["rules"] if ANNEX_CODE.fullmatch(r["id"])),
                                "results": sorted(r for r in results if ANNEX_CODE.fullmatch(r[0]))}
        contexts = {}
        for target in entry.get("contexts", []):
            code, out = call(reader, tree, "context", target, "--root", ".", "--format", "json")
            context = {"exit": code}
            if code != 2:
                result = json.loads(out)
                context.update({"codes": sorted({d["code"] for d in annex(result["diagnostics"])}), "items": sorted(i["id"] for i in result["items"]),
                                "links": tuples(result["links"])})
                if code == 0:  # Annex G renders a context that resolves; the text of a failure is a message
                    context["text"] = call(reader, tree, "context", target, "--root", ".", "--format", "text")[1]
            contexts[target] = context
        if contexts:
            summary["contexts"] = contexts
    if "base" in entry:
        with tempfile.TemporaryDirectory() as work:
            repo = pathlib.Path(work)
            env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "base", "GIT_AUTHOR_EMAIL": "base@example.com",
                   "GIT_COMMITTER_NAME": "base", "GIT_COMMITTER_EMAIL": "base@example.com", "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z"}
            git = lambda *args: subprocess.run(["git", "-C", str(repo), *args], env=env, capture_output=True, check=True)
            git("init", "-q", "-b", "main")
            write(repo, entry["base"])
            git("add", "-A")
            git("commit", "-q", "--allow-empty", "-m", "base")
            for path in entry["base"]:
                (repo / path).unlink()
            write(repo, entry["files"])
            code, out = call(reader, repo, "check", "--root", ".", "--base", "HEAD", "--format", "json")
            summary["impact"] = {"exit": code, "impact": json.loads(out).get("impact") if code != 2 else None}
    return summary


def run(reader, jobs):
    inputs = json.loads(CORPUS.read_text())
    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        summaries = dict(zip((i["id"] for i in inputs), pool.map(lambda entry: summarize(reader, entry), inputs)))
    return json.dumps(summaries, indent=1, ensure_ascii=True, sort_keys=True) + "\n"


def differences(expected, actual):
    found = []
    for ident in sorted(set(expected) | set(actual)):
        a, b = expected.get(ident), actual.get(ident)
        if a == b:
            continue
        if a is None or b is None:
            found.append(f"{ident}: only in {'actual' if a is None else 'expected'}")
            continue
        for field in sorted(set(a) | set(b)):
            if field == "contexts":
                for target in sorted(set(a.get(field, {})) | set(b.get(field, {}))):
                    x, y = a.get(field, {}).get(target), b.get(field, {}).get(target)
                    if x != y:
                        found.append(f"{ident} context {target}: expected {json.dumps(x)[:300]}, got {json.dumps(y)[:300]}")
            elif a.get(field) != b.get(field):
                found.append(f"{ident} {field}: expected {json.dumps(a.get(field))[:300]}, got {json.dumps(b.get(field))[:300]}")
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("generate")
    for name in ("run", "check"):
        command = commands.add_parser(name)
        command.add_argument("--reader", default=f"{shlex.quote(sys.executable)} {shlex.quote(str(HERE / 'reader.py'))}")
        command.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
        if name == "run":
            command.add_argument("--out", type=pathlib.Path, default=None)
    compare = commands.add_parser("compare")
    compare.add_argument("expected", type=pathlib.Path)
    compare.add_argument("actual", type=pathlib.Path)
    args = parser.parse_args(argv)
    if args.command == "generate":
        CORPUS.parent.mkdir(exist_ok=True)
        CORPUS.write_text(corpus_text())
        print(f"{len(corpus())} inputs written to {CORPUS.relative_to(HERE)}")
        return 0
    if args.command == "run":
        text = run(shlex.split(args.reader), args.jobs)
        (args.out.write_text(text) if args.out else sys.stdout.write(text))
        return 0
    if args.command == "compare":
        found = differences(json.loads(args.expected.read_text()), json.loads(args.actual.read_text()))
        print("\n".join(found) or "no difference")
        print(f"{len(found)} differences over {len(json.loads(args.expected.read_text()))} inputs", file=sys.stderr)
        return 1 if found else 0
    # check: the corpus is what the generator writes, and the reference reader gives the committed summaries.
    if CORPUS.read_text() != corpus_text():
        print("differential/corpus.json is not what `differential.py generate` writes", file=sys.stderr)
        return 1
    found = differences(json.loads(REFERENCE.read_text()), json.loads(run(shlex.split(args.reader), args.jobs)))
    print("\n".join(found) or f"corpus and reference summaries reproduce: {len(json.loads(REFERENCE.read_text()))} inputs")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
