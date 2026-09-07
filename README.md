# Rightsize Goal

Rightsize Goal is a cost-aware Codex workflow that treats delegated agents like an engineering team. A Sol/medium coordinator assigns bounded work to the lowest-cost role likely to succeed, measures task-level token usage and API-equivalent cost, learns from accepted work and rework, and reserves Astra for hard problems after documented Sol difficulty.

This repository is organized by host:

- [`codex/`](codex/) contains the working Codex skill, agent roles, installers, and tests.
- `claude-code/` is reserved for a future Claude Code implementation and is not included yet.

See the [Codex installation and usage guide](codex/README.md).
