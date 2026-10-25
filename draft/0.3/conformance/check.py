#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the 0.3 draft checks through the independent-code Python reader.

From the repository root: python3 draft/0.3/conformance/run.py
"""
import hashlib
import importlib.metadata
import json
import os
import pathlib
import re
import subprocess
import sys
import shutil
import tempfile
import urllib.parse

import reader

HERE = pathlib.Path(__file__).resolve().parent
DRAFT = HERE.parent
VECTORS = HERE / "vectors"
# The 0.2 vectors, byte for byte as published with 0.2, and the 0.3 requirements they exercise (Annex H).
VECTORS_02 = {
    "item-vectors.json": ("7ef4e294933e4757e913b7abe20ea1d8211f415ad31fa302a4c738959c779e27", ["OSTF-140", "OSTF-170"]),
    "code-vectors.json": ("0b1fde1b4551cad0a5e60f6a78d2c27e23c9bc210f14fbdbc154bdb1493b199b", ["OSTF-141", "OSTF-170", "Annex A"]),
    "lock-vectors.json": ("004db07d6e4763e27297c87e78907df11ea2d3919077e0e2561ae00235b827bc", ["OSTF-142", "Annex B"]),
}


def load(path):
    return json.loads(path.read_text())


def links(result):
    return [[l["source"], l["type"], l["target"], l["attributes"], l["origin"], l.get("state"), l.get("reasons")] for l in result["links"]]


def codes(result):
    """The Annex C codes of a result; the reader's own codes (OSTF-151) are no conformance target."""
    return sorted({d["code"] for d in result["diagnostics"] if not d["code"].startswith(reader.OWN_PREFIX)})


def states(analysis):
    return {k: (l.get("state"), l.get("reasons")) for k, l in analysis.links.items()}


def check_stamp(case_id, files, names, result, text):
    """Annex I.4: a stamp leaves a canonical lock in which the named links are valid and every other link
    keeps its state; without a lock before, the others get the states an empty lock gives them."""
    before = states(reader.Analysis(files if "trace.lock" in files else {**files, "trace.lock": "trace.lock 1\n"}))
    again = reader.Analysis({**files, "trace.lock": text})
    assert not {"LOCK_INVALID", "LOCK_DUPLICATE"} & set(codes(again.result())), f"{case_id}: lock problems after stamping"
    assert reader.lock_text(again.lock) == text, f"{case_id}: lock not canonical"
    for key, state in states(again).items():
        want = ("valid", []) if key in names else before[key]
        assert state == want, f"{case_id}: {key} is {state} after stamping, want {want}"
    assert reader.stamp(again, names)[1] == text, f"{case_id}: stamping twice changes the lock"


def check():
    for name, version in re.findall(r"^([A-Za-z0-9_-]+)==([^\s]+)", (HERE / "requirements.txt").read_text(), re.MULTILINE):
        assert importlib.metadata.version(name) == version, f"unexpected installed tool version: {name}"
    counts = {}

    # Budget rule 5: the 0.2 hash and lock vectors pass unchanged.
    for name, (digest, _) in VECTORS_02.items():
        assert hashlib.sha256((VECTORS / name).read_bytes()).hexdigest() == digest, f"{name} differs from the 0.2 vectors"
    for case in load(VECTORS / "item-vectors.json"):
        canonical = reader.item_projection(case["item"], case["types"])
        assert canonical.decode() == case["canonical"], case["id"] + ": canonical bytes"
        assert reader.fingerprint("f1", canonical) == case["fingerprint"], case["id"] + ": item hash"
    for case in load(VECTORS / "code-vectors.json"):
        parsed = reader.go1_source(case["source"].encode())
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

    # Annexes A, K and L: the go2, ts2 and py1 vectors, token bytes and digests, and those of the superseded ts1.
    superseded = {"ts1": ("ts2", reader.ts1_source)}
    for name, algorithm in (("go2-vectors.json", "go2"), ("ts1-vectors.json", "ts1"), ("ts2-vectors.json", "ts2"), ("py1-vectors.json", "py1")):
        for case in load(VECTORS / name):
            annex = reader.annex_for(case["path"])
            assert annex is not None and annex.algorithm == superseded.get(algorithm, (algorithm,))[0], case["id"] + ": annex"
            parse = superseded[algorithm][1] if algorithm in superseded else annex.parse
            parsed = parse(case["source"].encode(), case["path"])
            if case.get("parses") is False:  # syntax outside the annex: the file falls back to lf1 (OSTF-141)
                assert parsed is None, case["id"] + ": parses"
                got = {"source.sig": reader.fingerprint("lf1", case["source"].encode().replace(b"\r\n", b"\n"))}
                assert got == case["expect"], case["id"] + f": {got} != {case['expect']}"
                continue
            assert parsed is not None, case["id"] + ": parse"
            if case["symbol"]:
                found = annex.select(parsed["definitions"], case["symbol"], case["path"])
                sig, body = b" ".join(d["sig"] for d in found), b" ".join(d["body"] for d in found)
                assert body.decode() == case["bodyTokens"], case["id"] + f": body tokens {body!r}"
                got = {"source.sig": reader.fingerprint(algorithm, sig), "source.body": reader.fingerprint(algorithm, body)}
            else:
                sig = parsed["whole"]
                got = {"source.sig": reader.fingerprint(algorithm, sig)}
            assert sig.decode() == case["sigTokens"], case["id"] + f": signature tokens {sig!r}"
            assert got == case["expect"], case["id"] + f": {got} != {case['expect']}"
        counts[algorithm + "Vectors"] = len(load(VECTORS / name))

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

    # The Annex C.3 example: edit the body of CheckRefundLimit and add a field to Account.
    edited = {path: example.files[path] for path in example.files}
    edited["refund.go"] = edited["refund.go"].replace(b"\tDailyLimit    int\n}", b"\tDailyLimit    int\n\tFrozen        bool\n}").replace(
        b"if acct.RefundedToday+r.Amount > acct.DailyLimit && !r.Approved", b"if (acct.Frozen || acct.RefundedToday+r.Amount > acct.DailyLimit) && !r.Approved")
    spec_impact = json.loads(re.search(r"\*\*C\.3 Impact\.\*\*.*?```json\n(.*?)```", spec, re.S)[1])
    assert reader.impact(example, reader.Analysis(edited), "main") == spec_impact, "Annex C.3 example"
    # Stamping every link of the example from no lock rebuilds its lock, tagged and item links included (Annex I.4).
    unlocked = {path: value for path, value in edited.items() if path != "trace.lock"} | {"refund.go": example.files["refund.go"]}
    result, text = reader.stamp(reader.Analysis(unlocked), sorted(example.links))
    assert text == example.files["trace.lock"].decode() and len(result["links"]) == 8, "example lock from stamp"
    counts["exampleOutputs"] = 5

    defined = set(re.findall(r"\*\*(OSTF-\d{3}) ", spec))
    cases = load(HERE / "cases.json")
    every = cases["checks"] + cases["contexts"] + cases["stamps"] + cases["impacts"] + cases["sarif"] + cases["projections"] + cases["schemas"]
    ids = [c["id"] for c in every]
    assert len(ids) == len(set(ids)), "duplicate case ID"
    for case in every:
        for requirement in case["requirements"]:
            assert requirement in defined or re.fullmatch(r"Annex [A-L](\.\d+)?", requirement), f"{case['id']}: unknown requirement {requirement}"
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
        for ident, value in expect.get("linkFingerprints", {}).items():
            assert [l["fingerprints"] for l in result["links"] if reader.identity(l) == ident] == [value], f"{case['id']}: fingerprints of {ident}"
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
    for case in cases["stamps"]:
        result, text = reader.stamp(reader.Analysis(case["files"]), case["stamp"])
        expect = case["expect"]
        got = {"codes": codes(result), "links": [reader.identity(l) for l in result["links"]],
               "items": [i["id"] for i in result["items"]], "lock": text}
        assert got == expect, f"{case['id']}:\n got {got}\nwant {expect}"
        assert all(l["state"] == "valid" and l["reasons"] == [] for l in result["links"]), f"{case['id']}: stamped links are valid"
        if text is not None:
            check_stamp(case["id"], case["files"], case["stamp"], result, text)
    for case in cases["impacts"]:
        current = reader.Analysis(case["files"])
        got = reader.impact(reader.Analysis(case["base"]), current, case["rev"])
        assert got == case["expect"]["impact"], f"{case['id']}:\n got {got}\nwant {case['expect']['impact']}"
        # Computed after impact, so impact cannot add a diagnostic to the evaluated view.
        assert codes(current.result()) == case["expect"]["codes"], f"{case['id']}: codes {codes(current.result())}"
    for case in cases["sarif"]:
        analysis = reader.Analysis(case["files"])
        result = analysis.result()
        result["diagnostics"] = [d for d in result["diagnostics"] if not d["code"].startswith(reader.OWN_PREFIX)]
        log = reader.sarif(analysis, result)
        assert log["version"] == "2.1.0" and len(log["runs"]) == 1, f"{case['id']}: one SARIF 2.1.0 run"
        run_ = log["runs"][0]
        rules = [r["id"] for r in run_["tool"]["driver"]["rules"]]
        got = {"rules": rules, "diagnostics": [], "links": []}
        for row, diagnostic in zip(run_["results"], result["diagnostics"]):
            location = (row.get("locations") or [{}])[0]
            assert location.get("physicalLocation", {}).get("artifactLocation", {}).get("uri") == \
                (urllib.parse.quote(diagnostic["file"], safe="/") if "file" in diagnostic else None), f"{case['id']}: diagnostic uri"
            assert (location.get("logicalLocations") or [{}])[0].get("fullyQualifiedName") == diagnostic.get("subject"), f"{case['id']}: subject"
            assert row.get("properties", {}).get("ostf.hint") == diagnostic.get("hint"), f"{case['id']}: hint"
        for row in run_["results"]:
            assert row["ruleId"] in rules and row["message"]["text"], f"{case['id']}: rule and message of {row}"
            assert not re.search(r"[{}]", row["message"]["text"].replace("{{", "").replace("}}", "")), f"{case['id']}: undoubled brace"
            if "ostf.link" in row.get("properties", {}):
                location = row["locations"][0]
                got["links"].append([row["ruleId"], row["level"], location["physicalLocation"]["artifactLocation"]["uri"],
                                     location["logicalLocations"][0]["fullyQualifiedName"], row["properties"]["ostf.link"], row["properties"]["ostf.state"]])
            else:
                got["diagnostics"].append([row["ruleId"], row["level"]])
        got["diagnostics"].sort()
        got["links"].sort()
        assert rules == sorted(rules, key=str.encode) and got == case["expect"], f"{case['id']}:\n got {got}\nwant {case['expect']}"
    for case in cases["projections"]:
        assert reader.item_projection(case["item"], case["types"]).decode() == case["canonical"], case["id"]
    counts["checkCases"], counts["contextCases"], counts["projections"] = len(cases["checks"]), len(cases["contexts"]), len(cases["projections"])
    counts["stampCases"], counts["impactCases"], counts["sarifCases"] = len(cases["stamps"]), len(cases["impacts"]), len(cases["sarif"])
    counts["schemaCases"] = len(cases["schemas"])  # run by fixtures_test.go

    # Inputs that JSON cases cannot carry, and limits that must not crash the reader.
    bad = reader.Analysis({"trace.yaml": 'ostf: "0.3"\nitems:\n  - id: R-A\n    text: A.\n', "a.go": b"package a\n// @req R-A \xff\nfunc F() {}\n"})
    assert codes(bad.result()) == ["LOCK_MISSING", "PARSE_ERROR"], "invalid UTF-8 in Go source"
    chain = 'ostf: "0.3"\nitems:\n' + "".join(f"  - id: R-{i}\n    text: Step {i}.\n" + (f"    refines: [R-{i + 1}]\n" if i < 1199 else "") for i in range(1200))
    deep = reader.Analysis({"trace.yaml": chain})
    assert reader.render(deep, "R-0").count("\n") == 1201, "deep rendering"
    limit = 8 * 1024 * 1024
    head = 'ostf: "0.3"\nitems: []\n'
    assert codes(reader.Analysis({"trace.yaml": head + "#" * (limit - len(head))}).result()) == ["LOCK_MISSING"], "8 MiB is allowed"
    assert codes(reader.Analysis({"trace.yaml": head + "#" * (limit - len(head) + 1)}).result()) == ["FILE_TOO_LARGE"], "above 8 MiB"
    # A lock line that is not UTF-8 voids only itself (OSTF-142), so stamping keeps the other entries (Annex I.4).
    minimal_files = {path: (DRAFT / "fixtures" / "minimal" / path).read_bytes() for path in ("trace.yaml", "math.go", "math_test.go")}
    lock = (DRAFT / "fixtures" / "minimal" / "trace.lock").read_bytes()
    damaged = reader.Analysis({**minimal_files, "trace.lock": lock + b"\xff\n"})
    assert codes(damaged.result()) == ["LOCK_INVALID"] and all(l["state"] == "valid" for l in damaged.links.values()), "non-UTF-8 lock line"
    assert reader.stamp(damaged, ["math.go#Add implements R-ADD"])[1].encode() == lock, "stamp drops only the non-UTF-8 line"
    assert codes(reader.Analysis({**minimal_files, "trace.lock": b"trace.lock 1\xff\n" + lock[13:]}).result()) == ["LOCK_INVALID"], "non-UTF-8 header"
    # The reader's own info for statements that no link targets (OSTF-151): one diagnostic, never a failure.
    lonely = reader.Analysis({"trace.yaml": 'ostf: "0.3"\nitems:\n  - id: N-A\n    type: need\n    text: A need.\n'
                              '  - id: R-A\n    text: Do a.\n    refines: [N-A]\n  - id: R-B\n    text: Do b.\n    status: draft\n'
                              '  - id: R-C\n    text: Do c.\n    status: obsolete\n  - id: RISK-A\n    type: risk\n    text: A risk.\n'
                              '  - id: V-A\n    type: verification\n    text: Review a.\n    verifies: [R-A]\n'})
    assert [(d["severity"], d["message"]) for d in lonely.diagnostics if d["code"] == reader.UNLINKED] == \
        [("info", "1 statement that no link targets: R-B")] and not lonely.failed(), "statements that no link targets"
    many = reader.Analysis({"trace.yaml": 'ostf: "0.3"\nitems:\n' + "".join(f"  - id: R-{i:02}\n    text: Step {i}.\n" for i in range(12))})
    assert [d["message"] for d in many.diagnostics if d["code"] == reader.UNLINKED] == \
        ["12 statements that no link targets: R-00, R-01, R-02, R-03, R-04, R-05, R-06, R-07, R-08, R-09 and 2 more"], "unlinked statements counted"
    run_ = reader.sarif(many, many.result())["runs"][0]
    assert {"id": reader.UNLINKED} in run_["tool"]["driver"]["rules"] and \
        [r["level"] for r in run_["results"] if r["ruleId"] == reader.UNLINKED] == ["note"], "unlinked statements in SARIF"
    counts["directChecks"] = 10

    # Every requirement and Annex C code has a case, or cases.json says why not, so removing a case cannot go unnoticed.
    covered = {r for case in every for r in case["requirements"]}
    covered |= {r for _, requirements in VECTORS_02.values() for r in requirements}
    covered |= {code for case in cases["checks"] + cases["contexts"] + cases["stamps"] + cases["impacts"] for code in case["expect"]["codes"]}
    covered |= {code for case in load(VECTORS / "lock-vectors.json") for code in case["errors"]}
    covered |= {"PARSE_ERROR", "FILE_TOO_LARGE"}
    annex_c = set(re.findall(r"^\| `([A-Z_]+)` \| (?:error|warning|info) \|", spec, re.MULTILINE))
    assert len(annex_c) == 36, "Annex C.1 codes"
    for name, reason in cases["notCovered"].items():
        assert name in defined | annex_c and reason.strip(), f"notCovered {name}: not a requirement or code, or no reason"
    for name in sorted(defined | annex_c):
        assert (name in covered) != (name in cases["notCovered"]), f"{name}: needs a case or a reason in notCovered, not both"

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
    # A path that does not resolve gets a hint spelled from the working directory, which I.3 reads it from.
    code, out = run(DRAFT / "example" / "deploy", "context", "deploy/database.tf", "--format", "json")
    assert code == 1 and json.loads(out)["diagnostics"][0].get("hint", "").endswith("try database.tf"), "context hint from a subdirectory"
    code, out = run(DRAFT / "example", "context", "database.tf", "--format", "json")
    assert code == 1 and json.loads(out)["diagnostics"][0].get("hint", "").endswith("try deploy/database.tf"), "context hint for a file name"
    with tempfile.TemporaryDirectory() as temp:
        tree = pathlib.Path(temp)
        (tree / "sub").mkdir()
        (tree / "trace.yaml").write_text('ostf: "0.3"\nitems:\n  - id: R-A\n    text: Do a.\n    code: [sub/a.go#F]\n  - id: R-B\n    text: Do b.\n    aliases: ["a.go#F"]\n')
        (tree / "sub" / "a.go").write_text("package a\n\nfunc F() int { return 1 }\n")
        code, out = run(tree / "sub", "context", "a.go#F", "--format", "json")
        assert code == 0 and [i["id"] for i in json.loads(out)["items"]] == ["R-B"], "alias before anchor from a subdirectory"
        code, out = run(tree / "sub", "context", "a.go#F", "--root", "..", "--format", "json")
        assert code == 0 and [i["id"] for i in json.loads(out)["items"]] == ["R-B"], "alias before anchor with --root"
        (tree / "trace.lock").write_text("trace.lock 1\nsub/a.go#F implements R-A source.sig=go2:" + "A" * 43 + " target=f1:" + "A" * 43 + "\n")
        assert run(tree, "check")[0] == 1, "check exit 1 on a suspect link"
        os.remove(tree / "trace.yaml")
        assert run(tree, "check")[0] == 2, "check exit 2 without a root"
        assert run(tree, "stamp", "x implements R-A")[0] == 2, "stamp exit 2 without a root"
    with tempfile.TemporaryDirectory() as temp:
        tree = pathlib.Path(temp)
        for name, data in minimal_files.items():
            (tree / name).write_bytes(data)
        code, out = run(tree, "check")
        assert code == 0 and "math.go#Add implements R-ADD" in out and "math_test.go#TestAdd verifies R-ADD" in out, "text check names links without a state"
        # I.1: --strict also fails on LOCK_MISSING with links in the graph and on an unstamped link.
        assert run(tree, "check", "--strict")[0] == 1, "check --strict exit 1 without a lock"
        (tree / "trace.lock").write_text("trace.lock 1\n")
        assert run(tree, "check")[0] == 0 and run(tree, "check", "--strict")[0] == 1, "check --strict exit 1 on unstamped links"
        (tree / "trace.lock").write_bytes(lock)
        assert run(tree, "check", "--strict")[0] == 0, "check --strict exit 0 when every link is valid"
        os.remove(tree / "trace.lock")
        (tree / "empty").mkdir()
        (tree / "empty" / "trace.yaml").write_text('ostf: "0.3"\nitems:\n  - id: R-A\n    text: Do a.\n')
        assert run(tree / "empty", "check", "--strict")[0] == 0, "check --strict exit 0 without a lock or a link"
        # A lock that exists but cannot be read is not a missing lock: the command cannot run.
        (tree / "trace.lock").write_bytes(lock)
        os.chmod(tree / "trace.lock", 0)
        if not os.access(tree / "trace.lock", os.R_OK):
            assert run(tree, "check")[0] == 2, "check exit 2 on an unreadable lock"
        os.chmod(tree / "trace.lock", 0o644)
        # With --root, an anchor outside the root is in no file of the view (Annex I.3).
        (tree / "elsewhere").mkdir()
        code, out = run(tree / "elsewhere", "context", "math.go#Add", "--root", "..", "--format", "json")
        assert code == 1 and json.loads(out)["items"] == [], "context TARGET outside --root does not resolve"
        assert json.loads(out)["diagnostics"][0].get("hint", "").endswith("try ../math.go#Add"), "context hint with --root"
    # check --base, SARIF and stamp on an edited copy of the example, as an agent would run them.
    with tempfile.TemporaryDirectory() as temp:
        tree = pathlib.Path(temp) / "example"
        shutil.copytree(DRAFT / "example", tree)
        (tree / "refund.go").write_bytes(edited["refund.go"])
        assert run(tree, "check", "--base", "main")[0] == 2, "check --base outside a Git checkout exits 2"
        code, out = run(tree, "check", "--base", "main", "--base-tree", str(DRAFT / "example"), "--format", "json")
        assert code == 1 and json.loads(out)["impact"] == spec_impact, "check --base on the edited example"
        code, out = run(tree, "check", "--format", "sarif")
        assert code == 1 and [r["ruleId"] for r in json.loads(out)["runs"][0]["results"]] == ["BODY_CHANGED"], "check --format sarif"
        lock = (tree / "trace.lock").read_bytes()
        code, out = run(tree, "stamp", "refund.go#CheckRefundLimit implements R-NOPE", "refund.go#CheckRefundLimit implements R-REFUND-LIMIT")
        assert code == 1 and (tree / "trace.lock").read_bytes() == lock, "stamp exit 1 writes nothing"
        code, out = run(tree, "stamp", "refund.go#CheckRefundLimit implements R-REFUND-LIMIT", "--format", "json")
        assert code == 0 and [l["state"] for l in json.loads(out)["links"]] == ["valid"], "stamp exit 0"
        assert run(tree, "check")[0] == 0 and (tree / "trace.lock").read_bytes() != lock, "check passes after the stamp"
        assert not list(tree.glob(".trace.lock.*")), "stamp leaves no temporary file"
        os.remove(tree / "trace.lock")
        os.symlink(DRAFT / "example" / "trace.lock", tree / "trace.lock")
        assert run(tree, "stamp", "refund.go#CheckRefundLimit implements R-REFUND-LIMIT")[0] == 2, "stamp does not write through a symbolic link"
        os.remove(tree / "trace.lock")
        outside = pathlib.Path(temp) / "outside.lock"
        outside.write_bytes(lock)
        os.link(outside, tree / "trace.lock")
        assert run(tree, "stamp", "refund.go#CheckRefundLimit implements R-REFUND-LIMIT")[0] == 2 and outside.read_bytes() == lock, "stamp does not write a hard link"
        os.remove(tree / "trace.lock")
        os.symlink(outside, tree / "trace.lock")
        nofollow = getattr(os, "O_NOFOLLOW", None)
        if nofollow is not None:
            del os.O_NOFOLLOW  # as on platforms without it
        try:
            reader.write_lock(tree / "trace.lock", "trace.lock 1\n")
            raise AssertionError("write_lock wrote through a symbolic link without O_NOFOLLOW")
        except OSError:
            pass
        finally:
            if nofollow is not None:
                os.O_NOFOLLOW = nofollow
        assert outside.read_bytes() == lock, "write_lock without O_NOFOLLOW"
    # check --base REV reads the base view from Git when no base tree is given.
    if shutil.which("git"):
        with tempfile.TemporaryDirectory() as temp:
            repo = pathlib.Path(temp)
            git = lambda *a: subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false", *a],
                                            check=True, capture_output=True)
            git("init", "-q")
            (repo / "svc").mkdir()
            (repo / "svc" / "trace.yaml").write_text('ostf: "0.3"\nitems:\n  - id: R-A\n    text: A.\n    code: [a.go#F]\n')
            (repo / "svc" / "a.go").write_text("package a\nfunc F() int { return 1 }\n")
            git("add", ".")
            git("commit", "-q", "-m", "base")
            (repo / "svc" / "a.go").write_text("package a\nfunc F() int { return 2 }\n")
            code, out = run(repo / "svc", "check", "--base", "HEAD", "--format", "json")
            found = json.loads(out)["impact"]
            assert [c["anchor"] for c in found["changed"]] == ["a.go#F"] and found["items"]["added"] == [], "check --base from Git"
            assert run(repo / "svc", "check", "--base", "--nope")[0] == 2, "an option-like revision exits 2"
    counts["commandLine"] = 31
    return {"wireVersion": "0.3", "implementation": "independent-code-python-reader", "counts": counts,
            "passed": True, "independentParty": False, "fullConformance": False}


if __name__ == "__main__":
    try:
        print(json.dumps(check(), sort_keys=True))
    except AssertionError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
