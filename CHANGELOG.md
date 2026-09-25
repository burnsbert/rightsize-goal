# Changelog

## Unreleased

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
