# SPDX-License-Identifier: Apache-2.0
"""The scripted fake agent of the Phase 5 dry run (phase5.md, Harness): it calls no model.

It reads the task the harness hands it, makes the same generic change for every task of a kind,
in every arm, and writes its transcript in Claude Code's stream-json form, so that the harness
prepares, runs, reads, judges and scores it as it would a real agent. In the full arm it calls
`ostf`, and its answers repeat what the tool printed; elsewhere it reads the files. Its outcomes
measure the harness, never an arm: the fake knows no more in one arm than in another, and some
of its changes fail on purpose, such as a rename that does not move the function in TypeScript.
"""
import json
import re
import shutil
import subprocess
import urllib.parse
import uuid


class Session:
    """One fake session: the commands it runs and the files it writes, as transcript events."""

    def __init__(self, repo, env, transcript):
        self.repo, self.env, self.transcript = repo, env, transcript
        self.id = f"fake-{uuid.uuid4()}"
        self.events = [{"type": "system", "subtype": "init", "session_id": self.id, "model": "fake"}]
        self.n = 0

    def _call(self, name, data, output):
        self.n += 1
        ident = f"toolu_fake_{self.n}"
        self.events.append({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": ident, "name": name, "input": data}]}})
        self.events.append({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": ident, "content": output}]}})

    def sh(self, command):
        done = subprocess.run(["/bin/sh", "-c", command], cwd=self.repo, env=self.env, capture_output=True, text=True)
        output = (done.stdout + done.stderr)[-20000:]
        self._call("Bash", {"command": command}, output)
        return done.stdout

    def read(self, path):
        file = self.repo / path
        text = file.read_text() if file.is_file() else ""
        self._call("Read", {"file_path": str(file)}, text[:20000])
        return text

    def write(self, path, text):
        file = self.repo / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)
        self._call("Write", {"file_path": str(file), "content": text}, "ok")

    def finish(self, text):
        self.events.append({"type": "result", "result": text, "usage": {"input_tokens": 0, "output_tokens": 0}, "total_cost_usd": 0})
        self.transcript.write_text("".join(json.dumps(e) + "\n" for e in self.events))


def run(repo, env, prompt, transcript, resume=None, task=None, task_id=None, arm=None, fixture=None, turn=1, index=None, change=None, **_):
    s = Session(repo, env, transcript)
    go = (repo / "go.mod").exists()
    tool = shutil.which("ostf", path=env["PATH"]) is not None
    record = (repo / "trace.yaml").exists()
    kind = task["kind"] if task else "change"
    p = (task or {}).get("params", {})
    tag = re.sub(r"\W", "x", f"{task_id}N{index + 1}" if index is not None else (change or task_id or "x"))
    if tool:
        s.sh("ostf check --base main")
    elif record:
        s.read("trace.yaml")
    else:
        s.read("REQUIREMENTS.md")
    if kind == "explain":
        s.finish(explain(s, prompt, tool))
    elif kind in ("risk", "principal") and turn == 1:
        s.finish(f"{p['file']} holds code marked risk-relevant ({p['item']}). Shall I go ahead?")
    elif kind in ("risk", "principal"):
        comment = "// Changed at the user's request.\n"
        s.write(p["file"], (repo / p["file"]).read_text() + comment)
        s.sh("go test ./..." if go else "node --test")
        note = f" {p['item']} is risk-relevant: another person should look at it in the pull request." if kind == "principal" else ""
        s.finish(f"Done.{note}")
    elif kind == "rename":
        s.finish(rename(s, p, go, record))
    elif kind == "invented":
        s.finish(f"{p['id']} does not exist in the repository, so I added no test for it.")
    elif kind == "impact":
        s.finish(impact(s, go, tool))
    elif kind == "derived":
        s.sh("ostf check")
        s.finish("The check fails because a line of trace.derived is malformed. A test tool writes that file, so I left it as it is; "
                 "regenerate it with the tool.")
    elif kind == "review":
        if record:
            link_file(s, p["item"], p["file"])
        s.finish(f"No automated test covers {p['file']}; {p['verification']} verifies {p['item']}.")
    else:
        # implement, jira, threat, decision, injection, a T12 run and a longitudinal change
        s.finish(add(s, kind, tag, p, go, record, tool, change))


def explain(s, prompt, tool):
    import harness
    anchor = harness.anchor_of(prompt)
    if not tool:
        return "I could not tell from the repository."
    context = json.loads(s.sh(f"ostf context '{anchor}' --format json") or "{}")
    found = context.get("links", [])
    linked = sorted({l["target"] for l in found if l["source"] == anchor})
    texts = {i["id"]: " ".join(i.get("text", "").split()) for i in context.get("items", [])}
    tests = sorted({urllib.parse.unquote(l["source"].partition("#")[2]) for l in found if l["type"] == "verifies" and l["target"] in linked
                    and "#" in l["source"]})
    return "It exists because of " + "; ".join(f"{i}: {texts.get(i, '')}" for i in linked) + ". Tests: " + ", ".join(tests) + "."


def impact(s, go, tool):
    listed, tests = [], []
    if tool:
        result = json.loads(s.sh("ostf check --base main --format json") or "{}").get("impact", {})
        listed = sorted({i for c in result.get("changed", []) for i in c["items"]})
        tests = [urllib.parse.unquote(t.partition("#")[2]) for t in result.get("tests", [])]
    s.sh("go test -v ./..." if go else "node --test")
    return ("The change touches " + ", ".join(f"{i}, which still holds" for i in listed) + ". Tests: " + ", ".join(tests) + "."
            if listed else "I ran the tests; they pass.")


def link_file(s, item, path):
    """Add a whole-file anchor to an item's code, in the YAML file that declares it."""
    for rel in ["trace.yaml", *sorted(str(p.relative_to(s.repo)) for p in (s.repo / "trace").glob("*.yaml"))]:
        text = (s.repo / rel).read_text()
        block = re.search(rf"^  - id: {re.escape(item)}\n(?:    .*\n|      .*\n)*", text, re.M)
        if block:
            s.write(rel, text[:block.end()] + f"    code: [{path}]\n" + text[block.end():])
            return


def rename(s, p, go, record):
    old_path, _, old_name = p["oldAnchor"].partition("#")
    new_path, _, new_name = p["newAnchor"].partition("#")
    files = sorted(s.repo.glob("*/*.go") if go else s.repo.glob("src/*.ts"))
    for file in files:
        text = file.read_text()
        renamed = re.sub(rf"\b{re.escape(old_name)}\(", f"{new_name}(", text)
        renamed = re.sub(rf"\bfunction {re.escape(old_name)}\b", f"function {new_name}", renamed)
        if renamed != text:
            s.write(str(file.relative_to(s.repo)), renamed)
    if go:
        move_go(s, old_path, new_path, new_name)
    if record:
        for yaml in [s.repo / "trace.yaml", *sorted((s.repo / "trace").glob("*.yaml"))]:
            text = yaml.read_text()
            target = p["newAnchor"] if go else f"{old_path}#{new_name}"
            if p["oldAnchor"] in text:
                s.write(str(yaml.relative_to(s.repo)), text.replace(p["oldAnchor"], target))
    s.sh("go test ./..." if go else "node --test")
    return f"Renamed {old_name} to {new_name}."


GO_IMPORTS = ("errors", "fmt", "slices", "sync", "time")


def move_go(s, old_path, new_path, name):
    """Move a renamed Go function, with its doc comment, into a new file of the same package."""
    import harness
    reader = harness.load_reader()
    annex = reader.annex_for(old_path)
    data = (s.repo / old_path).read_bytes()
    found = [d for d in annex.parse(data, old_path)["definitions"] if d["name"] == name]
    if not found:
        return
    d = found[0]
    moved = data[d["docStart"]:d["end"]].decode()
    rest = (data[:d["docStart"]].decode().rstrip("\n") + "\n" + data[d["end"]:].decode().lstrip("\n")).rstrip("\n") + "\n"
    package = re.search(r"^package (\w+)", rest, re.M).group(1)
    needed = [i for i in GO_IMPORTS if f"{i}." in moved]
    header = f"// SPDX-License-Identifier: Apache-2.0\npackage {package}\n\n"
    if needed:
        header += "import (\n" + "".join(f'\t"{i}"\n' for i in needed) + ")\n\n"
    for i in GO_IMPORTS:
        if f"{i}." not in rest.split(")", 1)[-1]:
            rest = re.sub(rf'^\t"{i}"\n', "", rest, flags=re.M)
    rest = re.sub(r"import \(\n\)\n\n", "", rest)
    s.write(old_path, rest)
    s.write(new_path, header + moved + "\n")


def add(s, kind, tag, p, go, record, tool, change):
    """A new function and its test, and in trace.yaml a draft item or a tag that links them."""
    lower = tag.lower()
    name = ("Fake" if go else "fake") + tag
    item = f"R-FAKE-{tag.upper()}"
    tags = {"jira": p.get("item"), "decision": p.get("item")}.get(kind)
    code_tag = f"// @req {tags}\n" if record and tags else ""
    test_tag = f"// @req {tags if kind == 'jira' else item}\n" if record and kind in ("jira",) else ""
    if go:
        code, test = f"pricing/fake_{lower}.go", f"pricing/fake_{lower}_test.go"
        code_anchor, test_anchor = f"{code}#{name}", f"{test}#Test{name}"
        if kind != "injection":
            s.write(code, f"// SPDX-License-Identifier: Apache-2.0\npackage pricing\n\n// {name} returns one.\n{code_tag}func {name}() int {{ return 1 }}\n")
        body = f"\tif {name}() != 1 {{\n\t\tt.Fatal(\"want 1\")\n\t}}\n" if kind != "injection" else ""
        s.write(test, f"// SPDX-License-Identifier: Apache-2.0\npackage pricing\n\nimport \"testing\"\n\n{test_tag}func Test{name}(t *testing.T) {{\n{body}}}\n")
    else:
        code, test = f"src/fake-{lower}.ts", f"src/fake-{lower}.test.ts"
        code_anchor, test_anchor = f"{code}#{name}", f"{test}#{name} returns one"
        if kind != "injection":
            s.write(code, f"// SPDX-License-Identifier: Apache-2.0\n/** Returns one. */\n{code_tag}export function {name}(): number {{\n  return 1;\n}}\n")
        imports = f'import {{ {name} }} from "./fake-{lower}.ts";\n' if kind != "injection" else ""
        check = f"  assert.equal({name}(), 1);\n" if kind != "injection" else "  assert.ok(true);\n"
        s.write(test, f'// SPDX-License-Identifier: Apache-2.0\nimport {{ test }} from "node:test";\nimport assert from "node:assert/strict";\n{imports}\n'
                      f'{test_tag}test("{name} returns one", () => {{\n{check}}});\n')
    if record and kind in ("implement", "threat", "decision", "parallel", "change"):
        controls = f"    controls: [{p['threat']}]\n" if kind == "threat" else ""
        entry = (f"  - id: {item}\n    status: draft\n    title: {name}\n    text: {name} returns one.\n{controls}"
                 f"    code: [{code_anchor}]\n    tests: [\"{test_anchor}\"]\n")
        yaml = s.repo / "trace" / "requirements.yaml"
        s.write("trace/requirements.yaml", yaml.read_text().rstrip("\n") + "\n" + entry)
    elif not record and (s.repo / "AGENTS.md").read_text().find("REQUIREMENTS.md lists this project's requirements, risks") >= 0 \
            and kind in ("implement", "threat", "decision", "parallel", "change"):
        manifest = (s.repo / "REQUIREMENTS.md").read_text()
        s.write("REQUIREMENTS.md", manifest.rstrip("\n") + f"\n\n### {item}: {name}\n\n{name} returns one.\n\n- Status: draft\n- Code: `{name}` in `{code}`\n")
    s.sh("go test ./..." if go else "node --test")
    summary = ""
    if tool:
        result = json.loads(s.sh("ostf check --base main --format json") or "{}").get("impact", {})
        listed = sorted({i for c in result.get("changed", []) for i in c["items"]} | set(result.get("items", {}).get("added", [])))
        summary = " The check lists " + ", ".join(f"{i}, which my change keeps true" for i in listed) + "." if listed else ""
    added = f" I added {item}." if record and kind in ("implement", "threat", "decision", "parallel", "change") else ""
    return f"Added {name} and its test.{added}{summary}"
