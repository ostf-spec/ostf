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

import fastjsonschema

import reader

HERE = pathlib.Path(__file__).resolve().parent
DRAFT = HERE.parent
VECTORS = HERE / "vectors"
# The OASIS SARIF 2.1.0 schema (Errata 01), which run.py fetches and pins (Annex H).
SARIF_SCHEMA = HERE.parents[2] / ".venv" / "sarif-schema-2.1.0.json"
SARIF_SHA256 = "c3b4bb2d6093897483348925aaa73af03b3e3f4bd4ca38cef26dcb4212a2682e"
# The span vectors of Annexes A, B and C (OSTF-164).
SPAN_VECTORS = ("go-spans.json", "ts-spans.json", "py-spans.json")


def load(path):
    return json.loads(path.read_text())


def suite_digest(cases):
    """What the suite asks of a reader, as one SHA-256: cases.json without its suite entry, the span vectors and
    the example's expected outputs, each named and its bytes, in that order."""
    digest = hashlib.sha256()
    body = json.dumps({k: v for k, v in cases.items() if k != "suite"}, sort_keys=True).encode()
    parts = [("cases.json", body)] + [(f"vectors/{name}", (VECTORS / name).read_bytes()) for name in SPAN_VECTORS]
    parts += [(f"example/expected/{path.name}", path.read_bytes()) for path in sorted((DRAFT / "example" / "expected").iterdir())]
    for name, data in parts:
        digest.update(name.encode() + b"\0" + data + b"\0")
    return digest.hexdigest()


def case_files(case):
    """A case's files, each named in padTo extended with line feeds to that size, so that a case
    near a size limit (OSTF-105) need not carry the bytes."""
    files = dict(case["files"])
    for path, size in case.get("padTo", {}).items():
        files[path] = files[path].encode() + b"\n" * (size - len(files[path].encode()))
    return files


def links(result):
    return [[l["source"], l["type"], l["target"], l["attributes"], l["origin"]] for l in result["links"]]


def codes(result):
    """The Annex D codes of a result; the reader's own codes (OSTF-151) are no conformance target."""
    return sorted({d["code"] for d in result["diagnostics"] if not d["code"].startswith(reader.OWN_PREFIX)})


def sarif_validator():
    """Annex H: a validator for the OASIS SARIF 2.1.0 schema, which is JSON Schema draft-04."""
    assert SARIF_SCHEMA.is_file(), f"no {SARIF_SCHEMA}: run run.py, which fetches it"
    data = SARIF_SCHEMA.read_bytes()
    assert hashlib.sha256(data).hexdigest() == SARIF_SHA256, "the SARIF schema is not the pinned one"
    validate = fastjsonschema.compile(json.loads(data), use_default=False)  # never fill in defaults

    def check(log, what):
        try:
            validate(log)
        except fastjsonschema.JsonSchemaException as error:
            raise AssertionError(f"{what}: SARIF fails the OASIS schema: {error.message}") from None
    return check


def scripted_history(case, directory):
    """Annex F.3: a Git repository for a history case, and its commit identifiers by subject. Each commit applies
    `files` to the tree of its first parent, by default the commit before it, a null deleting a file; HEAD is the
    last commit; `depth` clones it shallow; `worktree` edits the checkout. Without commits, a plain directory."""
    checkout = directory / "repo"
    checkout.mkdir()
    ids = {}
    if case["commits"]:
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "ostf",
               "GIT_AUTHOR_EMAIL": "ostf@example.com", "GIT_COMMITTER_NAME": "ostf", "GIT_COMMITTER_EMAIL": "ostf@example.com"}
        git = lambda *args, stdin=None, cwd=checkout, extra=None: subprocess.run(
            ["git", *args], cwd=cwd, input=stdin, capture_output=True, check=True, env={**env, **(extra or {})}).stdout.decode().strip()
        git("init", "-q", "-b", "main")
        trees, previous = {}, None
        for commit in case["commits"]:
            parents = commit.get("parents", [previous] if previous else [])
            files = dict(trees[parents[0]]) if parents else {}
            for path, text in commit["files"].items():
                if text is None:
                    files.pop(path)
                else:
                    files[path] = text
            index = {"GIT_INDEX_FILE": str(directory / "index")}
            git("read-tree", "--empty", extra=index)
            entries = "".join(f"100644 {git('hash-object', '-w', '--stdin', stdin=text.encode())}\t{path}\n" for path, text in sorted(files.items()))
            git("update-index", "--index-info", stdin=entries.encode(), extra=index)
            tree = git("write-tree", extra=index)
            ids[commit["subject"]] = git("commit-tree", tree, "-m", commit["subject"], *[x for parent in parents for x in ("-p", ids[parent])])
            trees[commit["subject"]], previous = files, commit["subject"]
        git("update-ref", "refs/heads/main", ids[previous])
        git("reset", "-q", "--hard", "main")
        if "depth" in case:
            git("clone", "-q", "--depth", str(case["depth"]), f"file://{checkout}", "clone", cwd=directory)
            checkout = directory / "clone"
    for path, text in case.get("worktree", {}).items():
        target = checkout / path
        if text is None:
            target.unlink()
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(text.encode())
    return checkout, ids


def check():
    for name, version in re.findall(r"^([A-Za-z0-9_-]+)==([^\s]+)", (HERE / "requirements.txt").read_text(), re.MULTILINE):
        assert importlib.metadata.version(name) == version, f"unexpected installed tool version: {name}"
    counts = {}


    # Annexes A, B and C (OSTF-164): every definition of each vector source, by full symbol and span text in
    # source order, the span texts its symbol binds to, or no parse.
    for name in SPAN_VECTORS:
        for case in load(VECTORS / name):
            annex = reader.annex_for(case["path"])
            assert annex is not None, case["id"] + ": annex"
            parsed = annex.parse(case["source"].encode(), case["path"])
            if case.get("parses") is False:
                assert parsed is None, case["id"] + ": parses"
                continue
            assert parsed is not None, case["id"] + ": parse"
            got = [[d["name"], d["text"].decode()] for d in parsed["definitions"]]
            assert got == case["definitions"], case["id"] + f": definitions {got}"
            if "symbol" in case:
                found = [d["text"].decode() for d in annex.select(parsed["definitions"], case["symbol"], case["path"])]
                assert found == case["binds"], case["id"] + f": binds {found}"
        counts[name.removesuffix("-spans.json") + "Spans"] = len(load(VECTORS / name))

    # The example's expected outputs (Annex D.2, Annex F.3, Annex G), byte for byte.
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
    counts["minimalFixture"] = 1

    spec = (DRAFT / "ostf.md").read_text()
    # Annex E reproduces the rules of trace-derived.abnf.
    rules = [line.split(";")[0].rstrip() for line in (DRAFT / "trace-derived.abnf").read_text().splitlines()]
    assert [r for r in rules if r] == re.search(r"## Annex E .*?```abnf\n(.*?)```", spec, re.S)[1].splitlines(), "Annex E differs from trace-derived.abnf"

    # The Annex D.3 example: edit the body of CheckRefundLimit and add a field to Account.
    edited = {path: example.files[path] for path in example.files}
    edited["refund.go"] = edited["refund.go"].replace(b"\tDailyLimit    int\n}", b"\tDailyLimit    int\n\tFrozen        bool\n}").replace(
        b"if acct.RefundedToday+r.Amount > acct.DailyLimit && !r.Approved", b"if (acct.Frozen || acct.RefundedToday+r.Amount > acct.DailyLimit) && !r.Approved")
    spec_impact = json.loads(re.search(r"\*\*D\.3 Impact\.\*\*.*?```json\n(.*?)```", spec, re.S)[1])
    assert reader.impact(example, reader.Analysis(edited), "main") == spec_impact, "Annex D.3 example"
    counts["exampleOutputs"] = 4

    defined = set(re.findall(r"\*\*(OSTF-\d{3}) ", spec))
    cases = load(HERE / "cases.json")
    # The suite's version (OSTF-163): any change to what it asks of a reader gives it the next one, so the digest
    # recorded beside the version must be that of the suite as it is, and the README states the same version.
    suite = cases["suite"]
    assert isinstance(suite["version"], int) and suite["version"] >= 1, "suite version"
    assert suite["sha256"] == suite_digest(cases), \
        f"the suite changed: give it version {suite['version'] + 1} and the digest {suite_digest(cases)} (conformance README)"
    assert f"suite version {suite['version']}" in (HERE / "README.md").read_text(), "the conformance README states another suite version"
    every = cases["checks"] + cases["contexts"] + cases["impacts"] + cases["histories"] + cases["sarif"] + cases["schemas"]
    ids = [c["id"] for c in every]
    assert len(ids) == len(set(ids)), "duplicate case ID"
    # Each case and span vector names requirements the text defines, or annexes and sections it anchors.
    named = lambda r: r in defined or (re.fullmatch(r"Annex [A-L](\.\d+)?", r) and f'<a id="{r.replace(" ", "-")}"></a>' in spec)
    for case in every + [c for name in SPAN_VECTORS for c in load(VECTORS / name)]:
        for requirement in case["requirements"]:
            assert named(requirement), f"{case['id']}: unknown requirement {requirement}"
    # The official profiles (OSTF-121) are published files, and the cases that use one carry it byte for byte.
    profiles = {path.name: path.read_text() for path in (DRAFT / "profiles").glob("*.yaml")}
    assert sorted(profiles) == ["security.yaml"], "official profiles"
    for case in cases["checks"]:
        if case["id"].startswith("security-profile-"):
            assert case["files"]["profile.yaml"] == profiles["security.yaml"], f"{case['id']}: profile.yaml is not profiles/security.yaml"
    for case in cases["checks"]:
        analysis = reader.Analysis(case_files(case))
        result, expect = analysis.result(), case["expect"]
        assert codes(result) == expect["codes"], f"{case['id']}: codes {codes(result)} != {expect['codes']}"
        if "links" in expect:
            assert links(result) == expect["links"], f"{case['id']}: links\n got {links(result)}\nwant {expect['links']}"
        if "items" in expect:
            assert [i["id"] for i in result["items"]] == expect["items"], f"{case['id']}: items"
        if "corroboration" in expect:  # Annex E.3: by link identity, for every link that has one
            got = {reader.identity(l): l["corroboration"] for l in result["links"] if "corroboration" in l}
            assert got == expect["corroboration"], f"{case['id']}: corroboration\n got {got}\nwant {expect['corroboration']}"
        if "linkCount" in expect:
            assert len(result["links"]) == expect["linkCount"], f"{case['id']}: link count"
        if "risk" in expect:
            assert [i["id"] for i in result["items"] if i["riskRelevant"]] == expect["risk"], f"{case['id']}: risk relevance"
        for key, anchors in expect.get("hints", {}).items():  # OSTF-132: the anchors a hint must name, or no hint
            code, subject = key.split(" ", 1)
            found = [d for d in result["diagnostics"] if d["code"] == code and d.get("subject") == subject]
            assert len(found) == 1, f"{case['id']}: one {key}, found {len(found)}"
            assert ("hint" in found[0]) == bool(anchors) and all(a in found[0].get("hint", "") for a in anchors), \
                f"{case['id']}: hint of {key}: {found[0].get('hint')!r}, want {anchors}"
        for code, files in expect.get("diagnosticFiles", {}).items():
            assert sorted({d.get("file") for d in result["diagnostics"] if d["code"] == code}) == files, f"{case['id']}: files of {code}"
        for code, subjects in expect.get("diagnosticSubjects", {}).items():  # Annex D.2, by bytes, null for none
            got = sorted({d.get("subject") for d in result["diagnostics"] if d["code"] == code}, key=lambda s: (s is not None, (s or "").encode()))
            assert got == subjects, f"{case['id']}: subjects of {code}\n got {got}\nwant {subjects}"
    for case in cases["contexts"]:
        analysis = reader.Analysis(case["files"])
        result, resolved = reader.context(analysis, case["context"])
        expect = case["expect"]
        got = {"resolved": resolved, "codes": codes(result), "items": [i["id"] for i in result["items"]],
               "links": [reader.identity(l) for l in result["links"]]}
        if "text" in expect:
            got["text"] = reader.render(analysis, case["context"])
        assert got == expect, f"{case['id']}:\n got {got}\nwant {expect}"
    for case in cases["impacts"]:
        # The result of check --base: impact, and the nested roots evaluated on their own (OSTF-102).
        result = reader.check_base(reader.Analysis(case["base"]), reader.Analysis(case["files"]), case["rev"])
        got = result.get("impact")
        assert got == case["expect"]["impact"], f"{case['id']}:\n got {got}\nwant {case['expect']['impact']}"
        assert codes(result) == case["expect"]["codes"], f"{case['id']}: codes {codes(result)}"
        for key, anchors in case["expect"].get("hints", {}).items():  # OSTF-132 under a base view, by text
            code, subject = key.split(" ", 1)
            found = [d for d in result["diagnostics"] if d["code"] == code and d.get("subject") == subject]
            assert len(found) == 1 and ("hint" in found[0]) == bool(anchors) and all(a in found[0].get("hint", "") for a in anchors), \
                f"{case['id']}: hint of {key}: {[d.get('hint') for d in found]}, want {anchors}"
        # D.3: exactly the items that a context names carry their text in the result.
        named = {i for c in (got or {}).get("contexts", []) for i in c["items"]}
        assert {i["id"] for i in result["items"] if "text" in i} == {i for i in named if "text" in reader.Analysis(case["files"]).items[i]}, \
            f"{case['id']}: items with their text"
    valid_sarif = sarif_validator()
    try:  # a nested rule of the schema, reached through its references, is enforced
        valid_sarif({"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "x"}}, "results": [
            {"ruleId": "BROKEN_LINK", "level": "fatal", "message": {"text": "x"}}]}]}, "a level outside SARIF")
        raise RuntimeError("the SARIF schema accepted level fatal")
    except AssertionError:
        pass
    for case in cases["sarif"]:
        analysis = reader.Analysis(case["files"])
        result = analysis.result()
        result["diagnostics"] = [d for d in result["diagnostics"] if not d["code"].startswith(reader.OWN_PREFIX)]
        log = reader.sarif(analysis, result)
        valid_sarif(log, case["id"])
        assert log["version"] == "2.1.0" and len(log["runs"]) == 1, f"{case['id']}: one SARIF 2.1.0 run"
        run_ = log["runs"][0]
        rules = [r["id"] for r in run_["tool"]["driver"]["rules"]]
        got = {"rules": rules, "diagnostics": []}
        for row, diagnostic in zip(run_["results"], result["diagnostics"]):
            location = (row.get("locations") or [{}])[0]
            assert location.get("physicalLocation", {}).get("artifactLocation", {}).get("uri") == \
                (urllib.parse.quote(diagnostic["file"], safe="/") if "file" in diagnostic else None), f"{case['id']}: diagnostic uri"
            assert (location.get("logicalLocations") or [{}])[0].get("fullyQualifiedName") == diagnostic.get("subject"), f"{case['id']}: subject"
            assert row.get("properties", {}).get("ostf.hint") == diagnostic.get("hint"), f"{case['id']}: hint"
        for row in run_["results"]:
            assert row["ruleId"] in rules and row["message"]["text"], f"{case['id']}: rule and message of {row}"
            assert not re.search(r"[{}]", row["message"]["text"].replace("{{", "").replace("}}", "")), f"{case['id']}: undoubled brace"
            got["diagnostics"].append([row["ruleId"], row["level"]])
        got["diagnostics"].sort()
        assert rules == sorted(rules, key=str.encode) and got == case["expect"], f"{case['id']}:\n got {got}\nwant {case['expect']}"
    counts["checkCases"], counts["contextCases"] = len(cases["checks"]), len(cases["contexts"])
    counts["impactCases"], counts["sarifCases"] = len(cases["impacts"]), len(cases["sarif"])
    counts["schemaCases"] = len(cases["schemas"])  # run by fixtures_test.go

    # Inputs that JSON cases cannot carry, and limits that must not crash the reader.
    bad = reader.Analysis({"trace.yaml": 'ostf: "0.3"\nitems:\n  - id: R-A\n    text: A.\n', "a.go": b"package a\n// @req R-A \xff\nfunc F() {}\n"})
    assert codes(bad.result()) == ["PARSE_ERROR"], "invalid UTF-8 in Go source"
    chain = 'ostf: "0.3"\nitems:\n' + "".join(f"  - id: R-{i}\n    text: Step {i}.\n" + (f"    refines: [R-{i + 1}]\n" if i < 1199 else "") for i in range(1200))
    deep = reader.Analysis({"trace.yaml": chain})
    assert reader.render(deep, "R-0").count("\n") == 1201, "deep rendering"
    limit = 8 * 1024 * 1024
    head = 'ostf: "0.3"\nitems: []\n'
    assert codes(reader.Analysis({"trace.yaml": head + "#" * (limit - len(head))}).result()) == [], "8 MiB is allowed"
    assert codes(reader.Analysis({"trace.yaml": head + "#" * (limit - len(head) + 1)}).result()) == ["FILE_TOO_LARGE"], "above 8 MiB"
    minimal_files = {path: (DRAFT / "fixtures" / "minimal" / path).read_bytes() for path in ("trace.yaml", "math.go", "math_test.go")}
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
    log = reader.sarif(many, many.result())
    valid_sarif(log, "unlinked statements")
    run_ = log["runs"][0]
    assert {"id": reader.UNLINKED} in run_["tool"]["driver"]["rules"] and \
        [r["level"] for r in run_["results"] if r["ruleId"] == reader.UNLINKED] == ["note"], "unlinked statements in SARIF"
    counts["directChecks"] = 7

    # Every requirement and Annex D code has a case, or cases.json says why not, so removing a case cannot go unnoticed.
    covered = {r for case in every for r in case["requirements"]}
    covered |= {r for name in SPAN_VECTORS for case in load(VECTORS / name) for r in case["requirements"]}
    covered |= {code for case in cases["checks"] + cases["contexts"] + cases["impacts"] for code in case["expect"]["codes"]}
    covered |= {"PARSE_ERROR", "FILE_TOO_LARGE"}
    # The codes of Annex D.1 and the one of the optional Annex E, each a table row of the same form.
    code_row = r"^\| `([A-Z_]+)` \| (?:error|warning|info) \|"
    annex_e = set(re.findall(code_row, re.search(r"\n## Annex E .*?\n## Annex F ", spec, re.S)[0], re.MULTILINE))
    annex_d = set(re.findall(code_row, re.search(r"\n## Annex D .*?\n## Annex E ", spec, re.S)[0], re.MULTILINE))
    assert len(annex_d) == 34 and annex_e == {"DERIVED_INVALID"}, "Annex D.1 and Annex E.4 codes"
    annex_d |= annex_e
    for name, reason in cases["notCovered"].items():
        assert name in defined | annex_d and reason.strip(), f"notCovered {name}: not a requirement or code, or no reason"
    for name in sorted(defined | annex_d):
        assert (name in covered) != (name in cases["notCovered"]), f"{name}: needs a case or a reason in notCovered, not both"

    # Annex F command line: exit codes, root selection and TARGET kept as given.
    script = str(HERE / "reader.py")

    def run(cwd, *args):
        done = subprocess.run([sys.executable, script, *args], cwd=cwd, capture_output=True, text=True)
        return done.returncode, done.stdout

    assert run(DRAFT / "example", "check")[0] == 0, "check exit 0"
    code, out = run(DRAFT, "context", "example/refund.go#CheckRefundLimit", "--format", "json")
    assert code == 0 and json.loads(out)["context"] == "example/refund.go#CheckRefundLimit", "TARGET kept as given"
    assert [i["id"] for i in json.loads(out)["items"]] == ["N-REFUNDS", "R-REFUND-LIMIT", "RISK-REFUND-ABUSE"], "root from TARGET"
    assert run(DRAFT / "example", "context", "R-NOPE")[0] == 1, "context exit 1"
    # A path that does not resolve gets a hint spelled from the working directory, which F.3 reads it from.
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
        (tree / "sub" / "a.go").write_text("package a\n")
        assert run(tree, "check")[0] == 1, "check exit 1 on a broken link"
        os.remove(tree / "trace.yaml")
        assert run(tree, "check")[0] == 2, "check exit 2 without a root"
    with tempfile.TemporaryDirectory() as temp:
        tree = pathlib.Path(temp)
        for name, data in minimal_files.items():
            (tree / name).write_bytes(data)
        code, out = run(tree, "check")
        assert code == 0 and out == "1 items, 2 links\n", "text check counts items and links"
        # OSTF-102 and F.1: a nested root shows in the text of check, which still passes.
        (tree / "svc").mkdir()
        (tree / "svc" / "trace.yaml").write_text('ostf: "0.3"\nitems: []\n')
        code, out = run(tree, "check")
        assert code == 0 and any("NESTED_ROOT" in line and "svc/trace.yaml" in line for line in out.splitlines()), "text check names a nested root"
        # OSTF-102: with a base, a nested root that fails its own check fails the top-level one.
        (tree / "svc" / "trace.yaml").write_text('ostf: "0.3"\nitems:\n  - id: S-A\n    text: A.\n    refines: [S-NOPE]\n')
        code, out = run(tree, "check", "--base", "main", "--base-tree", str(tree))
        assert code == 1 and "NESTED_ROOT_FAILED svc/trace.yaml" in out and run(tree, "check")[0] == 0, "check --base fails on a failing nested root"
        os.remove(tree / "svc" / "trace.yaml")
        # With --root, an anchor outside the root is in no file of the view (Annex F.3).
        (tree / "elsewhere").mkdir()
        code, out = run(tree / "elsewhere", "context", "math.go#Add", "--root", "..", "--format", "json")
        assert code == 1 and json.loads(out)["items"] == [], "context TARGET outside --root does not resolve"
        assert json.loads(out)["diagnostics"][0].get("hint", "").endswith("try ../math.go#Add"), "context hint with --root"
    # check --base and SARIF on an edited copy of the example, as an agent would run them.
    with tempfile.TemporaryDirectory() as temp:
        tree = pathlib.Path(temp) / "example"
        shutil.copytree(DRAFT / "example", tree)
        (tree / "refund.go").write_bytes(edited["refund.go"])
        assert run(tree, "check", "--base", "main")[0] == 2, "check --base outside a Git checkout exits 2"
        code, out = run(tree, "check", "--base", "main", "--base-tree", str(DRAFT / "example"), "--format", "json")
        assert code == 0 and json.loads(out)["impact"] == spec_impact, "check --base on the edited example lists the change and passes"
        code, out = run(tree, "check", "--base", "main", "--base-tree", str(DRAFT / "example"))
        assert code == 0 and "\nrefund.go#CheckRefundLimit\n  implements R-REFUND-LIMIT: Refund limit (corroborated)\n" in out, \
            "the text of check --base renders each context (Annex G)"
        # Annex I.1: ndjson is the json result, one record per line, after the version line.
        code, out = run(tree, "check", "--base", "main", "--base-tree", str(DRAFT / "example"), "--format", "ndjson")
        rows = [json.loads(line) for line in out.splitlines()]
        rebuilt = {"ostf": rows[0]["ostf"], "diagnostics": [], "items": [], "links": []}
        for row in rows[1:]:
            (kind, value), = row.items()
            if kind == "impact":
                rebuilt["impact"] = value
            else:
                rebuilt[{"diagnostic": "diagnostics", "item": "items", "link": "links"}[kind]].append(value)
        assert code == 0 and rows[0] == {"ostf": "0.3"} and out.endswith("\n") and \
            rebuilt == json.loads(run(tree, "check", "--base", "main", "--base-tree", str(DRAFT / "example"), "--format", "json")[1]), "check --format ndjson"
        code, out = run(tree, "check", "--format", "sarif")
        assert code == 0 and json.loads(out)["runs"][0]["results"] == [], "check --format sarif"
        valid_sarif(json.loads(out), "check --format sarif")
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
    counts["commandLine"] = 22

    # Annex F.3: change information, from scripted Git histories run through the command line. Each commit has
    # its own subject, and every commit identifier in the output, whole or cut to 12 characters, is replaced by
    # its subject before comparing, so that a case holds whatever object format, names and dates Git uses.
    for case in cases["histories"]:
        with tempfile.TemporaryDirectory() as temp:
            checkout, ids = scripted_history(case, pathlib.Path(temp))
            where = checkout / case.get("root", ".")
            args = [ids.get(arg, arg) for arg in case["run"]]
            code, out = run(where, *args, "--format", "json")
            assert code in (0, 1), f"{case['id']}: exit {code}"
            for subject, commit in ids.items():
                out = out.replace(commit, subject)
            result = json.loads(out)
            got = {"changes": {reader.identity(l): [l.get("sourceChangedIn"), l.get("targetChangedIn")] for l in result["links"]
                               if "sourceChangedIn" in l or "targetChangedIn" in l}}
            if "text" in case["expect"]:
                text = run(where, *args)[1]
                for subject, commit in ids.items():
                    text = text.replace(commit, subject).replace(commit[:12], subject)
                got["text"] = text
            assert got == case["expect"], f"{case['id']}:\n got {got}\nwant {case['expect']}"
    counts["historyCases"] = len(cases["histories"])
    return {"wireVersion": "0.3", "suiteVersion": load(HERE / "cases.json")["suite"]["version"],
            "implementation": "independent-code-python-reader", "counts": counts,
            "passed": True, "independentParty": False, "fullConformance": False}


if __name__ == "__main__":
    try:
        print(json.dumps(check(), sort_keys=True))
    except AssertionError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
