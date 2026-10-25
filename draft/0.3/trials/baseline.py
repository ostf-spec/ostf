#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Write baseline.md, the report of the agent-first plan's Phase 1 (section 6), from what the
Phase 1 tools recorded in results/phase1/, and the sample of verdicts for a person to label.

    python3 baseline.py report
    python3 baseline.py sample
    python3 baseline.py check

`sample` writes results/phase1/human-sample.md: one verdict of the judge model in ten, drawn by a
hash of the run and the question, for the maintainer to label in its last column; `report` reads
the labels back and gives the agreement. `check` fails when baseline.md or baseline-defaults.md
is not what `report` and `defaults.py report` write, so the published wording cannot drift from
its generator.
"""
import collections
import hashlib
import json
import math
import pathlib
import re
import statistics
import sys

import harness

PHASE1 = harness.HERE / "results" / "phase1"
OUT = harness.HERE / "baseline.md"
ARMS = ("none", "intent", "full")
TASKS = {"T1": "Explain a function", "T2": "Implement a requirement", "T3": "Change a risk control", "T4": "Rename and move",
         "T5": "Link to a Jira item", "T6": "Refuse an invented ID", "T7": "Impact of a diff", "T8": "Repair a lock line"}
Z = 1.959964


def wilson(x, n):
    if not n:
        return (float("nan"),) * 2
    p = x / n
    centre = (p + Z * Z / (2 * n)) / (1 + Z * Z / n)
    half = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / (1 + Z * Z / n)
    # At 0 or n the bound is exact, and rounding must not print it as -0 or 101.
    return max(0.0, centre - half), min(1.0, centre + half)


def newcombe(x1, n1, x2, n2):
    """The difference p1 - p2 with Newcombe's hybrid score interval (method 10)."""
    p1, p2 = x1 / n1, x2 / n2
    (l1, u1), (l2, u2) = wilson(x1, n1), wilson(x2, n2)
    d = p1 - p2
    return d, d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)


def pct(x, n, interval=True):
    if not n:
        return "n/a"
    text = f"{x}/{n} ({100 * x / n:.0f} %"
    if interval:
        low, high = wilson(x, n)
        text += f", {100 * low:.0f} to {100 * high:.0f}"
    return text + ")"


def diff(a, b):
    """a and b are (passed, runs); the difference in points with its interval."""
    if not a[1] or not b[1]:
        return "n/a"
    d, low, high = newcombe(a[0], a[1], b[0], b[1])
    return f"{100 * d:+.0f} points ({100 * low:+.0f} to {100 * high:+.0f})"


def load_runs():
    return [json.loads(p.read_text()) for p in sorted(PHASE1.glob("*.json"))
            if re.match(r"(claude|codex)\.", p.name) and not p.name.startswith(("parallel", "fanout"))]


def load(name):
    path = PHASE1 / name
    return json.loads(path.read_text()) if path.exists() else None


def count(rows, test):
    return sum(1 for r in rows if test(r)), len(rows)


# --- the human sample -----------------------------------------------------------------------

def verdicts(runs):
    for r in runs:
        judge = r.get("judge") or {}
        for key, answer in sorted((judge.get("answers") or {}).items()):
            yield r, key, answer


def drawn(runs):
    """One verdict in ten: the tenth of all verdicts with the lowest hash of run and question."""
    every = sorted(verdicts(runs), key=lambda v: hashlib.sha256(f"{v[0]['run']}|{v[1]}".encode()).hexdigest())
    return every[:math.ceil(len(every) / 10)]


def sample(runs):
    rows = drawn(runs)
    lines = ["<!-- SPDX-License-Identifier: CC-BY-4.0 -->", "# Phase 1: verdicts for a person to label", "",
             f"One verdict of the judge model in ten, {len(rows)} of {sum(1 for _ in verdicts(runs))}, drawn by a hash of the run and "
             "the question ([protocol](../../protocol.md#agents-and-judge)). For each, read the question and the answer, and write "
             "`yes` or `no` after **Human:**; `baseline.py report` reads the labels back. Questions about a diff need the run's "
             "diff, which the work directory keeps in `judge.json`.", ""]
    for n, (r, key, answer) in enumerate(rows, 1):
        question = (r["judge"].get("questions") or {}).get(key, key)
        text = r["firstMessage"] if key == "asks" and r.get("firstMessage") else r["finalMessage"]
        lines += [f"## {n}. {r['run']}, `{key}`", "", f"Question: {question}", "", "Answer:", "",
                  "\n".join("> " + line for line in text[:3000].splitlines()), "",
                  f"Judge: {'yes' if answer else 'no'}", "", "**Human:** ", ""]
    (PHASE1 / "human-sample.md").write_text("\n".join(lines))
    print(f"{len(rows)} verdicts written to {PHASE1 / 'human-sample.md'}")


def agreement():
    path = PHASE1 / "human-sample.md"
    if not path.exists():
        return None
    labelled = re.findall(r"^Judge: (yes|no)\n\n\*\*Human:\*\* *(yes|no)\b", path.read_text(), re.M)
    total = len(re.findall(r"^\*\*Human:\*\*", path.read_text(), re.M))
    return sum(1 for judge, human in labelled if judge == human), len(labelled), total


# --- the report ---------------------------------------------------------------------------------

def report(runs):
    by = collections.defaultdict(list)
    for r in runs:
        by[(r["arm"], r["agent"])].append(r)
        by[(r["arm"], "both")].append(r)
    common = [t for t in TASKS if t != "T8"]
    outcome = lambda arm, agent: count([r for r in by[(arm, agent)] if r["task"] in common], lambda r: r["outcome"])
    lines = ["<!-- SPDX-License-Identifier: CC-BY-4.0 -->", "# Phase 1 baseline", "",
             "The baseline of the [agent-first plan](../plan-agent-first.md), section 6: what OSTF 0.3, as published in document "
             "revision 0.13, does for coding agents and for real code before Phase 2 changes anything. Each number below is what a "
             "change in Phases 2 and 3 must beat. The [protocol](protocol.md#agent-first-phase-1-three-arms) froze the trials before "
             "any scored run; generated by `baseline.py report` from [results/phase1/](results/phase1/).", ""]
    models = sorted({f"{r['agent']} {r['model']}" for r in runs})
    lines += [f"{len(runs)} trial runs; agents {', '.join(models)}; judge {harness.JUDGE_MODEL}.", ""]

    # Scorecard.
    full_none = diff(outcome("full", "both"), outcome("none", "both"))
    corroboration = load("corroboration.json")
    recheck = load("recheck.json")
    parallel = {n: load(f"parallel-{n}root.json") for n in (1, 2)}
    replay = load("replay-summary.json")
    tokens = token_rows(runs)
    guarded = guarded_counts(runs)
    rows = [("Corroborated", "80 %", corroborated_text(corroboration)),
            ("Queue precision", "50 %, per reason", precision_text(replay)),
            ("Recheck lag", "95 %", recheck_text(recheck)),
            ("Hand stamps", "0", stamps_text(replay)),
            ("Breadth", "95 %", "Not measured: the threat, control and decision tasks T9 to T11 are written in Phase 5, and 0.3's "
                                "default vocabulary has no threat or control type."),
            ("Parallel", "0", parallel_text(parallel)),
            ("Guarded", "0 each", guarded["text"]),
            ("Tokens", "600", tokens["text"]),
            ("Over baseline", "Positive, with its interval", f"`full` minus `none`, task outcome on T1 to T7, both agents: {full_none}.")]
    lines += ["## Scorecard", "", "| Row | Target | Phase 1 |", "| --- | --- | --- |"]
    lines += [f"| {name} | {target} | {value} |" for name, target, value in rows]

    # Arms.
    lines += ["", "## Arms", "",
              "Task outcome is the part of each task's criteria that is the same in every arm; pass adds what the arm's text asks of "
              "its record. 95 % Wilson intervals in parentheses; differences with Newcombe's interval, which treats runs as independent.",
              "", "| Arm | Agent | Outcome, T1 to T7 | Pass, every task |", "| --- | --- | --- | --- |"]
    for arm in ARMS:
        for agent in ("claude", "codex", "both"):
            rows_ = by[(arm, agent)]
            lines.append(f"| `{arm}` | {agent} | {pct(*outcome(arm, agent))} | {pct(*count(rows_, lambda r: r['pass']))} |")
    lines += ["", "| Difference | claude | codex | both |", "| --- | --- | --- | --- |"]
    for a, b in (("full", "none"), ("intent", "none"), ("full", "intent")):
        lines.append(f"| `{a}` minus `{b}` | " + " | ".join(diff(outcome(a, g), outcome(b, g)) for g in ("claude", "codex", "both")) + " |")
    # The plan's reading of the arms (section 6): intent holds the paragraph's rules that none lacks, so intent
    # minus none is the format with those rules, and the tool's share shows on T7, the impact listing.
    per_task = {arm: {task: count([r for r in by[(arm, "both")] if r["task"] == task], lambda r: r["outcome"]) for task in common}
                for arm in ARMS}
    made = [task for task in common if 2 * (per_task["full"][task][0] - per_task["none"][task][0]) >= per_task["full"][task][1]]
    named = [f"{task} {TASKS[task]}" for task in made]
    t7 = [per_task[arm]["T7"] for arm in ARMS]
    lines += ["", "The agents are the small model of each vendor, so these are small-model results. The difference between `full` and "
              f"`none` is made on {', '.join(named[:-1])} and {named[-1]}, where the two arms differ by half the runs or more "
              "([outcome by task](#outcome-by-task)). `intent` carries the paragraph's rules, which `none` lacks, so `intent` minus "
              "`none` measures the format together with those rules, not the format alone; Phase 5's `rules` arm separates the two. "
              f"The tool's own share shows on T7, the impact listing, where {t7[0][0]}, {t7[1][0]} and {t7[2][0]} of {t7[0][1]} runs "
              "in `none`, `intent` and `full` named what the change touched.", ""]
    lines += ["## Outcome by task", "", "| Task | " + " | ".join(f"`{a}`" for a in ARMS) + " |", "| --- |" + " --- |" * len(ARMS)]
    for task, title in TASKS.items():
        cells = []
        for arm in ARMS:
            rows_ = [r for r in by[(arm, "both")] if r["task"] == task]
            cells.append(pct(*count(rows_, lambda r: r["outcome"]), interval=False) if rows_ else "not run")
        lines.append(f"| {task} {title} | " + " | ".join(cells) + " |")
    lines += ["", "## Failed criteria", "", "| Arm | Task | Criterion | Runs |", "| --- | --- | --- | --- |"]
    failures = collections.Counter((r["arm"], r["task"], k) for r in runs for k, v in r["criteria"].items() if not v)
    lines += [f"| `{a}` | {t} | {k} | {n} |" for (a, t, k), n in sorted(failures.items(), key=lambda kv: (ARMS.index(kv[0][0]), kv[0][1], kv[0][2]))]
    lines += ["", "## Guarded", "", guarded["table"], "", "## Tokens", "", tokens["table"], ""]
    lines += sections(corroboration, recheck, parallel, replay)
    judged = sum(1 for _ in verdicts(runs))
    disagreements = sum(len(r.get("textMatch") or {}) for r in runs)
    agree = agreement()
    agent = load("sample-labels.json")
    if agree and agree[1]:
        sampled = f"The maintainer labelled {agree[1]} of the {agree[2]} sampled verdicts and agreed with the judge on {agree[0]}."
    elif agent:
        same = sum(1 for e in agent["labels"] if e["label"] == ("yes" if e["judge"] else "no"))
        differ = ", ".join(f"`{e['run']}` `{e['key']}`" for e in agent["labels"] if e["label"] != ("yes" if e["judge"] else "no"))
        sampled = (f"At the maintainer's request an agent, not a person, labelled the sample of one verdict in ten: {agent['labeller']}, "
                   f"reading the same material without the judge's verdicts. It agreed with the judge on {pct(same, len(agent['labels']))} "
                   f"of {len(agent['labels'])}" + (f"; it differed on {differ}." if differ else ".") +
                   " A person's labels, which the plan asks for, are still open in [results/phase1/human-sample.md]"
                   "(results/phase1/human-sample.md).")
    else:
        sampled = ("The sample of one verdict in ten is in [results/phase1/human-sample.md](results/phase1/human-sample.md), "
                   "not yet labelled.")
    lines += ["## The judge", "", f"{judged} verdicts of {harness.JUDGE_MODEL}. The text matching of rounds 1 to 3 disagreed with the judge "
              f"on {disagreements} criteria. " + sampled, ""]
    lines += cost_section(runs, parallel, replay)
    changed = sum(1 for r in runs if r.get("corrected") and r["pass"] != corrected_pass(r))
    rejudged = sum(1 for r in runs if "judge" in (r.get("corrected") or {}))
    lines += [f"After the scored runs, {rejudged} T1 and T7 records were judged again and the T5 and lock corrections applied, as the "
              f"[protocol](protocol.md#corrections) records; {changed} records changed from fail to pass or back.", ""]
    return "\n".join(lines)


def cost_section(runs, parallel, replay):
    """What the phase spent, as Claude Code and Codex report it: dollars for Claude, tokens for
    Codex, whose CLI reports no price."""
    claude = sum((r["usage"].get("cost") or 0) for r in runs if r["agent"] == "claude")
    judge = sum(((r.get("judge") or {}).get("cost") or 0) + (((r.get("corrected") or {}).get("judge") or {}).get("cost") or 0) for r in runs)
    tokens = collections.Counter()
    for r in runs:
        if r["agent"] == "codex":
            tokens.update({k: v for k, v in r["usage"].items() if isinstance(v, int)})
    for p in parallel.values():
        for a in (p or {}).get("agents", []):
            if a["agent"] == "claude":
                claude += (a.get("usage") or {}).get("cost") or 0
            else:
                tokens.update({k: v for k, v in (a.get("usage") or {}).items() if isinstance(v, int)})
    backfill = sum(r.get("backfillCost") or 0 for r in (replay or {}).get("repositories", []))
    labels = sum((r.get("labelCost") or {}).get("usd", 0) for r in (replay or {}).get("repositories", []))
    return ["## Cost", "",
            f"As the CLIs report it, in API-equivalent dollars: Claude Code agents in the trials and the parallel fixture {claude:.2f} USD; "
            f"the judge {judge:.2f} USD, re-judging included; backfilling the replay repositories {backfill:.2f} USD; labelling their "
            f"suspect links {labels:.2f} USD. Codex reports tokens, not prices: {tokens['input_tokens']:,} input tokens, of them "
            f"{tokens['cached_input_tokens']:,} cached, and {tokens['output_tokens'] + tokens['reasoning_output_tokens']:,} output and "
            "reasoning tokens. Not counted: the session that ran the phase, the pilot, the first py-repo backfill, which linked "
            "dead code and cost 1.34 USD, and the labelling of the sample of verdicts by Codex.", ""]


def corrected_pass(r):
    """A record's pass before its corrections, from the values each correction kept."""
    criteria = dict(r["criteria"])
    old = r.get("corrected") or {}
    for key in ("itemUnchanged", "namesItems", "namesTests"):
        if key in old:
            criteria[key] = old[key]
    if "lockHandEdits" in old and "noLockHandEdit" in criteria:
        criteria["noLockHandEdit"] = not old["lockHandEdits"]
    return all(criteria.values())


def guarded_counts(runs):
    rows = []
    for arm in ARMS:
        rs = [r for r in runs if r["arm"] == arm]
        invented = sum(1 for r in rs if r["criteria"].get("idNotWritten") is False or r["criteria"].get("noInventedIds") is False)
        hand = sum(1 for r in rs if r["metrics"]["lockHandEdits"])
        unasked = sum(1 for r in rs if r["criteria"].get("askedBeforeEditing") is False)
        rows.append((arm, invented, hand, unasked, len(rs)))
    table = ["| Arm | Runs | Invented ID in a file | Hand edit of trace.lock | T3 changed before asking |", "| --- | --- | --- | --- | --- |"]
    table += [f"| `{a}` | {n} | {i} | {h} | {u} |" for a, i, h, u, n in rows]
    full = rows[2]
    text = (f"`full`: {full[1]} runs wrote an invented ID, {full[2]} edited the lock by hand, {full[3]} T3 runs changed the control "
            f"before asking; instructions in item text were not tested (T13 comes in Phase 5); self-stamps of risk-relevant links are "
            f"under Recheck lag. `none`: {rows[0][1]}, n/a and {rows[0][3]}.")
    return {"text": text, "table": "\n".join(table)}


def token_rows(runs):
    table = ["Tokens of traceability output an agent read: OSTF calls and reads of `trace.yaml`, `trace/`, `trace.lock` or "
             "`REQUIREMENTS.md`, at four characters a token, per function, type or test that the run changed.", "",
             "| Arm | Runs that changed code | Median per changed symbol | Median per run, every run |", "| --- | --- | --- | --- |"]
    medians = {}
    for arm in ARMS:
        rs = [r for r in runs if r["arm"] == arm]
        per = [r["metrics"]["ostfOutputTokens"] / r["changedSymbols"] for r in rs if r.get("changedSymbols")]
        medians[arm] = statistics.median(per) if per else None
        table.append(f"| `{arm}` | {len(per)} | {round(medians[arm]) if per else 'n/a'} | "
                     f"{round(statistics.median([r['metrics']['ostfOutputTokens'] for r in rs])) if rs else 'n/a'} |")
    text = ", ".join(f"`{a}` {round(m)}" for a, m in medians.items() if m is not None) + " per changed symbol (median)."
    return {"text": text, "table": "\n".join(table)}


def corroborated_text(c):
    if not c:
        return "Not yet measured."
    a = c["agentDeclared"]
    return (f"{pct(a['confirmed'], a['onTestedCode'])} of agent-declared `implements` links to tested functions, confirmed by a "
            f"coverage run of a verifying test; 0.3 has no derived record, so nothing in OSTF reports it.")


def recheck_text(r):
    if not r:
        return "Not yet measured."
    t = r["total"]
    return (f"{pct(t['rechecked'], t['touched'])} of the links a `full` trial change touched were rechecked and stamped in the "
            f"same change; {r['runsWithSelfStamp']} runs stamped a risk-relevant link that the same agent had changed.")


def pooled(replay, field):
    totals = collections.defaultdict(lambda: [0, 0])
    for repo in replay["repositories"]:
        for reason, (hit, labelled) in repo[field].items():
            totals[reason][0] += hit
            totals[reason][1] += labelled
    return totals


def precision_text(replay):
    if not replay:
        return "Waiting on the replay."
    real, worth = pooled(replay, "precision"), pooled(replay, "worthALook")
    parts = [f"`{reason}` {pct(*real[reason])}" for reason in sorted(real)]
    per = "; ".join(f"{repo['name']} " + ", ".join(f"{p[0]}/{p[1]}" for _, p in sorted(repo["precision"].items())) for repo in replay["repositories"])
    return (f"Real mismatches among labelled suspect links, three repositories pooled: {', '.join(parts)} ({per}, body then signature). "
            "Counting links whose change touched the stated behavior while it still held: " +
            ", ".join(f"`{reason}` {pct(*worth[reason], interval=False)}" for reason in sorted(worth)) +
            ". `ITEM_CHANGED` cannot occur in a replay whose items do not change.")


def stamps_text(replay):
    if not replay:
        return "Waiting on the replay."
    return ("Stamps per 100 merged changes that the replayed histories would have needed: " +
            "; ".join(f"{r['name']} {r['stampsPer100']:.0f} under `bodyChange: all`, {r['stampsPer100Risk']:.0f} under `risk`"
                      for r in replay["repositories"]) +
            ". Under `risk` only `SIGNATURE_CHANGED` counts here, since no backfilled item controls a risk. 0.3 asks for every one of "
            "them, by whoever rechecks; nothing in it tells a person's stamp from an agent's.")


def turned_red(p):
    """Clean merges after which a root's check failed when it had passed after the merge before:
    a red main stays red, so later merges would otherwise count the same failure again."""
    count, red = 0, False
    for m in p["merges"]:
        if m["conflict"]:
            continue
        now = any(m["checks"].values())
        count += now and not red
        red = now
    return count


def parallel_text(parallel):
    parts = []
    for n, p in parallel.items():
        if p:
            parts.append(f"{n} root{'s' if n > 1 else ''}: {p['lockConflicts']} lock conflict in {len(p['merges'])} merges, "
                         f"{p['lockConflicts'] * 100 // len(p['merges'])} per 100, and {turned_red(p)} merge that turned `check` red")
    return "; ".join(parts) + "; one run of ten branches per layout." if parts else "Not yet measured."


def sections(corroboration, recheck, parallel, replay):
    lines = []
    if corroboration:
        f = corroboration["fixtures"]
        lines += ["## Corroboration", "",
                  "An `implements` link to a function is on tested code when a test verifies the same item, and confirmed when one of "
                  "those tests, run alone with coverage, executes a statement of the function's body. Links to types and constants are "
                  "left out, since coverage cannot confirm them ([corroborate.py](corroborate.py)).", "",
                  "| Links | Links to types or constants | On tested code | Confirmed |", "| --- | --- | --- | --- |"]
        for name, t in (("Go fixture, as published", f["go-shop"]), ("TypeScript fixture, as published", f["ts-shop"]),
                        ("Declared by agents in T2, T4 and T5", corroboration["agentDeclared"])):
            lines.append(f"| {name}: {t['implementsLinks']} | {t['toTypesOrConstants']} | {t['onTestedCode']} | {pct(t['confirmed'], t['onTestedCode'])} |")
        lines.append("")
    if recheck:
        t = recheck["total"]
        lines += ["## Recheck", "", f"In {len(recheck['runs'])} `full` runs of tasks that change code, the change touched {t['touched']} "
                  f"existing links: {t['rechecked']} were stamped again in the same change and {t['leftSuspect']} left suspect. Agents "
                  f"added {t['newLinks']} links and stamped {t['newLinksStamped']}. {t['selfStampsRiskRelevant']} stamps, in "
                  f"{recheck['runsWithSelfStamp']} runs, were of risk-relevant links that the stamping agent had changed itself: every "
                  "one in a T3 run, whose criterion, like the paragraph, has the agent that changed the control stamp it again after the "
                  "user said yes. 0.3 asks for these self-stamps; Phase 3's separation of duties is to remove them.", ""]
    if any(parallel.values()):
        lines += ["## Parallel agents", "", "Ten agents, Claude Code and Codex alternating, each refactoring one linked function on its own "
                  "branch of the Go fixture, merged in sequence ([parallel.py](parallel.py)).", "",
                  "| Roots | Merges | Conflicting | In trace.lock | Clean merges after which `check` failed | Of them, merges that turned it red |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for n, p in parallel.items():
            if p:
                lines.append(f"| {n} | {len(p['merges'])} | {p['conflicts']} | {p['lockConflicts']} | {p['redMerges']} | {turned_red(p)} |")
        lines.append("")
    for name in ("fanout-60.json", "fanout-300.json"):
        f = load(name)
        if not f:
            continue
        s = f["sweep"]
        lines += [f"## Scale: generated tree, {f['items']} items", "",
                  f"{f['links']} links, {f['functions']} linked functions; items link one, ten or a hundred functions, {f['itemsPerFanout']} "
                  f"of each, spread across 40 packages ([generate_fanout.py](../conformance/generate_fanout.py), [fanout.py](fanout.py)). "
                  f"The lock holds {f['lockLines']} lines, {f['lockBytes'] // 1024} KiB. With the reference reader: stamping every link "
                  f"{f['stampAllSeconds']} s, `check` {f['checkSeconds']} s, `check --base` {f['checkBaseSeconds']} s. `context` of an "
                  "item linking one, ten and a hundred functions: " + ", ".join(
                      f"{c['tokens']} tokens in {c['seconds']} s" for k, c in f["context"].items() if k.startswith("item")) +
                  f"; of a function, {f['context']['function']['tokens']} tokens.", "",
                  f"A sweep that edits the body of {s['functionsEdited']} functions, {round(100 * s['share'])} %, makes "
                  f"{s['bodyChangeAll']['suspectLinks']} links suspect on {s['bodyChangeAll']['suspectItems']} items under `bodyChange: all`, "
                  f"of them {s['bodyChangeAll']['itemsByFanout'].get('100', 0)} of the {f['itemsPerFanout']} items that link a hundred "
                  f"functions; under `bodyChange: risk`, {s['bodyChangeRisk']['suspectLinks']} links on {s['bodyChangeRisk']['suspectItems']} items.", ""]
    if replay:
        lines += ["## Replay of real repositories", "",
                  "Three repositories the maintainer controls, which are not public, so only counts appear here ([replay.py](replay.py)). "
                  "Claude Code on claude-haiku-5-5 backfilled one root per module at the start of each window; every change on the "
                  "main branch was then replayed, the links it made suspect recorded and stamped again, and claude-opus-5-5 labelled a "
                  "sample of 100 per repository, stratified by reason, as a real mismatch, relevant but still true, or noise. Two "
                  "windows are shorter than the three months the plan asks: go-repo's history begins 17 days before its end, and "
                  "py-repo's starts where its dead v1 package was deleted, two months before its last change "
                  "([decision record](../decisions.md#agent-first-plan-phase-1-baseline)).", "",
                  replay["text"], "",
                  "| Repository | Root | Items | Links | Lock lines | Anchors per item, median and largest | Whole-file anchors | "
                  "Items wanting a package anchor | `check` | `check --base` |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for repo in replay["repositories"]:
            for root, x in (repo["scale"] or {}).items():
                fan = x["fanOut"]
                lines.append(f"| {repo['name']} | `{root}` | {x['items']} | {x['links']} | {x['lockLines']} | "
                             f"{(statistics.median(fan) if fan else 0):g} and {max(fan) if fan else 0} | {x['wholeFileAnchors']} | "
                             f"{x['wantedPackageAnchor']} | {x['checkSeconds']} s | {x['checkBaseSeconds']} s |")
        lines += ["", "Measured at the end of each window with the reference reader. `check --base` reads the base view from Git, "
                  "against the window's first commit.", ""]
    return lines


def check(runs):
    import defaults
    for path, text in ((OUT, report(runs)), (defaults.OUT, defaults.report())):
        if path.read_text() != text:
            raise SystemExit(f"{path.name} is not what its generator writes; run it again")
    print("baseline reports reproduce")


def main(argv=None):
    command = (argv or sys.argv[1:] or ["report"])[0]
    runs = load_runs()
    if command == "sample":
        sample(runs)
    elif command == "check":
        check(runs)
    else:
        OUT.write_text(report(runs))
        print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
