# Rightsize Goal

Rightsize Goal is a cost-aware agent workflow that treats delegated agents like an
engineering team. A coordinator assigns bounded work to the lowest-cost role likely to
succeed, measures task-level token usage and API-equivalent cost, learns from accepted work
and rework, and reserves the most expensive model for hard problems after documented
difficulty at the tier below.

This repository is organized by host. Each implementation documents its own models, tools,
installation, and limitations; neither assumes the other's APIs.

- [`claude-code/`](claude-code/) — the Claude Code implementation: a plugin with one skill
  and five subagent roles across Haiku 4.5, Sonnet 5, Opus 5.5, and Fable 5.1, including an
  independent validator.
- [`codex/`](codex/) — the Codex implementation: a skill, five agent roles, and installers.

## Claude Code

### Install

Run these commands inside Claude Code:

```text
/plugin marketplace add burnsbert/rightsize-goal
/plugin install rightsize-goal@rightsize-goal
```

To receive updates, enable auto-update for the `rightsize-goal` marketplace under `/plugin` →
**Marketplaces**, or run `claude plugin update rightsize-goal` from a terminal.

### Use

Open Claude Code in the project you want to change, choose a capable coordinator, and
give it the goal:

```text
/model opus
/effort medium
/rightsize-goal:rightsize-goal Add CSV export to the reports page. The export must match the active filters and its tests must pass.
```

The plugin keeps the session working until an independent validator confirms the goal is
met: the persistence of `/goal`, with each task routed to the cheapest capable model. Say
"pause" to stop and "resume" to pick it back up. Running it under Claude Code's own
`/goal Use the rightsize-goal skill to ...` also works, and a manual skill install
(`/rightsize-goal`) relies on that for persistence.

See the [Claude Code guide](claude-code/README.md) for a manual install, the role table,
and how to check model access. [Usage](claude-code/docs/usage.md) covers acceptance
criteria, persistence, time bounds, pausing, and resuming. [Why these
roles](claude-code/docs/roles.md) explains the tier boundaries.
[Accounting](claude-code/docs/accounting.md) explains what is measured and what stays local.

## Codex

### Install

For the complete skill and five-agent workflow:

```sh
git clone https://github.com/burnsbert/rightsize-goal.git
cd rightsize-goal
sh codex/install.sh && sh codex/install.sh --verify
```

### Use

Open Codex in the project you want to change. Select `gpt-6-sol` with medium
reasoning for the coordinator when available, and select full access before
delegating. All five workers default to full access and live web research; the
parent session's active permission settings can override their defaults.
See the [Codex permission setup](codex/README.md#run), then ask:

```text
Use $rightsize-goal to add regression tests for this project's configuration parser.
Acceptance: cover invalid input and defaults; all existing tests pass.
Scope: tests only; do not change production code.
```

For substantial work, Rightsize Goal starts a native Codex goal when the goal
tools are available; you do not need to type `/goal` first. You can also start
one explicitly with `/goal Use $rightsize-goal to <objective>`, followed by
your acceptance conditions. A short, one-step request runs directly. If native
goal tools are unavailable, the skill can
continue in the current session using its saved project state, but automatic
continuation is unavailable.

See the [Codex installation and usage guide](codex/README.md) for copy, source archive, and
contributor symlink installation, the skill-only Codex marketplace option, a first goal,
and the model requirements.
[Usage](codex/docs/usage.md) explains acceptance criteria, time bounds, stopping, and
resuming. [Accounting](codex/docs/accounting.md) explains what is measured and which data
stays local.

## What it does not promise

Savings are task-dependent. The workflow does not guarantee uninterrupted execution or a
spending cap, and it is not a host-level watchdog. Dollar figures are standard-rate
API-equivalent estimates for comparing routing choices, not bills — a Claude Code
subscription is not billed per token at all.

Released under the [MIT License](LICENSE), copyright 2026 Eric Burns. See
[contributing](CONTRIBUTING.md), [security](SECURITY.md), and the [changelog](CHANGELOG.md).
This is an independent community project, affiliated with neither Anthropic nor OpenAI.
