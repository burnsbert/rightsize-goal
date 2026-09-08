# Changelog

## Unreleased

### Claude Code

- New `claude-code/` implementation, distributed as a Claude Code plugin with a repository
  marketplace manifest; two commands install it and `/plugin update` maintains it.
- Seven subagent roles across Claude Haiku 4.5, Sonnet 5, Opus 5, and Fable 5.1, each
  pinning model and effort, since the Agent tool has no dispatch-time effort override.
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
  the Codex tiers: each paid model pairs `medium` with `high`, the documented API default.
  `xhigh` and `max` are deliberately unused, so every role runs at or below a default session.
- Fable escalation evidence comes from a dispatched Opus-tier child whose documented struggle
  the coordinator relays and judges, rather than from the coordinator's own work. A cheaper
  tier's failure remains insufficient however it is relayed.
- Coordinator requirement stated as capability rather than a specific model.
- Guards against acceptance checks that silently verify nothing, and requires workers to report
  the literal command and its real output rather than prose shaped like runner output.
- Windows/macOS/Linux CI matrix for Python 3.11 and 3.13.

### Codex

- Codex skill with seven model/effort-specific roles and evidence-based escalation.
- Persistent completion gate with time/iteration bounds and saved run state.
- Local task usage ledger and versioned API-equivalent estimates.
- Copy installation by default, contributor symlinks, verification, replacement
  backups, and opt-in legacy configuration registration.
- Protect installation sources, roll back partial copies and verification failures,
  and require explicit replacement when changing install method.
- Preserve unknown telemetry attribution when a turn omits model/effort labels.
- Public installation, usage, accounting, contribution, and release documentation.
- Windows/macOS/Linux CI matrix for Python 3.11 and 3.13.
