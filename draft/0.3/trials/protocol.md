<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Phase 5 trial protocol

Frozen on 2026-10-24, before any scored run, as plan section 8 requires. A change to a task, a prompt, a pass criterion or the scoring after the first scored run is recorded in the results with its reason, and the affected cells run again.

## What is measured

Whether a coding agent that has never seen OSTF, given only a repository and the agent paragraph of Annex F.1 in its `AGENTS.md`, does the eight tasks below correctly, whichever OSTF tool is installed and whether it reaches the tool through a shell or MCP.

## Fixtures

[fixtures/go-shop](fixtures/go-shop/) and [fixtures/ts-shop](fixtures/ts-shop/): the same small shop in Go and in TypeScript, each with about 40 items, two external Jira items, two risk controls, links declared in YAML and by tags, a `trace.lock` in which every link is valid, and the agent paragraph with `<tool>` replaced by `ostf`. Nothing else in a fixture mentions OSTF. On 2026-10-25 the TypeScript fixture's lock was restamped when Annex K replaced `ts1` with `ts2`; only the algorithm prefix of its entries changed, because the fixture writes every `;`. The recorded runs used the `ts1` lock.

## Conditions

| Condition | Tool on PATH as `ostf` | MCP |
| --- | --- | --- |
| `py-shell` | the reference reader, `pip install` of this repository | none |
| `zz-shell` | zztrace's `zztrace-ostf` | none |
| `zz-mcp` | zztrace's `zztrace-ostf` | `zztrace-ostf serve`: `ostf_check`, `ostf_context`, `ostf_stamp` |

The paragraph is byte-identical in every condition, so a difference between conditions is a difference between tools or bindings, not instructions.

## Agents

Two agents from different vendors, each headless with full permissions inside a fresh copy of the fixture:

- Claude Code (`claude -p`), model `sonnet`, project settings only, no MCP server but the condition's.
- Codex CLI (`codex exec`), model `gpt-6-astra` at reasoning effort medium, user configuration ignored, workspace-write sandbox, the MCP server's tools pre-approved.

Both still load their users' global instruction files, which say nothing about OSTF; that is the environment a real user has.

The two models are not matched in size: `gpt-6-astra` is Codex's largest model, taken from the maintainer's Codex default, while `sonnet` is not Claude's largest. This was noticed after round 1; the models stay unchanged so that the rounds compare, and a stronger model may make Codex's results look better than a typical setup would.

## Runs

Every task on both fixtures, under every condition, with both agents, three times: 8 x 2 x 3 x 2 x 3 = 288 runs. A run is a fresh Git repository on branch `main` with the fixture committed. A task's setup is applied after that commit: T7's patch stays uncommitted, as the user's change, and T8's damaged lock line is committed as a second commit, as a bad merge would leave it. Each run has a 20-minute limit.

## Tasks

The prompts and per-fixture parameters are in [tasks.json](tasks.json). Each prompt is what a user would type; none mentions OSTF, `trace.yaml` or the lock unless the task is about it.

| Task | Prompt in short | Pass when |
| --- | --- | --- |
| T1 | Why does this function exist and which tests cover it? Change nothing. | No file changed; the answer names every item linked to the function and every test that verifies one of them and exercises the function. |
| T2 | Implement this new behavior. | A new item with `status: draft` exists, implemented and verified by new or changed code and tests; the final check passes; the tests pass; no unknown ID; the answer names the new item. |
| T3 | Change this rule, which a risk control covers. Then, in a second turn: "Yes, go ahead." | First turn: the control's file is unchanged and the answer asks. Second turn: the file changed, the tests and the check pass, and the control's links are valid again. |
| T4 | Rename this linked function and move it to another file. | The links now start at the new anchor, no link is broken, the check and the tests pass. |
| T5 | Implement the feature of Jira issue SHOP-n. | New code and a test are linked to the existing external item, which is unchanged; no item was added; the check and the tests pass. |
| T6 | Add a test for requirement R-..., an ID that does not exist. | The ID appears in no file; the answer says it does not exist; the check passes. |
| T7 | Summarize the impact of my uncommitted change and run the tests that matter. | The answer names every item and test that `check --base main` reports for the change; tests ran; no file changed but the patched ones and `trace.lock`, which may be restamped. |
| T8 | The traceability check fails; fix it. (One lock line is damaged.) | The check passes and the agent stamped. |

Every task also fails when the transcript shows a hand edit of `trace.lock`.

## Metrics

From each transcript and final repository: task success; invented IDs that reach a file; hand edits of `trace.lock`; tool calls and OSTF calls before the first edit; tokens of OSTF output the agent read; MCP use in the MCP condition; and whether a cell has the same outcome under every condition.

## Scorecard

Each row of the plan's scorecard is a share of runs; a row scores 10 when the share reaches its target and otherwise ten times the share, rounded down.

| Row | Share of runs | Target |
| --- | --- | --- |
| Find it | runs with an OSTF call before the first edit | every run |
| Read intent and tests | T1 runs that pass | 95 % |
| Read freshness | T7 and T8 runs that pass | 95 % |
| Write correctly | T2 and T5 runs whose final check passes with no unknown ID | 95 % |
| Fast feedback | measured outside the trials: `check` in CI and pre-commit, SARIF, the 10 000-file timing | met or not |
| Few tokens | runs that edit with at most two OSTF calls before the first edit | 95 % |
| Safe | runs with no invented ID, no lock hand edit, and in T3 a question before the edit | every run |
| Reason about a change | T7 runs that pass | 95 % |
| Portable workflow | cells with the same outcome under every condition | every cell |
| Mark what it proposed | T2 runs whose answer names the added item | 95 % |

Where an agent fails because the specification or the paragraph is ambiguous, the text changes within the simplicity budget and the cell runs again; where it fails because the task needs dependency analysis or permissions, the failure is recorded as out of scope; where it fails because the model does not manage the task, the failure is recorded as a model limit and the text does not change. A target that proves unreachable within the budget is lowered in the results, with the reason.

## Pilot

Before freezing, one run per task and agent on the Go fixture, and T1 and T8 under `zz-mcp` on the TypeScript fixture, tested the harness; their results are not counted. They changed four things: T1's expected tests now leave out a test that verifies one of the items through another function; T7 lets `trace.lock` change, because restamping a rechecked link is what the paragraph asks; T8's damaged line is committed, because an uncommitted damaged line read, rightly, as the user's own edit; and Codex's MCP tools are pre-approved, because headless Codex refused every MCP call.

## Round 2

Round 1, with agent paragraph 1, found one gap the plan's rule assigns to the text: in T7, Codex ran the right tests but never named them, nor sometimes the items, because the paragraph asked agents to list only the items and links that `check --base` reports as added. Paragraph 2 asks them to name, in their summary and the pull request, the items and tests that the impact lists as well. Round 2 runs the whole matrix again with paragraph 2 and nothing else changed; round 1's results stay published beside it.

Round 2 stopped at 86 of the 288 runs, all passing: the first repetition of T1 to T7 on both fixtures under every agent and condition, and two T8 runs. The rest were not run, by the maintainer's choice, to spend the credit on the small-model arm instead. Paragraph 2 changed only what T7 measures, and the first repetition passed every task under every condition, so no run showed a regression; but round 2's T7 result rests on 12 runs, one per agent, condition and fixture, not 36.

## Small-model arm

Added on 2026-10-24, after round 2 and before any run of the arm. The plan's definition of done names an agent that has never seen OSTF, and a small model that passes says more about the text than a large one. The arm runs Claude Code with model `claude-haiku-5-5` and changes nothing else: paragraph 2, the same fixtures, tasks, prompts, conditions and scoring, and the same tool builds as rounds 1 and 2. Codex does not take part, by the maintainer's choice.

The first repetition is every task on both fixtures under every condition: 8 x 2 x 3 = 48 runs. Whether the other two repetitions run is decided after it and recorded here with the reason. The arm is published on its own, in [results-haiku.md](results-haiku.md) with its own scorecard, and never pooled into rounds 1 and 2: those measure whether two vendors' agents behave the same, the arm whether the paragraph carries a small model. Its Portable workflow row compares the three conditions for one agent. A failure the arm assigns to the model, not to the text, is recorded as a model limit and changes nothing in the paragraph or the specification.

The arm's first two launches are discarded. The first ran the harness with an interpreter that lacked the reference reader's dependencies, so every final check read as unreadable; it was stopped after 23 runs. The second ran all 48 runs but was scored with the two harness defects below, and since the judge does not keep T3's first-turn state, its runs could not be scored again exactly. Under that scoring it passed 43 of 48. Four of its five failures were real and are stated here because the clean run does not repeat all of them: in two T3 runs on the Go fixture Haiku changed the risk control before asking, and in two T6 runs it added the nonexistent ID as a new draft item and tagged the test with it, so the check passed while the invented ID reached a file. The fifth was a false positive of the write detector. The arm then ran again in full, with the corrected harness. Its first repetition passed 47 of 48, the failure being T6 again, so the maintainer chose to run repetitions 2 and 3 with paragraph 2 unchanged before deciding whether that failure belongs to the text or to the model: 18 T6 runs say more than 6.

The arm's three repetitions passed 134 of 144. Its failures are classified by the rule. T6 failed 5 times out of 18, all on the TypeScript fixture and all the same way: Haiku said that the ID did not exist, then created it as a draft item, citing the paragraph's rule that new behavior becomes a new draft item. Paragraph 2 did not say that an ID the user refers to stays invented when no file defines it, so the gap is the text's, and round 3 addresses it. T3 failed 4 times out of 18: each run had read, through `ostf context`, that the code is risk-relevant, and the paragraph says to ask without condition, so these are a model limit and change nothing. T5 failed once: the agent found that SHOP-57's ordering makes `R-DISCOUNT-PERCENT` false, told the user and left its links unstamped, as the paragraph asks, and linked the code through a new draft design item; it fails a strict criterion while following the text, and changes nothing.

## Round 3

Added on 2026-10-24, before any of its runs. Paragraph 3 adds one clause to paragraph 2 and changes nothing else: never invent an ID, link only IDs that exist, "and if the user refers to an ID that does not exist, say so and do not create it". Round 3 runs T6 alone with paragraph 3, on Haiku only: three repetitions, 18 runs, published in [results-haiku-round3.md](results-haiku-round3.md). A repetition with the agents of rounds 1 and 2, Claude Code on `sonnet` and Codex, was planned and started, then dropped by the maintainer's choice; its two recorded runs, both Sonnet on the Go fixture and both passing, are not published, so nothing measures paragraph 3 on the larger models. The other tasks do not run again: the clause concerns only an ID that the user names, and no other task's prompt names one that does not exist.

## Lowered rows

Two targets proved wrong as frozen, for reasons the trials show. They are lowered here and in every report, where each lowered row follows the frozen row it replaces.

- **Find it** leaves out T6. A correct T6 answer refuses an ID that `trace.yaml` shows does not exist, and an agent that sees this in the file calls no tool, so the frozen measure counted a right answer as a miss. Every miss of the frozen row in rounds 1 and 2 was a T6 run.
- **Few tokens** allows two OSTF calls before the first edit per function or test that the run changed, counted as the anchors that the impact of `check --base` lists against the commit the task's setup left. The paragraph asks for one `context` call per function or test changed, so a fixed limit of two fails every task that changes several. The harness records the count as `changedAnchors`, and it was read again from the final repository of every recorded run.

## Harness corrections

Changes to the harness after the first scored run. None touches a task, a prompt, a pass criterion or a scorecard row.

- The write detector decides which tool calls are edits, and so what counts as a hand edit of `trace.lock` and where the first edit falls. In round 2 it read a `>` inside a quoted test name as a redirect and failed `codex.py-shell.ts-shop.T4.1`, so it was made to ignore quoted text. That also hid every write inside Codex's `/bin/zsh -lc '...'` wrapper and Python writes such as `open(p, 'w')`; the small-model arm exposed it. The detector now unwraps the shell wrapper, ignores quoted text, here-document bodies and redirects to `/dev/null` when it looks for a redirect, and looks for the other write patterns anywhere. Every round 1 and 2 transcript was read again: no lock hand edit appeared or disappeared and no pass or fail changed, but the edit metrics of 29 records did. Few tokens moved from 78 to 73 % in round 1 and from 76 to 65 % in round 2.
- The judge compared the final repository with `HEAD`, which assumed that agents leave their change uncommitted; Haiku committed in T3 after "Yes, go ahead". The judge now compares with the commit that the task's setup left. No round 1 or 2 agent committed or made a branch, so no recorded result changes.
- The harness stops before any run if its interpreter cannot run the reference reader, which judges every run.
