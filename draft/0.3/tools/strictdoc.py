#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Import StrictDoc documents into OSTF 0.3.

    python3 strictdoc.py import OSTF_DIR FILE.sdoc...

Each node with a UID becomes an item: TITLE is its `title`, STATEMENT its `text`, RATIONALE
its `rationale`; STATUS Draft is `draft`, Deleted `obsolete`; TAGS become the list attribute
`tags`, and other fields become attributes when their names are valid OSTF attribute names.
A Parent relation becomes `refines`, a Child relation the child's `refines`, and a File
relation a whole-file `code` anchor. The titles of the enclosing [[SECTION]] nodes form the
item's `section`. Comments, levels and relation roles are kept in `x-strictdoc`. Nodes
without a UID and [TEXT] nodes are not imported; see README.md for what is lost.

Writes OSTF_DIR/strictdoc/<document>.yaml per file and, when missing, OSTF_DIR/trace.yaml
including them. Only PyYAML is needed.
"""
import argparse
import pathlib
import re
import sys

import yaml

FIELD = re.compile(r"([A-Za-z_][A-Za-z0-9_]*): ?(.*)\Z")
ATTRIBUTE_NAME = re.compile(r"[A-Za-z][A-Za-z0-9]{0,47}\Z")
STATUS = {"Draft": "draft", "Active": None, "Deleted": "obsolete"}


class Dumper(yaml.SafeDumper):
    """Writes multi-line strings as literal blocks, as people write them."""


Dumper.add_representer(str, lambda dumper, value: dumper.represent_scalar(
    "tag:yaml.org,2002:str", value, style="|" if "\n" in value else None))


def parse(text):
    """The nodes of an SDoc file: (kind, fields, relations, section titles) in order. Fields
    keep their order and may repeat; a relation is a mapping of TYPE, VALUE and ROLE."""
    nodes, sections, lines = [], [], text.splitlines()
    i, current = 0, None
    while i < len(lines):
        line = lines[i]
        i += 1
        if re.fullmatch(r"\[\[/[A-Z_]+\]\]", line):
            if sections:
                sections.pop()
            current = None
            continue
        opening = re.fullmatch(r"(\[\[?)([A-Z_]+)\]\]?", line)
        if opening:
            current = {"kind": opening[2], "fields": [], "relations": [], "sections": [s for s in sections if isinstance(s, str)]}
            if opening[1] == "[[":
                # Every composite nests; only a SECTION's TITLE names a section.
                sections.append(None if opening[2] == "SECTION" else False)
                current["composite"] = True
            nodes.append(current)
            continue
        if current is None or not line.strip():
            continue
        if line == "RELATIONS:":
            while i < len(lines) and lines[i].startswith(("- ", "  ")):
                entry = lines[i]
                i += 1
                key, _, value = entry[2:].partition(": ")
                if entry.startswith("- "):
                    current["relations"].append({})
                current["relations"][-1][key.strip()] = value.strip()
            continue
        match = FIELD.match(line)
        if not match:
            continue
        name, value = match[1], match[2]
        if value == ">>>":
            body = []
            while i < len(lines) and lines[i] != "<<<":
                body.append(lines[i])
                i += 1
            i += 1
            value = "\n".join(body)
        current["fields"].append((name, value))
        if current.get("composite") and name == "TITLE" and sections and sections[-1] is None:
            sections[-1] = value
    return nodes


def import_files(target, files):
    target.mkdir(parents=True, exist_ok=True)
    (target / "strictdoc").mkdir(exist_ok=True)
    losses, documents, by_id = [], [], {}
    for path in files:
        items = []
        for node in parse(path.read_text(encoding="utf-8")):
            fields = node["fields"]
            uid = next((v for k, v in fields if k == "UID"), None)
            if node["kind"] == "DOCUMENT" or node.get("composite") and node["kind"] == "SECTION":
                continue
            if uid is None:
                losses.append(f"{path.name}: a [{node['kind']}] node without a UID is not imported")
                continue
            item, keep, attributes = {"id": uid}, {}, {}
            if node["kind"] not in ("REQUIREMENT", "SECTION"):
                keep["node"] = node["kind"]
            for name, value in fields:
                if name == "UID":
                    continue
                if name == "TITLE":
                    item["title"] = value
                elif name == "STATEMENT":
                    item["text"] = value
                elif name == "RATIONALE":
                    item["rationale"] = value
                elif name == "STATUS" and value in STATUS:
                    if STATUS[value]:
                        item["status"] = STATUS[value]
                elif name == "TAGS":
                    attributes["tags"] = [t.strip() for t in value.split(",") if t.strip()]
                elif name in ("COMMENT", "LEVEL", "MID") or not ATTRIBUTE_NAME.match(name):
                    keep.setdefault(name.lower(), []).append(value)
                else:
                    attributes[name] = value
            if "text" not in item:
                item["text"] = ""
            if node["sections"]:
                item["section"] = " / ".join(node["sections"])
            for relation in node["relations"]:
                kind = relation.get("TYPE")
                if relation.get("ROLE"):
                    keep.setdefault("roles", []).append(relation)
                if kind == "Parent":
                    item.setdefault("refines", []).append(relation.get("VALUE"))
                elif kind == "Child":
                    item.setdefault("x-children", []).append(relation.get("VALUE"))
                elif kind == "File":
                    # StrictDoc writes PATH, and VALUE in older files; a selector narrows nothing here.
                    file = relation.get("PATH") or relation.get("VALUE")
                    if not file:
                        losses.append(f"{uid}: a File relation without a path is not imported")
                        continue
                    item.setdefault("code", []).append(file)
                    for selector in sorted(set(relation) - {"TYPE", "PATH", "VALUE", "ROLE"}):
                        losses.append(f"{uid}: the {selector} of File relation {file} is not kept; the anchor names the whole file")
                else:
                    losses.append(f"{uid}: a {kind} relation has no OSTF form")
            if attributes:
                item["attributes"] = attributes
            if keep:
                item["x-strictdoc"] = keep
            items.append(item)
            by_id[uid] = item
        documents.append((path, items))
    for _, items in documents:  # Child relations resolve across every file read
        for item in items:
            for child in item.pop("x-children", []):
                if child in by_id:
                    by_id[child].setdefault("refines", []).append(item["id"])
                else:
                    losses.append(f"{item['id']}: child {child} is in none of the files read")
    for path, items in documents:
        out = {"ostf": "0.3", "x-strictdoc": {"file": path.name}, "items": items}
        (target / "strictdoc" / f"{path.stem}.yaml").write_text(
            yaml.dump(out, Dumper=Dumper, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")
    root = target / "trace.yaml"
    if not root.exists():
        root.write_text('ostf: "0.3"\ninclude: ["strictdoc/*.yaml"]\n', encoding="utf-8")
    return losses


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    importer = commands.add_parser("import")
    importer.add_argument("target", type=pathlib.Path)
    importer.add_argument("files", nargs="+", type=pathlib.Path)
    args = parser.parse_args(argv)
    for loss in import_files(args.target, args.files):
        print("loss:", loss, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
