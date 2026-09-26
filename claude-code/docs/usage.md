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
lookup or trivial localized edit is an example. A substantial objective, explicit `/goal`,
time or iteration bounds, and requests to resume a run use the persistent workflow.

If `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is set, workers run as reusable teammates and the
coordinator can send follow-up assignments to a warm worker. Without it, each dispatch is a
fresh in-process subagent and the coordinator bundles related work more aggressively instead.
Both modes are supported; see [Agent Teams](install.md#agent-teams-recommended).

## Start a substantial goal

Invoke the skill with the objective and how you will know it is done:

```text
/rightsize-goal:rightsize-goal Add CSV export to the reports page. The export must match the active filters, quoting must be correct, and tests must pass. Preserve the current API; do not publish or deploy.
```

Under a plugin install the run is self-driving: it keeps working until the validator
confirms the goal, you pause it, or a limit is reached. See
[holding the session open](#holding-the-session-open). Under a manual install, the skill
offers a `/goal` or gives you a complete `/goal Use the rightsize-goal skill to ...` prompt
to paste.

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

## How a run is planned

Before planning anything, the coordinator restates your goal as a short acceptance checklist and
asks about any clause that could reasonably be read two ways, so the work and the final validation
both follow the meaning you intend. It then plans along the work's natural seams: independent
pieces run in parallel, dependent chains become task families that one worker carries through in
order, and milestones mark points where part of the goal should work end to end. After each
milestone a light QA task runs the automated tests and checks that milestone against the goal, so
problems surface while they are cheap to fix rather than at the final validation.

## Holding the session open

A skill cannot start `/goal` itself, so the plugin ships its own Stop hook. Each time Claude
is about to stop, the hook checks whether this session owns an active Rightsize Goal in the
current directory. If it does not, the hook does nothing. If it does, the session keeps
going until one of these is true:

- `rightsize-validator` has returned **DONE** for the current wording of the goal, and no
  work has been recorded since;
- you **paused** the goal, or the coordinator is **waiting on your input**;
- **workers are still running**, so the coordinator can wait for their results;
- a requested **time or iteration limit** was reached, after the coordinator gives an
  incomplete handoff;
- the run made **no recorded progress** across several continuations, in which case it
  stops and tells you.

Each time the hook keeps the session going, it tells the coordinator what is still unmet, which
tasks are in progress, which are ready to start, and which are waiting on other tasks, so the next
step starts from the plan rather than from scratch. The hook
makes no model call, so it costs nothing in a session without an active goal.

**Validation.** When the coordinator believes the goal is met, it sends `rightsize-validator`
(Opus 5.5, read-only) the goal text and where to look, but not its own argument that the work
is done. The validator runs the checks itself and reads the goal the way a QA engineer or
product owner would. Done is not the same as perfect: a real defect or a clause the work plainly
fails makes it NOT DONE, while polish and minor inaccuracies go in non-blocking notes. It rates
every issue from 1 to 10 and returns DONE or NOT DONE, with a reason for each unmet part of the
goal. Each reason becomes a new task. A follow-up round checks those fixes and their effects rather
than starting a fresh review; only a new regression that is more than a nitpick, or an issue that
is not a regression but is rated 7 or higher, can newly fail the goal there. After
a DONE, the coordinator may bundle worthwhile notes into one final polish round, the way a team
clears small issues before a release, followed by a narrow check that the polish caused no
regression. If the
same reason comes back twice, the coordinator changes approach or routes that task to a stronger
tier.

**Steering.** Talk to it. Changing scope or requirements amends the goal: the coordinator
records your words alongside the original goal and re-plans, and an earlier DONE no longer
counts. "Stop" or "pause" pauses the goal; "resume" continues it, in this session or a later
one. If an instruction is ambiguous, the coordinator asks. Esc always interrupts, because
Stop hooks do not run on user interrupts.

**Using `/goal` instead.** Starting with `/goal Use the rightsize-goal skill to ...` still
works, and it is how a manual install persists. The skill then lets `/goal` drive, and the
plugin hook stands down. `/goal` is session-scoped, needs a trusted workspace and unrestricted
hooks, and `/goal clear` ends it early.

The hook and `/goal` both keep a session open; neither schedules work in a future session.
For recurring work, see `/loop` or `/schedule`, which have their own cost behavior.

## What happens

For a persistent run, the coordinator records the objective and acceptance conditions, resolves the role names
available in this session, creates a unique local log and completion gate, then assigns
bounded work to suitable roles. It verifies receipts, records accepted results or rework,
and escalates when justified. When it believes the goal is met, the validator decides.
It keeps a short, revisable task list and adjusts task boundaries as evidence arrives. A task has a coherent outcome and checkpoint; many simple
repeated steps may share one task, while uncertain implementation and live
evaluation may need separate assignments.

Each worker gets its own subagent transcript, so the accounting helper measures each
assignment directly rather than dividing up a session total. Each `.rightsize-goal/<goal-id>.jsonl` log contains only agent calls and results, including agent identity, measured tokens, estimated cost, and reasons for retries. The matching `.state.json` holds current evidence and routing notes; `.drive.json` holds the goal text and your amendments, the task list, validation verdicts, and pause status; `.gate.json` retains the time bounds and evaluated iteration count. The coordinator adds `.rightsize-goal/` to the project's local Git exclusion when applicable.
Do not commit logs containing private work.

One substantive iteration includes a hypothesis or improvement, a meaningful action, an
evaluation, and retained evidence. Tool calls, retries without new information, and waiting
do not count individually. You can request iteration bounds in prose; the coordinator passes
them to the gate helper. Time and iteration minimums must both be satisfied when both are
specified.

## Completion, limits, and stopping

A completion claim requires a fresh DONE from the validator and every requested minimum. Time measures
elapsed wall-clock time from saved initialization, including pauses; it is not active work,
model compute, or billed time. A minimum does not justify sleeping or manufacturing work. If
meaningful authorized work cannot continue, the coordinator reports the unmet requirement and
the dependency.

Maximums stop new dispatches at checkpoints. In-flight work can overrun; these are not hard
timers or spending caps. If acceptance remains unmet, the result is incomplete. Your stop or
pause instructions take precedence over any minimum: the coordinator checkpoints running
workers and pauses the goal. Under `/goal`, use `/goal clear` if the session goal would
otherwise keep it going.

To resume in the same session, say "resume". In a new session, point at the saved goal:

```text
/rightsize-goal:rightsize-goal Resume goal <existing-goal-id>.
```

Resuming binds the goal to the new session and continues from the saved goal text,
amendments, task list, verdicts, bounds, and completed iterations.

Do not initialize a replacement gate just to reset the timer or hide prior failures.
Requested bound changes need to be recorded explicitly and reconciled with the saved state.
The gate helper has no command to edit existing bounds automatically.

## Practical limits

- A skill guides the coordinator; it is not a host-level watchdog. Crashes, usage limits,
  account policy, missing tools, or model instruction failures can interrupt it.
- The plugin hook and `/goal` hold a session open but do not schedule future sessions. A
  saved goal alone schedules nothing. A manual install has no hook, and hooks do not run at
  all when `disableAllHooks` is set.
- More agents can increase token consumption. The policy seeks lower total cost including
  rework; it does not establish guaranteed savings, and the Claude price ladder is flat
  enough that one rework cycle can erase a tier's savings. See
  [why these roles](roles.md#two-levers-not-one).
- Dollar figures are API-equivalent estimates. A Claude Code subscription is not billed per
  token, so the numbers are a routing comparison basis and not your bill.
- Permissions remain those of the host and your request. A persistent goal does not
  authorize unrelated publishing, messages, purchases, commits, pushes, or destructive
  operations. Workers are additionally denied the ability to spawn agents.
- Research-only tasks may still create this workflow's local logs and usage metadata; they
  do not authorize product-code changes.
