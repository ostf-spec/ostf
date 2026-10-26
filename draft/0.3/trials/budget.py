#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The Phase 5 budget (phase5.md, Budget): the runs counted, and priced from the usage and timing
fields of the Phase 1 run records at the list prices of harness.PRICES.

    python3 budget.py

A Phase 1 Haiku run is priced at the cost Claude Code recorded for it, which applies Haiku 5.5's
prices for prompts above 100,000 tokens request by request; a Codex run at its token counts and
gpt-6-sol's short-context prices, its reasoning tokens counted as output; a judge call at the cost
Claude Code recorded for the Opus judge. A Phase 5 task that Phase 1 did not run is priced as the
Phase 1 task closest to it in work (PROXY), and the rules arm as the none arm, which also reads
REQUIREMENTS.md. The large-model block prices the same token counts at the large models' prices.
"""
import collections
import json
import statistics

import harness

PHASE1 = harness.HERE / "results" / "phase1"
# A Phase 5 task, or a T12 run or a longitudinal change, priced as these Phase 1 tasks.
PROXY = {"T1": ["T1"], "T2": ["T2"], "T3": ["T3"], "T4": ["T4"], "T5": ["T5"], "T6": ["T6"], "T7": ["T7"], "T8": ["T8"],
         "T9": ["T2"], "T10": ["T2"], "T11": ["T4"], "T12": ["T2"], "T13": ["T2", "T6"], "T14": ["T3"], "change": ["T2", "T4", "T5"]}
ARM_PROXY = {"none": "none", "rules": "none", "intent": "intent", "full": "full"}
JUDGE_PROXY = {"T9": ["T2"], "T10": ["T2"], "T11": ["T6"], "T13": ["T6"], "T14": ["T3"], "T8": ["T6"], "change": ["T7"]}
REPS = 3
FIXTURES = ("go-shop", "ts-shop")
AGENTS = {"claude": "claude-haiku-5-5", "codex": "gpt-6-sol"}
LARGE = {"claude": "claude-opus-5-5", "codex": "gpt-6-astra"}


def records():
    return [json.loads(p.read_text()) for p in sorted(PHASE1.glob("c*.*.json")) if p.name.split(".")[0] in ("claude", "codex")]


def priced(record, model=None):
    """A Phase 1 run's cost in USD, at its own model's prices or at another model's."""
    u = record["usage"]
    if record["agent"] == "claude":
        if model is None:
            return u.get("cost") or 0.0
        inp, write, read, out = harness.PRICES[model]
        return (u.get("input_tokens", 0) * inp + u.get("cache_creation_input_tokens", 0) * write + u.get("cache_read_input_tokens", 0) * read
                + u.get("output_tokens", 0) * out) / 1e6
    inp, write, read, out = harness.PRICES[model or "gpt-6-sol"]
    cached = u.get("cached_input_tokens", 0)
    return ((u.get("input_tokens", 0) - cached) * inp + cached * read + u.get("cache_write_input_tokens", 0) * write
            + (u.get("output_tokens", 0) + u.get("reasoning_output_tokens", 0)) * out) / 1e6


def table(rows):
    """Mean cost, seconds and judge cost per (agent, arm, task) of the Phase 1 records."""
    by = collections.defaultdict(list)
    for r in rows:
        by[(r["agent"], r["arm"], r["task"])].append(r)
    return by


def mean(by, agent, arm, tasks, value):
    pool = [value(r) for t in tasks for r in by[(agent, ARM_PROXY[arm], t)]]
    return statistics.mean(pool) if pool else 0.0


def cells(arms=("none", "intent", "rules", "full")):
    """The cells and agent runs of the trial matrix, per agent and repetition count of REPS."""
    main = harness.load_tasks(1)["tasks"]
    out = []
    for arm in arms:
        for task, by_fixture in main.items():
            for fixture in FIXTURES:
                if arm != "full" and by_fixture[fixture]["kind"] == "derived":
                    continue
                runs = len(by_fixture[fixture]["prompts"]) if by_fixture[fixture]["kind"] == "parallel" else 1
                judged = by_fixture[fixture]["kind"] not in ("rename", "parallel")
                out.append((arm, task, fixture, runs, judged))
    return out


def verdicts():
    """The judge's verdicts, the questions it answers, over the matrix, main and held-out tasks."""
    total = 0
    for rep in range(1, REPS + 1):
        tasks = harness.load_tasks(rep)["tasks"]
        for arm, task, fixture, runs, judged in cells():
            if not judged:
                continue
            t = tasks[task][fixture]
            questions = harness.judge_questions(t, fixture, None, None)
            # T2 asks whether the answer names its draft item when one was added, in intent and full.
            total += len(questions) + (1 if t["kind"] == "implement" and arm in harness.RECORD_ARMS else 0)
    return total * len(AGENTS)


def main():
    rows = records()
    by = table(rows)
    history = json.loads((harness.PHASE5 / "longitudinal.json").read_text())["history"]
    changes = sum(len(c) for c in history.values())
    blocks = []
    for agent, model in AGENTS.items():
        usd = seconds = judge = calls = runs = count = 0.0
        for arm, task, fixture, n, judged in cells():
            count += REPS
            runs += REPS * n
            usd += REPS * n * mean(by, agent, arm, PROXY[task], priced)
            seconds += REPS * n * mean(by, agent, arm, PROXY[task], lambda r: r["timing"]["seconds"])
            if judged:
                calls += REPS
                judge += REPS * mean(by, agent, arm, JUDGE_PROXY.get(task, PROXY[task]), lambda r: (r.get("judge") or {}).get("cost") or 0)
        blocks.append({"block": f"Trials, {model}", "cells": int(count), "runs": int(runs), "judgeCalls": int(calls), "agentUsd": usd,
                       "judgeUsd": judge, "hours": seconds / 3600, "optional": False})
    # The longitudinal replay: every change in full and none, the agents alternating, and one judge call per full-arm change.
    usd = seconds = 0.0
    for arm in ("full", "none"):
        for n in range(changes):
            agent = ("claude", "codex")[n % 2]
            usd += mean(by, agent, arm, PROXY["change"], priced)
            seconds += mean(by, agent, arm, PROXY["change"], lambda r: r["timing"]["seconds"])
    judge = changes * statistics.mean(mean(by, a, "full", JUDGE_PROXY["change"], lambda r: (r.get("judge") or {}).get("cost") or 0) for a in AGENTS)
    blocks.append({"block": "Longitudinal replay, both agents alternating", "cells": 4, "runs": 2 * changes, "judgeCalls": changes,
                   "agentUsd": usd, "judgeUsd": judge, "hours": seconds / 3600, "optional": False})
    # The large-model repetition: one repetition of every cell, the same token counts at the large models' prices.
    for agent, model in LARGE.items():
        usd = seconds = judge = calls = runs = count = 0.0
        for arm, task, fixture, n, judged in cells():
            count += 1
            runs += n
            usd += n * mean(by, agent, arm, PROXY[task], lambda r: priced(r, model))
            seconds += n * mean(by, agent, arm, PROXY[task], lambda r: r["timing"]["seconds"])
            if judged:
                calls += 1
                judge += mean(by, agent, arm, JUDGE_PROXY.get(task, PROXY[task]), lambda r: (r.get("judge") or {}).get("cost") or 0)
        blocks.append({"block": f"Optional: one repetition on {model}", "cells": int(count), "runs": int(runs), "judgeCalls": int(calls),
                       "agentUsd": usd, "judgeUsd": judge, "hours": seconds / 3600, "optional": True})
    lines = ["| Block | Cells | Agent runs | Judge calls | Agents, USD | Judge, USD | Total, USD | Agent hours |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for b in blocks:
        lines.append(f"| {b['block']} | {b['cells']} | {b['runs']} | {b['judgeCalls']} | {b['agentUsd']:.2f} | {b['judgeUsd']:.2f} | "
                     f"{b['agentUsd'] + b['judgeUsd']:.2f} | {b['hours']:.1f} |")
    required = [b for b in blocks if not b["optional"]]
    lines.append(f"| Required blocks | {sum(b['cells'] for b in required)} | {sum(b['runs'] for b in required)} | "
                 f"{sum(b['judgeCalls'] for b in required)} | {sum(b['agentUsd'] for b in required):.2f} | {sum(b['judgeUsd'] for b in required):.2f} | "
                 f"{sum(b['agentUsd'] + b['judgeUsd'] for b in required):.2f} | {sum(b['hours'] for b in required):.1f} |")
    print("\n".join(lines))
    print(f"\nVerdicts in the trial matrix: {verdicts()}; one in ten for the human sample: {round(verdicts() / 10)}.")
    phase1 = collections.Counter(r["agent"] for r in rows)
    print(f"Phase 1 records priced: {dict(phase1)}; recorded Haiku cost {sum(priced(r) for r in rows if r['agent'] == 'claude'):.2f} USD, "
          f"Haiku at the short-prompt list price {sum(priced(r, 'claude-haiku-5-5') for r in rows if r['agent'] == 'claude'):.2f} USD, "
          f"Codex at gpt-6-sol list price {sum(priced(r) for r in rows if r['agent'] == 'codex'):.2f} USD, "
          f"judge {sum((r.get('judge') or {}).get('cost') or 0 for r in rows):.2f} USD.")


if __name__ == "__main__":
    main()
