# Changelog

## 1.1.2 — 2026-09-26

### Claude Code

- Teammates can now accept a shutdown request: every role has `SendMessage` and is told to
  approve a shutdown when idle. Before this, a shutdown request could not be accepted, so
  teammates accumulated.
- A happier medium on reuse: reuse a teammate when its context has room and the next task is a
  natural follow-on. `finish` advice now has three bands: room below 120,000 tokens, only small
  dependent follow-ons up to 200,000, and retire after that.
- `finish` reports `assignment_growth_tokens` and flags an assignment that alone grew past
  200,000 tokens as work to split next time; the skill keeps single assignments well within that.
- Every role, including the junior and the validator, can research online with `WebFetch` and
  `WebSearch`.

### Codex

- The same reuse bands and oversized-assignment flag, measured against 128,000 tokens or half
  the context window, whichever is lower.
- Every role sets `sandbox_mode = "danger-full-access"`, `approval_policy = "never"`,
  and `web_search = "live"` for full filesystem and command network access plus live
  web research. The repository's Codex config registers the five packaged roles and
  applies the same coordinator defaults. Active parent permission overrides still apply.
- Worker cleanup checks runtime capabilities before closing agents. When closure is
  unavailable, finished workers are retired from future assignments while their actual
  runtime status is retained. Interrupting or retiring a worker is not treated as
  confirmation that a concurrency slot was released.

## 1.1.1 — 2026-09-25

### Claude Code

- Reuse a teammate only for a direct follow-up on its own recent work; give work in a
  different area to a fresh teammate with a short handoff. `task_usage.py finish` now reports
  the worker's context size and advises retiring it past 200,000 tokens, since every request
  re-reads everything the worker has seen.
- Shut down teammates that are unlikely to get another assignment with a `SendMessage`
  shutdown request, and keep live teammates few, typically three to five.

### Codex

- Reuse an agent only for a direct follow-up on its own recent work. `task_usage.py finish`
  now reports the worker's context size and window, and advises retiring it past 128,000
  tokens or half its context window, whichever is lower.
- Close agents that are unlikely to get another assignment with `close_agent`.

## 1.1.0 — 2026-09-25

### Claude Code

- Self-driving persistence under a plugin install: `/rightsize-goal:rightsize-goal <goal>`
  keeps working like `/goal` would, without typing `/goal`. A plugin Stop hook, with no model
  call, holds the session open while it owns an active goal, and feeds back what is unmet and
  which tasks are open. It releases on a fresh DONE verdict, a pause, waiting on the user, a
  reached limit, or several continuations without recorded progress, and lets the coordinator
  wait quietly while workers are running. Its message includes the exact `drive.py` commands.
  It stays silent in every other session and stands down when `/goal` drives.
- New read-only `rightsize-validator` role (Opus 5.5, high). The coordinator decides when it
  believes the goal is done; the validator checks the current goal from its own evidence and
  returns DONE or NOT DONE. Each NOT DONE reason becomes a task, and a repeated reason forces
  a change of approach or tier.
- New `drive.py` helper for the goal text and the user's amendments, the living task list,
  validation verdicts, and pause, resume, and waiting status. An amendment or later work makes
  an earlier DONE stale. "Stop" or "pause" pauses, and "resume" continues in the same or a
  later session.
- Manual installs have no hook and keep using `/goal` for persistence.
- Task a goal out the way a capable development team would, using how a tech lead would
  ticket it for real engineers to choose task boundaries and owners.

### Codex

- Task a goal out the way a capable development team would, using how a tech lead would
  ticket it for real engineers to choose task boundaries and owners. Bump the Codex plugin to
  1.1.0 so installed copies receive it.

## 1.0.2 — 2026-09-24

### Claude Code

- Keep a revisable view of pending tasks, split work at consequential checkpoints, and keep simple repetitive operations together without making assignments unmanageably broad.

### Codex

- Choose manageable task boundaries from the current evidence, revise pending tasks after each result, and split work at consequential checkpoints while keeping simple repetitive operations together.

## 1.0.1 — 2026-09-24

### Claude Code

- Recommend starting substantial runs with `/goal Use the rightsize-goal skill to ...`; when a direct skill invocation needs redirection, provide that complete prompt with the user's acceptance conditions and constraints. Bump the plugin to 1.0.1 so installed copies can receive the change.

### Codex

- Clarify direct `$rightsize-goal` invocation as the default usage path and align the Codex plugin version with the 1.0.1 repository release.

## 1.0.0 — 2026-09-24

### Claude Code

- Store the usage ledger and one call/result JSONL log per goal under the current directory's `.rightsize-goal/`; include agent identity, retry reason, measured tokens, and estimated cost, with no new user-wide Rightsize Goal logs.
- One-step requests use the main Claude Code session without agent dispatch or persistent goal setup.
- New `claude-code/` implementation, distributed as a Claude Code plugin with a repository
  marketplace manifest; two commands install it and `claude plugin update rightsize-goal`
  (or marketplace auto-update, off by default for third-party marketplaces) maintains it.
- Plugin version 1.0.0. Earlier installs were pinned at 0.1.0 and never received changes;
  run `claude plugin update rightsize-goal` once to move to 1.0.0. Every later user-facing
  change bumps the version, and CI runs `claude plugin validate --strict`.
- Four subagent roles across Claude Haiku 4.5, Sonnet 5, Opus 5.5, and Fable 5.1 (one role per
  model, each paid role at `high` effort), each pinning model and effort, since the Agent
  tool has no dispatch-time effort override. Simplified before first release from an
  earlier seven-role ladder (a `medium`- and a `high`-effort variant of each paid model);
  see [why these four roles](claude-code/docs/roles.md#why-four-roles).
- Roles are denied agent-spawning tools, so the escalation gate cannot be bypassed by a
  worker escalating itself; a packaged test asserts this.
- Skill resolves plugin-prefixed and bare role names at run time, and refuses to substitute
  a default agent when a role is unavailable.
- Session persistence built on `/goal` and the `ProposeGoal` tool, with the session-scoped
  limits stated rather than implied.
- Usage accounting reads per-subagent transcripts directly, so each assignment is measured
  rather than apportioned. Deduplicates streaming records by request id, records the served
  model and effort rather than the requested ones, and prices all five rate categories
  including both cache-write TTLs.
- Explicit unavailable results for expired tariffs, unpriced models, missing cache TTL
  splits, records without request identity, and missing or ambiguous transcripts.
- Optional file installer with copy, symlink, verification, conflict backups, and rollback;
  it writes no configuration.
- Public installation, usage, role-design, accounting, and release documentation.
- Supports both dispatch modes: Agent Teams teammates (reusable via `SendMessage`, resolved by
  the `agentName`/`teamName` recorded in their own session transcript) and plain in-process
  subagents, with the workflow adapting and reporting when reuse is unavailable.
- Effort levels set from Anthropic's published per-model guidance rather than inherited from
  the Codex tiers: each paid role runs at `high`. That is the documented API default for
  Sonnet 5 and Fable 5.1; Opus 5.5 defaults to `medium`, and the senior role deliberately
  runs one level above it so a documented Opus struggle reflects a serious attempt. `xhigh`
  and `max` are deliberately unused, so no role runs above a default session.
- The senior role runs on Claude Opus 5.5, which the `opus` alias now resolves to
  (`claude-opus-5-5`); the tariff adds its rates and keeps `claude-opus-5` for pricing
  earlier transcripts. Fable 5.1 stays as a break-glass tier, used only after documented
  Opus struggle.
- Fable escalation evidence comes from a dispatched Opus-tier child whose documented struggle
  the coordinator relays and judges, rather than from the coordinator's own work. A cheaper
  tier's failure remains insufficient however it is relayed.
- Coordinator requirement stated as capability rather than a specific model.
- Guards against acceptance checks that silently verify nothing, and requires workers to report
  the literal command and its real output rather than prose shaped like runner output.
- Windows/macOS/Linux CI matrix for Python 3.11 and 3.13.
- **Known issue (Claude Code only):** a Claude Code bug
  ([anthropics/claude-code#80569](https://github.com/anthropics/claude-code/issues/80569))
  makes an Agent Teams teammate silently inherit the coordinator's own session effort instead
  of its role's pinned `effort`; `model` crosses over correctly. Effort is honored on the
  plain in-process subagent path. Documented in
  [Agent Teams](claude-code/docs/install.md#agent-teams-recommended). No equivalent in the
  Codex implementation, which has no teammate dispatch mode.

### Codex

- Add a Codex marketplace entry that installs the Codex skill instead of the Claude Code plugin; the five custom agents still require `codex/install.py`.
- Store the usage ledger and one call/result JSONL log per goal under the current directory's `.rightsize-goal/`; include agent identity, retry reason, measured tokens, and estimated cost, with no new user-wide Rightsize Goal logs.
- Codex skill with five model/effort-specific roles and evidence-based escalation; GPT-6 Luna and Sol replace their 5.6 counterparts. The roster is junior, midlevel, senior (Sol/medium), staff (Sol/high), and principal (Astra/medium); the Terra and Astra/low tiers are retired.
- Route known moderate work directly to Sol/medium rather than a Luna trial; allow Luna
  factual research that has clear sources and no material judgment call.
- Use the Sol/high staff engineer as the strongest first pass for the most complex
  work where Astra escalation is most at risk; Astra is one medium-effort principal
  engineer role.
- Report the complete known cost of linked rework/escalation chains by initial route.
- One-step requests use the main Codex thread without agent dispatch or persistent goal setup.
- Persistent completion gate with time/iteration bounds and saved run state.
- Local task usage ledger and versioned API-equivalent estimates.
- Copy installation by default, contributor symlinks, verification, replacement
  backups, and opt-in legacy configuration registration.
- Protect installation sources, roll back partial copies and verification failures,
  and require explicit replacement when changing install method.
- Preserve unknown telemetry attribution when a turn omits model/effort labels.
- Public installation, usage, accounting, contribution, and release documentation.
- Windows/macOS/Linux CI matrix for Python 3.11 and 3.13.
