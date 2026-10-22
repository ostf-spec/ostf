#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run fixed draft vectors through the independent-code Python analyzer."""
import json
import importlib.metadata
import pathlib
import re
import sys

import reader

HERE = pathlib.Path(__file__).resolve().parent


def load(name):
    return json.loads((HERE / name).read_text())


def check():
    for name, version in re.findall(r"^([A-Za-z0-9_-]+)==([^\s]+)", (HERE / "requirements.txt").read_text(), re.MULTILINE):
        assert importlib.metadata.version(name) == version, f"unexpected installed tool version: {name}"
    suite = load("suite.json")
    assert suite["suiteVersion"] == "0.1.3" and suite["wireVersion"] == "0.1"
    all_cases = [case for name in suite["files"] for case in load(name)]
    ids = [case["id"] for case in all_cases]
    assert len(set(ids)) == len(ids), "duplicate conformance case ID"
    defined = set(re.findall(r"\*\*(OSTF-\d{3}):", (HERE.parent / "draft/core.md").read_text()))
    assert defined == set(suite["requirements"]), "contract and suite requirement IDs differ"
    for identity, mapping in suite["requirements"].items():
        assert mapping["cases"] or mapping.get("disposition"), f"unmapped requirement {identity}"
        assert all(case in ids for case in mapping["cases"]), f"missing case for {identity}"
        actual = {case["id"] for case in all_cases if identity in case["requirements"]}
        assert actual == set(mapping["cases"]), f"incorrect reverse mapping for {identity}"
    for case in all_cases:
        assert set(case["requirements"]) <= defined, f"unknown requirement in {case['id']}"
    counts = {}
    for case in load("item-vectors.json"):
        canonical = reader.item_projection(case["item"], case["types"])
        assert canonical.decode() == case["canonical"], case["id"] + ": canonical bytes"
        assert reader.fingerprint("f1", canonical) == case["fingerprint"], case["id"] + ": item hash"
    counts["itemVectors"] = len(load("item-vectors.json"))
    for case in load("code-vectors.json"):
        got = reader.code_fingerprint(case["path"], case["symbol"], case["source"].encode())
        assert got == case["expect"], f"{case['id']}: {got} != {case['expect']}"
        definitions, whole, _ = reader.go_source(case["source"].encode())
        if not case["symbol"]:
            sig, body = whole, None
        else:
            selected = [d for d in definitions if d["name"] == case["symbol"]]
            if not selected and "." not in case["symbol"]:
                selected = [d for d in definitions if d["name"].split(".")[-1] == case["symbol"]]
            sig = b" ".join(d["sig"] for d in selected)
            body = b" ".join(d["body"] for d in selected)
        assert sig.decode() == case["sigTokens"], case["id"] + ": signature token bytes"
        assert (body.decode() if body is not None else None) == case["bodyTokens"], case["id"] + ": body token bytes"
    counts["goVectors"] = len(load("code-vectors.json"))
    for case in load("lock-vectors.json"):
        entries, errors = reader.parse_lock(case["text"])
        assert errors == case["errors"], case["id"] + ": lock errors"
        if not errors:
            lines = [reader.lock_key(entry) + "".join(" " + k + "=" + reader.lock_escape(entry["fingerprints"][k]) for k in reader.FINGERPRINT_KEYS if k in entry["fingerprints"]) for entry in entries.values()]
            canonical = "trace.lock 1\n" + "".join(line + "\n" for line in sorted(lines))
            assert canonical == case["canonical"], case["id"] + ": lock bytes"
    counts["lockVectors"] = len(load("lock-vectors.json"))
    for case in load("repositories.json"):
        result = reader.analyze(case["files"])
        assert "unsupported" not in result, f"{case['id']}: {result}"
        for field, expected in case["expect"].items():
            assert result.get(field) == expected, f"{case['id']}: {field}\ngot {result.get(field)}\nexpected {expected}"
    counts["repositoryCases"] = len(load("repositories.json"))

    example = HERE.parent / "examples/minimal"
    files = {name: (example / name).read_text() for name in ("trace.yaml", "trace.lock", "math.go", "math_test.go")}
    result = reader.analyze(files)
    assert result["errorCodes"] == [] and result["warningCodes"] == [], "worked example diagnostics"
    assert [(link["source"], link["state"]) for link in result["links"]] == [
        ("math.go#Add", "valid"), ("math_test.go#TestAdd", "valid")
    ], "worked example links"
    counts["workedExample"] = 1

    # Fail visibly for unsupported features, rather than reporting a false pass.
    unsupported = [
        {"trace.yaml": 'ostf: "0.1"\nprofile: iec62304\nitems: []\n'},
        {"trace.yaml": 'ostf: "0.1"\nitems: [{id: R-A, text: A, code: [main.ts#Run]}]\n', "main.ts": "function Run() {}"},
        {"trace.yaml": 'ostf: "0.1"\nprofile: profile.yaml\nitems: []\n', "profile.yaml": 'ostf: "0.1"\nextends: default\nriskMatrix: {}\n'},
        {"trace.yaml": 'ostf: "0.1"\nprofile: profile.yaml\nitems: []\n', "profile.yaml": 'ostf: "0.1"\nextends: default\nintegrity: {}\n'},
    ]
    for files in unsupported:
        assert "unsupported" in reader.analyze(files), "unsupported construct silently passed"
    counts["unsupportedGuards"] = len(unsupported)
    return {"suiteVersion": suite["suiteVersion"], "wireVersion": suite["wireVersion"], "implementation": "independent-code-python-prototype", "claim": suite["claim"], "counts": counts, "toolVersions": {name: importlib.metadata.version(name) for name in ("PyYAML", "tree-sitter", "tree-sitter-go", "rfc8785")}, "passed": True, "independentParty": False, "fullCoreConformance": False}


if __name__ == "__main__":
    try:
        print(json.dumps(check(), sort_keys=True))
    except (AssertionError, ValueError, reader.Unsupported) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
