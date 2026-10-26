#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Convert between a Doorstop tree and OSTF 0.3, in both directions.

    python3 doorstop.py import DOORSTOP_DIR OSTF_DIR [--type PREFIX=TYPE ...]
    python3 doorstop.py export OSTF_DIR DOORSTOP_DIR

`import` writes OSTF_DIR/trace.yaml and one item file per Doorstop document under
OSTF_DIR/doorstop/. Each Doorstop item becomes an item with the same UID, its header as
`title`, its text as `text`, its links as `refines` (or `verifies` from a `verification`
item) and its file references as whole-file `code` anchors (`tests` for a verification
item); an inactive item is `obsolete`. What OSTF has no field for is kept in `x-doorstop`,
so `export` rebuilds the tree. See README.md in this directory for what is lost.

Paths in Doorstop references are taken relative to OSTF_DIR, which is normally the
repository root that Doorstop also uses. Only PyYAML is needed.
"""
import argparse
import pathlib
import sys

import yaml

DOCUMENT = ".doorstop.yml"
STANDARD = {"active", "derived", "header", "level", "links", "normative", "ref", "references", "reviewed", "text"}
ATTRIBUTE_NAME = __import__("re").compile(r"[A-Za-z][A-Za-z0-9]{0,47}\Z")


class Dumper(yaml.SafeDumper):
    """Writes multi-line strings as literal blocks, as people write them."""


Dumper.add_representer(str, lambda dumper, value: dumper.represent_scalar(
    "tag:yaml.org,2002:str", value, style="|" if "\n" in value.rstrip("\n") or (value.endswith("\n") and value.strip()) else None))


def dump(value):
    return yaml.dump(value, Dumper=Dumper, sort_keys=False, allow_unicode=True, width=1000)


def attribute_ok(value):
    """OSTF-114: a string, a finite number, a boolean or a list of strings."""
    if isinstance(value, bool) or isinstance(value, str):
        return True
    if isinstance(value, (int, float)):
        return value == value and value not in (float("inf"), float("-inf"))
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def documents(root):
    """Doorstop documents under root: (directory, settings, items by UID), in path order."""
    found = []
    for config in sorted(root.rglob(DOCUMENT)):
        if any(part.startswith(".") and part != DOCUMENT for part in config.relative_to(root).parts):
            continue
        settings = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
        prefix = settings.get("settings", {}).get("prefix", "")
        items = {}
        for path in sorted(config.parent.glob("*.yml")):
            if path.name != DOCUMENT and path.stem.startswith(prefix):
                items[path.stem] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        found.append((config.parent.relative_to(root), settings, items))
    return found


def import_tree(source, target, types):
    target.mkdir(parents=True, exist_ok=True)
    (target / "doorstop").mkdir(exist_ok=True)
    losses = []
    for directory, settings, items in documents(source):
        prefix = settings["settings"]["prefix"]
        kind = types.get(prefix, "requirement")
        out = []
        for uid, data in items.items():
            item = {"id": uid}
            if kind != "requirement":
                item["type"] = kind
            header = (data.get("header") or "").rstrip("\n")
            if header:
                item["title"] = header
            item["text"] = data.get("text") or ""
            if data.get("active") is False:
                item["status"] = "obsolete"
            parents = [next(iter(link)) if isinstance(link, dict) else link for link in data.get("links") or []]
            if parents:
                item["verifies" if kind == "verification" else "refines"] = parents
            references = data.get("references") or []
            anchors = [r["path"] for r in references if isinstance(r, dict) and r.get("type", "file") == "file" and r.get("path")]
            if anchors:
                item["tests" if kind == "verification" else "code"] = anchors
            extra = {k: v for k, v in data.items() if k not in STANDARD}
            attributes = {k: v for k, v in extra.items() if ATTRIBUTE_NAME.match(k) and attribute_ok(v)}
            if attributes:
                item["attributes"] = attributes
            keep = {"level": data.get("level"), "derived": data.get("derived", False), "normative": data.get("normative", True),
                    "ref": data.get("ref", ""), "reviewed": data.get("reviewed")}
            if references:
                keep["references"] = references
            stamps = {next(iter(link)): next(iter(link.values())) for link in data.get("links") or [] if isinstance(link, dict) and next(iter(link.values()))}
            if stamps:
                keep["link-stamps"] = stamps
            others = {k: v for k, v in extra.items() if k not in attributes}
            if others:
                keep["attributes"] = others
            item["x-doorstop"] = keep
            out.append(item)
            if data.get("reviewed"):
                losses.append(f"{uid}: the review stamp is kept but not checked; in OSTF the pull request rechecks a link")
        document = {"ostf": "0.3", "x-doorstop": {"path": directory.as_posix(), **settings}, "items": out}
        (target / "doorstop" / f"{prefix}.yaml").write_text(dump(document), encoding="utf-8")
    root = target / "trace.yaml"
    if not root.exists():
        root.write_text(dump({"ostf": "0.3", "include": ["doorstop/*.yaml"]}), encoding="utf-8")
    return losses


def export_tree(source, target):
    files = sorted((source / "doorstop").glob("*.yaml"))
    losses = []
    for path in files:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        info = dict(document.get("x-doorstop") or {})
        directory = target / info.pop("path", path.stem)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / DOCUMENT).write_text(dump(info), encoding="utf-8")
        for item in document.get("items") or []:
            keep = item.get("x-doorstop") or {}
            stamps = keep.get("link-stamps") or {}
            parents = item.get("refines", []) + item.get("verifies", [])
            for name in item:
                if name not in {"id", "type", "title", "text", "status", "refines", "verifies", "code", "tests", "attributes", "x-doorstop", "aliases", "section", "rationale"}:
                    losses.append(f"{item['id']}: link type or field {name} has no Doorstop form")
            for unsupported in ("aliases", "section", "rationale"):
                if unsupported in item:
                    losses.append(f"{item['id']}: {unsupported} has no Doorstop form")
            anchors = [a if isinstance(a, str) else a.get("ref") for a in item.get("code", []) + item.get("tests", [])]
            previous = {}
            for reference in keep.get("references") or []:
                if isinstance(reference, dict):
                    previous.setdefault(reference.get("path"), []).append(reference)
            references, seen = [], set()
            for anchor in anchors:
                file, _, symbol = anchor.partition("#")
                if symbol:
                    losses.append(f"{item['id']}: anchor {anchor} keeps only its file")
                if file not in seen:
                    seen.add(file)
                    references += previous.get(file, [{"path": file, "type": "file"}])
            if item.get("status") == "draft":
                losses.append(f"{item['id']}: status draft has no Doorstop form; it exports as active")
            for parent in parents:
                if isinstance(parent, dict) and set(parent) - {"to"}:
                    losses.append(f"{item['id']}: the attributes of its link to {parent['to']} have no Doorstop form")
            data = {
                "active": item.get("status") != "obsolete",
                "derived": keep.get("derived", False),
                "header": item["title"] + "\n" if item.get("title") else "",
                "level": keep.get("level", 1.0),
                "links": [{parent if isinstance(parent, str) else parent["to"]: stamps.get(parent if isinstance(parent, str) else parent["to"])} for parent in parents],
                "normative": keep.get("normative", True),
                "ref": keep.get("ref", ""),
                "reviewed": keep.get("reviewed"),
                "text": item.get("text", ""),
            }
            if references:
                data["references"] = references
            data.update(item.get("attributes") or {})
            data.update(keep.get("attributes") or {})
            (directory / f"{item['id']}.yml").write_text(yaml.safe_dump(dict(sorted(data.items())), allow_unicode=True, width=1000), encoding="utf-8")
    return losses


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    importer = commands.add_parser("import")
    importer.add_argument("source", type=pathlib.Path)
    importer.add_argument("target", type=pathlib.Path)
    importer.add_argument("--type", action="append", default=[], metavar="PREFIX=TYPE")
    exporter = commands.add_parser("export")
    exporter.add_argument("source", type=pathlib.Path)
    exporter.add_argument("target", type=pathlib.Path)
    args = parser.parse_args(argv)
    if args.command == "import":
        losses = import_tree(args.source, args.target, dict(t.split("=", 1) for t in args.type))
    else:
        losses = export_tree(args.source, args.target)
    for loss in losses:
        print("loss:", loss, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
