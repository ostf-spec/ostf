#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check the converters on their samples: Doorstop to OSTF and back, StrictDoc to OSTF.

Run by ../conformance/run.py after the reader checks. The Doorstop sample was written and
validated with Doorstop 3.2 and the StrictDoc sample with StrictDoc 0.30.4; neither tool
is needed here.
"""
import pathlib
import shutil
import sys
import tempfile

import yaml

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "conformance"))
import doorstop  # noqa: E402
import reader  # noqa: E402
import strictdoc  # noqa: E402

SAMPLES = HERE / "samples"


def ostf_links(root):
    analysis = reader.Analysis(reader.Tree(root))
    result = analysis.result()
    errors = [d for d in result["diagnostics"] if d["severity"] == "error"]
    assert not errors, f"{root}: {errors}"
    return sorted(reader.identity(l) for l in result["links"]), {i["id"]: i["status"] for i in result["items"]}


def yml_files(root):
    return {p.relative_to(root).as_posix(): yaml.safe_load(p.read_text(encoding="utf-8")) for p in root.rglob("*.yml")}


def check():
    with tempfile.TemporaryDirectory() as temp:
        temp = pathlib.Path(temp)
        sample = SAMPLES / "doorstop"
        imported = temp / "ostf"
        shutil.copytree(sample / "src", imported / "src")
        shutil.copytree(sample / "tests", imported / "tests", ignore=shutil.ignore_patterns("doc"))
        doorstop.import_tree(sample, imported, {"SYS": "need", "TST": "verification"})
        links, statuses = ostf_links(imported)
        assert links == ["REQ001 refines SYS001", "REQ002 refines SYS001", "REQ003 refines SYS002", "TST001 verifies REQ001",
                         "TST001 verifies REQ002", "src/payments.py implements REQ001", "tests/test_payments.py verifies TST001"], links
        assert statuses["REQ003"] == "obsolete" and statuses["REQ001"] == "accepted", statuses
        exported = temp / "back"
        doorstop.export_tree(imported, exported)
        assert yml_files(exported) == yml_files(sample), "Doorstop round trip"
        # An item added in OSTF exports to the document of its prefix's file.
        path = imported / "doorstop" / "REQ.yaml"
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        document["items"].append({"id": "REQ005", "title": "Receipts", "text": "Every charge has a receipt.\n", "refines": ["SYS001"]})
        path.write_text(doorstop.dump(document), encoding="utf-8")
        doorstop.export_tree(imported, temp / "back2")
        added = yaml.safe_load((temp / "back2" / "reqs" / "req" / "REQ005.yml").read_text(encoding="utf-8"))
        assert added["links"] == [{"SYS001": None}] and added["header"] == "Receipts\n" and added["active"] is True, added

        sample = SAMPLES / "strictdoc"
        imported = temp / "sd"
        shutil.copytree(sample / "src", imported / "src")
        losses = strictdoc.import_files(imported, [sample / "shop.sdoc"])
        links, statuses = ostf_links(imported)
        assert links == ["SHOP-2 refines SHOP-1", "SHOP-3 refines SHOP-1", "src/payments.py implements SHOP-2"], links
        assert statuses == {"SHOP-1": "accepted", "SHOP-2": "draft", "SHOP-3": "obsolete"}, statuses
        assert len(losses) == 2, losses

        # Review findings: references sharing a path survive the round trip, and export names
        # what it drops.
        shutil.copytree(SAMPLES / "doorstop", temp / "ds2")
        item = temp / "ds2" / "reqs" / "req" / "REQ001.yml"
        data = yaml.safe_load(item.read_text(encoding="utf-8"))
        data["references"] = [{"path": "src/payments.py", "type": "file", "keyword": "first"}, {"path": "src/payments.py", "type": "file", "keyword": "second"}]
        item.write_text(yaml.safe_dump(data), encoding="utf-8")
        doorstop.import_tree(temp / "ds2", temp / "ostf2", {})
        document = yaml.safe_load((temp / "ostf2" / "doorstop" / "REQ.yaml").read_text(encoding="utf-8"))
        document["items"][0]["status"] = "draft"
        (temp / "ostf2" / "doorstop" / "REQ.yaml").write_text(doorstop.dump(document), encoding="utf-8")
        losses = doorstop.export_tree(temp / "ostf2", temp / "back3")
        back = yaml.safe_load((temp / "back3" / "reqs" / "req" / "REQ001.yml").read_text(encoding="utf-8"))
        assert [r["keyword"] for r in back["references"]] == ["first", "second"], back["references"]
        assert any("status draft" in loss for loss in losses), losses

        # StrictDoc: PATH relations, Child relations across files, composite nodes that are not
        # sections, and mixed-case field names.
        (temp / "a.sdoc").write_text("[DOCUMENT]\nTITLE: A\n\n[[REQUIREMENT]]\nUID: P\nTITLE: Parent\nSTATEMENT: Parent.\nPriority: High\nRELATIONS:\n- TYPE: Child\n  VALUE: C\n- TYPE: File\n  PATH: src/payments.py\n  FUNCTION: charge\n\n[REQUIREMENT]\nUID: Q\nSTATEMENT: Inside.\n\n[[/REQUIREMENT]]\n", encoding="utf-8")
        (temp / "b.sdoc").write_text("[DOCUMENT]\nTITLE: B\n\n[REQUIREMENT]\nUID: C\nSTATEMENT: Child.\n", encoding="utf-8")
        shutil.copytree(SAMPLES / "strictdoc" / "src", temp / "sd2" / "src")
        losses = strictdoc.import_files(temp / "sd2", [temp / "a.sdoc", temp / "b.sdoc"])
        a = {i["id"]: i for i in yaml.safe_load((temp / "sd2" / "strictdoc" / "a.yaml").read_text(encoding="utf-8"))["items"]}
        b = {i["id"]: i for i in yaml.safe_load((temp / "sd2" / "strictdoc" / "b.yaml").read_text(encoding="utf-8"))["items"]}
        assert a["P"]["code"] == ["src/payments.py"] and any("FUNCTION" in loss for loss in losses), (a["P"], losses)
        assert b["C"]["refines"] == ["P"], b["C"]
        assert "section" not in a["Q"], a["Q"]
        assert a["P"]["attributes"]["Priority"] == "High", a["P"]
    return {"doorstopRoundTrip": True, "strictdocImport": True}


if __name__ == "__main__":
    try:
        print(check())
    except AssertionError as error:
        print(error, file=sys.stderr)
        sys.exit(1)
