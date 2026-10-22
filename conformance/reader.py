#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Independent-code draft analyzer. Does not import or execute zztrace.

This is a bounded interoperability probe, not a full Core implementation.
See README.md and ../draft/support.md for unsupported constructs.
"""
from __future__ import annotations

import argparse
import base64
import copy
import fnmatch
import hashlib
import json
import math
import pathlib
import re
import sys
import urllib.parse

import rfc8785
import yaml
from tree_sitter import Language, Parser
import tree_sitter_go

MAX_FILE_BYTES = 8 * 1024 * 1024
ITEM_ID = re.compile(r"[A-Za-z][A-Za-z0-9._-]{0,127}\Z")
TYPE_NAME = re.compile(r"[a-z][a-z0-9-]{0,47}\Z")
LINK_NAME = re.compile(r"[a-z][a-z0-9_]{0,47}\Z")
ATTRIBUTE_NAME = re.compile(r"[a-zA-Z][a-zA-Z0-9]{0,47}\Z")
FINGERPRINT_KEYS = ("source", "source.sig", "source.body", "target")
ITEM_FIELDS = set("id type title text status section rationale aliases derived attributes provenance justifications owners code tests".split())
ROOT_FIELDS = set("ostf profile include code links imports external policy items".split())
PROFILE_FIELDS = set("ostf extends types links coverage riskMatrix integrity idSuffix fingerprints policy".split())
LITERALS = {"interpreted_string_literal", "raw_string_literal", "rune_literal", "int_literal", "float_literal", "imaginary_literal"}
GO = Language(tree_sitter_go.language())


class Unsupported(ValueError):
    """A valid-looking construct outside the prototype's declared support."""


class SafeCoreLoader(yaml.SafeLoader):
    pass


# PyYAML's default scalar resolution is YAML 1.1. Restrict it to Core 1.2.
SafeCoreLoader.yaml_implicit_resolvers = copy.deepcopy(yaml.SafeLoader.yaml_implicit_resolvers)
for char, rules in SafeCoreLoader.yaml_implicit_resolvers.items():
    SafeCoreLoader.yaml_implicit_resolvers[char] = [
        (tag, regex) for tag, regex in rules if tag not in {
            "tag:yaml.org,2002:bool", "tag:yaml.org,2002:timestamp",
            "tag:yaml.org,2002:int", "tag:yaml.org,2002:float",
        }
    ]
SafeCoreLoader.add_implicit_resolver("tag:yaml.org,2002:bool", re.compile(r"^(?:true|false)$"), list("tf"))
SafeCoreLoader.add_implicit_resolver("tag:yaml.org,2002:int", re.compile(r"^[-+]?(?:0|[1-9][0-9]*|0o[0-7]+|0x[0-9a-fA-F]+)$"), list("-+0123456789"))
SafeCoreLoader.add_implicit_resolver("tag:yaml.org,2002:float", re.compile(r"^[-+]?(?:[0-9]+\.[0-9]*|\.[0-9]+|[0-9]+)(?:[eE][-+]?[0-9]+)?$"), list("-+0123456789."))


def _mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in result or key == "<<":
            raise ValueError("duplicate, merge, or non-string mapping key")
        result[key] = loader.construct_object(value_node)
    return result


SafeCoreLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def read_yaml(text):
    if len(text.encode()) > MAX_FILE_BYTES:
        raise ValueError("file exceeds 8 MiB")
    for event in yaml.parse(text):
        if isinstance(event, yaml.events.AliasEvent) or getattr(event, "anchor", None) or getattr(event, "tag", None):
            raise ValueError("aliases, anchors and explicit tags are outside the safe subset")
    value = yaml.load(text, Loader=SafeCoreLoader)
    if not isinstance(value, dict) or value.get("ostf") != "0.1":
        raise ValueError("expected mapping with ostf: 0.1")
    return value


def clean_path(value):
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/") or any(p in {"", ".", ".."} for p in value.split("/")):
        raise ValueError("unclean relative path")
    return value


def match_glob(pattern, path):
    """Match path segments with Go's zero-or-more-directory ** rule."""
    parts, names = pattern.split("/"), path.split("/")

    def match(rest, remaining):
        if not rest:
            return not remaining
        if rest[0] == "**":
            return any(match(rest[1:], remaining[skip:]) for skip in range(len(remaining) + 1))
        return bool(remaining) and fnmatch.fnmatchcase(remaining[0], rest[0].replace("[^", "[!")) and match(rest[1:], remaining[1:])

    return match(parts, names)


def fingerprint(algorithm, data):
    return algorithm + ":" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")


def normalize_text(text):
    return "\n".join(line.rstrip(" \t\r") for line in text.replace("\r\n", "\n").split("\n")).rstrip("\n")


def item_projection(item, types):
    fields = {"type": item.get("type", "requirement")}
    for key in ("title", "text"):
        value = normalize_text(item.get(key, ""))
        if value:
            fields[key] = value
    attributes = {}
    for key, spec in types[fields["type"]].get("attributes", {}).items():
        value = item.get("attributes", {}).get(key)
        if key not in item.get("attributes", {}) or not spec.get("meaning"):
            continue
        if spec["type"] == "text":
            value = normalize_text(value)
        if value != "":
            attributes[key] = value
    if attributes:
        fields["attributes"] = attributes
    return rfc8785.dumps(fields)


def _token_bytes(node, source, start, end):
    tokens = []

    def visit(n):
        if n.end_byte <= start or n.start_byte >= end or n.type == "comment":
            return
        if n.type in LITERALS or not n.children:
            raw = source[max(start, n.start_byte):min(end, n.end_byte)]
            if n.type == "raw_string_literal":
                raw = raw.replace(b"\r", b"")
            if raw:
                tokens.append(raw)
            return
        for child in n.children:
            visit(child)

    visit(node)
    return b" ".join(tokens)


def go_source(source):
    """Independent tree-sitter declarations and token streams."""
    tree = Parser(GO).parse(source)
    if tree.root_node.has_error:
        raise Unsupported("Go syntax not accepted by the independent parser")
    definitions = []
    comments = []

    def collect_comments(n):
        if n.type == "comment":
            comments.append(n)
        else:
            for c in n.named_children:
                collect_comments(c)

    collect_comments(tree.root_node)
    for declaration in tree.root_node.named_children:
        spans = []
        if declaration.type in {"function_declaration", "method_declaration"}:
            name = declaration.child_by_field_name("name").text.decode()
            receiver = declaration.child_by_field_name("receiver")
            if receiver:
                t = receiver.named_children[0].child_by_field_name("type")
                while t.type in {"pointer_type", "generic_type"}:
                    t = t.child_by_field_name("type") or t.named_children[0]
                name = t.text.decode() + "." + name
            body = declaration.child_by_field_name("body")
            spans.append((name, declaration.start_byte, declaration.end_byte, body.start_byte if body else declaration.end_byte))
        elif declaration.type in {"type_declaration", "var_declaration", "const_declaration"}:
            grouped = any(c.type in {"(", "var_spec_list"} for c in declaration.children)
            specs = [c for c in declaration.named_children if c.type in {"type_spec", "type_alias", "var_spec", "const_spec"}]
            # Go's grammar puts grouped var specs in a list node.
            if not specs:
                specs = [s for c in declaration.named_children for s in c.named_children if s.type in {"var_spec", "const_spec"}]
            for spec in specs:
                for name_node in spec.children_by_field_name("name"):
                    start, end = (spec.start_byte, spec.end_byte) if grouped else (declaration.start_byte, declaration.end_byte)
                    spans.append((name_node.text.decode(), start, end, end))
        for name, start, end, header in spans:
            doc_start = start
            for comment in reversed(comments):
                if comment.end_byte <= doc_start:
                    gap = source[comment.end_byte:doc_start]
                    if gap.strip() or gap.count(b"\n") > 1:
                        break
                    doc_start = comment.start_byte
            definitions.append({"name": name, "start": start, "docStart": doc_start, "end": end,
                                "sig": _token_bytes(tree.root_node, source, start, header),
                                "body": _token_bytes(tree.root_node, source, start, end)})
    return definitions, _token_bytes(tree.root_node, source, 0, len(source)), comments


def code_fingerprint(path, symbol, source):
    if not path.endswith(".go"):
        if symbol:
            raise Unsupported("non-Go symbol anchors")
        return {"source.sig": fingerprint("lf1", source.replace(b"\r\n", b"\n"))}
    symbol = symbol.split("/", 1)[0]
    definitions, whole, _ = go_source(source)
    if not symbol:
        return {"source.sig": fingerprint("go1", whole)}
    selected = [d for d in definitions if d["name"] == symbol]
    if not selected and "." not in symbol:
        selected = [d for d in definitions if d["name"].split(".")[-1] == symbol]
    if not selected:
        return None
    return {"source." + kind: fingerprint("go1", b" ".join(d[kind] for d in selected)) for kind in ("sig", "body")}


def lock_escape(value):
    return "".join(f"%{b:02X}" if b <= 32 or b in {37, 61, 127} else bytes([b]).decode("latin1") for b in value.encode()).encode("latin1").decode()


def lock_key(entry):
    fields = [lock_escape(entry["source"]), entry["type"], lock_escape(entry["target"])]
    fields += [key + "=" + lock_escape(value) for key, value in sorted(entry.get("attributes", {}).items())]
    return " ".join(fields)


def parse_lock(text):
    entries, errors = {}, []
    lines = text.replace("\r\n", "\n").split("\n")
    if lines[0] != "trace.lock 1":
        return entries, ["LOCK_INVALID"]

    def decode(value):
        if re.search(r"%(?![0-9a-fA-F]{2})", value):
            raise ValueError("invalid percent escape")
        if any(ord(char) <= 32 or char in "=\x7f" for char in value):
            raise ValueError("unescaped lock byte")
        return urllib.parse.unquote(value, errors="strict")

    for line in lines[1:]:
        if not line:
            continue
        try:
            parts = line.split(" ")
            if len(parts) < 3 or not LINK_NAME.fullmatch(parts[1]):
                raise ValueError("invalid link")
            entry = {"source": decode(parts[0]), "type": parts[1], "target": decode(parts[2]), "attributes": {}, "fingerprints": {}}
            for part in parts[3:]:
                key, value = part.split("=", 1)
                field = "fingerprints" if key in FINGERPRINT_KEYS else "attributes"
                if key in entry[field] or (field == "attributes" and not ATTRIBUTE_NAME.fullmatch(key)):
                    raise ValueError("invalid/repeated key")
                entry[field][key] = decode(value)
            key = lock_key(entry)
            if key in entries:
                errors.append("LOCK_DUPLICATE")
            else:
                entries[key] = entry
        except (ValueError, UnicodeError):
            errors.append("LOCK_INVALID")
    return entries, sorted(set(errors))


def default_profile():
    statements = ["need", "requirement", "design"]
    return {"types": {**{t: {} for t in statements + ["risk"]}, "verification": {"attributes": {
        "method": {"type": "enum", "required": True, "values": ["test", "inspection", "analysis", "review"]},
        "procedure": {"type": "text"}, "acceptance": {"type": "text"},
    }}}, "links": {
        "refines": {"from": statements, "to": statements, "acyclic": True},
        "controls": {"from": statements, "to": ["risk"]},
        "implements": {"from": ["code"], "to": statements},
        "verifies": {"from": ["tests", "verification"], "to": statements + ["verification"], "attributes": {"role": {"type": "enum", "values": ["implementation", "effectiveness"]}}},
    }, "fingerprints": {"bodyChange": "risk-relevant"}}


def check_attributes(specs, values):
    for name, spec in specs.items():
        if spec.get("required") and name not in values:
            return False
    for name, value in values.items():
        if name not in specs:
            return False
        spec, good = specs[name], True
        kind = spec["type"]
        if kind in {"string", "text", "date", "enum"}:
            good = isinstance(value, str)
            if good and kind == "enum":
                good = value in spec.get("values", [])
            if good and kind == "date":
                import datetime
                try:
                    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
                        raise ValueError("date needs YYYY-MM-DD")
                    datetime.date.fromisoformat(value)
                except ValueError:
                    good = False
        elif kind == "number":
            good = type(value) in {int, float} and math.isfinite(value)
        elif kind == "bool":
            good = type(value) is bool
        elif kind == "list":
            good = isinstance(value, list) and all(isinstance(v, str) for v in value)
        else:
            raise Unsupported("attribute kind " + kind)
        if not good:
            return False
    return True


def analyze(files):
    """Return deterministic common data, excluding tool-specific coverage/policy."""
    try:
        return _analyze(files)
    except Unsupported as error:
        return {"unsupported": str(error)}
    except (ValueError, TypeError, KeyError, yaml.YAMLError, UnicodeError) as error:
        return {"errorCodes": ["FORMAT_INVALID"]}


def _analyze(files):
    root = read_yaml(files["trace.yaml"])
    if any(k not in ROOT_FIELDS and not k.startswith("x-") for k in root):
        raise ValueError("unknown root key")
    profile = default_profile()
    name = root.get("profile", "default")
    if name != "default":
        if name == "iec62304":
            raise Unsupported("Risk/Architecture modules and iec62304")
        declared = read_yaml(files[clean_path(name)])
        if set(declared) - PROFILE_FIELDS - {k for k in declared if k.startswith("x-")}:
            raise ValueError("unknown profile key")
        if declared.get("extends", "default") != "default":
            raise Unsupported("non-default profile inheritance")
        if any(key in declared for key in ("riskMatrix", "integrity")):
            raise Unsupported("Risk/Architecture module settings")
        for registry in ("types", "links"):
            allowed = {"description", "textOptional", "attributes"} if registry == "types" else {"from", "to", "inverse", "acyclic", "suspect", "attributes"}
            for definition in declared.get(registry, {}).values():
                if set(definition) - allowed:
                    raise ValueError("unknown profile declaration field")
                for attribute in definition.get("attributes", {}).values():
                    if set(attribute) - {"type", "values", "required", "meaning"}:
                        raise ValueError("unknown profile attribute field")
        for registry in ("types", "links"):
            for key, value in declared.get(registry, {}).items():
                profile[registry][key] = {**profile[registry].get(key, {}), **value}
        profile["fingerprints"].update(declared.get("fingerprints", {}))
    documents = [root]
    document_files = ["trace.yaml"]
    warnings = []
    seen_files = {"trace.yaml"}
    for pattern in root.get("include", []):
        clean_path(pattern)
        matches = [path for path in sorted(files) if match_glob(pattern, path) and path not in seen_files]
        if not matches:
            warnings.append("INCLUDE_EMPTY")
        for path in matches:
            document = read_yaml(files[path])
            if set(document) - {"ostf", "document", "items"} - {k for k in document if k.startswith("x-")}:
                raise ValueError("unknown item-file key")
            if "items" not in document or not isinstance(document["items"], list):
                raise ValueError("item file needs items")
            documents.append(document)
            document_files.append(path)
            seen_files.add(path)
    document_ids = set()
    document_rows = []
    for path, document in zip(document_files[1:], documents[1:]):
        if "document" not in document:
            continue
        header = document["document"]
        required = {"id", "title", "kind"}
        if not isinstance(header, dict) or not required <= set(header) or any(key not in required and not key.startswith("x-") for key in header) or not isinstance(header["id"], str) or not ITEM_ID.fullmatch(header["id"]) or any(not isinstance(header[key], str) or not header[key].strip() for key in ("title", "kind")) or header["id"] in document_ids:
            raise ValueError("invalid or duplicate document header")
        document_ids.add(header["id"])
        document_rows.append({"id": header["id"], "title": header["title"], "kind": header["kind"],
                              "file": path, "items": [item["id"] for item in document["items"]]})
    skipped = [key for key in ("external",) if key in root]
    for settings, keys in ((root.get("links", {}), ("keyword",)), (root.get("code", {}), ("tests", "justified"))):
        skipped.extend(key for key in keys if key in settings)
    items, aliases, errors, links = {}, {}, [], []
    for document in documents:
        for raw in document.get("items", []):
            item = {"type": "requirement", "status": "accepted", **raw}
            if set(item) - ITEM_FIELDS - set(profile["links"]) - {k for k in item if k.startswith("x-")}:
                raise ValueError("unknown item field")
            identity = item["id"]
            if not isinstance(identity, str) or not ITEM_ID.fullmatch(identity):
                errors.append("INVALID_ID")
                continue
            if any(identity.lower() == a.lower() for a in aliases):
                errors.append("DUPLICATE_ID")
            items[identity] = item
            for alias in [identity, *item.get("aliases", [])]:
                if not isinstance(alias, str) or not alias or alias.strip() != alias or len(alias.encode()) > 512 or any(ord(c) < 32 or ord(c) == 127 for c in alias):
                    errors.append("INVALID_ALIAS")
                    continue
                if any(alias.lower() == a.lower() for a in aliases) and alias != identity:
                    errors.append("DUPLICATE_ID")
                aliases[alias] = identity
            if item["type"] not in profile["types"]:
                errors.append("UNKNOWN_TYPE")
                continue
            if not item.get("text", "").strip() and not profile["types"][item["type"]].get("textOptional"):
                errors.append("MISSING_TEXT")
            if item["status"] not in {"draft", "accepted", "obsolete"}:
                errors.append("INVALID_STATUS")
            if item.get("derived") and not item.get("rationale", "").strip():
                errors.append("DERIVED_WITHOUT_RATIONALE")
            if not check_attributes(profile["types"][item["type"]].get("attributes", {}), item.get("attributes", {})):
                errors.append("INVALID_ATTRIBUTE")
    if errors:
        return {"errorCodes": sorted(set(errors))}

    def valid_anchor(kind, identity, attributes):
        spec = profile["links"][kind]
        source_type = "code" if kind == "implements" else "tests"
        if source_type not in spec["from"] or items[identity]["type"] not in spec["to"]:
            errors.append("LINK_NOT_ALLOWED")
        elif not check_attributes(spec.get("attributes", {}), attributes):
            errors.append("INVALID_ATTRIBUTE")
        else:
            return True
        return False

    for identity, item in items.items():
        for kind, spec in profile["links"].items():
            for target in item.get(kind, []):
                attrs = {} if isinstance(target, str) else {k: v for k, v in target.items() if k != "to"}
                target = target if isinstance(target, str) else target["to"]
                if target not in aliases:
                    errors.append("UNKNOWN_TARGET")
                    continue
                target = aliases[target]
                if target == identity:
                    errors.append("SELF_LINK")
                elif item["type"] not in spec["from"] or items[target]["type"] not in spec["to"]:
                    errors.append("LINK_NOT_ALLOWED")
                elif not check_attributes(spec.get("attributes", {}), attrs):
                    errors.append("INVALID_ATTRIBUTE")
                else:
                    if items[target]["status"] == "obsolete":
                        warnings.append("OBSOLETE_TARGET")
                    links.append({"source": identity, "type": kind, "target": target, "attributes": attrs, "origin": "imported" if item.get("provenance") else "declared"})
        for field, kind in (("code", "implements"), ("tests", "verifies")):
            for anchor in item.get(field, []):
                attrs = {} if isinstance(anchor, str) else {k: v for k, v in anchor.items() if k != "ref"}
                anchor = anchor if isinstance(anchor, str) else anchor["ref"]
                if valid_anchor(kind, identity, attrs):
                    links.append({"source": anchor, "type": kind, "target": identity, "attributes": attrs, "origin": "imported" if item.get("provenance") else "declared"})
    mode = root.get("links", {}).get("source", "yaml")
    if mode not in {"yaml", "tags", "both"}:
        raise ValueError("invalid links.source")
    if mode != "yaml":
        for path, text in sorted(files.items()):
            if not path.endswith(".go") or "@req" not in text:
                continue
            source = text.encode()
            definitions, _, comments = go_source(source)
            for comment in comments:
                for offset, line in enumerate(comment.text.decode().splitlines()):
                    match = re.search(r"@req(-file)?[ \t]+(.*?)(?:\*/)?$", line)
                    if not match:
                        continue
                    binding = path
                    if not match[1]:
                        line_number = comment.start_point.row + offset
                        found = [d for d in definitions if source[:d["docStart"]].count(b"\n") <= line_number <= source[:d["end"]].count(b"\n")]
                        if not found:
                            errors.append("TAG_UNBOUND")
                            continue
                        binding += "#" + min(found, key=lambda d: d["end"] - d["docStart"])["name"]
                    words = re.split(r"[, \t]+", match[2].strip())
                    roles = [w[5:] for w in words if w.startswith("role=")]
                    if len(roles) > 1:
                        errors.append("INVALID_ATTRIBUTE")
                        continue
                    attrs = {"role": roles[0]} if roles else {}
                    for word in (w for w in words if w and not w.startswith("role=")):
                        if word not in aliases:
                            errors.append("TAG_UNKNOWN_ID")
                        else:
                            kind = "verifies" if path.endswith("_test.go") else "implements"
                            if not valid_anchor(kind, aliases[word], attrs):
                                continue
                            entry = {"source": binding, "type": kind, "target": aliases[word], "attributes": attrs, "origin": "tagged"}
                            if not any(all(e[k] == entry[k] for k in ("source", "type", "target", "attributes")) for e in links):
                                links.append(entry)
    for kind, spec in profile["links"].items():
        if not spec.get("acyclic"):
            continue
        visiting, visited = set(), set()

        def visit(identity):
            if identity in visiting:
                errors.append("LINK_CYCLE")
                return
            if identity in visited:
                return
            visiting.add(identity)
            for link in links:
                if link["type"] == kind and link["source"] == identity:
                    visit(link["target"])
            visiting.remove(identity)
            visited.add(identity)

        for identity in items:
            visit(identity)
    if errors:
        return {"errorCodes": sorted(set(errors))}
    hashes = {identity: fingerprint("f1", item_projection(item, profile["types"])) for identity, item in items.items()}
    risk = {e["source"] for e in links if e["type"] == "controls"}
    while True:
        added = {e["source"] for e in links if e["type"] == "refines" and e["target"] in risk}
        if added <= risk:
            break
        risk |= added
    lock, lock_errors = parse_lock(files["trace.lock"]) if "trace.lock" in files else ({}, [])
    result_links = []
    for entry in sorted(links, key=lock_key):
        current = {"target": hashes[entry["target"]]}
        broken = False
        if entry["source"] in hashes:
            current["source"] = hashes[entry["source"]]
        else:
            path, _, symbol = entry["source"].partition("#")
            clean_path(path)
            code = code_fingerprint(path, symbol, files[path].encode()) if path in files else None
            if code is None:
                broken = True
                errors.append("BROKEN_LINK")
                current = {}
            else:
                current.update(code)
        row = {**entry, "fingerprints": current}
        if "trace.lock" in files:
            stamped = lock.get(lock_key(entry))
            reasons = ["LINK_BROKEN"] if broken else []
            if stamped is None:
                reasons.append("LINK_UNSTAMPED")
            elif any(v.split(":", 1)[0] not in {"f1", "go1", "lf1"} for v in stamped["fingerprints"].values()):
                reasons.append("UNKNOWN_ALGORITHM")
            elif not broken:
                ends = profile["links"][entry["type"]].get("suspect", "both")
                previous = stamped["fingerprints"]
                if ends != "target":
                    body = profile["fingerprints"]["bodyChange"]
                    if previous.get("source") != current.get("source"):
                        reasons.append("ITEM_CHANGED")
                    elif previous.get("source.sig") != current.get("source.sig"):
                        reasons.append("SIGNATURE_CHANGED")
                    elif previous.get("source.body") != current.get("source.body") and (body == "all" or (body != "none" and (entry["source"] in risk or entry["target"] in risk))):
                        reasons.append("BODY_CHANGED")
                if ends != "source" and previous.get("target") != current.get("target") and (not reasons or reasons[-1] != "ITEM_CHANGED"):
                    reasons.append("ITEM_CHANGED")
            row["state"] = "broken" if broken else "unstamped" if reasons and reasons[0] in {"LINK_UNSTAMPED", "UNKNOWN_ALGORITHM"} else "suspect" if reasons else "valid"
            row["reasons"] = reasons
        result_links.append(row)
    result = {"errorCodes": sorted(set(errors + lock_errors)), "items": [{"id": identity, "type": items[identity]["type"], "fingerprint": hashes[identity]} for identity in sorted(items)], "links": result_links}
    result["warningCodes"] = sorted(set(warnings))
    result["documents"] = document_rows
    if skipped:
        result["skipped"] = sorted(set(skipped))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=pathlib.Path)
    args = parser.parse_args()
    # Read only the supplied local tree. No Git invocation, subprocess or network.
    root = args.repository.resolve()
    files = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            continue
        if path.is_file() and ".git" not in path.relative_to(root).parts and path.suffix in {".yaml", ".go", ".lock"}:
            if path.stat().st_size > MAX_FILE_BYTES:
                raise SystemExit("input exceeds 8 MiB")
            files[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    result = analyze(files)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 2 if "unsupported" in result else 1 if result.get("errorCodes") else 0


if __name__ == "__main__":
    sys.exit(main())
