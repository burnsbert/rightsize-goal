---
name: rightsize-goal
description: Pursue a goal with cost-aware task delegation, using the main session or Haiku/Sonnet agents for routine work, Opus for hard tasks, and Fable only after Opus struggles. Use when the user requests rightsize-goal or this tiered goal workflow.
license: MIT
---

# Rightsize Goal

Run a persistent goal with a small engineering team. Choose the lowest-cost tier likely to do each task well. Delegate hard work before a cheap tier wastes attempts; reserve Fable for evidenced Opus difficulty. This skill explicitly instructs the coordinator to use subagents for suitable bounded assignments.

Discussing, reviewing, or installing this workflow is not itself a request to run a persistent goal. For execution, resolve a working Python 3.11+ interpreter (`python3`, `python`, or `py -3.11`) and use it consistently for the examples below. Resolve the helper scripts relative to this installed skill directory, not the working project.

## Resolve the role names first

The seven roles ship either as a plugin or as user-level agent files, and the two install methods produce different dispatch names:

- Plugin install: `rightsize-goal:rightsize-junior-doer`, and so on for each role.
- Manual install into `~/.claude/agents/`: the bare name, `rightsize-junior-doer`.

Before the first dispatch, read the available-agents list for this session and record which form is present. Use that exact string as `subagent_type`. A bare name fails with "Agent type not found" under a plugin install, and burning a dispatch on the wrong form is a pure waste. Record the resolved prefix once in the scratch header and reuse it.

If none of the seven roles is available, say so plainly and stop rather than substituting a default agent: the roles exist to pin model and effort, and the Agent tool has no dispatch-time effort override.

## Cost and completion

Optimize expected total spend to reach the user's acceptance conditions, including worker effort, context transfer, coordination, verification, and likely rework. Successful goal completion remains the objective. Do not weaken acceptance to save money, and do not buy expensive reassurance when adequate evidence already exists.

Two levers move cost on this host, and they are not equally strong:

- **Model tier.** Haiku, Sonnet, Opus, and Fable are ordered from cheapest to most expensive per token. Use that ordering as your planning prior. The exact published rates are in [references/tariff.json](references/tariff.json); read them there rather than inventing numbers or percentages. The spread from cheapest to most expensive is roughly tenfold, so moving one tier down saves less here than the tier names suggest, and a single rework cycle can erase it.
- **Effort.** Every tier except the Haiku junior pins an effort level, and effort drives how many tokens a model spends at a fixed rate. Claude Code's session default is `xhigh`; six of the seven roles deliberately run at or below it. Choosing `rightsize-lower-senior-doer` over `rightsize-senior-doer` is a real cost decision even though both are Opus.

Do not invent numeric effectiveness ratings, relative-cost percentages, or effort multipliers. Use the accounting helper's measured token usage and versioned tariff calculations to learn actual task cost patterns, with calculated amounts explicitly labeled. Choose by task fit and revise routing from observed acceptance, rework, escalation, and usage.

- Before dispatch, briefly judge the task's uncertainty, consequence of error, and cheapest tier likely to succeed. Record the routing reason in the existing assignment row, not as a separate planning exercise. Do not mechanically send every task through every tier.
- When capability is uncertain and a failed attempt would be cheap and reversible, give the cheaper plausible worker a bounded task with a clear checkpoint. If the task is already hard or likely to stretch that tier, assign Opus directly. A cheap attempt is useful only when it can advance the work or reveal something that changes the next assignment.
- Buy expensive effort for the difficult portion. When practical, let a cheap tier gather precise evidence or execute an understood plan and let Opus resolve the hard question. Use Fable only under the escalation gate below. Avoid splitting so finely that handoffs and repeated context cost more than keeping a coherent assignment together.
- Every dispatch carries a fixed overhead: the worker's system prompt and skill context are billed as cache-write tokens before it reads a single project file. Bundle closely related small work rather than creating one agent per shell command or file edit.
- At meaningful results or checkpoints, reassess fit: continue with a worker making useful progress, move up when evidence shows a capability mismatch, and move down when the remaining work becomes routine. Do not interrupt a productive assignment solely to switch tiers; normally change ownership at a clean handoff. Neither past spending nor an idle expensive agent justifies more expensive work.
- Use observed success, rework, and escalation patterns to tune later assignments in this project. Log concise `routing-adjustment` events when the policy for a task type changes, linked to the supporting task IDs. Preserve the model roster, user constraints, and the Fable gate; do not silently rewrite global roles or claim broad capability conclusions from one result.
- After every completed, failed, cancelled, or interrupted assignment, capture its result and cost evidence before choosing the next worker. Record the exact per-assignment token categories the accounting helper reports. If usage is not attributable to that assignment, record `usage/cost=unavailable`; do not allocate a session aggregate across tasks, infer usage from elapsed time or visible output, or substitute a benchmark average.
- Label the measurement surface. A price calculation from token counts is an `API-equivalent estimate`, not the user's actual Claude bill, and a Claude Code subscription is not billed per token at all. Record the tariff version and the input, cache-read, cache-write, and output categories used in any calculation. Output tokens already include thinking tokens; never add thinking a second time.
- At each checkpoint, compare the measured usage with the result: accepted, rework required, unresolved but informative, or wasted. Adjust later routing only when the evidence is comparable and the change still respects capability and the Fable gate. Never invent a numeric savings claim when attribution is incomplete.

## Start and resume

Read [references/accounting.md](references/accounting.md) at start and at resume. Use its helper for assignment accounting and inspect its global report before the first dispatch. After every terminal assignment, capture usage, judge the result, and read the updated project and global routing summary before choosing the next worker. The ledger is global learning metadata outside project source control; the scratch file remains the human-readable project record.

Follow the lightweight-coordinator boundary below whatever model the main session runs. Running a capable model at the top does not make it the default executor.

- Capture the user's objective, acceptance evidence, constraints, and any explicit budget. Calling this workflow with an objective authorizes creating a session goal; discussing or installing the workflow does not.
- Inspect the current session goal. If a goal is already active and matches this objective, reuse it. Never clear or overwrite an unrelated active goal to make room; if it conflicts, resolve which goal the user intends before continuing.
- Set the session goal for a newly requested objective. Prefer the `ProposeGoal` tool when it is available in this session, which renders a one-keypress approval without blocking your work. Otherwise ask the user to type `/goal <condition>` themselves, and phrase the exact condition for them to paste. Do not claim a goal is set when it is not.
- A Claude Code session goal is a session-scoped Stop hook: it blocks the session from stopping until a separate evaluator confirms the condition, and it clears itself when the condition is met. It is not cross-session scheduling. If the user needs work to resume in a later session, say so and point at the saved gate and scratch file, or at `/loop` and `/schedule` if the user wants to arrange recurrence themselves. Never promise unattended continuation the host does not provide.
- The coordinator needs enough judgment to route, verify, and decide acceptance; it does not need to be a specific model. Opus at `medium` effort is a good default. Sonnet 5 at `high` or above is also a capable coordinator, and either is a reasonable choice. Haiku is not suitable for this role. A skill's frontmatter can only override model and effort for one turn, so this skill does not change them; the user sets them with `/model` and `/effort`. Read the actual coordinator effort from the `CLAUDE_EFFORT` environment variable and the actual coordinator model from the session transcript, and record both, or `unknown`. Note the pairing once in the log and move on; do not repeatedly flag a capable coordinator as a mismatch, and never falsely label the model.
- Keep one scratch file per goal at `.rightsize-goal/<unique-run-id>.md` in the working project, or in the project's configured external scratch location. Use a filename-safe system-local timestamp plus a random suffix for the run ID and never overwrite an existing record. Announce its path. Use the log contract below. For Git projects, add `.rightsize-goal/` to the local Git exclude file if it is not already ignored; do not commit project scratch data. For non-Git projects it remains local scratch.
- On continuation or compaction, read the existing scratch file and the current goal state, reconcile live child agents and outputs, and resume outstanding work without repeating finished assignments. Recover by the recorded path; otherwise match active records by exact objective and resolve ambiguity with the user. A running child remains live; only a runtime-confirmed interrupted or failed child is treated as interrupted. Do not reset failure history or budgets.

## Lightweight coordinator

The top-level session is the manager, not the default lower-senior engineer. Delegate substantive engineering work to the lowest capable doer, including `rightsize-lower-senior-doer` or `rightsize-senior-doer` for hard work. Retain prioritization, assignment, acceptance decisions, escalation, and goal ownership at the top level. Do not routinely combine manager and implementer responsibilities simply because the manager also runs Opus.

- Before routine exploration or implementation, dispatch the bounded outcome to a cheap tier. Do not solve the task yourself first and then ask a cheap worker to transcribe the solution. Read required project and skill instructions yourself; delegate optional code inspection, precise evidence collection, routine plan details, edits, test execution, and log analysis within the cheap tiers' capability.
- Give `rightsize-midlevel-doer` ownership of a coherent basic work package: inspect the relevant code, choose an approach using established patterns, implement, verify, and return a receipt. Supply outcome, boundaries, and acceptance criteria rather than a line-by-line plan. `rightsize-junior-doer` receives explicit smaller tasks with examples. Known hard work still goes directly to Opus; discovery of hard work triggers a handoff rather than repeated retries at a cheap tier.
- Keep coordinator turns focused on dispatch, a decision based on evidence, integration, or goal-state bookkeeping. Do not expand a brief routing decision into a second investigation or re-plan an accepted work package at every checkpoint. Read full worker artifacts or raw logs only when acceptance, risk, inconsistency, or a specific unresolved question warrants it.
- Ask for compact worker receipts: outcome, changed paths, checks and results, unresolved issues, and next useful action. Keep detailed logs in artifacts and pass focused context to workers. Reuse an appropriate worker for related tasks, and bundle related operations instead of creating one child per shell command or file edit.
- Verify proportionately without duplicating the work. The coordinator judges whether the evidence meets acceptance; routine execution of checks can stay with a cheap tier. Use an independent check where warranted by risk, not a paid review ritual for every trivial change. Run the deterministic gate directly; do not ask a model to recalculate time or iteration arithmetic.
- Subagents run in the background and notify you when they finish. If only workers are running and there is no useful coordinator action, wait for that notification. Do not fill the interval with speculative planning, repeated reasoning, or status polling. Never fabricate or predict a pending agent's result.
- Before substantive execution in the main session, record a main-task assignment and why a cheaper worker is unsuitable (hard reasoning, a consequential decision, or a genuinely smaller total cost than another handoff). Tiny checks and bookkeeping may remain local without a separate justification. Main-session implementation and research must be visible in the same cost-routing log as child assignments.
- At a meaningful milestone, inspect whether routine work drifted into the main session and adjust the next assignments. Summaries should distinguish coordinator decisions from main-session execution, and flag duplicated investigations or excessive handoffs. Use actual model and token usage when available; task counts or short visible replies do not prove low reasoning-token spend. Do not enforce a percentage quota that would push genuinely hard work onto a cheap tier.

These instructions reduce avoidable coordinator work but cannot cap the main model's internal reasoning or per-turn charges. Keep model and effort as the user selected them; do not claim the skill can switch them for the session. Evaluate coordinated runs against unassisted runs using observed usage, acceptance, and rework before claiming savings.

## Persistent completion gate

Recognize `--minimum-time="30 minutes"` and `--maximum-time="3 hours"` anywhere in the invocation that reached this skill, whichever command form was used (`/rightsize-goal:rightsize-goal` under a plugin install, `/rightsize-goal` otherwise). These are skill arguments, not `/goal` flags. Forward their values unchanged to the helper's `init` command; do not merely remember them in prose or round them into estimated hours. Supported values are one nonnegative number plus seconds, minutes, hours, or days (also `s`, `m`, `h`, `d` and common abbreviations); fractional values such as `1.5 hours` are accepted. An omitted flag supplies no bound. Reject invalid units, contradictory bounds, or conflicting prose and flag instructions before dispatch. The helper retains legacy `--min-hours` and `--max-hours`, but combining an old and a new flag for the same bound is rejected.

After initialization, read back the persisted `not_before` and `deadline` timestamps, convert them to the computer's local timezone, announce those bounds in readable local date and time with AM/PM, and link the state file. Keep UTC only in machine gate state for reliable arithmetic; do not require the user to convert UTC when reading logs or progress updates. The minimum is a mandatory completion condition and the maximum a mandatory dispatch ceiling at checkpoints. Do not override, shorten, or reset either to declare success. Resume uses those saved bounds; changed flags require explicit user steering and a recorded change, not an unnoticed replacement of the state file.

For every new run, use [scripts/goal_gate.py](scripts/goal_gate.py) to create `<run-id>.gate.json` beside the scratch log. Python 3.11+ is supported. Resolve the script relative to this installed skill. The coordinator alone writes this state through the helper. On resume use the existing file; never initialize a new clock or zero the iteration count to recover. If a pre-existing run has no gate, recover the start and completed work from trustworthy evidence before adding bounds; do not invent historical credit or silently apply new defaults.

Capture user-specified minimum and maximum time and iterations separately. Do not invent mandatory minimums or a maximum budget when none was requested. For "at least six hours or twenty iterations, whichever is longer," require BOTH six elapsed hours AND twenty completed iterations. A maximum on either dimension is a ceiling, not success. Reject same-dimension maximums below minimums; explain that a maximum can end the run incomplete before other minimums are met.

The helper measures elapsed wall-clock hours from its saved UTC start, NOT active labor, model compute, or billed time. If the user specifically requires active working hours excluding pauses, explain that this helper cannot verify those and resolve that measurement requirement rather than relabeling elapsed hours as work. Never sleep, busy-poll, repeat unchanged checks, or manufacture tasks just to meet a minimum. Continue meaningful authorized experiments, improvements, or verification; if none are possible, preserve the unmet requirements and report the concrete dependency.

Example commands (bounds are illustrative, never defaults):

```text
python3 <skill-dir>/scripts/goal_gate.py init --state <run-id>.gate.json --objective "<objective>" --minimum-time="30 minutes" --maximum-time="3 hours" --min-iterations 20 --max-iterations 30
python3 <skill-dir>/scripts/goal_gate.py iteration --state <run-id>.gate.json --id I001 --hypothesis "<testable idea>" --action "<meaningful action>" --result "<evaluated result>" --evidence <existing-evidence-path>
python3 <skill-dir>/scripts/goal_gate.py check --state <run-id>.gate.json
```

Define a substantive iteration for the task before starting: one hypothesis or improvement, a meaningful action or experiment, an evaluation, and retained evidence. Count it only after evaluation; a failure can count when it adds evidence. Child messages, individual tool calls, cosmetic variations, waiting, and unchanged retries are not separate iterations. Multiple workers contributing to one experiment count as one iteration. The helper validates IDs and the existence of evidence paths; the coordinator must judge substance and evidence quality.

Run `check` on resume, after each completed iteration, before dispatching another work batch, and immediately before a completion claim. Pass `--acceptance-met` ONLY after independently verifying the user's outcome criteria and recording their evidence in the scratch log. Until that flag is justified, the helper must not report completion eligibility. Record the latest decision, elapsed hours, completed iterations, unmet conditions, and next action in current state.

- `completion_eligible` (exit 0): acceptance and every minimum are met. Reconcile all live children and required deliverables, then record and report verified completion from the gate and scratch evidence. A worker finishing its bounded assignment never completes the parent goal by itself. An active session goal clears itself once its evaluator agrees; do not tell the user to run `/goal clear` after success.
- `continue` (exit 2): do not claim completion or conclude with a discretionary handoff while useful authorized work remains. Dispatch the next useful assignment or inspect a running one. When a route stalls, use the evidence-based Opus and Fable escalation process instead of treating exhausted ideas as task success.
- `limit_reached` (exit 3): stop dispatching new work, arrange safe checkpoints for running workers, preserve results, and report `incomplete: limit reached` with unmet criteria. Tell the user they can end an active session goal early with `/goal clear`; do not attempt to satisfy the goal condition by asserting it is met. Bounds are checked at checkpoints, so an in-flight operation may overrun; give workers remaining budget and a practical stop condition before dispatch.
- Invalid, missing, or corrupt gate state is a verification problem, never permission to complete. Recover from evidence or report the dependency.

An explicit user stop or cancel overrides `continue`: stop new dispatches, safely checkpoint or interrupt workers, persist state, and report stopped and incomplete. A gate does not override user steering.

This is a deterministic completion check invoked by the workflow, not a tool interceptor or an external watchdog. A model can still fail to call it, and usage limits, crashes, or interruptions can end execution. Never promise uninterrupted wall time. Keep session-goal status and gate status distinct in the log.

## Assignment routing

| Tier | Model / effort | Assign when |
| --- | --- | --- |
| Main session (manager) | A capable model; Opus / medium or Sonnet 5 / high are both good choices | Own priorities, goal state, routing, acceptance decisions, and escalation. Delegate engineering execution to the cheapest capable doer; keep tiny coordination and checks local when dispatch costs more. |
| `rightsize-junior-doer` (entry-level to junior engineer) | Haiku 4.5 (no effort control) | Very basic, explicit tasks with an existing example or prescribed approach: straightforward localized edits, precise lookups, known-pattern updates, and routine checks with clear acceptance criteria. Its context window is smaller than the other tiers, so keep the working set small. |
| `rightsize-midlevel-doer` (lower-midlevel engineer) | Sonnet 5 / medium | Independently execute bounded work using established patterns: small features or fixes, several related edits, straightforward code tracing, and routine implementation choices without step-by-step instructions. |
| `rightsize-upper-midlevel-doer` (upper-midlevel engineer) | Sonnet 5 / xhigh | Moderately complex bounded work needing more judgment: multi-file changes in established architecture, localized debugging across known components, focused research synthesis, and practical design options within existing constraints. |
| `rightsize-lower-senior-doer` (lower-senior engineer) | Opus 5 / medium | Hard work beyond bounded midlevel scope: deeply ambiguous debugging, unfamiliar complex integrations, substantive research, consequential design tradeoffs, or difficult new hypotheses. No cheaper failure is required first. |
| `rightsize-senior-doer` (senior engineer) | Opus 5 / xhigh | Deep interacting constraints or difficult reasoning where more effort on the same model is likely to pay off; may receive such tasks directly or after Opus/medium stalls. |
| `rightsize-staff-doer` (staff engineer) | Fable 5.1 / low | Bounded expert implementation, reframing, architecture review, research synthesis, or a discriminating next step after documented Opus struggle. Complexity, prestige, or wanting extra reassurance alone does not qualify. |
| `rightsize-principal-doer` (principal engineer / lead architect) | Fable 5.1 / medium | The hardest bounded unresolved implementation, reasoning, or fresh-direction consultation after documented Opus struggle, when staff-level low effort is unlikely to be sufficient. |

These experience levels are task-assignment analogies, not claims about model credentials. Keep tiny tasks in the main session when dispatch would add more overhead than value. For useful basic delegation, give `rightsize-junior-doer` explicit guidance and examples; use `rightsize-midlevel-doer` when a developer can independently choose routine details within established patterns. Neither is the route for hard tasks. If the junior tier exposes only modest additional complexity, the lower-midlevel tier may help; if either discovers hard or ambiguous work, route the evidence directly to Opus without requiring another cheap attempt. A Haiku or Sonnet failure alone never qualifies for Fable.

Use `rightsize-upper-midlevel-doer` directly for moderate work between lower-midlevel and lower-senior scope, or when a cheaper tier reveals that level of complexity. It is optional, not a compulsory escalation step: known hard, deeply ambiguous, or consequential architectural work still goes directly to lower-senior or senior.

Use `implement`, `research`, or `brainstorm` as the assignment mode for any tier, within that tier's complexity boundary. Separate mode instructions preserve research-only boundaries without duplicating the model roster. Research returns cited evidence and uncertainty. Brainstorming returns a few materially different, grounded hypotheses with a cheap discriminating next step; novelty must advance the objective, not merely sound exciting.

Treat struggle as evidence: a substantive approach failed its acceptance check and Opus can explain why the next step is unresolved, or Opus examined the relevant evidence but can produce only already-tried or unsupported directions. A typo, a transient tool failure, a waiting job, an absent credential, or a missing user decision is not a reasoning failure. Restored access is new evidence that can justify retrying the same technical approach.

When the main session is Opus, a logged substantive investigation or brainstorming attempt by that coordinator can supply the required Opus evidence. Merely reading a failed cheap-tier receipt does not. Use a lower-senior or senior child for a bounded independent hard task when useful, not as an obligatory extra consultation on every coordinator decision.

After lower-senior Opus/medium struggles, prefer senior Opus/xhigh when deeper analysis of the same evidence is promising. Senior is optional, not a compulsory toll before Fable. Use staff Fable/low when a bounded expert perspective, architecture decision, implementation, or discriminating hypothesis is plausibly enough. Use principal Fable/medium directly when the unresolved core needs sustained principal-level implementation or deeper reasoning, or after staff returns a precise need for principal involvement. Staff is not a compulsory toll, and its failure is not permission for an open-ended principal run. Log why the selected role and effort are the smallest sufficient purchase. After two substantive failed approaches without new evidence, stop repeating that route and change tier or hypothesis.

Before each Fable assignment, log the linked Opus assignments, attempts and results, the remaining question, why Fable is justified, why staff or principal is the right role, and a bounded deliverable and stop condition. Default to one Fable assignment at a time and one consultation per unresolved question; another needs new evidence and a recorded reason. Fable may implement when that bounded implementation itself is the unresolved hard core after Opus struggle. Never use Fable for routine review, polling, clerical edits, or automatic final signoff. After the hard uncertainty is resolved, return implementation and verification to the lowest capable tier. Worker agents cannot spawn agents and must not escalate themselves; the main coordinator dispatches according to this workflow.

If the account cannot use one of these models, the affected roles will fail at dispatch. Disclose the limitation, treat the highest available tier as the top of the ladder, and say in the final report that escalation was capped. Never silently substitute a different model into a role name, because the ledger and the tariff both key on the model actually served.

## Execute and verify

- Break the next useful work into bounded tasks, not a speculative full-project backlog. Bundle closely related small work to avoid dispatch overhead. Log meaningful main-session tasks too, but not every tool call.
- For every child assignment, send: task ID, mode, desired outcome and acceptance checks, relevant paths and evidence, owned files or read-only scope, forbidden changes, prior attempts, stop condition, and expected concise result. State that others share the codebase and that their edits must be preserved.
- Spawn the named role with the Agent tool, using the resolved `subagent_type` string. The role definition pins model and effort. The Agent tool's `model` parameter cannot set effort, so overriding the model on a generic agent does not reproduce a role; if a role is unavailable, report that limitation rather than silently substituting a different model or effort.
- Two dispatch modes exist and both are supported. Detect which one is live from what the Agent tool returns, and record it once in the scratch header.
  - **Agent Teams enabled** (recommended). Passing `name` makes the worker a teammate: it runs as its own addressable session, `ListAgents` lists it, and `SendMessage` sends it follow-up assignments with its context intact. The tool returns `<agentName>@<teamName>`; record that string verbatim as the agent ID. Prefer this mode, because reuse avoids paying to rebuild a worker's context for every related task.
  - **Agent Teams unavailable.** Omit `name` and dispatch a plain in-process subagent. The tool returns a bare agent id. This mode works fully, with one consequence: there is no `SendMessage` reuse, so a follow-up means a fresh worker that must be given its context again. Bundle related work into a single assignment more aggressively here, and say in the final report that reuse was unavailable.
- A teammate is a whole session, not a lightweight helper: it loads its own project instructions and does its own orientation before it reads a single file you named. Its floor cost per dispatch is therefore several times a plain subagent's. Bundle accordingly, and do not spawn a teammate for work that is smaller than its own startup cost.
- Give each spawned agent a new task ID per assignment and record the returned agent ID against it. Reuse an existing suitable agent for related follow-ups where the mode allows it. Do not send cheaper work to an existing expensive agent just because it is idle. Parallelize only independent assignments with distinct ownership and useful coordinator work; send parallel dispatches in a single message.
- A worker does not inherit your working directory. State the absolute working directory in the assignment whenever it differs from the session's, and have the worker confirm the paths it actually touched in its receipt.
- Check that the acceptance command actually exercises the work before trusting its result. A runner that collects nothing still exits successfully: `unittest discover` reports `NO TESTS RAN` for pytest-style bare functions, a filtered run can match zero cases, and a missing runner can send a worker to an improvised substitute. Confirm the check ran the expected number of cases, and treat a zero-case pass as a failed verification, not a pass. Where a named runner may be absent, say which fallback is acceptable and require the worker to report the command and its case count verbatim.
- The main session alone owns the goal, the scratch log, and the gate state. Integrate completed results, verify appropriate acceptance evidence, and record accepted, rework, unresolved, or cancelled outcomes. An agent saying "done" is not completion evidence, and neither is a receipt that formats its own prose to look like runner output; require the literal command and its real output. Verification that itself stretches a cheap tier goes to Opus; avoid duplicating an entire investigation without cause.
- Preserve the user's authorization boundaries throughout persistence. A goal is not permission for unrelated external writes, messages, publishing, purchases, commits, pushes, or destructive operations.
- Keep advancing while useful authorized work remains and no explicit ceiling or user stop has been reached. Record a necessary user or external dependency and work on independent tasks meanwhile; if none remain, report the concrete dependency. Honor user stop and cancel steering.

## Compact scratch contract

Create the following header, a short current-state section, and an append-only event table. Only update current state; preserve historical rows. Use the computer's system-local date and time, formatted for direct human reading, for example `Sep 6, 2026, 6:15:30 PM`. Record the OS timezone name and current UTC offset once in the header; show a timezone abbreviation or offset on entries if the timezone changes or a daylight-saving transition would make the time ambiguous. Obtain time from the system clock (`python3 -c "from datetime import datetime; print(datetime.now().astimezone().strftime('%b %d, %Y, %I:%M:%S %p %Z (UTC%z)'))"`, or PowerShell `Get-Date -Format 'MMM d, yyyy, h:mm:ss tt'`), not by guessing from UTC. Stable IDs (`T001`, `T002`) connect assignments and outcomes. Escape table pipes and keep each event to one concise line. Use Edit or MultiEdit when updating the scratch file. Preserve historical timestamps; do not relabel old rows.

```markdown
# Rightsize goal: <run-id>
Objective: <user objective>
Acceptance: <observable completion evidence>
Session goal: <condition set via /goal or ProposeGoal, or unavailable>
Coordinator: <actual model / effort or unknown>
Role prefix: <"rightsize-goal:" for a plugin install, or none>
Log timezone: <OS local timezone name and current offset>
Budget: <explicit user budget or unspecified>
Gate: <run-id>.gate.json
Usage ledger: <global usage.sqlite3 path>; run <run-id>; tariff <version>

## Current state
Status: active
Next: <next task or dependency>
Live assignments: <task IDs and agent IDs>
Evidence: <artifact paths>
Gate decision: <decision, elapsed hours, iteration count, unmet criteria>
Cost checkpoint: <known attributable API-equivalent subtotal; measured/unknown tasks; routing implication>

## Events
| Local time | Task | Event | Role / model / effort | Mode | Assignment or result | Routing reason / prior task | Agent / evidence | Usage / cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
```

Record `assign` before dispatch, then `started` with the returned agent ID (or `dispatch-failed`); record `result` and the coordinator's `accept`, `rework`, or `unresolved` decision with artifact and check references. Fill `Usage / cost` on the terminal row using the measurement contract above, including `unavailable` when necessary. Record escalations as a new assignment linked to the prior ID and its failure evidence. Capture main-session assignments with agent `main` and close each meaningful main-session task with its attributable usage when exposed. Mark interrupted assignments unresolved on recovery unless their artifacts prove completion. Do not log secrets, full transcripts, estimates presented as bills, or invented token or cost numbers.

At completion or a necessary handoff, add a brief tally by tier and mode: assignments, accepted results, rework, escalation reasons, and attributable measured usage grouped by measurement surface. Keep unavailable items explicit and do not total incompatible units. Note evidence of over- or under-assignment and any adjustments worth trying next time; distinguish observations from hypotheses. Link the scratch file in the final response; report verified completion and any material limits. Assignment counts are tuning data, not a measurement of monetary savings.
