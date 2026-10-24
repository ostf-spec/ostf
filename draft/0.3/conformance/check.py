#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the 0.3 draft checks through the independent-code Python reader.

From the repository root: python3 draft/0.3/conformance/run.py
"""
import importlib.metadata
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

import reader

HERE = pathlib.Path(__file__).resolve().parent
DRAFT = HERE.parent
VECTORS = HERE / "vectors"


def load(path):
    return json.loads(path.read_text())


def links(result):
    return [[l["source"], l["type"], l["target"], l["attributes"], l["origin"], l.get("state"), l.get("reasons")] for l in result["links"]]


def codes(result):
    return sorted({d["code"] for d in result["diagnostics"]})


def check():
    for name, version in re.findall(r"^([A-Za-z0-9_-]+)==([^\s]+)", (HERE / "requirements.txt").read_text(), re.MULTILINE):
        assert importlib.metadata.version(name) == version, f"unexpected installed tool version: {name}"
    counts = {}

    # Budget rule 5: the 0.2 hash and lock vectors pass unchanged.
    for case in load(VECTORS / "item-vectors.json"):
        canonical = reader.item_projection(case["item"], case["types"])
        assert canonical.decode() == case["canonical"], case["id"] + ": canonical bytes"
        assert reader.fingerprint("f1", canonical) == case["fingerprint"], case["id"] + ": item hash"
    for case in load(VECTORS / "code-vectors.json"):
        parsed = reader.go_source(case["source"].encode())
        assert parsed is not None, case["id"] + ": parse"
        if case["symbol"]:
            found = reader.select(parsed["definitions"], case["symbol"])
            sig, body = b" ".join(d["sig"] for d in found), b" ".join(d["body"] for d in found)
            got = {"source.sig": reader.fingerprint("go1", sig), "source.body": reader.fingerprint("go1", body)}
            assert body.decode() == case["bodyTokens"], case["id"] + ": body tokens"
        else:
            sig = parsed["whole"]
            got = {"source.sig": reader.fingerprint("go1", sig)}
        assert sig.decode() == case["sigTokens"], case["id"] + ": signature tokens"
        assert got == case["expect"], case["id"] + f": {got} != {case['expect']}"
    for case in load(VECTORS / "lock-vectors.json"):
        entries, problems = reader.parse_lock(case["text"])
        assert sorted({code for code, _ in problems}) == case["errors"], case["id"] + ": lock errors"
        if not problems:
            assert reader.lock_text(entries) == case["canonical"], case["id"] + ": lock bytes"
    counts["vectors02"] = sum(len(load(VECTORS / n)) for n in ("item-vectors.json", "code-vectors.json", "lock-vectors.json"))

    # The example's expected outputs (Annex C.2, Annex I.3, Annex J), byte for byte.
    example = reader.Analysis(reader.Tree(DRAFT / "example"))
    expected = DRAFT / "example" / "expected"
    dump = lambda value: json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    assert dump(example.result()) == (expected / "check.json").read_text(), "example check.json"
    result, resolved = reader.context(example, "refund.go#CheckRefundLimit")
    assert resolved and dump(result) == (expected / "context.json").read_text(), "example context.json"
    assert reader.render(example, "refund.go#CheckRefundLimit") == (expected / "context.txt").read_text(), "example context.txt"
    counts["exampleOutputs"] = 3

    minimal = reader.Analysis(reader.Tree(DRAFT / "fixtures" / "minimal"))
    assert minimal.result()["diagnostics"] == [] and not minimal.failed(), "minimal fixture diagnostics"
    assert [l[5] for l in links(minimal.result())] == ["valid", "valid"], "minimal fixture states"
    counts["minimalFixture"] = 1

    spec = (DRAFT / "ostf.md").read_text()
    defined = set(re.findall(r"\*\*(OSTF-\d{3}) ", spec))
    cases = load(HERE / "cases.json")
    ids = [c["id"] for c in cases["checks"] + cases["contexts"]]
    assert len(ids) == len(set(ids)), "duplicate case ID"
    for case in cases["checks"] + cases["contexts"]:
        for requirement in case["requirements"]:
            assert requirement in defined or re.fullmatch(r"Annex [A-J](\.\d+)?", requirement), f"{case['id']}: unknown requirement {requirement}"
    for case in cases["checks"]:
        analysis = reader.Analysis(case["files"])
        result, expect = analysis.result(), case["expect"]
        assert codes(result) == expect["codes"], f"{case['id']}: codes {codes(result)} != {expect['codes']}"
        if "links" in expect:
            assert links(result) == expect["links"], f"{case['id']}: links\n got {links(result)}\nwant {expect['links']}"
        if "items" in expect:
            assert [i["id"] for i in result["items"]] == expect["items"], f"{case['id']}: items"
        if "linkCount" in expect:
            assert len(result["links"]) == expect["linkCount"], f"{case['id']}: link count"
        if "risk" in expect:
            assert [i["id"] for i in result["items"] if i["riskRelevant"]] == expect["risk"], f"{case['id']}: risk relevance"
        for ident, value in expect.get("itemFingerprints", {}).items():
            assert next(i["fingerprint"] for i in result["items"] if i["id"] == ident) == value, f"{case['id']}: fingerprint of {ident}"
        for code, file in expect.get("diagnosticFiles", {}).items():
            assert {d.get("file") for d in result["diagnostics"] if d["code"] == code} == {file}, f"{case['id']}: file of {code}"
    for case in cases["contexts"]:
        analysis = reader.Analysis(case["files"])
        result, resolved = reader.context(analysis, case["context"])
        expect = case["expect"]
        got = {"resolved": resolved, "codes": codes(result), "items": [i["id"] for i in result["items"]],
               "links": [reader.identity(l) for l in result["links"]]}
        if "text" in expect:
            got["text"] = reader.render(analysis, case["context"])
        assert got == expect, f"{case['id']}:\n got {got}\nwant {expect}"
    for case in cases["projections"]:
        assert reader.item_projection(case["item"], case["types"]).decode() == case["canonical"], case["id"]
    counts["checkCases"], counts["contextCases"], counts["projections"] = len(cases["checks"]), len(cases["contexts"]), len(cases["projections"])

    # Inputs that JSON cases cannot carry, and limits that must not crash the reader.
    bad = reader.Analysis({"trace.yaml": 'ostf: "0.3"\nitems:\n  - id: R-A\n    text: A.\n', "a.go": b"package a\n// @req R-A \xff\nfunc F() {}\n"})
    assert codes(bad.result()) == ["LOCK_MISSING", "PARSE_ERROR"], "invalid UTF-8 in Go source"
    chain = 'ostf: "0.3"\nitems:\n' + "".join(f"  - id: R-{i}\n    text: Step {i}.\n" + (f"    refines: [R-{i + 1}]\n" if i < 1199 else "") for i in range(1200))
    deep = reader.Analysis({"trace.yaml": chain})
    assert reader.render(deep, "R-0").count("\n") == 1201, "deep rendering"
    counts["directChecks"] = 2

    # Annex I command line: exit codes, root selection and TARGET kept as given.
    script = str(HERE / "reader.py")

    def run(cwd, *args):
        done = subprocess.run([sys.executable, script, *args], cwd=cwd, capture_output=True, text=True)
        return done.returncode, done.stdout

    assert run(DRAFT / "example", "check")[0] == 0, "check exit 0"
    code, out = run(DRAFT, "context", "example/refund.go#CheckRefundLimit", "--format", "json")
    assert code == 0 and json.loads(out)["context"] == "example/refund.go#CheckRefundLimit", "TARGET kept as given"
    assert [i["id"] for i in json.loads(out)["items"]] == ["N-REFUNDS", "R-REFUND-LIMIT", "RISK-REFUND-ABUSE"], "root from TARGET"
    assert run(DRAFT / "example", "context", "R-NOPE")[0] == 1, "context exit 1"
    with tempfile.TemporaryDirectory() as temp:
        tree = pathlib.Path(temp)
        (tree / "sub").mkdir()
        (tree / "trace.yaml").write_text('ostf: "0.3"\nitems:\n  - id: R-A\n    text: Do a.\n    code: [sub/a.go#F]\n  - id: R-B\n    text: Do b.\n    aliases: ["a.go#F"]\n')
        (tree / "sub" / "a.go").write_text("package a\n\nfunc F() int { return 1 }\n")
        code, out = run(tree / "sub", "context", "a.go#F", "--format", "json")
        assert code == 0 and [i["id"] for i in json.loads(out)["items"]] == ["R-B"], "alias before anchor from a subdirectory"
        code, out = run(tree / "sub", "context", "a.go#F", "--root", "..", "--format", "json")
        assert code == 0 and [i["id"] for i in json.loads(out)["items"]] == ["R-B"], "alias before anchor with --root"
        (tree / "trace.lock").write_text("trace.lock 1\nsub/a.go#F implements R-A source.sig=go1:" + "A" * 43 + " target=f1:" + "A" * 43 + "\n")
        assert run(tree, "check")[0] == 1, "check exit 1 on a suspect link"
        os.remove(tree / "trace.yaml")
        assert run(tree, "check")[0] == 2, "check exit 2 without a root"
    counts["commandLine"] = 7
    return {"wireVersion": "0.3", "implementation": "independent-code-python-reader", "counts": counts,
            "passed": True, "independentParty": False, "fullConformance": False}


if __name__ == "__main__":
    try:
        print(json.dumps(check(), sort_keys=True))
    except AssertionError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
