# Using Rightsize Goal

Give the coordinator an objective, observable acceptance conditions, scope, and
any actual limits. Open Codex in the project you want it to work on. Select
`gpt-5.6-sol` at medium reasoning when available. Other root models are disclosed
as a mismatch; the skill cannot switch the root model for you.

## Examples

Implementation:

```text
/goal Use $rightsize-goal to add CSV export to the existing reports page.
Acceptance: exported rows match the active filters, quoting is correct, and tests pass.
Preserve the current API. Do not publish or deploy.
```

Investigation:

```text
Use $rightsize-goal to investigate intermittent cache invalidation failures.
Acceptance: provide a reproduction, evidence-backed cause, and proposed fix.
Research only; do not change production code.
```

Time-bounded work:

```text
/goal Use $rightsize-goal --maximum-time="3 hours" to improve parser error messages.
Acceptance: invalid input errors identify the field and all parser tests pass.
```

Only add a minimum when you really require it:

```text
/goal Use $rightsize-goal --minimum-time="30 minutes" --maximum-time="3 hours"
to investigate and fix the reported performance regression.
Acceptance: reproduce it, identify the cause, and demonstrate improvement with a benchmark.
```

The duration flags belong to the skill, not Codex's native `/goal` parser. They
accept a nonnegative number with seconds, minutes, hours, or days, including
fractions such as `1.5 hours`. Omitted bounds impose no default duration.

## What happens

The coordinator records the objective and acceptance conditions, inspects any
existing native goal, creates a unique local log and completion gate, then assigns
bounded work to suitable agents. It verifies receipts, records accepted results
or rework, and escalates when justified. The role table is in the [Codex README](../README.md).

The log under `.rightsize-goal/<run-id>.md` contains assignments, evidence, current
state, and cost notes. `<run-id>.gate.json` retains time bounds and evaluated
iteration count. The coordinator adds the scratch directory to the project's
local Git exclusion when applicable. Do not commit logs containing private work.

One substantive iteration includes a hypothesis/improvement, meaningful action,
evaluation, and retained evidence. Tool calls, retries without new information,
and waiting do not count individually. You can request iteration bounds in prose;
the coordinator passes them to the gate helper. Time and iteration minimums must
both be satisfied when both are specified.

## Completion, limits, and stopping

A completion claim requires verified acceptance and every requested minimum.
Time measures elapsed wall-clock time from saved initialization, including pauses;
it is not active work, model compute, or billed time. Minimum time does not justify
sleeping or manufacturing work. If meaningful authorized work cannot continue,
the coordinator reports the unmet requirement and dependency.

Maximums stop new dispatches at checkpoints. In-flight work can overrun; these
are not hard timers or spending caps. If acceptance remains unmet, the result is
incomplete. User stop/cancel instructions take precedence over minimums. Ask the
coordinator to stop and checkpoint; use the host's pause/stop controls when needed
to stop native continuation as well.

For resumption, point to the existing run log:

```text
Resume $rightsize-goal from .rightsize-goal/<existing-run-id>.md.
Keep the saved objective, bounds, completed iterations, and prior results.
```

Do not initialize a replacement gate just to reset the timer or hide prior failures.
Requested bound changes need to be explicitly recorded and reconciled with saved
state. The gate helper has no command to edit existing bounds automatically.

## Practical limits

- A skill guides the coordinator; it is not a host-level watchdog. Crashes, usage
  limits, account policy, missing tools, or model instruction failures can interrupt it.
- Native goal tools are optional for current-session work, but required for native
  automatic continuation. A scratch log alone does not schedule future execution.
- More agents can increase token consumption. The policy seeks lower total cost,
  including rework; it does not establish guaranteed savings.
- Permissions remain those of the host and user request. Persistent goals do not
  authorize unrelated publishing, messages, purchases, or destructive operations.
- Research-only tasks may still create the authorized workflow's local logs and
  usage metadata; they do not authorize product-code changes.
