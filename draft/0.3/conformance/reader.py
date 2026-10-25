#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""OSTF wire 0.3 reader: an independent-code Analyzer for Go, TypeScript, JavaScript and
Python (Annexes A, K and L) with the check, context and stamp commands of Annex I. Does not
import or execute zztrace.

It is a development probe ported from the 0.2 Python prototype, not a hardened service. The
reader reads one root from a local tree with no subprocess and no network; only the command
line's `check --base REV` without `--base-tree` runs Git's plumbing commands to read REV.
"""
from __future__ import annotations

import argparse
import ast
import base64
import bisect
import copy
import difflib
import hashlib
import io
import json
import math
import os
import pathlib
import posixpath
import re
import stat
import sys
import tempfile
import tokenize
import unicodedata
import urllib.parse

import rfc8785
import yaml
from tree_sitter import Language, Parser
import tree_sitter_go
import tree_sitter_javascript
import tree_sitter_typescript

MAX_FILE_BYTES = 8 * 1024 * 1024
ITEM_ID = re.compile(r"[A-Za-z][A-Za-z0-9._-]{0,127}\Z")
TYPE_NAME = re.compile(r"[a-z][a-z0-9-]{0,47}\Z")
LINK_NAME = re.compile(r"[a-z][a-z0-9_]{0,47}\Z")
ATTRIBUTE_NAME = re.compile(r"[A-Za-z][A-Za-z0-9]{0,47}\Z")
SOURCE_ALIAS = re.compile(r"[a-z][a-z0-9-]{0,31}\Z")
EXTERNAL = re.compile(r"([a-z][a-z0-9-]{0,31}):([^\s\x00-\x1f\x7f]+)\Z")
FINGERPRINT_KEYS = ("source", "source.sig", "source.body", "target")
ALGORITHMS = {"f1", "go2", "lf1", "ts2", "py1"}
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
    "NESTED_ROOT": "info",
}
# This reader's own codes, outside Annex C (OSTF-151); the prefix is its SARIF driver name.
OWN_PREFIX = "ostf-reader."
UNLINKED = OWN_PREFIX + "UNLINKED"
SEVERITY[UNLINKED] = "info"
LITERALS = {"interpreted_string_literal", "raw_string_literal", "rune_literal", "int_literal",
            "float_literal", "imaginary_literal"}
GO = Language(tree_sitter_go.language())
TS = Language(tree_sitter_typescript.language_typescript())
TSX = Language(tree_sitter_typescript.language_tsx())
JS = Language(tree_sitter_javascript.language())


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
    if any(c in text for c in "\u0085\u2028\u2029"):  # YAML 1.1 reads them as line breaks, 1.2 does not (OSTF-101)
        raise ValueError("U+0085, U+2028 and U+2029 are outside the subset")
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


# A.4 (go2): the lists whose elements the grammar ends with ;, and the declarations whose
# specifications are such elements when grouped in parentheses.
GO_LISTS = {"source_file", "statement_list", "import_spec_list", "var_spec_list", "field_declaration_list", "interface_type"}
GO_GROUPS = {"const_declaration", "type_declaration"}


def _go_element(n):
    """A.4 (go2): whether n is a statement, declaration, specification, field or interface element
    that the grammar ends with ;."""
    if not n.is_named or n.type == "comment" or n.parent is None:
        return False
    if n.parent.type in GO_LISTS:
        return True
    return n.parent.type in GO_GROUPS and any(c.type == "(" for c in n.parent.children)


def _go_omitted(root):
    """A.4 (go2): the (start, end) of every element whose ; the source omits, at a line end or
    before a closing bracket: neither its last token nor the token after it is a written ;."""
    tokens, elements, stack = [], [], [root]
    while stack:
        n = stack.pop()
        if n.type == "comment":
            continue
        if _go_element(n):
            elements.append(n)
        if n.type in LITERALS or not n.children:
            tokens.append((n.start_byte, n.type))
            continue
        stack.extend(reversed(n.children))
    starts = [t[0] for t in tokens]
    omitted = []
    for n in elements:
        after = bisect.bisect_left(starts, n.end_byte)
        written = (after > 0 and tokens[after - 1][1] == ";" and tokens[after - 1][0] >= n.start_byte) or \
            (after < len(tokens) and tokens[after][1] == ";")
        if not written:
            omitted.append((n.start_byte, n.end_byte))
    return sorted(omitted, key=lambda span: span[1])


def _insert_omitted(tokens, ends, omitted, start, end, own=None):
    """A.4, K.4: a ; after each construct in `omitted`, sorted by end, that source[start:end] holds
    whole, other than `own`."""
    for element in omitted[bisect.bisect_right(omitted, start, key=lambda span: span[1]):]:
        if element[1] > end:
            break
        if element[0] >= start and element != own:
            at = bisect.bisect_right(ends, element[1])
            tokens.insert(at, b";")
            ends.insert(at, element[1])


def _token_bytes(node, source, start, end, omitted=None, own=None):
    """A.4: the token stream of source[start:end]. With `omitted`, that of go2: a ; after each element
    in it that the span holds whole, other than `own`, the definition the span belongs to."""
    tokens, ends = [], []

    def visit(n):
        if n.end_byte <= start or n.start_byte >= end or n.type == "comment":
            return
        if n.type in LITERALS or not n.children:
            raw = source[max(start, n.start_byte):min(end, n.end_byte)]
            if n.type == "raw_string_literal":
                raw = raw.replace(b"\r", b"")
            if raw:
                tokens.append(raw)
                ends.append(n.end_byte)
            return
        for child in n.children:
            visit(child)

    visit(node)
    _insert_omitted(tokens, ends, omitted or [], start, end, own)
    return b" ".join(tokens)


ESCAPE = {"interpreted_string_literal": re.compile(rb'\\(?:[abfnrtv\\"]|[0-7]{3}|x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8})'),
          "rune_literal": re.compile(rb"\\(?:[abfnrtv\\']|[0-7]{3}|x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8})")}


def _escapes_ok(root, source):
    """Go's escape rules for interpreted strings and runes, which tree-sitter does not enforce."""
    stack = [root]
    while stack:
        n = stack.pop()
        if n.type in ESCAPE:
            if ESCAPE[n.type].sub(b"", source[n.start_byte:n.end_byte]).count(b"\\"):
                return False
            continue
        stack.extend(n.children)
    return True


def _doc_start(source, comments, start):
    """A.5, K.5, L.5: the first byte of the comments directly above `start`, each beginning its own
    line with no blank line between; `start` itself when there are none."""
    doc_start = start
    for comment in reversed(comments):
        if comment["end"] <= doc_start:
            gap = source[comment["end"]:doc_start]
            line_start = source.rfind(b"\n", 0, comment["start"]) + 1
            if gap.strip() or gap.count(b"\n") > 1 or source[line_start:comment["start"]].strip(b" \t"):
                break
            doc_start = comment["start"]
    return doc_start


def _comment(node_start, node_end, row, text):
    """A comment as tags read it: its bytes, first row and lines without the comment delimiters."""
    if text.startswith("//"):
        text = text[2:]
    elif text.startswith("/*"):
        text = text[2:-2] if text.endswith("*/") else text[2:]
    elif text.startswith("#"):
        text = text[1:]
    return {"start": node_start, "end": node_end, "row": row, "lines": text.split("\n")}


def _tree_comments(root, source, kinds=("comment",), opaque=()):
    """The comments of a tree, not looking inside `opaque` nodes such as literals. Rows are
    counted at line feeds (OSTF-133)."""
    found, stack = [], [root]
    while stack:
        n = stack.pop()
        if n.type in kinds:
            found.append(_comment(n.start_byte, n.end_byte, source.count(b"\n", 0, n.start_byte), source[n.start_byte:n.end_byte].decode()))
        elif n.type not in opaque:
            stack.extend(reversed(n.children))
    return sorted(found, key=lambda c: c["start"])


def _go_empty_statement_only(root):
    """tree-sitter-go 0.25.0 refuses an empty statement between two statements, as in a();; b(),
    which Go reads (Annex A). Its recovery wraps the statements up to the empty statement in an
    ERROR node; accept a tree whose every error is that one."""
    stack = [root]
    while stack:
        n = stack.pop()
        if n.is_missing:
            return False
        if n.type == "ERROR":
            if n.parent is None or n.parent.type != "block" or [c.type for c in n.children] != ["statement_list"] \
                    or n.children[0].has_error or n.children[0].named_children[-1].type != "empty_statement":
                return False
            continue
        stack.extend(n.children)
    return True


# tree-sitter-go 0.25.0 lexes new and make as keywords whose first argument must be a type, where Go
# reads them as identifiers, and Go 1.26 reads an expression after new (Annex A).
GO_NEW_MAKE = re.compile(rb"\b(?:new|make)(?=[ \t]*\()")


def _go_errors(root):
    """The bytes under error nodes, and the missing nodes, of a tree-sitter tree."""
    total, stack = 0, [root]
    while stack:
        n = stack.pop()
        if n.type == "ERROR" or n.is_missing:
            total += n.end_byte - n.start_byte + 1
            continue
        stack.extend(n.children)
    return total


def _go_parse(source):
    """The tree of a Go file. Where tree-sitter refuses it, each call of new or make in turn is spelled
    as an identifier of the same length, for the parse alone, and stays so when the parse has fewer
    errors; tokens, names and comments are always read from the source as written."""
    tree = Parser(GO).parse(source)
    if not tree.root_node.has_error:
        return tree
    best, respelled = _go_errors(tree.root_node), source
    for match in GO_NEW_MAKE.finditer(source):
        trial = respelled[:match.start()] + match.group().upper() + respelled[match.end():]
        parsed = Parser(GO).parse(trial)
        errors = _go_errors(parsed.root_node)
        if errors < best:
            tree, best, respelled = parsed, errors, trial
    return tree


def go_source(source, path="", algorithm="go2"):
    """Annex A: definitions, whole-file token stream and comments, or None when the file does not parse.
    With algorithm "go1", the token streams of the superseded go1 (A.6)."""
    try:
        source.decode("utf-8")
    except UnicodeError:
        return None
    tree = _go_parse(source)
    if (tree.root_node.has_error and not _go_empty_statement_only(tree.root_node)) or not _escapes_ok(tree.root_node, source):
        return None
    definitions = []
    comments = _tree_comments(tree.root_node, source)
    omitted = _go_omitted(tree.root_node) if algorithm == "go2" else None
    spelled = lambda n: source[n.start_byte:n.end_byte].decode()  # as written, whatever _go_parse respelled
    for declaration in tree.root_node.named_children:
        spans = []
        function = declaration.type == "function_declaration"
        if declaration.type in {"function_declaration", "method_declaration"}:
            name = spelled(declaration.child_by_field_name("name"))
            receiver = declaration.child_by_field_name("receiver")
            member = False
            if receiver:
                t = receiver.named_children[0].child_by_field_name("type")
                while t.type in {"pointer_type", "generic_type", "parenthesized_type"}:
                    t = t.child_by_field_name("type") or t.named_children[0]
                name, member = spelled(t) + "." + name, True
            body = declaration.child_by_field_name("body")
            spans.append((name, declaration.start_byte, declaration.end_byte, body.start_byte if body else declaration.end_byte, member))
        elif declaration.type in {"type_declaration", "var_declaration", "const_declaration"}:
            grouped = any(c.type in {"(", "var_spec_list"} for c in declaration.children)
            specs = [c for c in declaration.named_children if c.type in {"type_spec", "type_alias", "var_spec", "const_spec"}]
            if not specs:
                specs = [s for c in declaration.named_children for s in c.named_children if s.type in {"var_spec", "const_spec"}]
            for spec in specs:
                for name_node in spec.children_by_field_name("name"):
                    start, end = (spec.start_byte, spec.end_byte) if grouped else (declaration.start_byte, declaration.end_byte)
                    spans.append((spelled(name_node), start, end, end, False))
        for name, start, end, header, member in spans:
            definition = {"name": name, "start": start, "docStart": _doc_start(source, comments, start), "end": end,
                          "function": function, "member": member,
                          "sig": _token_bytes(tree.root_node, source, start, header, omitted, (start, end)),
                          "body": _token_bytes(tree.root_node, source, start, end, omitted, (start, end))}
            definition["test"] = is_test(definition, path)
            definitions.append(definition)
    return {"definitions": definitions, "whole": _token_bytes(tree.root_node, source, 0, len(source), omitted), "comments": comments}


def go1_source(source, path=""):
    """A.6: the superseded go1, for its vectors; no Analyzer state uses it."""
    return go_source(source, path, "go1")


def is_test(definition, path):
    """Annex A.1: a top-level function of a test file named Test or Fuzz, alone or
    followed by a character that is not a lowercase letter."""
    name = definition["name"]
    if not definition["function"] or not path.endswith("_test.go"):
        return False
    return any(name.startswith(prefix) and (name == prefix or unicodedata.category(name[len(prefix)]) != "Ll")
               for prefix in ("Test", "Fuzz"))


def _select_members(definitions, symbol):
    """A.2, K.2, L.2: the full symbol first; for a symbol without a dot, the last component of member names."""
    found = [d for d in definitions if d["name"] == symbol]
    if not found and "." not in symbol:
        found = [d for d in definitions if d["member"] and d["name"].rsplit(".", 1)[-1] == symbol]
    return found


def select(definitions, symbol, path=""):
    """Annex A.2: full symbol first, then the last component of method names. Subtest
    components after `/` bind only a test function of a test file (Annex A.1)."""
    if "/" in symbol:
        name = symbol.split("/", 1)[0]
        return [d for d in definitions if d["name"] == name and d["test"]]
    return _select_members(definitions, symbol)


# --- Annex K: TypeScript and JavaScript, ts2 --------------------------------

TS_TYPESCRIPT, TS_TSX = (".ts", ".mts", ".cts"), (".tsx",)
TS_JAVASCRIPT = (".js", ".mjs", ".cjs", ".jsx")
TS_ATOMS = {"string", "template_string", "template_literal_type", "regex", "jsx_text"}
TS_COMMENTS = {"comment", "hash_bang_line", "html_comment"}
TS_FUNCTIONS = {"arrow_function", "function_expression", "function", "generator_function"}
TS_NAMES = {"identifier", "type_identifier", "property_identifier", "private_property_identifier", "nested_identifier"}
# K.4 (ts2): the statements and declarations that the grammar ends with ;, the class members that end with
# one, the containers of type members, and what export default declares without one.
TS_TERMINATED = {"expression_statement", "variable_declaration", "lexical_declaration", "return_statement",
                 "throw_statement", "break_statement", "continue_statement", "debugger_statement", "do_statement",
                 "import_statement", "import_alias", "type_alias_declaration", "function_signature"}
TS_CLASS_FIELDS = {"public_field_definition", "field_definition", "method_signature", "abstract_method_signature",
                   "index_signature"}
TS_TYPE_MEMBERS = {"object_type", "interface_body"}
TS_UNTERMINATED_EXPORTS = {"function_expression", "generator_function", "class", "import_alias"}
# ECMAScript WhiteSpace and LineTerminator code points (K.4).
JS_SPACE = re.compile("[\t\v\f  ﻿  -   　\n\r  ]+")


_DIGITS = r"[0-9](?:_?[0-9])*"
# ECMAScript 2024 NumericLiteral: a separator stands between two digits (K.4). Legacy octal and
# octal-like integers take none.
JS_NUMBER = re.compile(rf"""(?:(?:0|[1-9](?:_?[0-9])*|0[0-7]*[89][0-9]*)(?:\.(?:{_DIGITS})?)?(?:[eE][+-]?{_DIGITS})?
                          |\.{_DIGITS}(?:[eE][+-]?{_DIGITS})?
                          |0[0-7]+
                          |(?:0|[1-9](?:_?[0-9])*)n
                          |0[xX][0-9a-fA-F](?:_?[0-9a-fA-F])*n?
                          |0[oO][0-7](?:_?[0-7])*n?
                          |0[bB][01](?:_?[01])*n?)\Z""", re.VERBOSE)


def _js_numbers_ok(root):
    """Numeric literals that ECMAScript reads; tree-sitter accepts some it does not, such as 0_1."""
    stack = [root]
    while stack:
        n = stack.pop()
        if n.type == "number" and n.is_named:  # not the type keyword number
            if not JS_NUMBER.match(n.text.decode()):
                return False
            continue
        stack.extend(n.children)
    return True


def ts_test_file(path):
    """K.1: a name ending in .test or .spec before the extension, or a file beneath __tests__."""
    name = path.rsplit("/", 1)[-1]
    stem = name.rsplit(".", 1)[0]
    return stem.endswith((".test", ".spec")) or "__tests__" in path.split("/")[:-1]


def _ts_terminated(n):
    """K.4 (ts2): whether the grammar ends n with ;: a statement or declaration that takes one, a class
    field or member signature, or a type member. Keywords, such as module, are not constructs."""
    if not n.is_named:
        return False
    parent = n.parent.type if n.parent is not None else None
    if parent in TS_TYPE_MEMBERS:
        return n.type not in TS_COMMENTS
    if parent == "class_body":
        return n.type in TS_CLASS_FIELDS
    if n.type == "export_statement":
        named = [c for c in n.named_children if c.type not in TS_COMMENTS and c.type != "decorator"]
        return n.child_by_field_name("declaration") is None and not (named and named[-1].type in TS_UNTERMINATED_EXPORTS)
    if n.type == "module":  # declare module "name", without a body
        return n.child_by_field_name("body") is None
    return n.type in TS_TERMINATED


def _ts_omitted(root):
    """K.4 (ts2): the (start, end) of every construct that the grammar ends with ; and whose ; the source
    omits: neither its last token nor the token after it is a ;, or a , after a type member."""
    tokens, constructs, stack = [], [], [root]
    while stack:
        n = stack.pop()
        if n.type in TS_COMMENTS:
            continue
        if _ts_terminated(n):
            constructs.append(n)
        if n.type in TS_ATOMS or not n.children:
            if n.end_byte > n.start_byte:
                tokens.append((n.start_byte, n.end_byte, n.type))
            continue
        stack.extend(reversed(n.children))
    starts = [t[0] for t in tokens]
    omitted = []
    for n in constructs:
        last = bisect.bisect_left(starts, n.end_byte) - 1
        after = last + 1
        written = (last >= 0 and tokens[last][2] == ";" and tokens[last][0] >= n.start_byte) or \
            (after < len(tokens) and tokens[after][2] in ((";", ",") if n.parent.type in TS_TYPE_MEMBERS else (";",)))
        if not written:
            omitted.append((n.start_byte, n.end_byte))
    return sorted(omitted, key=lambda span: span[1])


def _ts_tokens(root, source, start, end, omitted=None):
    """K.4: the ts2 token stream of source[start:end], with a ; after each construct in `omitted` that the
    span holds whole and a ; for each , after a type member; with `omitted` None, that of ts1."""
    tokens, ends = [], []
    stack = [root]
    while stack:
        n = stack.pop()
        if n.end_byte <= start or n.start_byte >= end or n.type in TS_COMMENTS:
            continue
        if n.type in TS_ATOMS or not n.children:
            raw = source[max(start, n.start_byte):min(end, n.end_byte)]
            if n.type == "jsx_text":
                raw = JS_SPACE.sub(" ", raw.decode()).strip(" ").encode()
            if raw == b"," and omitted is not None and n.parent.type in TS_TYPE_MEMBERS:
                raw = b";"  # ts2: a , after a type member is its ;
            if raw:
                tokens.append(raw)
                ends.append(n.end_byte)
            continue
        stack.extend(reversed(n.children))
    _insert_omitted(tokens, ends, omitted or [], start, end)
    # A , before a closing bracket is dropped; under ts2, not an elision, a , after [ or another , (K.4).
    kept = [t for i, t in enumerate(tokens) if not (t == b"," and i + 1 < len(tokens) and tokens[i + 1] in (b")", b"]", b"}", b">")
                                                    and (omitted is None or i == 0 or tokens[i - 1] not in (b"[", b",")))]
    return b" ".join(kept)


def ts_source(source, path="", algorithm="ts2"):
    """Annex K: definitions, whole-file token stream and comments, or None when the file does not parse.
    With algorithm "ts1", the token streams of the superseded ts1 (K.6)."""
    try:
        source.decode("utf-8")
    except UnicodeError:
        return None
    language = TS if path.endswith(TS_TYPESCRIPT) else TSX if path.endswith(TS_TSX) else JS
    tree = Parser(language).parse(source)
    root = tree.root_node
    if root.has_error or not _js_numbers_ok(root):
        return None
    comments = _tree_comments(root, source, opaque=TS_ATOMS)
    omitted = _ts_omitted(root) if algorithm == "ts2" else None
    definitions = []
    test_file = ts_test_file(path)

    def unparen(n):
        while n is not None and n.type == "parenthesized_expression" and n.named_children:
            n = next((c for c in n.named_children if c.type != "comment"), None)
        return n

    def function(n):
        return unparen(n) is not None and unparen(n).type in TS_FUNCTIONS

    def body_of(n):
        return unparen(n).child_by_field_name("body")

    def add(name, outer, body, member=False, test=False):
        if not name:
            return
        start, end = outer.start_byte, outer.end_byte
        previous = outer.prev_sibling
        while previous is not None and previous.type in ("decorator", "comment"):  # K.3, K.5: decorators, past comments
            if previous.type == "decorator":
                start = previous.start_byte
            previous = previous.prev_sibling
        following = outer.next_sibling
        while member and following is not None and following.type == "comment":
            following = following.next_sibling
        if member and following is not None and following.type == ";":  # K.3: a class member's terminating ;
            end = following.end_byte
        header = body.start_byte if body is not None else end
        definitions.append({"name": name, "start": start, "docStart": _doc_start(source, comments, start), "end": end,
                            "member": member, "test": test,
                            "sig": _ts_tokens(root, source, start, header, omitted),
                            "body": _ts_tokens(root, source, start, end, omitted)})

    def named(node, prefix):
        field = node.child_by_field_name("name")
        return prefix + field.text.decode() if field is not None and field.type in TS_NAMES else None

    def container(node, prefix):
        for outer in node.named_children:
            inner = outer
            while inner is not None and inner.type in {"export_statement", "ambient_declaration"}:  # alone or combined
                unwrapped = inner.child_by_field_name("declaration")
                if unwrapped is None:
                    named = [c for c in inner.named_children if c.type not in ("comment", "decorator")]
                    unwrapped = named[-1] if named else None
                inner = unwrapped
            if inner is not None:
                definition(outer, inner, prefix)

    def bound_names(pattern):
        """Identifiers a binding pattern declares, destructuring included (K.2)."""
        if pattern is None:
            return []
        if pattern.type in ("identifier", "shorthand_property_identifier_pattern"):
            return [pattern.text.decode()]
        if pattern.type == "pair_pattern":
            return bound_names(pattern.child_by_field_name("value"))
        if pattern.type == "assignment_pattern":
            return bound_names(pattern.child_by_field_name("left"))
        if pattern.type in ("object_pattern", "array_pattern", "rest_pattern", "object_assignment_pattern"):
            return [n for c in pattern.named_children if c.type != "comment" for n in bound_names(c)]
        return []

    def definition(outer, inner, prefix):
        kind, member = inner.type, bool(prefix)
        if kind in {"function_declaration", "generator_function_declaration", "function_signature"}:
            add(named(inner, prefix), outer, inner.child_by_field_name("body"), member)
        elif kind in {"class_declaration", "abstract_class_declaration"}:
            name, body = named(inner, prefix), inner.child_by_field_name("body")
            add(name, outer, body, member)
            if name and body is not None:
                class_members(body, name + ".")
        elif kind in {"interface_declaration", "type_alias_declaration", "enum_declaration"}:
            add(named(inner, prefix), outer, None, member)
        elif kind in {"internal_module", "module"}:
            name, body = named(inner, prefix), inner.child_by_field_name("body")
            add(name, outer, body, member)
            if name and body is not None:
                container(body, name + ".")
        elif kind in {"lexical_declaration", "variable_declaration"}:
            declarators = [c for c in inner.named_children if c.type == "variable_declarator"]
            for declarator in declarators:
                value = declarator.child_by_field_name("value")
                body = body_of(value) if function(value) else None
                for name in bound_names(declarator.child_by_field_name("name")):
                    add(prefix + name, outer if len(declarators) == 1 else declarator, body, member)
        elif kind == "expression_statement" and inner.named_children:
            child = inner.named_children[0]
            if child.type == "internal_module":
                definition(outer, child, prefix)
            elif child.type == "call_expression" and not prefix and test_file:
                test_call(outer, child, "")
            elif child.type == "assignment_expression":
                left, right = child.child_by_field_name("left"), child.child_by_field_name("right")
                if left is not None and left.type in {"identifier", "member_expression", "subscript_expression"} and function(right):
                    add(prefix + left.text.decode(), outer, body_of(right), member or left.type != "identifier")

    def class_members(body, prefix):
        for m in body.named_children:
            if m.type in {"method_definition", "method_signature", "abstract_method_signature"}:
                add(named(m, prefix), m, m.child_by_field_name("body"), True)
            elif m.type in {"public_field_definition", "field_definition"}:
                value = m.child_by_field_name("value")
                if function(value):
                    field = m.child_by_field_name("name") or m.child_by_field_name("property")
                    if field is not None and field.type in TS_NAMES:
                        add(prefix + field.text.decode(), m, body_of(value), True)

    def test_call(outer, call, prefix):
        callee = call.child_by_field_name("function")
        if callee is not None and callee.type == "member_expression":
            callee = callee.child_by_field_name("object")
        arguments = call.child_by_field_name("arguments")
        values = [c for c in arguments.named_children if c.type != "comment"] if arguments is not None else []
        if callee is None or callee.type != "identifier" or len(values) < 2:
            return
        word = callee.text.decode()
        if word not in {"describe", "suite", "it", "test"}:
            return
        first, second = values[0], values[1]
        literal = first.type == "string" or (first.type == "template_string" and not any(c.type == "template_substitution" for c in first.children))
        contents = first.text[1:-1].decode()
        if not literal or not contents or "\n" in contents or "\r" in contents or not function(second):  # K.1
            return
        name = prefix + contents
        body = body_of(second)
        add(name, outer, body, test=True)
        if word in {"describe", "suite"} and body is not None and body.type == "statement_block":
            for statement in body.named_children:
                if statement.type == "expression_statement" and statement.named_children and statement.named_children[0].type == "call_expression":
                    test_call(statement, statement.named_children[0], name + " > ")

    container(root, "")
    return {"definitions": definitions, "whole": _ts_tokens(root, source, 0, len(source), omitted), "comments": comments}


def ts1_source(source, path=""):
    """K.6: the superseded ts1, for its vectors; no Analyzer state uses it."""
    return ts_source(source, path, "ts1")


def ts_select(definitions, symbol, path=""):
    """K.2: a test is its identity; otherwise the full symbol, then member names."""
    return _select_members(definitions, symbol)


# --- Annex L: Python, py1 ---------------------------------------------------

def py_test_file(path):
    """L.1: a name beginning with test_ or ending in _test.py."""
    name = path.rsplit("/", 1)[-1]
    return name.startswith("test_") or name.endswith("_test.py")


def py_source(source, path=""):
    """Annex L with CPython's own tokenizer and parser: definitions, whole-file token stream and
    comments, or None when the file does not parse."""
    try:
        # Python reads CRLF and CR as line ends; positions below are in the normalized source.
        text = source.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        source = text.encode()
        tree = ast.parse(text, feature_version=(3, 12))  # Annex L: the Python 3.12 grammar
        if any(getattr(node, "is_lazy", 0) for node in ast.walk(tree)):
            return None  # lazy imports are Python 3.15 syntax, which feature_version does not refuse
        lines = io.StringIO(text).readlines()
        raw_tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (UnicodeError, SyntaxError, ValueError, tokenize.TokenError):
        return None
    starts, total = [], 0
    for line in lines:
        starts.append(total)
        total += len(line.encode())
    starts.append(total)

    def offset(row, col, chars=True):
        if row - 1 >= len(lines):
            return total
        return starts[row - 1] + (len(lines[row - 1][:col].encode()) if chars else col)

    # L.4: tokens with their logical line and indentation depth; an f-string is one token.
    tokens, comments, depth, logical, f_depth, f_start = [], [], 0, 0, 0, None
    for tok in raw_tokens:
        kind = tok.type
        if f_depth:
            if kind == getattr(tokenize, "FSTRING_START", -1):
                f_depth += 1
            elif kind == getattr(tokenize, "FSTRING_END", -1):
                f_depth -= 1
                if not f_depth:
                    end = offset(*tok.end)
                    tokens.append((source[f_start:end], f_start, end, depth, logical))
            continue
        if kind == tokenize.INDENT:
            depth += 1
        elif kind == tokenize.DEDENT:
            depth -= 1
        elif kind == tokenize.NEWLINE:
            logical += 1
        elif kind == tokenize.COMMENT:
            start = offset(*tok.start)
            comments.append(_comment(start, offset(*tok.end), tok.start[0] - 1, tok.string))
        elif kind == getattr(tokenize, "FSTRING_START", -1):
            f_depth, f_start = 1, offset(*tok.start)
        elif kind in (tokenize.NAME, tokenize.NUMBER, tokenize.STRING, tokenize.OP, tokenize.ERRORTOKEN):
            start, end = offset(*tok.start), offset(*tok.end)
            tokens.append((source[start:end], start, end, depth, logical))

    def stream(start, end):
        lines_, base = {}, None
        for spelling, a, b, d, line in tokens:
            if a >= start and b <= end:
                if base is None:
                    base = d
                lines_.setdefault(line, [d - base]).append(spelling)
        return b"\n".join(str(group[0]).encode() + b" " + b" ".join(group[1:]) for _, group in sorted(lines_.items()))

    test_file = py_test_file(path)
    definitions = []

    def add(name, start, end, header, member, test=False):
        definitions.append({"name": name, "start": start, "docStart": _doc_start(source, comments, start), "end": end,
                            "member": member, "test": test, "sig": stream(start, header), "body": stream(start, end)})

    def names(target):
        if isinstance(target, ast.Name):  # as written, not as the parser normalizes it (L.2)
            return [source[offset(target.lineno, target.col_offset, chars=False):offset(target.end_lineno, target.end_col_offset, chars=False)].decode()]
        if isinstance(target, (ast.Tuple, ast.List)):
            return [n for element in target.elts for n in names(element)]
        if isinstance(target, ast.Starred):
            return names(target.value)
        return []

    def header_end(keyword):
        """The end of the colon that ends a def or class header: the first at bracket depth 0."""
        depth = 0
        for spelling, a, b, _, _ in tokens:
            if a < keyword:
                continue
            if spelling in (b"(", b"[", b"{"):
                depth += 1
            elif spelling in (b")", b"]", b"}"):
                depth -= 1
            elif spelling == b":" and depth == 0:
                return b
        return keyword

    def spelled(start):
        """The name token at or after start, as written (L.2)."""
        return next(t[0].decode() for t in tokens if t[1] >= start and t[0] not in (b"async", b"def", b"class"))

    def visit(body, prefix, top, test_class):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                keyword = offset(node.lineno, node.col_offset, chars=False)
                start = keyword
                if node.decorator_list:
                    first = node.decorator_list[0]
                    at = offset(first.lineno, first.col_offset, chars=False)
                    start = max(t[1] for t in tokens if t[0] == b"@" and t[1] < at)
                end = offset(node.end_lineno, node.end_col_offset, chars=False)
                header = header_end(keyword)
                name = prefix + spelled(keyword)
                test = (not isinstance(node, ast.ClassDef) and test_file and node.name.startswith("test") and (top or test_class))
                add(name, start, end, header, bool(prefix), test)
                if isinstance(node, ast.ClassDef):
                    visit(node.body, name + ".", False, top and node.name.startswith("Test"))
            elif top and isinstance(node, (ast.Assign, ast.AnnAssign)):
                start = offset(node.lineno, node.col_offset, chars=False)
                end = offset(node.end_lineno, node.end_col_offset, chars=False)
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for name in dict.fromkeys(n for target in targets for n in names(target)):
                    add(name, start, end, end, False)

    visit(tree.body, "", True, False)
    return {"definitions": definitions, "whole": stream(0, len(source)), "comments": comments, "source": source}


def py_select(definitions, symbol, path=""):
    """L.1, L.2: a parametrization identifier in brackets binds only the test function before it."""
    if "[" in symbol and symbol.endswith("]"):
        return [d for d in _select_members(definitions, symbol[:symbol.index("[")]) if d["test"]]
    return _select_members(definitions, symbol)


class Annex:
    def __init__(self, algorithm, extensions, parse, select_, test_file):
        self.algorithm, self.extensions, self.parse, self.select, self.test_file = algorithm, extensions, parse, select_, test_file


ANNEXES = [
    Annex("go2", (".go",), go_source, select, lambda path: path.endswith("_test.go")),
    Annex("ts2", TS_TYPESCRIPT + TS_TSX + TS_JAVASCRIPT, ts_source, ts_select, ts_test_file),
    Annex("py1", (".py",), py_source, py_select, py_test_file),
]


def annex_for(path):
    """The language annex that covers a file, or None (OSTF-164)."""
    return next((a for a in ANNEXES if path.endswith(a.extensions)), None)


# --- lock file (OSTF-142, Annex B) ------------------------------------------

def lock_escape(value):
    return "".join(f"%{b:02X}" if b <= 32 or b in {37, 61, 127} else bytes([b]).decode("latin1") for b in value.encode()).encode("latin1").decode()


def identity(link):
    fields = [lock_escape(link["source"]), link["type"], lock_escape(link["target"])]
    fields += [name + "=" + lock_escape(value) for name, value in sorted(link["attributes"].items())]
    return " ".join(fields)


def parse_lock(data):
    """Entries by identity, and (code, line) problems. Each line is decoded on its own."""
    entries, problems, duplicates = {}, [], set()
    data = data.encode() if isinstance(data, str) else data
    lines = []
    for raw in data.replace(b"\r\n", b"\n").split(b"\n"):
        try:
            lines.append(raw.decode("utf-8"))
        except UnicodeError:
            lines.append(None)
            problems.append(("LOCK_INVALID", raw.decode("utf-8", "backslashreplace")))
    if lines[0] != "trace.lock 1":
        return entries, problems if lines[0] is None else [("LOCK_INVALID", lines[0])]

    def decode(value):
        if re.search(r"%(?![0-9a-fA-F]{2})", value) or any(ord(c) <= 32 or c in "=\x7f" for c in value):
            raise ValueError("bad escape")
        return urllib.parse.unquote(value, errors="strict")

    for line in lines[1:]:
        if not line:  # an empty line, or one already reported as not UTF-8
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
                duplicates.add(key)
            else:
                entries[key] = entry
        except (ValueError, UnicodeError):
            problems.append(("LOCK_INVALID", line))
    # OSTF-142: neither duplicate entry is used, so the link is unstamped.
    return {key: entry for key, entry in entries.items() if key not in duplicates}, problems


def lock_text(entries):
    lines = []
    for key, entry in entries.items():
        pairs = [k + "=" + lock_escape(entry["fingerprints"][k]) for k in FINGERPRINT_KEYS if k in entry["fingerprints"]]
        lines.append(" ".join([key] + pairs))
    return "trace.lock 1\n" + "".join(line + "\n" for line in sorted(lines, key=str.encode))


# --- paths and globs (OSTF-102, OSTF-105) -----------------------------------

def clean_path(value):
    return (isinstance(value, str) and bool(value) and "\\" not in value and "#" not in value and not value.startswith("/")
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
    """Path and symbol of an anchor, or None when it is malformed or names the root's trace.lock,
    in any ASCII case (OSTF-132)."""
    if not isinstance(anchor, str):
        return None
    path, hash_, symbol = anchor.partition("#")
    if not clean_path(path) or fold(path) == "trace.lock" or (hash_ and (not symbol or "\r" in symbol or "\n" in symbol)):
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
            if not ATTRIBUTE_NAME.fullmatch(attribute) or attribute in {"source", "target", "to", "ref"} or not isinstance(declared.get("required", False), bool):
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
        """OSTF-102: a root covers files with valid paths outside nested roots."""
        parts = path.split("/")[:-1]
        return clean_path(path) and not any("/".join(parts[:n]) + "/trace.yaml" in self.files for n in range(1, len(parts) + 1))

    # steps 1 to 3
    def _load(self, path, allowed, invalid="FORMAT_INVALID", unknown="UNKNOWN_KEY"):
        """A profile reports its schema failures, unknown keys included, as PROFILE_INVALID (OSTF-104, OSTF-121)."""
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
            self.report(invalid, path, message="not a mapping")
            raise Stop
        version = document.get("ostf")
        if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+", version):
            self.report(invalid, path, message="ostf must be a version string")
            raise Stop
        if version != "0.3":
            self.report("VERSION_UNSUPPORTED", path, message="this reader implements 0.3")
            raise Stop
        for key in document:
            if key not in allowed and not key.startswith("x-"):
                self.report(unknown, path, key)
                raise Stop
        return document

    def _build(self):
        if "trace.yaml" not in self.files:
            return  # Annex C.3: a base view without the root's trace.yaml has an empty graph.
        # OSTF-102: every other trace.yaml beneath the root is a nested root that this result does not cover.
        for path in sorted((p for p in self.files if p.endswith("/trace.yaml")), key=str.encode):
            directory = path[:-len("/trace.yaml")]
            self.report("NESTED_ROOT", path, message=f"nested root {directory}/ is not covered here",
                        hint=f"check it on its own, with --root {directory}")
        root = self._load("trace.yaml", {"ostf", "profile", "include", "tags", "sources", "items"})
        self.root = root
        if "tags" in root and not isinstance(root["tags"], bool):
            self.report("FORMAT_INVALID", "trace.yaml", "tags", "tags must be true or false")
            raise Stop
        sources = root.get("sources", {})
        if not isinstance(sources, dict) or any(not SOURCE_ALIAS.fullmatch(a) or not isinstance(s, dict)
                                                or not isinstance(s.get("url", "x"), str) or s.get("url") == ""
                                                for a, s in sources.items()):
            self.report("FORMAT_INVALID", "trace.yaml", "sources", "sources must map aliases to entries with a url")
            raise Stop
        for alias, source in sources.items():
            for key in source:
                if key != "url" and not key.startswith("x-"):
                    self.report("UNKNOWN_KEY", "trace.yaml", key, f"source {alias} has no key {key}")
                    raise Stop
        self.sources = sources
        if "profile" in root:
            name = root["profile"]
            if not clean_path(name):
                self.report("PATH_INVALID", "trace.yaml", "profile", str(name))
                raise Stop
            if name not in self.files:
                self.report("PROFILE_INVALID", "trace.yaml", name, "profile file not found")
                raise Stop
            profile = self._load(name, {"ostf", "types", "links", "fingerprints"}, "PROFILE_INVALID", "PROFILE_INVALID")
            try:
                self.vocabulary = merge_profile(self.vocabulary, profile)
            except (ValueError, TypeError, KeyError) as error:
                self.report("PROFILE_INVALID", name, message=str(error))
                raise Stop
        documents = [("trace.yaml", root)]
        include = root.get("include", [])
        if not isinstance(include, list):
            self.report("FORMAT_INVALID", "trace.yaml", "include", "include must be a list of globs")
            raise Stop
        matched = set()
        for pattern in include:
            if not clean_path(pattern):
                self.report("PATH_INVALID", "trace.yaml", "include", str(pattern))
                raise Stop
            found = {p for p in self.files if p != "trace.yaml" and self.covered(p) and match_glob(pattern, p)}
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
        self._unlinked()

    # step 4: items (section 4)
    def _register(self, path, raw):
        if not isinstance(raw, dict) or "id" not in raw:
            self.report("FORMAT_INVALID", path, message="an item must be a mapping with an id")
            return
        if not isinstance(raw["id"], str):
            self.report("INVALID_ID", path, message="the id is not a string")
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
            self.report("LINK_DUPLICATE", link["file"], link["source"], key + " is declared more than once")
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
        """A link entry: a string, or a mapping with key and string attributes. A mapping with an
        attribute that is not a string gives attributes None (INVALID_ATTRIBUTE, OSTF-134)."""
        if isinstance(entry, str):
            return entry, {}
        if isinstance(entry, dict) and isinstance(entry.get(key), str):
            attributes = {k: v for k, v in entry.items() if k != key}
            return entry[key], attributes if all(isinstance(v, str) for v in attributes.values()) else None
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
                if attributes is None:
                    self.report("INVALID_ATTRIBUTE", path, ident, "link attributes are strings")
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
                if anchor is None:  # an entry of another shape (OSTF-131)
                    self.report("FORMAT_INVALID", path, ident, "malformed " + field + " entry")
                    continue
                if split_anchor(anchor) is None:
                    self.report("ANCHOR_INVALID", path, anchor, "malformed anchor")
                    continue
                if "#" not in anchor and anchor in self.items:  # its identity would be the item's (OSTF-132)
                    self.report("ANCHOR_INVALID", path, anchor, "a whole-file anchor equals an item ID")
                    continue
                if attributes is None:
                    self.report("INVALID_ATTRIBUTE", path, anchor, "link attributes are strings")
                    continue
                if self._endpoint(kind, path, anchor, attributes, field, ident):
                    self._add({"source": anchor, "type": kind, "target": ident, "attributes": attributes,
                               "origin": "declared", "file": path, "anchor": True})

    def parse(self, path):
        """The language annex parse of a file, once; PARSE_ERROR when it does not parse (OSTF-141)."""
        if path not in self.parsed:
            self.parsed[path] = annex_for(path).parse(self.data(path), path)
            if self.parsed[path] is None:
                self.report("PARSE_ERROR", path)
        return self.parsed[path]

    def _tags(self):
        for path in sorted(self.files, key=str.encode):
            annex = annex_for(path)
            if annex is None or not self.covered(path) or b"@req" not in self.data(path):
                continue
            parsed = self.parse(path)
            if parsed is None:
                continue
            source = parsed.get("source", self.data(path))
            for comment in parsed["comments"]:
                for offset, line in enumerate(comment["lines"]):
                    match = re.search(r"@req(-file)?[ \t]+(.*?)(?:\*/)?$", line.rstrip("\r"))
                    if not match:
                        continue
                    anchors = [path]
                    if not match[1]:
                        # A.5, K.5, L.5: the innermost definitions whose lines, from their comments above
                        # to their end, hold the tag.
                        row = comment["row"] + offset
                        found = [d for d in parsed["definitions"]
                                 if source[:d["docStart"]].count(b"\n") <= row <= source[:d["end"] - 1].count(b"\n")]
                        found = [d for d in found if not any(e is not d and d["docStart"] <= e["docStart"] and e["end"] <= d["end"]
                                                             and (e["docStart"], e["end"]) != (d["docStart"], d["end"]) for e in found)]
                        if not found:
                            self.report("TAG_UNBOUND", path, line.strip(), "the tag binds to no definition")
                            continue
                        anchors = list(dict.fromkeys(path + "#" + d["name"] for d in found))
                    kind = "verifies" if annex.test_file(path) else "implements"
                    for word in (w for w in re.split(r"[, \t]+", match[2].strip()) if w):
                        target = self.names.get(word)
                        if target is None:
                            self.report("TAG_UNKNOWN_ID", path, word, word + " is not an item ID or alias", self.nearest(word))
                            continue
                        for anchor in anchors:
                            if "#" not in anchor and anchor in self.items:  # OSTF-132
                                self.report("ANCHOR_INVALID", path, anchor, "a whole-file anchor equals an item ID")
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
                for key in sorted((k for k, l in self.links.items() if l["type"] == kind and not l["anchor"]
                                   and l["source"] in component and l["target"] in component), key=str.encode):
                    self.report("LINK_CYCLE", self.links[key]["file"], self.links[key]["source"], key + " is part of a cycle")
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
        annex = annex_for(path)
        if annex is None:
            if symbol:
                return "unsupported", None, None
            return "ok", {"source.sig": fingerprint("lf1", self.data(path).replace(b"\r\n", b"\n"))}, ("file", path)
        parsed = self.parse(path)
        if not symbol:
            if parsed is None:
                return "ok", {"source.sig": fingerprint("lf1", self.data(path).replace(b"\r\n", b"\n"))}, ("file", path)
            return "ok", {"source.sig": fingerprint(annex.algorithm, parsed["whole"])}, ("file", path)
        if parsed is None:
            return "missing", None, None
        found = annex.select(parsed["definitions"], symbol, path)
        if not found:
            return "missing", None, None
        return "ok", {"source.sig": fingerprint(annex.algorithm, b" ".join(d["sig"] for d in found)),
                      "source.body": fingerprint(annex.algorithm, b" ".join(d["body"] for d in found))}, \
            ("defs", path, frozenset((d["start"], d["name"]) for d in found))

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
        if "trace.lock" in self.files and self.size("trace.lock") > MAX_FILE_BYTES:
            # OSTF-105 and OSTF-142: a lock above the size limit is not read, and no entry is used.
            self.lock = {}
            self.report("FILE_TOO_LARGE", "trace.lock", message="larger than 8 MiB; no entry is used")
        elif "trace.lock" in self.files:
            self.lock, problems = parse_lock(self.data("trace.lock"))
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
            if any(not value.partition(":")[1] or value.partition(":")[0] not in ALGORITHMS for value in recorded.values()):
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

    def _unlinked(self):
        """One info for the statements, other than obsolete ones, that no link targets: check
        reports whether links are fresh, so without it such a statement passes in silence.
        The count and the first ten IDs keep it short on a large imported set."""
        targets = {link["target"] for link in self.links.values()}
        statements = set(self.vocabulary["links"]["implements"]["to"])
        found = sorted((i for i, item in self.items.items() if item["type"] in statements
                        and item["status"] != "obsolete" and i not in targets), key=str.encode)
        if found:
            shown = ", ".join(found[:10]) + (f" and {len(found) - 10} more" if len(found) > 10 else "")
            self.report(UNLINKED, "trace.yaml", message=f"{len(found)} {'statement' if len(found) == 1 else 'statements'} that no link targets: {shown}",
                        hint="link the code, tests or verification item that carry each; check tracks links, not coverage")

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

    def failed(self, strict=False):
        """Annex I.1: whether check exits 1; with strict, also on an unstamped link and on a missing
        lock while the graph has links."""
        failing = {"suspect", "broken", "unstamped"} if strict else {"suspect", "broken"}
        return any(d["severity"] == "error" for d in self.diagnostics) or \
            any(l.get("state") in failing for l in self.links.values()) or \
            (strict and self.lock is None and not self.stopped and bool(self.links))


# --- context (Annex I.3, Annex J) -------------------------------------------

def item_context(analysis, ident):
    """Annex I.3: the items reached from ident by item-to-item links in their direction and the links
    from them, and every link to ident with its source when that is an item, one level deep."""
    reached, frontier = {ident}, [ident]
    while frontier:
        current = frontier.pop()
        for link in analysis.links.values():
            if not link["anchor"] and link["source"] == current and link["target"] not in reached:
                reached.add(link["target"])
                frontier.append(link["target"])
    incoming = {k for k, l in analysis.links.items() if l["target"] == ident}
    links = {k for k, l in analysis.links.items() if not l["anchor"] and l["source"] in reached} | incoming
    return reached | {analysis.links[k]["source"] for k in incoming if not analysis.links[k]["anchor"]}, links


def resolve(analysis, target, anchor=None):
    """('item', ID), ('anchor', direct link keys) or (code, None). TARGET names an item
    first; otherwise `anchor`, its root-relative form, is bound (Annex I.3)."""
    if target in analysis.names:
        return "item", analysis.names[target]
    if anchor == "":  # an anchor whose file lies outside the root is in no file of the view
        return ("UNKNOWN_TARGET" if ITEM_ID.fullmatch(target) else "BROKEN_LINK"), None
    status, _, binding = analysis.bind(target if anchor is None else anchor)
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
    if status == "invalid":
        return "ANCHOR_INVALID", None
    if status == "unsupported":
        return "UNSUPPORTED_LANGUAGE", None
    if ITEM_ID.fullmatch(target) and "#" not in target:
        return "UNKNOWN_TARGET", None
    return "BROKEN_LINK", None


def path_hint(analysis, target, anchor, spell, guess=False):
    """For a TARGET whose file is not in the view: the covered files whose path ends with the
    path given, spelled from the working directory by `spell`, since I.3 reads TARGET from there.
    With `guess`, TARGET may be a mistyped ID, so a hint needs such a file."""
    given, mark, symbol = target.partition("#")
    looked = (target if anchor is None else anchor).partition("#")[0]
    if not given or looked in analysis.files:
        return None  # the file is there, so its symbol is what failed
    tail = posixpath.normpath(given)
    found = sorted((p for p in analysis.files if analysis.covered(p) and (p == tail or p.endswith("/" + tail))), key=str.encode)
    if found:
        return "paths are relative to the working directory: try " + " or ".join(spell(p) + mark + symbol for p in found[:3])
    if guess:
        return None
    return f"paths are relative to the working directory, and the root has no {looked}" if looked else "the path is outside the root"


def context(analysis, target, anchor=None, spell=lambda path: path):
    """Annex I.3: the json context result and whether TARGET resolved. `spell` writes a
    root-relative path as TARGET would need it, for hints."""
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
        if kind == "UNKNOWN_TARGET":
            hint = analysis.nearest(target) or path_hint(analysis, target, anchor, spell, guess=True)
        else:
            hint = path_hint(analysis, target, anchor, spell) if kind == "BROKEN_LINK" else None
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
    shown, drawn = set(), set()

    def tree(ident, depth, skip):
        pad = "  " * depth
        item = analysis.items[ident]
        if ident in analysis.risk:
            lines.append(pad + "risk-relevant: ask before changing")
        if normalize_text(item.get("text", "")):
            lines.extend((pad + line).rstrip(" ") for line in normalize_text(item["text"]).split("\n"))
        if "rationale" in item:
            rationale = normalize_text(item["rationale"]).split("\n")
            lines.extend((pad + ("rationale: " if n == 0 else "") + line).rstrip(" ") for n, line in enumerate(rationale))
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
                               key=lambda l: (l["type"].encode(), l["target"].encode(), l["identity"].encode())))

        work = [(children(ident), depth)]
        while work:
            link = next(work[-1][0], None)
            if link is None:
                work.pop()
                continue
            level = "  " * work[-1][1]
            drawn.add(link["identity"])
            if link["target"] in shown:
                lines.append(level + f"{name(link)} {link['target']}{state(link)}")
                continue
            shown.add(link["target"])
            lines.append(level + f"{name(link)} {label(link['target'], True)}{state(link)}")
            work.append((children(link["target"]), work[-1][1] + 1))
        # Rule 4: links to the item from another anchor or from an item, unless rule 3 showed them.
        incoming = sorted((l for l in analysis.links.values() if l["target"] == ident and l["identity"] not in skip | drawn),
                          key=lambda l: (name(l, True).encode(), l["source"].encode()))
        for link in incoming:
            source = link["source"] if link["anchor"] or link["source"] in shown else label(link["source"], True)
            lines.append(pad + f"{name(link, True)} {source}{state(link)}")

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


# --- impact (Annex C.3) -----------------------------------------------------

def _parsed(view, path):
    """The annex parse of a file in a view, without reporting PARSE_ERROR outside OSTF-141's scope."""
    return view.parsed[path] if path in view.parsed else annex_for(path).parse(view.data(path), path)


def _definitions(view, path):
    """Body token streams by full symbol; a file that does not parse has none (C.3)."""
    parsed = _parsed(view, path) if path in view.files else None
    groups = {}
    for d in parsed["definitions"] if parsed else []:
        groups.setdefault(d["name"], []).append(d["body"])
    return {name: b" ".join(bodies) for name, bodies in groups.items()}


def _file_sig(view, path):
    if path not in view.files:
        return None
    annex = annex_for(path)
    parsed = _parsed(view, path) if annex else None
    return fingerprint(annex.algorithm, parsed["whole"]) if parsed else fingerprint("lf1", view.data(path).replace(b"\r\n", b"\n"))


def _bound(view, anchor):
    """The path of an anchor and the full symbols it binds to in a view; None for a whole file."""
    path, symbol = split_anchor(anchor)
    if not symbol:
        return path, None
    annex = annex_for(path)
    parsed = _parsed(view, path) if annex and path in view.files else None
    return path, {d["name"] for d in annex.select(parsed["definitions"], symbol, path)} if parsed else set()


def impact(base, current, rev):
    """Annex C.3: what changed from the base view to the evaluated view, or None when either graph failed."""
    if base.stopped or current.stopped:
        return None
    views = (base, current)
    anchored = {split_anchor(l["source"])[0] for v in views for l in v.links.values() if l["anchor"]}
    paths = {p for v in views for p in v.files if annex_for(p) and v.covered(p)} | {p for p in anchored if annex_for(p)}
    changed = {}
    for path in sorted(paths, key=str.encode):
        if path in base.files and path in current.files and base.data(path) == current.data(path):
            continue
        before, after = _definitions(base, path), _definitions(current, path)
        for name in before.keys() | after.keys():
            if before.get(name) != after.get(name):
                changed[path + "#" + name] = set()
    for path in {l["source"] for v in views for l in v.links.values() if l["anchor"] and "#" not in l["source"]}:
        if _file_sig(base, path) != _file_sig(current, path):
            changed[path] = set()
    for view in views:
        for link in view.links.values():
            if not link["anchor"]:
                continue
            path, names = _bound(view, link["source"])
            for anchor in changed:
                where, _, symbol = anchor.partition("#")
                if where == path and (names is None or symbol in names):
                    changed[anchor].add(link["target"])
    added = sorted(current.items.keys() - base.items.keys(), key=str.encode)
    removed = sorted(base.items.keys() - current.items.keys(), key=str.encode)
    modified = sorted((i for i in current.items.keys() & base.items.keys()
                       if current.hashes[i] != base.hashes[i] or current.items[i]["status"] != base.items[i]["status"]), key=str.encode)
    named = set().union(*changed.values()) | set(added) | set(modified)
    tests = {l["source"] for l in current.links.values()
             if l["anchor"] and l["type"] == "verifies" and l.get("status") == "ok" and l["target"] in named}
    for anchor in changed:
        path, _, symbol = anchor.partition("#")
        parsed = _parsed(current, path) if symbol and path in current.files else None
        if parsed and any(d["name"] == symbol and d["test"] for d in parsed["definitions"]):
            tests.add(anchor)
    return {
        "base": rev,
        "coverage": "direct",
        "changed": [{"anchor": a, "items": sorted(changed[a], key=str.encode)} for a in sorted(changed, key=str.encode)],
        "items": {"added": added, "changed": modified, "removed": removed},
        "links": {"added": sorted(current.links.keys() - base.links.keys(), key=str.encode),
                  "removed": sorted(base.links.keys() - current.links.keys(), key=str.encode)},
        "lock": {(True, True): "kept", (False, True): "added", (True, False): "removed", (False, False): "absent"}[
            ("trace.lock" in base.files, "trace.lock" in current.files)],
        "tests": sorted(tests, key=str.encode),
    }


# --- stamp (Annex I.4) ------------------------------------------------------

def stamp(analysis, names):
    """Annex I.4: the json result and the new trace.lock text, or None when nothing is stamped."""
    result = {"ostf": "0.3", "diagnostics": [d for d in analysis.diagnostics if analysis.stopped or d.get("file") == "trace.lock"],
              "items": [], "links": []}
    chosen, refused = [], []
    for name in dict.fromkeys(names):
        link = analysis.links.get(name)  # keys are identities, so a LINK must equal one byte for byte
        if link is None or link["status"] != "ok":
            why = "is not a link in the graph" if link is None else "has UNSUPPORTED_LANGUAGE" if link["status"] == "unsupported" else "is broken"
            refused.append({"code": "STAMP_REFUSED", "severity": "error", "subject": name, "message": name + " " + why})
        else:
            chosen.append(link)
    if refused:
        result["diagnostics"] += refused
        return result, None
    # Keep every entry a reader may use (OSTF-142); malformed lines and duplicates are dropped.
    entries = dict(analysis.lock or {})
    items = set()
    for link in chosen:
        entries[link["identity"]] = {"fingerprints": link["fingerprints"]}
        items |= {link["target"]} | (set() if link["anchor"] else {link["source"]})
    text = lock_text(entries)
    if len(text.encode()) > MAX_FILE_BYTES:  # a lock that no reader would use (OSTF-105)
        result["diagnostics"].append({"code": "STAMP_REFUSED", "severity": "error", "file": "trace.lock",
                                      "message": "the lock would be larger than 8 MiB", "hint": "split the root, so that each lock holds fewer links"})
        return result, None
    result["items"] = [analysis.item_row(i) for i in sorted(items, key=str.encode)]
    result["links"] = [{**analysis.link_row(l), "state": "valid", "reasons": []} for l in sorted(chosen, key=lambda l: l["identity"].encode())]
    return result, text


# --- SARIF (Annex D) --------------------------------------------------------

LEVEL = {"error": "error", "warning": "warning", "info": "note"}
STATE_LEVEL = {"broken": "error", "suspect": "warning", "unstamped": "note"}


def sarif(analysis, result):
    """Annex D: a check result as one SARIF 2.1.0 run."""
    def locations(file, name):
        location = {}
        if file is not None:
            location["physicalLocation"] = {"artifactLocation": {"uri": urllib.parse.quote(file, safe="/")}}
        if name is not None:
            location["logicalLocations"] = [{"fullyQualifiedName": name}]
        return {"locations": [location]} if location else {}

    def text(value):
        return {"text": value.replace("{", "{{").replace("}", "}}")}

    results = []
    for d in result["diagnostics"]:
        row = {"ruleId": d["code"], "level": LEVEL[d["severity"]], "message": text(d.get("message") or d["code"]),
               **locations(d.get("file"), d.get("subject"))}
        if "hint" in d:
            row["properties"] = {"ostf.hint": d["hint"]}
        results.append(row)
    for link in result["links"]:
        if link.get("state", "valid") == "valid":
            continue
        key = identity(link)
        file = split_anchor(link["source"])[0] if analysis.links[key]["anchor"] else analysis.item_file[link["source"]]
        for reason in link["reasons"]:
            results.append({"ruleId": reason, "level": STATE_LEVEL[link["state"]], "message": text(key + " " + link["state"]),
                            **locations(file, link["source"]), "properties": {"ostf.link": key, "ostf.state": link["state"]}})
    rules = sorted({r["ruleId"] for r in results}, key=str.encode)
    return {"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "ostf-reader", "rules": [{"id": r} for r in rules]}},
                                          "results": results}]}


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


def write_lock(path, text):
    """Annex I.6: modify no file but trace.lock. A lock that is a symbolic link, not a regular file or
    has other hard links is refused; the new lock is written to a file created beside it and renamed
    into place, so that a link made in the meantime is replaced, never written through."""
    path = pathlib.Path(path)
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        info = None
    if info is not None and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
        raise OSError("trace.lock is not a regular file with one link; not writing it")
    fd, temp = tempfile.mkstemp(prefix=".trace.lock.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as lock:
            lock.write(text.encode())
        os.chmod(temp, 0o644)
        os.replace(temp, path)
    except BaseException:
        os.unlink(temp)
        raise


def find_root(start):
    for directory in [start, *start.parents]:
        if (directory / "trace.yaml").is_file():
            return directory
    return None


def text_diagnostics(result):
    lines = []
    for d in result["diagnostics"]:
        where = " ".join(x for x in (d.get("file"), d.get("subject")) if x)
        hint = f" ({d['hint']})" if "hint" in d else ""
        lines.append(f"{d['severity']} {d['code']} {where}: {d['message']}{hint}")
    return lines


def text_check(result):
    lines = text_diagnostics(result)
    for link in result["links"]:
        if link.get("state") != "valid":
            lines.append(f"{link.get('state', 'no-state')} {identity(link)} {' '.join(link.get('reasons', []))}".rstrip())
    states = [l.get("state") for l in result["links"]]
    lines.append(f"{len(result['items'])} items, {len(states)} links, {states.count('valid')} valid")
    if "impact" in result:
        found = result["impact"]
        lines.append(f"impact against {found['base']} ({found['coverage']}):")
        lines += [f"  changed {c['anchor']} {' '.join(c['items'])}".rstrip() for c in found["changed"]]
        lines += [f"  item {kind} {i}" for kind in ("added", "changed", "removed") for i in found["items"][kind]]
        lines += [f"  link {kind} {i}" for kind in ("added", "removed") for i in found["links"][kind]]
        lines += [f"  trace.lock {found['lock']}"] if found["lock"] in ("added", "removed") else []
        lines += [f"  test {t}" for t in found["tests"]]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="OSTF 0.3 reader (Annex I check, context and stamp).")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("check", "context", "stamp"):
        sub = commands.add_parser(command)
        sub.add_argument("--root", type=pathlib.Path)
        sub.add_argument("--format", choices=["json", "text", "sarif"] if command == "check" else ["json", "text"], default="text")
        if command == "check":
            sub.add_argument("--base", metavar="REV")
            # Added option (Annex I.6): read the base view from a checkout of REV, given as the
            # directory that holds this root there, instead of from Git.
            sub.add_argument("--base-tree", metavar="DIR", type=pathlib.Path)
            sub.add_argument("--strict", action="store_true")
        if command == "context":
            sub.add_argument("target")
        if command == "stamp":
            sub.add_argument("links", nargs="+", metavar="LINK")
    args = parser.parse_args(argv)
    cwd = pathlib.Path(os.path.realpath(os.getcwd()))
    target = getattr(args, "target", None)
    # I.3: an anchor TARGET is a path relative to the working directory and selects the
    # root that covers its file; TARGET itself is kept as given for item lookup and output.
    path = target.partition("#")[0] if target is not None else None
    full = pathlib.Path(os.path.normpath(cwd / path)) if path else None
    looks_like_anchor = full is not None
    if args.root:
        root = pathlib.Path(os.path.realpath(args.root)) if (args.root / "trace.yaml").is_file() else None
    else:
        root = find_root(full.parent if looks_like_anchor else cwd)
    if root is None:
        where = "the working directory" if args.root or not looks_like_anchor or full.parent == cwd else \
            f"the directory of {path} (paths are relative to the working directory)"
        print("no trace.yaml at or above " + where, file=sys.stderr)
        return 2
    anchor = None
    if looks_like_anchor:
        anchor = full.relative_to(root).as_posix() + target[len(path):] if full.is_relative_to(root) and full != root else ""
    if args.command == "check" and (args.base is not None or args.base_tree is not None):
        if not args.base or (args.base_tree is not None and not args.base_tree.is_dir()):
            print("--base needs a nonempty REV, and --base-tree a directory: a checkout of REV at this root", file=sys.stderr)
            return 2
    try:
        analysis = Analysis(Tree(root))
        return _run(args, analysis, target, anchor, root)
    except (OSError, GitError) as error:
        print(error, file=sys.stderr)
        return 2


class GitError(Exception):
    """Git could not read the base revision."""


def git_view(root, rev):
    """The files under `root` at Git revision `rev`, by path relative to root, read with Git's
    plumbing commands, which run no hooks, filters or repository code. A revision without the
    root's directory gives an empty view (Annex C.3)."""
    import subprocess

    def git(*args, stdin=None):
        done = subprocess.run(["git", "-c", "core.fsmonitor=false", "-C", str(root), *args], input=stdin, capture_output=True)
        if done.returncode != 0:
            raise GitError(f"git {args[0]}: {done.stderr.decode(errors='replace').strip()}")
        return done.stdout

    try:
        prefix = git("rev-parse", "--show-prefix").decode().removesuffix("\n").removesuffix("/")
        commit = git("rev-parse", "--verify", "--quiet", "--end-of-options", rev + "^{commit}").decode().strip()
    except (GitError, OSError) as error:
        raise GitError(f"--base {rev} needs a Git checkout and a commit: {error}") from None
    try:
        listing = git("ls-tree", "-r", "-z", "--full-tree", "--end-of-options", commit + (":" + prefix if prefix else "^{tree}"))
    except GitError:
        return {}
    names, objects = [], []
    for entry in listing.split(b"\0"):
        meta, _, name = entry.partition(b"\t")
        fields = meta.split()
        if len(fields) == 3 and fields[1] == b"blob" and fields[0] != b"120000":
            names.append(name.decode("utf-8", "surrogateescape"))
            objects.append(fields[2])
    files, out = {}, git("cat-file", "--batch", stdin=b"".join(o + b"\n" for o in objects)) if objects else b""
    for name in names:
        header, _, out = out.partition(b"\n")
        size = int(header.split()[2])
        files[name], out = out[:size], out[size + 1:]
    return files


def _run(args, analysis, target, anchor, root):
    if args.command == "check":
        result = analysis.result()
        if args.base is not None:
            base = Tree(args.base_tree) if args.base_tree is not None else git_view(root, args.base)
            found = impact(Analysis(base), analysis, args.base)
            if found is not None:
                result["impact"] = found
        if args.format == "sarif":
            print(json.dumps(sarif(analysis, result), indent=2, ensure_ascii=False))
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False) if args.format == "json" else text_check(result), end="\n" if args.format == "json" else "")
        return 1 if analysis.failed(args.strict) else 0
    if args.command == "stamp":
        result, text = stamp(analysis, args.links)
        if text is not None:
            write_lock(root / "trace.lock", text)
        if args.format == "json":
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("".join(line + "\n" for line in text_diagnostics(result) + ["stamped " + identity(l) for l in result["links"]]), end="")
        return 0 if text is not None else 1
    cwd = os.path.realpath(os.getcwd())
    result, resolved = context(analysis, target, anchor, lambda p: pathlib.Path(os.path.relpath(root / p, cwd)).as_posix())
    if args.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif resolved:
        print(render(analysis, target, anchor), end="")
    else:
        print(text_check(result), end="")
    return 0 if resolved else 1


if __name__ == "__main__":
    sys.exit(main())
