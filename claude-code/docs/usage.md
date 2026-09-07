# Using Rightsize Goal

Give the coordinator an objective, observable acceptance conditions, scope, and any real
limits. Open Claude Code in the project you want it to work on and select the coordinator
configuration:

```text
/model opus
/effort medium
```

Other root models work; the skill discloses a mismatch once and continues. A skill's
frontmatter can only override model and effort for a single turn, so this workflow does not
try to set them for you — the session settings above are what actually hold.

## Invoking the skill

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
/goal the CSV export matches the active filters and the export test suite passes
```

The coordinator will offer to set one for you when it can. Three things are worth knowing:

- It is **session-scoped**. It does not schedule work in a future session. For that, look
  at `/loop` or `/schedule`, which are separate features with their own cost behavior.
- It needs a **trusted workspace** and unrestricted hooks.
- `/goal active` shows the current condition and `/goal clear` ends it early. You do not
  need `/goal clear` after a successful run; the hook clears itself.

A session goal and the workflow's own completion gate are different things and are logged
separately. The gate is a deterministic check the coordinator runs; the goal is a host
mechanism that blocks stopping.

## What happens

The coordinator records the objective and acceptance conditions, resolves the role names
available in this session, creates a unique local log and completion gate, then assigns
bounded work to suitable roles. It verifies receipts, records accepted results or rework,
and escalates when justified.

Each worker gets its own subagent transcript, so the accounting helper measures each
assignment directly rather than dividing up a session total. The log under
`.rightsize-goal/<run-id>.md` contains assignments, evidence, current state, and cost notes.
`<run-id>.gate.json` retains the time bounds and the evaluated iteration count. The
coordinator adds the scratch directory to the project's local Git exclusion when applicable.
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
/rightsize-goal:rightsize-goal Resume from .rightsize-goal/<existing-run-id>.md.
Keep the saved objective, bounds, completed iterations, and prior results.
```

Do not initialize a replacement gate just to reset the timer or hide prior failures.
Requested bound changes need to be recorded explicitly and reconciled with the saved state.
The gate helper has no command to edit existing bounds automatically.

## Practical limits

- A skill guides the coordinator; it is not a host-level watchdog. Crashes, usage limits,
  account policy, missing tools, or model instruction failures can interrupt it.
- `/goal` holds a session open but does not schedule future sessions. A scratch log alone
  schedules nothing.
- More agents can increase token consumption. The policy seeks lower total cost including
  rework; it does not establish guaranteed savings, and the Claude price ladder is flat
  enough that one rework cycle can erase a tier's savings. See
  [why these seven roles](roles.md#two-levers-not-one).
- Dollar figures are API-equivalent estimates. A Claude Code subscription is not billed per
  token, so the numbers are a routing comparison basis and not your bill.
- Permissions remain those of the host and your request. A persistent goal does not
  authorize unrelated publishing, messages, purchases, commits, pushes, or destructive
  operations. Workers are additionally denied the ability to spawn agents.
- Research-only tasks may still create this workflow's local logs and usage metadata; they
  do not authorize product-code changes.
