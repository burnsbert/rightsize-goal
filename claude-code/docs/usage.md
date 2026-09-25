# Using Rightsize Goal

Give the coordinator an objective, observable acceptance conditions, scope, and any real
limits. Open Claude Code in the project you want it to work on and select the coordinator
configuration:

```text
/model opus
/effort medium
```

The coordinator needs enough judgment to route, verify, and decide acceptance — not a specific
model. Opus at `medium` and Sonnet 5 at `high` are both capable choices; Haiku is not suitable
for this role. A skill's frontmatter can only override model and effort for a single turn, so
this workflow does not try to set them for you — the session settings above are what actually
hold.

When invoked for a short self-contained request, the skill handles it in the main
session and skips agents, accounting, and persistent goal setup. A current-time
lookup or trivial localized edit is an example. Explicit `/goal`, time or
iteration bounds, and requests to resume a run use the persistent workflow.

If `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is set, workers run as reusable teammates and the
coordinator can send follow-up assignments to a warm worker. Without it, each dispatch is a
fresh in-process subagent and the coordinator bundles related work more aggressively instead.
Both modes are supported; see [Agent Teams](install.md#agent-teams-recommended).

## Start a substantial goal

Use `/goal` as the entry point and name the skill in the condition:

```text
/goal Use the rightsize-goal skill to add CSV export to the reports page. The export must match the active filters, quoting must be correct, and tests must pass. Preserve the current API; do not publish or deploy.
```

Claude Code starts working toward the condition immediately. If you invoke the
skill directly and it cannot propose a session goal, it gives you a complete
`/goal Use the rightsize-goal skill to ...` prompt to paste with your objective,
acceptance conditions, and constraints.

## Invoking the skill directly

The command name depends on the install method: `/rightsize-goal:rightsize-goal` under a
plugin, `/rightsize-goal` under a manual `install.py` install. The examples below use the
plugin form; the arguments are identical either way. Typing `/rightsize` and letting
autocomplete finish it is the reliable move.

## Examples

Implementation:

```text
/rightsize-goal:rightsize-goal Add CSV export to the existing reports page.
Acceptance: exported rows match the active filters, quoting is correct, and tests pass.
Preserve the current API. Do not publish or deploy.
```

Investigation:

```text
/rightsize-goal:rightsize-goal Investigate intermittent cache invalidation failures.
Acceptance: provide a reproduction, an evidence-backed cause, and a proposed fix.
Research only; do not change production code.
```

Time-bounded work:

```text
/rightsize-goal:rightsize-goal --maximum-time="3 hours" Improve parser error messages.
Acceptance: invalid input errors identify the field and all parser tests pass.
```

Only add a minimum when you really require one:

```text
/rightsize-goal:rightsize-goal --minimum-time="30 minutes" --maximum-time="3 hours"
Investigate and fix the reported performance regression. Acceptance: reproduce it, identify the cause, and
demonstrate improvement with a benchmark.
```

The duration flags belong to the skill. They accept a nonnegative number with seconds,
minutes, hours, or days, including fractions such as `1.5 hours`. Omitted bounds impose no
default duration.

## Holding the session open

Claude Code's `/goal` sets a session-scoped Stop hook: the session keeps working until a
separate evaluator agrees the condition is met, then the goal clears itself. It is the
closest thing to persistence this host offers, and it pairs well with this workflow.

```text
/goal Use the rightsize-goal skill to add CSV export to the reports page. The export must match the active filters and the export test suite must pass.
```

The coordinator offers to set one if you invoke the skill directly and the
goal proposal tool is available. Three things are worth knowing:

- It is **session-scoped**. It does not schedule work in a future session. For that, look
  at `/loop` or `/schedule`, which are separate features with their own cost behavior.
- It needs a **trusted workspace** and unrestricted hooks.
- `/goal active` shows the current condition and `/goal clear` ends it early. You do not
  need `/goal clear` after a successful run; the hook clears itself.

A session goal and the workflow's own completion gate are different things and are logged
separately. The gate is a deterministic check the coordinator runs; the goal is a host
mechanism that blocks stopping.

## What happens

For a persistent run, the coordinator records the objective and acceptance conditions, resolves the role names
available in this session, creates a unique local log and completion gate, then assigns
bounded work to suitable roles. It verifies receipts, records accepted results or rework,
and escalates when justified.
It keeps a short, revisable view of upcoming tasks and adjusts their boundaries
as evidence arrives. A task has a coherent outcome and checkpoint; many simple
repeated steps may share one task, while uncertain implementation and live
evaluation may need separate assignments.

Each worker gets its own subagent transcript, so the accounting helper measures each
assignment directly rather than dividing up a session total. Each `.rightsize-goal/<goal-id>.jsonl` log contains only agent calls and results, including agent identity, measured tokens, estimated cost, and reasons for retries. The matching `.state.json` holds current objective and evidence; `.gate.json` retains the time bounds and evaluated iteration count. The coordinator adds `.rightsize-goal/` to the project's local Git exclusion when applicable.
Do not commit logs containing private work.

One substantive iteration includes a hypothesis or improvement, a meaningful action, an
evaluation, and retained evidence. Tool calls, retries without new information, and waiting
do not count individually. You can request iteration bounds in prose; the coordinator passes
them to the gate helper. Time and iteration minimums must both be satisfied when both are
specified.

## Completion, limits, and stopping

A completion claim requires verified acceptance and every requested minimum. Time measures
elapsed wall-clock time from saved initialization, including pauses; it is not active work,
model compute, or billed time. A minimum does not justify sleeping or manufacturing work. If
meaningful authorized work cannot continue, the coordinator reports the unmet requirement and
the dependency.

Maximums stop new dispatches at checkpoints. In-flight work can overrun; these are not hard
timers or spending caps. If acceptance remains unmet, the result is incomplete. Your stop or
cancel instructions take precedence over any minimum. Ask the coordinator to stop and
checkpoint, and use `/goal clear` if a session goal would otherwise keep it going.

To resume, point at the existing run log:

```text
/rightsize-goal:rightsize-goal Resume from .rightsize-goal/<existing-goal-id>.state.json.
Keep the saved objective, bounds, completed iterations, and prior results.
```

Do not initialize a replacement gate just to reset the timer or hide prior failures.
Requested bound changes need to be recorded explicitly and reconciled with the saved state.
The gate helper has no command to edit existing bounds automatically.

## Practical limits

- A skill guides the coordinator; it is not a host-level watchdog. Crashes, usage limits,
  account policy, missing tools, or model instruction failures can interrupt it.
- `/goal` holds a session open but does not schedule future sessions. A saved goal log alone
  schedules nothing.
- More agents can increase token consumption. The policy seeks lower total cost including
  rework; it does not establish guaranteed savings, and the Claude price ladder is flat
  enough that one rework cycle can erase a tier's savings. See
  [why these four roles](roles.md#two-levers-not-one).
- Dollar figures are API-equivalent estimates. A Claude Code subscription is not billed per
  token, so the numbers are a routing comparison basis and not your bill.
- Permissions remain those of the host and your request. A persistent goal does not
  authorize unrelated publishing, messages, purchases, commits, pushes, or destructive
  operations. Workers are additionally denied the ability to spawn agents.
- Research-only tasks may still create this workflow's local logs and usage metadata; they
  do not authorize product-code changes.
