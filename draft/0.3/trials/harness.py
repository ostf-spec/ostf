#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Phase 5 trials: run coding agents on the fixture repositories and score them.

    python3 harness.py run [--agents claude,codex] [--conditions ...] [--fixtures ...] [--tasks ...] [--reps 3] [--jobs 4]
    python3 harness.py report

The tasks, prompts and pass criteria are in tasks.json and protocol.md, frozen before any run.
Each run copies a fixture into a fresh Git repository, applies the task's setup, puts the
condition's tool on PATH as `ostf`, runs the agent headless with the prompt and scores the
final repository and the transcript. Results go to results/RUN.json; transcripts stay in the
work directory, which is outside the repository.
"""
import argparse
import concurrent.futures
import datetime
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
RESULTS = pathlib.Path(os.environ.get("OSTF_TRIALS_RESULTS", HERE / "results"))
DRAFT = HERE.parent
WORK = pathlib.Path(os.environ.get("OSTF_TRIALS_WORK", "/tmp/ostf-trials/runs"))
TOOLS = {
    "python": pathlib.Path(os.environ.get("OSTF_TRIALS_PYTHON_TOOL", "/tmp/ostf-trials/ostf-venv/bin/ostf")),
    "zztrace": pathlib.Path(os.environ.get("OSTF_TRIALS_ZZTRACE_TOOL", "/tmp/ostf-trials/zztrace-ostf")),
}
# condition: (tool, MCP binding available)
CONDITIONS = {"py-shell": ("python", False), "zz-shell": ("zztrace", False), "zz-mcp": ("zztrace", True)}
CLAUDE_MODEL = os.environ.get("OSTF_TRIALS_CLAUDE_MODEL", "sonnet")
CODEX_MODEL = os.environ.get("OSTF_TRIALS_CODEX_MODEL", "gpt-6-astra")
CODEX_EFFORT = os.environ.get("OSTF_TRIALS_CODEX_EFFORT", "medium")
TIMEOUT = int(os.environ.get("OSTF_TRIALS_TIMEOUT", "1200"))
GIT = ["git", "-c", "user.name=trial", "-c", "user.email=trial@example.com", "-c", "commit.gpgsign=false"]
READER = DRAFT / "conformance" / "reader.py"


def load_tasks():
    return json.loads((HERE / "tasks.json").read_text())


# --- preparing a run ---------------------------------------------------------

def prepare(run_dir, fixture, task, tool):
    if run_dir.exists():
        shutil.rmtree(run_dir)
    repo = run_dir / "repo"
    shutil.copytree(FIXTURES / fixture, repo)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    (repo / ".git" / "info" / "exclude").write_text(".cache/\n")
    subprocess.run(GIT + ["-C", str(repo), "add", "-A"], check=True)
    subprocess.run(GIT + ["-C", str(repo), "commit", "-q", "-m", "Shop at main"], check=True)
    setup = task.get("setup", {})
    if "patch" in setup:
        subprocess.run(["git", "-C", str(repo), "apply", str(HERE / setup["patch"])], check=True)
    if "corruptLock" in setup:
        # The damaged line is committed, as a bad merge would leave it, so that it is the
        # repository's state and not an uncommitted edit of the user's.
        lock = repo / "trace.lock"
        lines = lock.read_text().split("\n")
        old, new = setup["corruptLock"]
        lines = [line.replace(old, new) if old in line else line for line in lines]
        lock.write_text("\n".join(lines))
        subprocess.run(GIT + ["-C", str(repo), "commit", "-q", "-a", "-m", "Merge branch 'refund-tweaks'"], check=True)
    bin_dir = run_dir / "bin"
    bin_dir.mkdir()
    (bin_dir / "ostf").symlink_to(TOOLS[tool])
    return repo, bin_dir


def environment(repo, bin_dir):
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["GOCACHE"] = str(repo / ".cache" / "go-build")
    env["GOTMPDIR"] = str(repo / ".cache")
    env["GOFLAGS"] = "-mod=mod"
    env.pop("OSTF_DRAFT", None)
    return env


# --- running agents ----------------------------------------------------------

def run_claude(repo, bin_dir, prompt, mcp, transcript, resume=None):
    command = ["claude", "-p", prompt, "--model", CLAUDE_MODEL, "--output-format", "stream-json", "--verbose",
               "--dangerously-skip-permissions", "--setting-sources", "project", "--strict-mcp-config"]
    if mcp:
        config = transcript.parent / "mcp.json"
        config.write_text(json.dumps({"mcpServers": {"ostf": {"command": str(TOOLS["zztrace"]), "args": ["serve", "--root", str(repo)]}}}))
        command += ["--mcp-config", str(config)]
    if resume:
        command += ["--resume", resume]
    return _run(command, repo, bin_dir, transcript)


def run_codex(repo, bin_dir, prompt, mcp, transcript, resume=None):
    options = ["--json", "-m", CODEX_MODEL, "-c", f'model_reasoning_effort="{CODEX_EFFORT}"', "--ignore-user-config",
               "--skip-git-repo-check", "-c", 'sandbox_mode="workspace-write"']
    if mcp:
        options += ["-c", f'mcp_servers.ostf.command="{TOOLS["zztrace"]}"', "-c", f'mcp_servers.ostf.args=["serve","--root","{repo}"]',
                    "-c", 'mcp_servers.ostf.default_tools_approval_mode="approve"']
    if resume:
        command = ["codex", "exec", "resume", *options, resume, prompt]
    else:
        command = ["codex", "exec", *options, "-C", str(repo), prompt]
    return _run(command, repo, bin_dir, transcript)


def _run(command, repo, bin_dir, transcript):
    started = time.time()
    with open(transcript, "w") as out:
        try:
            done = subprocess.run(command, cwd=repo, env=environment(repo, bin_dir), stdin=subprocess.DEVNULL, stdout=out,
                                  stderr=subprocess.PIPE, timeout=TIMEOUT)
            code = done.returncode
        except subprocess.TimeoutExpired:
            code = "timeout"
    return {"exit": code, "seconds": round(time.time() - started, 1)}


AGENTS = {"claude": run_claude, "codex": run_codex}

# --- reading transcripts -----------------------------------------------------

def unwrapped(command):
    """The script inside a shell wrapper such as Codex's /bin/zsh -lc '...', or the command itself."""
    wrapped = re.fullmatch(r"\S*/(?:ba|z)?sh\s+-l?c\s+(['\"])(.*)\1", command, re.S)
    if not wrapped:
        return command
    script = wrapped.group(2)
    return script.replace("'\\''", "'") if wrapped.group(1) == "'" else re.sub(r'\\(["\\$`])', r"\1", script)


def unquoted(command):
    """A shell command with its here-document bodies and quoted strings blanked, so that a > inside
    a quoted test name, a commit message or a script does not read as a redirect."""
    command = re.sub(r"(<<-?\s*(['\"]?)(\w+)\2[^\n]*\n).*?^\t*\3$", r"\1", command, flags=re.S | re.M)
    return re.sub(r"'[^']*'|\"(?:\\.|[^\"\\])*\"", "''", command)


# A redirect counts only outside quotes and here-documents, and not to /dev/null; the other
# patterns count anywhere, since a script that writes a file usually quotes the file name or the mode.
REDIRECT = re.compile(r"(?<![0-9&])>>?(?!&)\s*(?!/dev/null\b)[^\s&|]")
WRITES = re.compile(r"\bsed\s+-i|\bperl\s+-[a-z]*i|\btee\b|\bapply_patch\b|\bmv\s|\bcp\s|\brm\s|\btruncate\b|gofmt\s+-w|\bwrite_text\b|open\([^)]*['\"]w")


def writes(command):
    command = unwrapped(command)
    return bool(WRITES.search(command) or REDIRECT.search(unquoted(command)))


def calls(agent, transcript):
    """The ordered tool calls of a transcript as dicts with kind (shell, edit, read, mcp, other),
    detail, output and the final message, session id and usage."""
    found, final, session, usage, outputs = [], "", None, {}, {}
    for line in transcript.read_text().splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if agent == "claude":
            kind = event.get("type")
            if kind == "system" and event.get("subtype") == "init":
                session = event.get("session_id")
                usage["model"] = event.get("model")
            elif kind == "assistant":
                for block in event["message"]["content"]:
                    if block.get("type") == "tool_use":
                        name, data = block["name"], block.get("input") or {}
                        if name == "Bash":
                            call = {"kind": "shell", "detail": data.get("command", "")}
                        elif name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
                            call = {"kind": "edit", "detail": data.get("file_path", "")}
                        elif name in ("Read", "Grep", "Glob", "LS"):
                            call = {"kind": "read", "detail": json.dumps(data)[:300]}
                        elif name.startswith("mcp__"):
                            call = {"kind": "mcp", "detail": name.split("__")[-1] + " " + json.dumps(data)}
                        else:
                            call = {"kind": "other", "detail": name}
                        call["id"] = block.get("id")
                        found.append(call)
            elif kind == "user":
                for block in event["message"].get("content", []):
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        content = block.get("content")
                        text = content if isinstance(content, str) else "".join(c.get("text", "") for c in content or [] if isinstance(c, dict))
                        outputs[block.get("tool_use_id")] = text
            elif kind == "result":
                final = event.get("result") or ""
                usage.update({k: v for k, v in (event.get("usage") or {}).items() if isinstance(v, int)})
                usage["cost"] = event.get("total_cost_usd")
        else:
            kind = event.get("type")
            item = event.get("item") or {}
            if kind == "thread.started":
                session = event.get("thread_id")
            elif kind == "item.completed":
                if item.get("type") == "command_execution":
                    found.append({"kind": "shell", "detail": item.get("command", ""), "output": item.get("aggregated_output", ""),
                                  "exit": item.get("exit_code")})
                elif item.get("type") == "file_change":
                    for change in item.get("changes") or []:
                        found.append({"kind": "edit", "detail": change.get("path", "")})
                elif item.get("type") == "mcp_tool_call":
                    found.append({"kind": "mcp", "detail": f"{item.get('tool')} {json.dumps(item.get('arguments'))}",
                                  "output": json.dumps(item.get("result"))[:200000]})
                elif item.get("type") == "agent_message":
                    final = item.get("text") or final
            elif kind == "turn.completed":
                for k, v in (event.get("usage") or {}).items():
                    usage[k] = usage.get(k, 0) + v
    for call in found:
        if "id" in call:
            call["output"] = outputs.get(call.pop("id"), "")
        if call["kind"] == "shell" and writes(call["detail"]) and not re.search(r"\bostf\s+stamp\b", call["detail"]):
            call["writes"] = True
    return found, final, session, usage


def metrics(found):
    """Metrics of plan section 8 that a transcript gives."""
    def is_ostf(call):
        return call["kind"] == "mcp" or re.search(r"(^|[\s/;&|'\"])ostf\s+(check|context|stamp)\b", call["detail"])

    def is_edit(call):
        return call["kind"] == "edit" or call.get("writes")

    first_edit = next((i for i, c in enumerate(found) if is_edit(c)), None)
    ostf_calls = [c for c in found if is_ostf(c)]
    ostf_bytes = sum(len(c.get("output", "")) for c in ostf_calls)
    ostf_bytes += sum(len(c.get("output", "")) for c in found if c["kind"] in ("read", "shell") and re.search(r"trace\.(yaml|lock)|trace/", c["detail"]) and not is_ostf(c))
    lock_edits = [c["detail"] for c in found if (c["kind"] == "edit" and c["detail"].endswith("trace.lock"))
                  or (c.get("writes") and "trace.lock" in c["detail"])]
    first_ostf = next((i for i, c in enumerate(found) if is_ostf(c)), None)
    return {
        "calls": len(found),
        "callsBeforeFirstEdit": first_edit if first_edit is not None else len(found),
        "edited": first_edit is not None,
        "ostfCalls": len(ostf_calls),
        "ostfCallsBeforeFirstEdit": sum(1 for c in found[: first_edit if first_edit is not None else len(found)] if is_ostf(c)),
        "firstOstfCall": first_ostf,
        "usedMcp": any(c["kind"] == "mcp" for c in found),
        "usedShellTool": any(c["kind"] == "shell" and is_ostf(c) for c in found),
        "contextCalls": sum(1 for c in ostf_calls if "context" in c["detail"]),
        "stampCalls": sum(1 for c in ostf_calls if "stamp" in c["detail"]),
        "ostfOutputTokens": round(ostf_bytes / 4),
        "lockHandEdits": lock_edits,
    }


# --- judging the final repository ---------------------------------------------

def judge(repo, setup):
    """The final state as the reference reader and the tests see it, and what changed since setup,
    the commit the task's setup left, whether or not the agent committed its change."""
    python = sys.executable
    done = subprocess.run([python, str(READER), "check", "--format", "json"], cwd=repo, capture_output=True, text=True)
    try:
        result = json.loads(done.stdout)
    except json.JSONDecodeError:
        result = {"diagnostics": [{"code": "UNREADABLE", "severity": "error"}], "items": [], "links": []}
    if (repo / "go.mod").exists():
        tests = subprocess.run(["go", "test", "./..."], cwd=repo, capture_output=True, text=True, env=environment(repo, repo))
    else:
        tests = subprocess.run(["node", "--test"], cwd=repo, capture_output=True, text=True)
    git = ["git", "-C", str(repo)]
    tracked = subprocess.run(git + ["diff", "--name-only", setup], capture_output=True, text=True).stdout.splitlines()
    untracked = subprocess.run(git + ["ls-files", "--others", "--exclude-standard"], capture_output=True, text=True).stdout.splitlines()
    changed = sorted({path for path in tracked + untracked if path and not path.startswith(".cache")})
    diff = subprocess.run(git + ["diff", setup], capture_output=True, text=True).stdout
    return {"checkExit": done.returncode, "result": result, "testsPass": tests.returncode == 0, "changed": changed, "diff": diff}


def changed_anchors(repo, setup):
    """How many functions and tests changed since setup, as the impact of check --base lists them."""
    done = subprocess.run([sys.executable, str(READER), "check", "--base", setup, "--format", "json"], cwd=repo, capture_output=True, text=True)
    try:
        return len(json.loads(done.stdout)["impact"]["changed"])
    except (json.JSONDecodeError, KeyError):
        return None


def codes(state):
    return sorted({d["code"] for d in state["result"]["diagnostics"]})


def links(state):
    return {(l["source"], l["type"], l["target"]): l for l in state["result"]["links"]}


def items(state):
    return {i["id"]: i for i in state["result"]["items"]}


def changed_files(state):
    return state["changed"]


ASKS = re.compile(r"\?|\b(confirm|go ahead|proceed|approv|permission|shall I|should I|want me to)", re.I)


def mentions(text, needles):
    return {n: (n in text) for n in needles}


def no_invented_ids(state):
    return not ({"UNKNOWN_TARGET", "TAG_UNKNOWN_ID"} & set(codes(state)))


def score(task, base, state, final, found, m, second=None):
    """Pass criteria of protocol.md, by task kind. Returns (pass, criteria)."""
    kind, p = task["kind"], task.get("params", {})
    c = {}
    if kind == "explain":
        c["noFilesChanged"] = changed_files(state) == []
        c["namesItems"] = all(mentions(final, p["items"]).values())
        c["namesTests"] = all(mentions(final, p["tests"]).values())
    elif kind == "implement":
        new = {i: v for i, v in items(state).items() if i not in items(base)}
        drafts = [i for i, v in new.items() if v["status"] == "draft"]
        linked = {l[2] for l in links(state) if l[2] in drafts}
        impl = {l[2] for l, v in links(state).items() if l[2] in drafts and l[1] == "implements"}
        ver = {l[2] for l, v in links(state).items() if l[2] in drafts and l[1] == "verifies"}
        c["newDraftItem"] = bool(drafts)
        c["implementedAndVerified"] = bool(impl & ver)
        c["checkPasses"] = state["checkExit"] == 0
        c["testsPass"] = state["testsPass"]
        c["noInventedIds"] = no_invented_ids(state)
        c["listsAddedItem"] = any(d in final for d in drafts)
    elif kind == "risk":
        first, final1 = second
        c["askedBeforeEditing"] = all(p["file"] not in f for f in changed_files(first)) and bool(ASKS.search(final1))
        c["changedAfterYes"] = p["file"] in state["diff"]
        c["checkPasses"] = state["checkExit"] == 0
        c["testsPass"] = state["testsPass"]
        c["linkValid"] = all(v.get("state") == "valid" for k, v in links(state).items() if k[0].startswith(p["file"]) and k[2] == p["item"])
    elif kind == "rename":
        new_links = [k for k in links(state) if k[0] == p["newAnchor"]]
        c["linkMoved"] = bool(new_links) and all(k[2] in p["items"] for k in new_links)
        c["noBrokenLink"] = "BROKEN_LINK" not in codes(state)
        c["oldNameGone"] = p["oldName"] not in state["diff"].replace("-", "") or p["oldAnchor"] not in {k[0] for k in links(state)}
        c["checkPasses"] = state["checkExit"] == 0
        c["testsPass"] = state["testsPass"]
    elif kind == "jira":
        target = p["item"]
        to_item = [k for k in links(state) if k[2] == target and (k not in links(base))]
        c["codeLinked"] = any(k[1] == "implements" for k in to_item)
        c["testLinked"] = any(k[1] == "verifies" for k in to_item)
        c["itemUnchanged"] = items(state).get(target, {}).get("fingerprint") == items(base)[target]["fingerprint"]
        c["noDuplicateItem"] = len(items(state)) == len(items(base))
        c["checkPasses"] = state["checkExit"] == 0
        c["testsPass"] = state["testsPass"]
    elif kind == "invented":
        c["idNotWritten"] = p["id"] not in state["diff"]
        c["reported"] = p["id"] in final
        c["checkPasses"] = state["checkExit"] == 0
    elif kind == "impact":
        c["namesItems"] = all(mentions(final, p["items"]).values())
        c["namesTests"] = all(mentions(final, p["tests"]).values())
        c["ranTests"] = any(re.search(r"\bgo\s+test\b|\bnode\s+--test\b|\bnpm\s+test\b", x["detail"]) for x in found if x["kind"] == "shell")
        c["noOtherFilesChanged"] = set(changed_files(state)) <= set(p["patchFiles"]) | {"trace.lock"}
    elif kind == "lock":
        c["checkPasses"] = state["checkExit"] == 0
        c["usedStamp"] = m["stampCalls"] > 0
    c["noLockHandEdit"] = not m["lockHandEdits"]
    return all(c.values()), c


# --- one run --------------------------------------------------------------------

def run_one(agent, condition, fixture, task_id, rep):
    tasks = load_tasks()
    task = tasks["tasks"][task_id][fixture]
    name = f"{agent}.{condition}.{fixture}.{task_id}.{rep}"
    target = RESULTS / f"{name}.json"
    if target.exists():
        return json.loads(target.read_text())
    tool, mcp = CONDITIONS[condition]
    run_dir = WORK / name
    repo, bin_dir = prepare(run_dir, fixture, task, tool)
    setup = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    base = judge(repo, setup)
    transcript = run_dir / "transcript.jsonl"
    timing = AGENTS[agent](repo, bin_dir, task["prompt"], mcp, transcript)
    found, final, session, usage = calls(agent, transcript)
    second = None
    if task["kind"] == "risk":
        first_state, first_final = judge(repo, setup), final
        transcript2 = run_dir / "transcript2.jsonl"
        timing2 = AGENTS[agent](repo, bin_dir, task["followUp"], mcp, transcript2, resume=session)
        found2, final, _, usage2 = calls(agent, transcript2)
        found = found + found2
        for k, v in usage2.items():
            if isinstance(v, (int, float)) and isinstance(usage.get(k), (int, float)):
                usage[k] += v
        timing = {"exit": [timing["exit"], timing2["exit"]], "seconds": timing["seconds"] + timing2["seconds"]}
        second = (first_state, first_final)
    m = metrics(found)
    state = judge(repo, setup)
    passed, criteria = score(task, base, state, final, found, m, second)
    record = {"run": name, "agent": agent, "condition": condition, "fixture": fixture, "task": task_id, "rep": rep,
              "pass": passed, "criteria": criteria, "metrics": m, "timing": timing, "usage": usage,
              "finalCheck": {"exit": state["checkExit"], "codes": codes(state)}, "testsPass": state["testsPass"],
              "changedFiles": changed_files(state), "changedAnchors": changed_anchors(repo, setup), "finalMessage": final[-4000:],
              "date": datetime.date.today().isoformat()}
    RESULTS.mkdir(exist_ok=True)
    target.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n")
    return record


def main(argv=None):
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--agents", default="claude,codex")
    run.add_argument("--conditions", default=",".join(CONDITIONS))
    run.add_argument("--fixtures", default="go-shop,ts-shop")
    run.add_argument("--tasks", default="")
    run.add_argument("--reps", type=int, default=3)
    run.add_argument("--jobs", type=int, default=4)
    commands.add_parser("report")
    args = parser.parse_args(argv)
    if args.command == "report":
        import report
        corrected = ("The edit metrics were read again from every transcript after the write detector was corrected; "
                     "no pass or fail changed ([protocol](protocol.md#harness-corrections)).")
        report.write(HERE / "results" / "round1", HERE / "results-round1.md", "Phase 5 trial results, round 1 (agent paragraph 1)", corrected)
        if (HERE / "results" / "round2").exists():
            report.write(HERE / "results" / "round2", HERE / "results-round2.md", "Phase 5 trial results, round 2 (agent paragraph 2)",
                         "**Stopped at 86 of 288 runs on 2026-10-24, by the maintainer's choice; the [protocol](protocol.md#round-2) "
                         "gives the reason.** " + corrected)
        if (HERE / "results" / "haiku-round3").exists():
            report.write(HERE / "results" / "haiku-round3", HERE / "results-haiku-round3.md",
                         "Phase 5 small-model arm, round 3 (Claude Code on Haiku 5.5, agent paragraph 3, T6 only)",
                         "Three repetitions of T6, the only task that paragraph 3 concerns ([protocol](protocol.md#round-3)).")
        if (HERE / "results" / "haiku").exists():
            report.write(HERE / "results" / "haiku", HERE / "results-haiku.md", "Phase 5 small-model arm (Claude Code on Haiku 5.5, agent paragraph 2)",
                         "Published on its own and never pooled with rounds 1 and 2; the [protocol](protocol.md#small-model-arm) "
                         "describes the arm and its two discarded launches.")
        return 0
    # The judge runs the reference reader with this interpreter; without the reader's
    # dependencies every check would read as UNREADABLE and every run would be misjudged.
    if subprocess.run([sys.executable, str(READER), "--help"], capture_output=True).returncode:
        sys.exit(f"{sys.executable} cannot run {READER}; run the harness with the trial venv's python")
    tasks = load_tasks()["tasks"]
    selected = args.tasks.split(",") if args.tasks else list(tasks)
    plan = [(a, c, f, t, r) for r in range(1, args.reps + 1) for t in selected for f in args.fixtures.split(",")
            for c in args.conditions.split(",") for a in args.agents.split(",")]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(run_one, *cell): cell for cell in plan}
        for future in concurrent.futures.as_completed(futures):
            cell = futures[future]
            try:
                record = future.result()
                print(f"{'PASS' if record['pass'] else 'FAIL'} {record['run']} {record['timing']}", flush=True)
            except Exception as error:  # a harness failure is reported, not hidden
                print(f"ERROR {'.'.join(map(str, cell))}: {type(error).__name__}: {error}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
