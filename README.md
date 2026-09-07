# Rightsize Goal

Rightsize Goal is a cost-aware Codex workflow that treats delegated agents like an engineering team. A Sol/medium coordinator assigns bounded work to the lowest-cost role likely to succeed, measures task-level token usage and API-equivalent cost, learns from accepted work and rework, and reserves Astra for hard problems after documented Sol difficulty.

This repository is organized by host:

- [`codex/`](codex/) contains the working Codex skill, agent roles, installers, and tests.
- `claude-code/` is reserved for a future Claude Code implementation and is not included yet.

See the [Codex installation and usage guide](codex/README.md).

Start there for copy, source archive, and contributor symlink installation, a first
goal, and the model requirements. [Usage](codex/docs/usage.md) explains acceptance
criteria, time bounds, stopping, and resuming. [Accounting](codex/docs/accounting.md)
explains what is measured and which data stays local. Savings are task-dependent,
and the workflow does not guarantee uninterrupted execution or a spending cap.

Released under the [MIT License](LICENSE), copyright 2026 Eric Burns.
See [contributing](CONTRIBUTING.md), [security](SECURITY.md), and the
[changelog](CHANGELOG.md). This is an independent community project.
