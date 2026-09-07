# Rightsize Goal

Rightsize Goal is a cost-aware agent workflow that treats delegated agents like an
engineering team. A coordinator assigns bounded work to the lowest-cost role likely to
succeed, measures task-level token usage and API-equivalent cost, learns from accepted work
and rework, and reserves the most expensive model for hard problems after documented
difficulty at the tier below.

This repository is organized by host. Each implementation documents its own models, tools,
installation, and limitations; neither assumes the other's APIs.

- [`claude-code/`](claude-code/) — the Claude Code implementation: a plugin with one skill
  and seven subagent roles across Haiku 4.5, Sonnet 5, Opus 5, and Fable 5.1.
- [`codex/`](codex/) — the Codex implementation: a skill, seven agent roles, and installers.

## Claude Code

Two commands, from inside Claude Code:

```text
/plugin marketplace add burnsbert/rightsize-goal
/plugin install rightsize-goal@rightsize-goal
```

Then start a goal:

```text
/model opus
/effort medium
/rightsize-goal:rightsize-goal Add CSV export to the reports page.
Acceptance: exported rows match the active filters and tests pass.
```

See the [Claude Code guide](claude-code/README.md) for a manual install, the role table,
and how to check model access. [Usage](claude-code/docs/usage.md) covers acceptance
criteria, `/goal`, time bounds, stopping, and resuming. [Why these seven
roles](claude-code/docs/roles.md) explains the tier boundaries.
[Accounting](claude-code/docs/accounting.md) explains what is measured and what stays local.

## Codex

```sh
git clone https://github.com/burnsbert/rightsize-goal.git
cd rightsize-goal
sh codex/install.sh && sh codex/install.sh --verify
```

See the [Codex installation and usage guide](codex/README.md) for copy, source archive, and
contributor symlink installation, a first goal, and the model requirements.
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
