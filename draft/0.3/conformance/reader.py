#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""OSTF wire 0.3 reader: an independent-code Analyzer for Go with the check and
context commands of Annex I. Does not import or execute zztrace.

It is a development probe ported from the 0.2 Python prototype, not a hardened
service. It reads one root from a local tree: no Git, no
subprocess, no network.
"""
from __future__ import annotations

import argparse
import base64
import copy
import difflib
import hashlib
import json
import math
import os
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
ATTRIBUTE_NAME = re.compile(r"[A-Za-z][A-Za-z0-9]{0,47}\Z")
SOURCE_ALIAS = re.compile(r"[a-z][a-z0-9-]{0,31}\Z")
EXTERNAL = re.compile(r"([a-z][a-z0-9-]{0,31}):([^\s\x00-\x1f\x7f]+)\Z")
FINGERPRINT_KEYS = ("source", "source.sig", "source.body", "target")
ALGORITHMS = {"f1", "go1", "lf1"}
ITEM_FIELDS = {"id", "type", "title", "text", "status", "section", "rationale", "aliases",
               "attributes", "external", "revision", "code", "tests"}
STATEMENTS = ["need", "requirement", "design"]
SEVERITY = {
    "FORMAT_INVALID": "error", "VERSION_UNSUPPORTED": "error", "RESERVED_KEY_SKIPPED": "info",
    "UNKNOWN_KEY": "error", "PATH_INVALID": "error", "FILE_TOO_LARGE": "error",
    "INCLUDE_EMPTY": "warning", "PROFILE_INVALID": "error", "INVALID_ID": "error",
    "DUPLICATE_ID": "error", "INVALID_ALIAS": "error", "UNKNOWN_TYPE": "error",
    "MISSING_TEXT": "error", "INVALID_STATUS": "error", "INVALID_ATTRIBUTE": "error",
    "UNKNOWN_SOURCE": "error", "INVALID_EXTERNAL": "error", "DUPLICATE_EXTERNAL": "error",
    "UNKNOWN_LINK_TYPE": "error", "UNKNOWN_TARGET": "error", "SELF_LINK": "error",
    "LINK_NOT_ALLOWED": "error", "LINK_CYCLE": "error", "LINK_DUPLICATE": "warning",
    "OBSOLETE_TARGET": "warning", "ANCHOR_INVALID": "error", "BROKEN_LINK": "error",
    "UNSUPPORTED_LANGUAGE": "warning", "PARSE_ERROR": "warning", "TAG_UNKNOWN_ID": "error",
    "TAG_UNBOUND": "error", "TAGS_NOT_BOUND": "info", "LOCK_MISSING": "info",
    "LOCK_INVALID": "error", "LOCK_DUPLICATE": "error", "STAMP_REFUSED": "error",
}
LITERALS = {"interpreted_string_literal", "raw_string_literal", "rune_literal", "int_literal",
            "float_literal", "imaginary_literal"}
GO = Language(tree_sitter_go.language())


class Stop(Exception):
    """A failure that stops graph construction (OSTF-150)."""


# --- YAML subset (OSTF-101) -------------------------------------------------

class SafeCoreLoader(yaml.SafeLoader):
    pass


# PyYAML resolves scalars as YAML 1.1. Restrict implicit types to the 1.2 core schema.
SafeCoreLoader.yaml_implicit_resolvers = copy.deepcopy(yaml.SafeLoader.yaml_implicit_resolvers)
for _char, _rules in SafeCoreLoader.yaml_implicit_resolvers.items():
    SafeCoreLoader.yaml_implicit_resolvers[_char] = [
        (tag, regex) for tag, regex in _rules if tag not in {
            "tag:yaml.org,2002:bool", "tag:yaml.org,2002:timestamp",
            "tag:yaml.org,2002:int", "tag:yaml.org,2002:float",
        }
    ]
SafeCoreLoader.add_implicit_resolver("tag:yaml.org,2002:bool", re.compile(r"^(?:true|false)$"), list("tf"))
SafeCoreLoader.add_implicit_resolver("tag:yaml.org,2002:int", re.compile(r"^(?:[-+]?[0-9]+|0o[0-7]+|0x[0-9a-fA-F]+)$"), list("-+0123456789"))
SafeCoreLoader.add_implicit_resolver("tag:yaml.org,2002:float", re.compile(r"^(?:[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$"), list("-+0123456789."))


def _int(loader, node):
    value = loader.construct_scalar(node)
    return int(value[2:], 8) if value.startswith("0o") else int(value[2:], 16) if value.startswith("0x") else int(value, 10)


def _float(loader, node):
    value = loader.construct_scalar(node).lower()
    return math.copysign(math.inf, -1 if value.startswith("-") else 1) if value.lstrip("+-") == ".inf" else math.nan if value == ".nan" else float(value)


SafeCoreLoader.add_constructor("tag:yaml.org,2002:int", _int)
SafeCoreLoader.add_constructor("tag:yaml.org,2002:float", _float)


def _mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in result or key == "<<":
            raise ValueError("duplicate, merge or non-string mapping key")
        result[key] = loader.construct_object(value_node)
    return result


SafeCoreLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def parse_yaml(data):
    if data.startswith(b"\xef\xbb\xbf"):
        raise ValueError("byte order mark")
    text = data.decode("utf-8")
    for event in yaml.parse(text):
        if isinstance(event, yaml.events.AliasEvent) or getattr(event, "anchor", None) or getattr(event, "tag", None):
            raise ValueError("aliases, anchors and explicit tags are outside the subset")
    documents = list(yaml.load_all(text, Loader=SafeCoreLoader))
    if len(documents) != 1:
        raise ValueError("expected exactly one YAML document")
    return documents[0]


# --- hashes (OSTF-140, OSTF-141, Annex A) -----------------------------------

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
    values = item.get("attributes", {})
    for name, spec in types.get(fields["type"], {}).get("attributes", {}).items():
        if name not in values or not spec.get("meaning"):
            continue
        value = values[name]
        if spec.get("type") == "text":
            value = normalize_text(value)
        if value != "":
            attributes[name] = value
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


ESCAPE = {"interpreted_string_literal": re.compile(rb'\\(?:[abfnrtv\\"]|[0-7]{3}|x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8})'),
          "rune_literal": re.compile(rb"\\(?:[abfnrtv\\']|[0-7]{3}|x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8})")}


def _escapes_ok(root):
    """Go's escape rules for interpreted strings and runes, which tree-sitter does not enforce."""
    stack = [root]
    while stack:
        n = stack.pop()
        if n.type in ESCAPE:
            if ESCAPE[n.type].sub(b"", n.text).count(b"\\"):
                return False
            continue
        stack.extend(n.children)
    return True


def go_source(source):
    """Definitions, whole-file token stream and comments, or None when the file does not parse."""
    try:
        source.decode("utf-8")
    except UnicodeError:
        return None
    tree = Parser(GO).parse(source)
    if tree.root_node.has_error or not _escapes_ok(tree.root_node):
        return None
    definitions, comments = [], []

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
    return {"definitions": definitions, "whole": _token_bytes(tree.root_node, source, 0, len(source)), "comments": comments}


def select(definitions, symbol):
    """Annex A.2: full symbol first, then the last component of method names."""
    symbol = symbol.split("/", 1)[0]
    found = [d for d in definitions if d["name"] == symbol]
    if not found and "." not in symbol:
        found = [d for d in definitions if d["name"].split(".")[-1] == symbol]
    return found


# --- lock file (OSTF-142, Annex B) ------------------------------------------

def lock_escape(value):
    return "".join(f"%{b:02X}" if b <= 32 or b in {37, 61, 127} else bytes([b]).decode("latin1") for b in value.encode()).encode("latin1").decode()


def identity(link):
    fields = [lock_escape(link["source"]), link["type"], lock_escape(link["target"])]
    fields += [name + "=" + lock_escape(value) for name, value in sorted(link["attributes"].items())]
    return " ".join(fields)


def parse_lock(text):
    """Entries by identity, and (code, line) problems."""
    entries, problems = {}, []
    lines = text.replace("\r\n", "\n").split("\n")
    if lines[0] != "trace.lock 1":
        return entries, [("LOCK_INVALID", lines[0])]

    def decode(value):
        if re.search(r"%(?![0-9a-fA-F]{2})", value) or any(ord(c) <= 32 or c in "=\x7f" for c in value):
            raise ValueError("bad escape")
        return urllib.parse.unquote(value, errors="strict")

    for line in lines[1:]:
        if not line:
            continue
        try:
            parts = line.split(" ")
            if len(parts) < 3 or not LINK_NAME.fullmatch(parts[1]) or not parts[0] or not parts[2]:
                raise ValueError("bad entry")
            entry = {"source": decode(parts[0]), "type": parts[1], "target": decode(parts[2]), "attributes": {}, "fingerprints": {}}
            for part in parts[3:]:
                key, value = part.split("=", 1)
                field = "fingerprints" if key in FINGERPRINT_KEYS else "attributes"
                if key in entry[field] or (field == "attributes" and not ATTRIBUTE_NAME.fullmatch(key)):
                    raise ValueError("bad or repeated key")
                entry[field][key] = decode(value)
            key = identity(entry)
            if key in entries:
                problems.append(("LOCK_DUPLICATE", line))
            else:
                entries[key] = entry
        except (ValueError, UnicodeError):
            problems.append(("LOCK_INVALID", line))
    return entries, problems


def lock_text(entries):
    lines = []
    for key, entry in entries.items():
        pairs = [k + "=" + lock_escape(entry["fingerprints"][k]) for k in FINGERPRINT_KEYS if k in entry["fingerprints"]]
        lines.append(" ".join([key] + pairs))
    return "trace.lock 1\n" + "".join(line + "\n" for line in sorted(lines, key=str.encode))


# --- paths and globs (OSTF-102, OSTF-105) -----------------------------------

def clean_path(value):
    return (isinstance(value, str) and bool(value) and "\\" not in value and not value.startswith("/")
            and "\r" not in value and "\n" not in value
            and all(p not in {"", ".", ".."} for p in value.split("/")))


def _component(pattern, name):
    """`*` and `?` within one path component, in linear time."""
    p = n = 0
    star, mark = -1, 0
    while n < len(name):
        if p < len(pattern) and (pattern[p] == "?" or pattern[p] == name[n]) and pattern[p] != "*":
            p, n = p + 1, n + 1
        elif p < len(pattern) and pattern[p] == "*":
            star, mark, p = p, n, p + 1
        elif star >= 0:
            p, mark = star + 1, mark + 1
            n = mark
        else:
            return False
    while p < len(pattern) and pattern[p] == "*":
        p += 1
    return p == len(pattern)


def match_glob(pattern, path):
    parts, names = pattern.split("/"), path.split("/")
    seen = {}

    def match(i, j):
        if (i, j) not in seen:
            if i == len(parts):
                seen[i, j] = j == len(names)
            elif parts[i] == "**":
                seen[i, j] = any(match(i + 1, k) for k in range(j, len(names) + 1))
            else:
                seen[i, j] = j < len(names) and _component(parts[i], names[j]) and match(i + 1, j + 1)
        return seen[i, j]

    return match(0, 0)


def split_anchor(anchor):
    if not isinstance(anchor, str):
        return None
    path, hash_, symbol = anchor.partition("#")
    if not clean_path(path) or (hash_ and (not symbol or "\r" in symbol or "\n" in symbol)):
        return None
    return path, symbol


# --- vocabulary (OSTF-120, OSTF-121) ----------------------------------------

def default_vocabulary():
    return {
        "types": {t: {} for t in STATEMENTS + ["risk", "verification"]},
        "links": {
            "refines": {"from": list(STATEMENTS), "to": list(STATEMENTS), "acyclic": True, "inverse": "refined_by"},
            "controls": {"from": list(STATEMENTS), "to": ["risk"], "inverse": "controlled_by"},
            "implements": {"from": ["code"], "to": list(STATEMENTS), "inverse": "implemented_by"},
            "verifies": {"from": ["tests", "verification"], "to": STATEMENTS + ["verification"], "inverse": "verified_by"},
        },
        "bodyChange": "all",
    }


def merge_profile(vocabulary, profile):
    """Merge a profile over the default vocabulary, or raise ValueError (PROFILE_INVALID)."""
    def mapping(value, keys):
        if not isinstance(value, dict) or any(k not in keys for k in value):
            raise ValueError("unexpected profile shape")
        return value

    mapping(profile, {"ostf", "types", "links", "fingerprints"} | {k for k in profile if k.startswith("x-")})
    for name, spec in mapping(profile.get("types", {}), set(profile.get("types", {}))).items():
        if not TYPE_NAME.fullmatch(name):
            raise ValueError("type name")
        mapping(spec, {"description", "attributes"})
        if not isinstance(spec.get("description", ""), str):
            raise ValueError("description")
        for attribute, declared in mapping(spec.get("attributes", {}), set(spec.get("attributes", {}))).items():
            mapping(declared, {"type", "values", "required", "meaning"})
            if not ATTRIBUTE_NAME.fullmatch(attribute) or declared.get("type") not in {"string", "text", "number", "boolean", "list"}:
                raise ValueError("attribute declaration")
            if "values" in declared and (not isinstance(declared["values"], list) or not declared["values"] or not all(isinstance(v, str) for v in declared["values"])):
                raise ValueError("attribute values")
            if any(not isinstance(declared.get(k, False), bool) for k in ("required", "meaning")):
                raise ValueError("attribute flags")
        vocabulary["types"][name] = {**vocabulary["types"].get(name, {}), **spec}
    for name, spec in mapping(profile.get("links", {}), set(profile.get("links", {}))).items():
        if not LINK_NAME.fullmatch(name):
            raise ValueError("link name")
        mapping(spec, {"description", "from", "to", "acyclic", "inverse", "attributes"})
        if not isinstance(spec.get("description", ""), str):
            raise ValueError("description")
        if name not in vocabulary["links"] and not {"from", "to"} <= set(spec):
            raise ValueError("a new link needs from and to")
        for attribute, declared in mapping(spec.get("attributes", {}), set(spec.get("attributes", {}))).items():
            mapping(declared, {"values", "required"})
            if not ATTRIBUTE_NAME.fullmatch(attribute) or attribute in {"source", "target"} or not isinstance(declared.get("required", False), bool):
                raise ValueError("link attribute")
            if "values" in declared and (not isinstance(declared["values"], list) or not declared["values"] or not all(isinstance(v, str) for v in declared["values"])):
                raise ValueError("link attribute values")
        if not isinstance(spec.get("acyclic", False), bool) or ("inverse" in spec and not (isinstance(spec["inverse"], str) and LINK_NAME.fullmatch(spec["inverse"]))):
            raise ValueError("link flags")
        vocabulary["links"][name] = {**vocabulary["links"].get(name, {}), **spec}
    for name, spec in vocabulary["links"].items():
        for end in ("from", "to"):
            ends = spec[end]
            if not isinstance(ends, list) or not ends or not all(isinstance(e, str) for e in ends):
                raise ValueError("link endpoints")
            for e in ends:
                anchor = e in {"code", "tests"}
                if anchor and (end == "to" or name not in {"implements", "verifies"}):
                    raise ValueError("anchor kinds only in from of implements and verifies")
                if not anchor and e not in vocabulary["types"]:
                    raise ValueError("unknown endpoint type " + e)
    fingerprints = mapping(profile.get("fingerprints", {}), {"bodyChange"})
    if "bodyChange" in fingerprints:
        if fingerprints["bodyChange"] not in {"all", "risk", "none"}:
            raise ValueError("bodyChange")
        vocabulary["bodyChange"] = fingerprints["bodyChange"]
    return vocabulary


def attribute_value_ok(value):
    if isinstance(value, bool) or isinstance(value, str):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(value)
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def declared_attributes_ok(specs, values):
    for name, spec in specs.items():
        if spec.get("required") and name not in values:
            return False
        if name not in values:
            continue
        value, kind = values[name], spec.get("type", "string")
        good = {"string": isinstance(value, str), "text": isinstance(value, str),
                "number": isinstance(value, (int, float)) and not isinstance(value, bool),
                "boolean": isinstance(value, bool),
                "list": isinstance(value, list)}[kind]
        if good and "values" in spec:
            good = all(v in spec["values"] for v in (value if isinstance(value, list) else [value]))
        if not good:
            return False
    return True


# --- analysis ---------------------------------------------------------------

def fold(name):
    """OSTF-110: equality ignoring ASCII case only."""
    return name.translate(ASCII_FOLD)


ASCII_FOLD = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


class Analysis:
    """One root evaluated in one source view (OSTF-150)."""

    def __init__(self, files):
        self.files = files
        self.diagnostics = []
        self.stopped = False
        self.vocabulary = default_vocabulary()
        self.root = {}
        self.items = {}          # canonical ID -> item mapping, in reading order
        self.item_file = {}      # canonical ID -> the file that declares it
        self.names = {}          # ID or alias -> canonical ID
        self.lowered = set()
        self.externals = set()
        self.links = {}          # identity -> link
        self.parsed = {}         # path -> go_source result or None
        self.risk = set()
        self.hashes = {}
        self.lock = None
        try:
            self._build()
        except Stop:
            self.stopped = True
            self.links = {}
            self.items = {}

    # diagnostics
    def report(self, code, file=None, subject=None, message="", hint=None):
        row = {"code": code, "severity": SEVERITY[code]}
        if file is not None:
            row["file"] = file
        if subject is not None:
            row["subject"] = subject
        row["message"] = message or code
        if hint:
            row["hint"] = hint
        if row not in self.diagnostics:
            self.diagnostics.append(row)

    def nearest(self, name):
        lowered = {fold(n): self.names[n] for n in self.names}
        found = difflib.get_close_matches(fold(name), list(lowered), n=3, cutoff=0.8)
        ids = list(dict.fromkeys(lowered[f] for f in found))
        return "nearest IDs: " + ", ".join(ids) if ids else None

    def data(self, path):
        value = self.files[path]
        return value.encode() if isinstance(value, str) else value

    def size(self, path):
        return self.files.size(path) if isinstance(self.files, Tree) else len(self.data(path))

    def covered(self, path):
        """OSTF-102: a root covers files outside nested roots."""
        parts = path.split("/")[:-1]
        return not any("/".join(parts[:n]) + "/trace.yaml" in self.files for n in range(1, len(parts) + 1))

    # steps 1 to 3
    def _load(self, path, allowed, stop_code="FORMAT_INVALID"):
        if self.size(path) > MAX_FILE_BYTES:
            self.report("FILE_TOO_LARGE", path)
            raise Stop
        data = self.data(path)
        try:
            document = parse_yaml(data)
        except (ValueError, UnicodeError, yaml.YAMLError) as error:
            self.report("FORMAT_INVALID", path, message=str(error).splitlines()[0])
            raise Stop
        if not isinstance(document, dict):
            self.report("FORMAT_INVALID", path, message="not a mapping")
            raise Stop
        version = document.get("ostf")
        if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+", version):
            self.report("FORMAT_INVALID", path, message="ostf must be a version string")
            raise Stop
        if version != "0.3":
            self.report("VERSION_UNSUPPORTED", path, message="this reader implements 0.3")
            raise Stop
        for key in document:
            if key not in allowed and not key.startswith("x-"):
                self.report("UNKNOWN_KEY", path, key)
                raise Stop
        return document

    def _build(self):
        root = self._load("trace.yaml", {"ostf", "profile", "include", "tags", "sources", "items"})
        self.root = root
        if "tags" in root and not isinstance(root["tags"], bool):
            self.report("FORMAT_INVALID", "trace.yaml", "tags", "tags must be true or false")
            raise Stop
        sources = root.get("sources", {})
        if not isinstance(sources, dict) or any(not SOURCE_ALIAS.fullmatch(a) or not isinstance(s, dict)
                                                or any(k != "url" and not k.startswith("x-") for k in s)
                                                or not isinstance(s.get("url", "x"), str) or s.get("url") == ""
                                                for a, s in sources.items()):
            self.report("FORMAT_INVALID", "trace.yaml", "sources", "sources must map aliases to entries with a url")
            raise Stop
        self.sources = sources
        if "profile" in root:
            name = root["profile"]
            if not clean_path(name):
                self.report("PATH_INVALID", "trace.yaml", str(name))
                raise Stop
            if name not in self.files:
                self.report("PROFILE_INVALID", "trace.yaml", name, "profile file not found")
                raise Stop
            profile = self._load(name, {"ostf", "types", "links", "fingerprints"})
            try:
                self.vocabulary = merge_profile(self.vocabulary, profile)
            except (ValueError, TypeError, KeyError) as error:
                self.report("PROFILE_INVALID", name, message=str(error))
                raise Stop
        documents = [("trace.yaml", root)]
        include = root.get("include", [])
        if not isinstance(include, list) or not all(isinstance(p, str) for p in include):
            self.report("FORMAT_INVALID", "trace.yaml", "include", "include must be a list of globs")
            raise Stop
        matched = set()
        for pattern in include:
            if not clean_path(pattern):
                self.report("PATH_INVALID", "trace.yaml", pattern)
                raise Stop
            found = {p for p in self.files if p != "trace.yaml" and match_glob(pattern, p)}
            if not found:
                self.report("INCLUDE_EMPTY", "trace.yaml", pattern)
            matched |= found
        for path in sorted(matched, key=str.encode):
            document = self._load(path, {"ostf", "items"})
            if "items" not in document:
                self.report("FORMAT_INVALID", path, message="an item file needs items")
                raise Stop
            documents.append((path, document))
        for path, document in documents:
            if not isinstance(document.get("items", []), list):
                self.report("FORMAT_INVALID", path, "items", "items must be a list")
                raise Stop
        # step 4
        for path, document in documents:
            for raw in document.get("items", []):
                self._register(path, raw)
        # step 5
        for ident in list(self.items):
            self._item_links(ident)
        if root.get("tags", True):
            self._tags()
        # step 6
        self._cycles()
        self._freshness()

    # step 4: items (section 4)
    def _register(self, path, raw):
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str):
            self.report("FORMAT_INVALID", path, message="an item must be a mapping with a string id")
            return
        ident = raw["id"]
        errors = []

        def bad(code, message=""):
            errors.append((code, message))

        if not ITEM_ID.fullmatch(ident):
            bad("INVALID_ID", "does not match item-id")
        item = {"type": "requirement", "status": "accepted", **raw}
        for key in ("title", "text", "section", "rationale", "revision"):
            if key in raw and not isinstance(raw[key], str):
                bad("FORMAT_INVALID", key + " must be a string")
        if raw.get("revision") == "":
            bad("FORMAT_INVALID", "revision must not be empty")
        if not isinstance(item["type"], str) or item["type"] not in self.vocabulary["types"]:
            bad("UNKNOWN_TYPE", str(item["type"]))
        if not isinstance(item["status"], str) or item["status"] not in {"draft", "accepted", "obsolete"}:
            bad("INVALID_STATUS", str(item["status"]))
        if "text" not in raw and "external" not in raw:
            bad("MISSING_TEXT")
        aliases = raw.get("aliases", [])
        if not isinstance(aliases, list):
            bad("FORMAT_INVALID", "aliases must be a list")
            aliases = []
        for alias in aliases:
            if not isinstance(alias, str) or not alias or alias != alias.strip() or len(alias.encode()) > 512 or any(ord(c) < 32 or ord(c) == 127 for c in alias):
                bad("INVALID_ALIAS", repr(alias))
        if "external" in raw:
            match = EXTERNAL.fullmatch(raw["external"]) if isinstance(raw["external"], str) else None
            if not match:
                bad("INVALID_EXTERNAL", str(raw["external"]))
            elif match[1] not in self.sources:
                bad("UNKNOWN_SOURCE", match[1])
        elif "revision" in raw:
            bad("INVALID_EXTERNAL", "revision without external")
        attributes = raw.get("attributes", {})
        if not isinstance(attributes, dict) or any(not ATTRIBUTE_NAME.fullmatch(k) or not attribute_value_ok(v) for k, v in attributes.items()):
            bad("INVALID_ATTRIBUTE", "attribute names or values")
        elif isinstance(item["type"], str) and not declared_attributes_ok(self.vocabulary["types"].get(item["type"], {}).get("attributes", {}), attributes):
            bad("INVALID_ATTRIBUTE", "declared attribute")
        if errors:
            for code, message in errors:
                self.report(code, path, ident, message)
            return
        names = [ident] + aliases
        lowered = [fold(n) for n in names]
        if len(set(lowered)) != len(lowered) or any(n in self.lowered for n in lowered):
            self.report("DUPLICATE_ID", path, ident, "an ID or alias collides with one read earlier")
            return
        if "external" in raw and raw["external"] in self.externals:
            self.report("DUPLICATE_EXTERNAL", path, ident, raw["external"])
            return
        self.item_file[ident] = path
        self.items[ident] = item
        for name in names:
            self.names[name] = ident
        self.lowered.update(lowered)
        if "external" in raw:
            self.externals.add(raw["external"])

    # step 5: links (section 6)
    def _add(self, link):
        key = identity(link)
        if key in self.links:
            self.report("LINK_DUPLICATE", link["file"], key)
            if link["origin"] == "declared":
                self.links[key]["origin"] = "declared"
            return
        link["identity"] = key
        self.links[key] = link

    def _link_attributes(self, kind, attributes):
        specs = self.vocabulary["links"][kind].get("attributes", {})
        if any(name not in specs for name in attributes):
            return False
        return all(not (spec.get("required") and name not in attributes) and
                   (name not in attributes or "values" not in spec or attributes[name] in spec["values"])
                   for name, spec in specs.items())

    def _endpoint(self, kind, path, subject, attributes, source_kind, target):
        """Check a link's endpoint types and attributes (OSTF-134)."""
        spec = self.vocabulary["links"][kind]
        if source_kind not in spec["from"] or self.items[target]["type"] not in spec["to"]:
            self.report("LINK_NOT_ALLOWED", path, subject, f"{kind} from {source_kind} to {self.items[target]['type']}")
            return False
        if not self._link_attributes(kind, attributes):
            self.report("INVALID_ATTRIBUTE", path, subject, "link attributes of " + kind)
            return False
        if self.items[target]["status"] == "obsolete":
            self.report("OBSOLETE_TARGET", path, subject, target + " is obsolete")
        return True

    def _entry(self, entry, key):
        """A link entry: a string, or a mapping with key and string attributes."""
        if isinstance(entry, str):
            return entry, {}
        if isinstance(entry, dict) and isinstance(entry.get(key), str) and all(isinstance(v, str) for k, v in entry.items()):
            return entry[key], {k: v for k, v in entry.items() if k != key}
        return None, None

    def _item_links(self, ident):
        item = self.items[ident]
        path = self.item_file[ident]
        for kind, entries in item.items():
            if kind in ITEM_FIELDS or kind.startswith("x-"):
                continue
            if kind not in self.vocabulary["links"]:
                self.report("UNKNOWN_LINK_TYPE", path, ident, kind)
                continue
            if not isinstance(entries, list):
                self.report("FORMAT_INVALID", path, ident, kind + " must be a list")
                continue
            for entry in entries:
                ref, attributes = self._entry(entry, "to")
                if ref is None:
                    self.report("FORMAT_INVALID", path, ident, "malformed " + kind + " entry")
                    continue
                target = self.names.get(ref)
                if target is None:
                    self.report("UNKNOWN_TARGET", path, ident, ref + " does not resolve", self.nearest(ref))
                    continue
                if target == ident:
                    self.report("SELF_LINK", path, ident)
                    continue
                if self._endpoint(kind, path, ident, attributes, item["type"], target):
                    self._add({"source": ident, "type": kind, "target": target, "attributes": attributes,
                               "origin": "declared", "file": path, "anchor": False})
        for field, kind in (("code", "implements"), ("tests", "verifies")):
            if not isinstance(item.get(field, []), list):
                self.report("FORMAT_INVALID", path, ident, field + " must be a list")
                continue
            for entry in item.get(field, []):
                anchor, attributes = self._entry(entry, "ref")
                if anchor is None or split_anchor(anchor) is None:
                    self.report("ANCHOR_INVALID", path, ident, str(entry))
                    continue
                if self._endpoint(kind, path, anchor, attributes, field, ident):
                    self._add({"source": anchor, "type": kind, "target": ident, "attributes": attributes,
                               "origin": "declared", "file": path, "anchor": True})

    def go(self, path):
        if path not in self.parsed:
            self.parsed[path] = go_source(self.data(path))
            if self.parsed[path] is None:
                self.report("PARSE_ERROR", path)
        return self.parsed[path]

    def _tags(self):
        for path in sorted(self.files, key=str.encode):
            if not path.endswith(".go") or not self.covered(path) or b"@req" not in self.data(path):
                continue
            parsed = self.go(path)
            if parsed is None:
                continue
            source = self.data(path)
            for comment in parsed["comments"]:
                for offset, line in enumerate(comment.text.decode().splitlines()):
                    match = re.search(r"@req(-file)?[ \t]+(.*?)(?:\*/)?$", line)
                    if not match:
                        continue
                    anchor = path
                    if not match[1]:
                        row = comment.start_point.row + offset
                        found = [d for d in parsed["definitions"]
                                 if source[:d["docStart"]].count(b"\n") <= row <= source[:d["end"]].count(b"\n")]
                        if not found:
                            self.report("TAG_UNBOUND", path, line.strip())
                            continue
                        anchor += "#" + min(found, key=lambda d: d["end"] - d["docStart"])["name"]
                    kind = "verifies" if path.endswith("_test.go") else "implements"
                    for word in (w for w in re.split(r"[, \t]+", match[2].strip()) if w):
                        target = self.names.get(word)
                        if target is None:
                            self.report("TAG_UNKNOWN_ID", path, word, word + " is not an item ID or alias", self.nearest(word))
                            continue
                        if self._endpoint(kind, path, anchor, {}, "tests" if kind == "verifies" else "code", target):
                            self._add({"source": anchor, "type": kind, "target": target, "attributes": {},
                                       "origin": "tagged", "file": path, "anchor": True})

    # step 6
    def _cycles(self):
        for kind, spec in self.vocabulary["links"].items():
            if not spec.get("acyclic"):
                continue
            edges = {}
            for link in self.links.values():
                if link["type"] == kind and not link["anchor"]:
                    edges.setdefault(link["source"], []).append(link["target"])
            index, low, stack, on, sccs = {}, {}, [], set(), []
            for start in sorted(edges):
                if start in index:
                    continue
                work = [(start, 0)]
                while work:
                    v, i = work.pop()
                    if i == 0:
                        index[v] = low[v] = len(index)
                        stack.append(v)
                        on.add(v)
                    successors = edges.get(v, [])
                    if i > 0:
                        low[v] = min(low[v], low[successors[i - 1]])
                    while i < len(successors) and (successors[i] in index):
                        if successors[i] in on:
                            low[v] = min(low[v], index[successors[i]])
                        i += 1
                    if i < len(successors):
                        work.append((v, i + 1))
                        work.append((successors[i], 0))
                        continue
                    if low[v] == index[v]:
                        component = set()
                        while True:
                            w = stack.pop()
                            on.discard(w)
                            component.add(w)
                            if w == v:
                                break
                        if len(component) > 1:
                            sccs.append(component)
            for component in sccs:
                self.report("LINK_CYCLE", self.item_file[min(component)], ", ".join(sorted(component)), kind)
                for key in [k for k, l in self.links.items() if l["type"] == kind and not l["anchor"] and l["source"] in component and l["target"] in component]:
                    del self.links[key]

    # binding and fingerprints (OSTF-132, OSTF-141)
    def bind(self, anchor):
        """('ok', fingerprints, binding) or (problem, None, None) for an anchor in this view."""
        parts = split_anchor(anchor)
        if parts is None:
            return "invalid", None, None
        path, symbol = parts
        if path not in self.files:
            return "missing", None, None
        if not path.endswith(".go"):
            if symbol:
                return "unsupported", None, None
            return "ok", {"source.sig": fingerprint("lf1", self.data(path).replace(b"\r\n", b"\n"))}, ("file", path)
        parsed = self.go(path)
        if not symbol:
            if parsed is None:
                return "ok", {"source.sig": fingerprint("lf1", self.data(path).replace(b"\r\n", b"\n"))}, ("file", path)
            return "ok", {"source.sig": fingerprint("go1", parsed["whole"])}, ("file", path)
        if parsed is None:
            return "missing", None, None
        found = select(parsed["definitions"], symbol)
        if not found:
            return "missing", None, None
        return "ok", {"source.sig": fingerprint("go1", b" ".join(d["sig"] for d in found)),
                      "source.body": fingerprint("go1", b" ".join(d["body"] for d in found))}, \
            ("defs", path, frozenset(d["start"] for d in found))

    def _freshness(self):
        types = self.vocabulary["types"]
        self.hashes = {ident: fingerprint("f1", item_projection(item, types)) for ident, item in self.items.items()}
        controls = {l["source"] for l in self.links.values() if l["type"] == "controls" and not l["anchor"]}
        self.risk = set(controls)
        while True:
            added = {l["source"] for l in self.links.values() if l["type"] == "refines" and not l["anchor"] and l["target"] in self.risk}
            if added <= self.risk:
                break
            self.risk |= added
        if "trace.lock" in self.files:
            try:
                text = self.data("trace.lock").decode("utf-8")
            except UnicodeError:
                text = ""
            self.lock, problems = parse_lock(text)
            for code, line in problems:
                self.report(code, "trace.lock", line)
        else:
            self.report("LOCK_MISSING", "trace.lock")
        for link in self.links.values():
            current = {}
            status = "ok"
            if link["anchor"]:
                status, code, link["binding"] = self.bind(link["source"])
                if status == "ok":
                    current.update(code)
                elif status == "unsupported":
                    self.report("UNSUPPORTED_LANGUAGE", link["file"], link["source"])
                else:
                    self.report("BROKEN_LINK", link["file"], link["source"])
            else:
                current["source"] = self.hashes[link["source"]]
            current["target"] = self.hashes[link["target"]]
            link["fingerprints"] = current
            link["status"] = status
            if self.lock is None or status == "unsupported":
                continue
            if status != "ok":
                link["state"], link["reasons"] = "broken", ["LINK_BROKEN"]
                continue
            entry = self.lock.get(link["identity"])
            if entry is None:
                link["state"], link["reasons"] = "unstamped", ["LINK_UNSTAMPED"]
                continue
            recorded = entry["fingerprints"]
            if any(value.split(":", 1)[0] not in ALGORITHMS for value in recorded.values()):
                link["state"], link["reasons"] = "unstamped", ["UNKNOWN_ALGORITHM"]
                continue
            risky = link["source"] in self.risk or link["target"] in self.risk
            reasons = set()
            for key in set(recorded) | set(current):
                if recorded.get(key) == current.get(key):
                    continue
                if key in {"source", "target"}:
                    reasons.add("ITEM_CHANGED")
                elif key == "source.sig":
                    reasons.add("SIGNATURE_CHANGED")
            if (recorded.get("source.body") != current.get("source.body") and "SIGNATURE_CHANGED" not in reasons
                    and (self.vocabulary["bodyChange"] == "all" or (self.vocabulary["bodyChange"] == "risk" and risky))):
                reasons.add("BODY_CHANGED")
            link["reasons"] = sorted(reasons, key=str.encode)
            link["state"] = "suspect" if reasons else "valid"

    # Annex C.2
    def item_row(self, ident, detail=False):
        item = self.items[ident]
        row = {"id": ident, "type": item["type"], "status": item["status"], "riskRelevant": ident in self.risk,
               "fingerprint": self.hashes[ident]}
        if detail:
            for key in ("title", "text", "rationale", "external", "revision"):
                if key in item:
                    row[key] = item[key]
        return row

    def link_row(self, link):
        row = {k: link[k] for k in ("source", "type", "target", "attributes", "origin", "fingerprints")}
        if "state" in link:
            row["state"], row["reasons"] = link["state"], link["reasons"]
        return row

    def result(self):
        return {
            "ostf": "0.3",
            "diagnostics": self.diagnostics,
            "items": [self.item_row(i) for i in sorted(self.items, key=str.encode)],
            "links": [self.link_row(self.links[k]) for k in sorted(self.links, key=str.encode)],
        }

    def failed(self):
        return any(d["severity"] == "error" for d in self.diagnostics) or \
            any(l.get("state") in {"suspect", "broken"} for l in self.links.values())


# --- context (Annex I.3, Annex J) -------------------------------------------

def item_context(analysis, ident):
    reached, frontier = {ident}, [ident]
    while frontier:
        current = frontier.pop()
        for link in analysis.links.values():
            if not link["anchor"] and link["source"] == current and link["target"] not in reached:
                reached.add(link["target"])
                frontier.append(link["target"])
    links = {k for k, l in analysis.links.items() if (not l["anchor"] and l["source"] in reached) or (l["anchor"] and l["target"] == ident)}
    return reached, links


def resolve(analysis, target, anchor=None):
    """('item', ID), ('anchor', direct link keys) or (code, None). TARGET names an item
    first; otherwise `anchor`, its root-relative form, is bound (Annex I.3)."""
    if target in analysis.names:
        return "item", analysis.names[target]
    status, _, binding = analysis.bind(anchor or target)
    if status == "ok":
        path = binding[1]
        direct = []
        for key, link in analysis.links.items():
            other = link.get("binding")
            if not link["anchor"] or other is None:
                continue
            if other == binding or (binding[0] == "defs" and other == ("file", path)) or (binding[0] == "file" and other[1] == path):
                direct.append(key)
        return "anchor", direct
    if status == "unsupported":
        return "UNSUPPORTED_LANGUAGE", None
    if ITEM_ID.fullmatch(target) and "#" not in target:
        return "UNKNOWN_TARGET", None
    return "BROKEN_LINK", None


def context(analysis, target, anchor=None):
    """Annex I.3: the json context result and whether TARGET resolved."""
    result = {"ostf": "0.3", "context": target, "diagnostics": [], "items": [], "links": []}
    if analysis.stopped:
        result["diagnostics"] = list(analysis.diagnostics)
        return result, False
    kind, value = resolve(analysis, target, anchor)
    items, links, unresolved = set(), set(), []
    if kind in {"item", "anchor"}:
        starts = [value] if kind == "item" else sorted({analysis.links[k]["target"] for k in value}, key=str.encode)
        for ident in starts:
            reached, keys = item_context(analysis, ident)
            items |= reached
            links |= keys
    else:
        row = {"code": kind, "severity": SEVERITY[kind], "subject": target, "message": target + " does not resolve"}
        hint = analysis.nearest(target) if kind == "UNKNOWN_TARGET" else None
        if hint:
            row["hint"] = hint
        unresolved = [row]
    subjects = items | {analysis.links[k]["source"] for k in links} | links
    paths = {split_anchor(analysis.links[k]["source"])[0] for k in links if analysis.links[k]["anchor"]}
    result["diagnostics"] = unresolved + [d for d in analysis.diagnostics if d.get("file") == "trace.lock"
                                          or d.get("subject") in subjects or d.get("file") in paths]
    result["items"] = [analysis.item_row(i, True) for i in sorted(items, key=str.encode)]
    result["links"] = [analysis.link_row(analysis.links[k]) for k in sorted(links, key=str.encode)]
    return result, not unresolved


def render(analysis, target, anchor=None):
    """Annex J text for a resolved TARGET."""
    kind, value = resolve(analysis, target, anchor)
    vocabulary = analysis.vocabulary["links"]

    def label(ident, summary=False):
        item = analysis.items[ident]
        text = ident
        if "title" in item:
            text += ": " + item["title"]
        elif summary and normalize_text(item.get("text", "")):
            text += ": " + normalize_text(item["text"]).split("\n")[0]
        if item["status"] != "accepted":
            text += f" [{item['status']}]"
        return text

    def state(link):
        return f" ({link['state']})" if "state" in link else ""

    def name(link, inverse=False):
        base = vocabulary[link["type"]].get("inverse", link["type"] + "_by") if inverse else link["type"]
        return " ".join([base] + [f"{k}={v}" for k, v in sorted(link["attributes"].items())])

    lines = []
    shown = set()

    def tree(ident, depth, skip):
        pad = "  " * depth
        item = analysis.items[ident]
        if ident in analysis.risk:
            lines.append(pad + "risk-relevant: ask before changing")
        lines.extend(pad + line for line in normalize_text(item.get("text", "")).split("\n") if item.get("text"))
        if "rationale" in item:
            lines.append(pad + "rationale: " + normalize_text(item["rationale"]))
        if "external" in item:
            alias, native = item["external"].split(":", 1)
            parts = [item["external"]]
            if "revision" in item:
                parts.append("revision " + item["revision"])
            if "url" in analysis.sources.get(alias, {}):
                parts.append(analysis.sources[alias]["url"].replace("{id}", urllib.parse.quote(native, safe="")))
            lines.append(pad + "external: " + ", ".join(parts))

        def children(source):
            return iter(sorted((l for l in analysis.links.values() if not l["anchor"] and l["source"] == source),
                               key=lambda l: (l["type"].encode(), l["target"].encode())))

        work = [(children(ident), depth)]
        while work:
            link = next(work[-1][0], None)
            if link is None:
                work.pop()
                continue
            level = "  " * work[-1][1]
            if link["target"] in shown:
                lines.append(level + f"{name(link)} {link['target']}{state(link)}")
                continue
            shown.add(link["target"])
            lines.append(level + f"{name(link)} {label(link['target'], True)}{state(link)}")
            work.append((children(link["target"]), work[-1][1] + 1))
        incoming = sorted((l for l in analysis.links.values() if l["anchor"] and l["target"] == ident and l["identity"] not in skip),
                          key=lambda l: (name(l, True).encode(), l["source"].encode()))
        for link in incoming:
            lines.append(pad + f"{name(link, True)} {link['source']}{state(link)}")

    if kind == "item":
        shown.add(value)
        lines.append(label(value))
        tree(value, 1, set())
    else:
        lines.append(target)
        direct = {}
        for key in sorted(value, key=str.encode):
            direct.setdefault(analysis.links[key]["target"], []).append(key)
        for ident in sorted(direct, key=lambda i: (i not in analysis.risk, i.encode())):
            shown.add(ident)
            for key in direct[ident]:
                link = analysis.links[key]
                lines.append(f"  {name(link)} {label(ident)}{state(link)}")
            tree(ident, 2, set(direct[ident]))
    return "\n".join(lines) + "\n"


# --- command line (Annex I) -------------------------------------------------

class Tree(dict):
    """Regular files of a local root, read on demand and not kept. Symbolic links are
    skipped; a file that turns into one, or leaves the root, after listing is an error."""

    def __init__(self, root):
        super().__init__()
        self.root = pathlib.Path(os.path.realpath(root))
        for directory, dirs, names in os.walk(self.root):
            dirs[:] = sorted(d for d in dirs if d != ".git" and not os.path.islink(os.path.join(directory, d)))
            for name in names:
                full = os.path.join(directory, name)
                if os.path.isfile(full) and not os.path.islink(full):
                    dict.__setitem__(self, pathlib.Path(full).relative_to(self.root).as_posix(), None)

    def _checked(self, path):
        dict.__getitem__(self, path)
        full = self.root / path
        if os.path.islink(full) or not os.path.realpath(full).startswith(str(self.root) + os.sep):
            raise OSError("file changed while reading: " + path)
        return full

    def size(self, path):
        return os.lstat(self._checked(path)).st_size

    def __getitem__(self, path):
        return self._checked(path).read_bytes()


def find_root(start):
    for directory in [start, *start.parents]:
        if (directory / "trace.yaml").is_file():
            return directory
    return None


def text_check(result):
    lines = []
    for d in result["diagnostics"]:
        where = " ".join(x for x in (d.get("file"), d.get("subject")) if x)
        hint = f" ({d['hint']})" if "hint" in d else ""
        lines.append(f"{d['severity']} {d['code']} {where}: {d['message']}{hint}")
    for link in result["links"]:
        if link.get("state", "valid") != "valid":
            ident = identity(link)
            lines.append(f"{link['state']} {ident} {' '.join(link['reasons'])}".rstrip())
    states = [l.get("state") for l in result["links"]]
    lines.append(f"{len(result['items'])} items, {len(states)} links, {states.count('valid')} valid")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="OSTF 0.3 reader (Annex I check and context).")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("check", "context"):
        sub = commands.add_parser(command)
        sub.add_argument("--root", type=pathlib.Path)
        sub.add_argument("--format", choices=["json", "text"], default="text")
        if command == "context":
            sub.add_argument("target")
    args = parser.parse_args(argv)
    cwd = pathlib.Path(os.path.realpath(os.getcwd()))
    target = getattr(args, "target", None)
    # I.3: an anchor TARGET is a path relative to the working directory and selects the
    # root that covers its file; TARGET itself is kept as given for item lookup and output.
    path = target.partition("#")[0] if target is not None else None
    full = pathlib.Path(os.path.normpath(cwd / path)) if path else None
    looks_like_anchor = full is not None and ("#" in target or full.is_file())
    if args.root:
        root = pathlib.Path(os.path.realpath(args.root)) if (args.root / "trace.yaml").is_file() else None
    else:
        root = find_root(full.parent if looks_like_anchor else cwd)
    if root is None:
        print("no trace.yaml at or above the working directory", file=sys.stderr)
        return 2
    anchor = None
    if looks_like_anchor and full.is_relative_to(root):
        anchor = full.relative_to(root).as_posix() + target[len(path):]
    try:
        analysis = Analysis(Tree(root))
        return _run(args, analysis, target, anchor)
    except OSError as error:
        print(error, file=sys.stderr)
        return 2


def _run(args, analysis, target, anchor):
    if args.command == "check":
        result = analysis.result()
        print(json.dumps(result, indent=2, ensure_ascii=False) if args.format == "json" else text_check(result), end="\n" if args.format == "json" else "")
        return 1 if analysis.failed() else 0
    result, resolved = context(analysis, target, anchor)
    if args.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif resolved:
        print(render(analysis, target, anchor), end="")
    else:
        print(text_check(result), end="")
    return 0 if resolved else 1


if __name__ == "__main__":
    sys.exit(main())
