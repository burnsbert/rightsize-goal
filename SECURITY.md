# Security and privacy

Do not post credentials, private source, transcripts, or sensitive reproduction
data in public issues. Use the repository's GitHub **Report a vulnerability** flow
if private vulnerability reporting is enabled. If it is unavailable, open a minimal
issue requesting a private contact route without publishing exploit details or
private data.

Installation writes to user-selected local skill and agent directories. The Codex installer
can additionally edit Codex configuration in legacy mode; the Claude Code installer writes
no configuration at all. Review changes and use the least permissions needed.

Both workflows inherit their host's permissions and enforce no independent sandbox or
spending cap. Delegated workers are constrained by their role definitions — under Claude
Code they are denied agent-spawning tools and are instructed not to commit, push, publish,
or send external messages unless an assignment explicitly authorizes it — but a role
definition is a configuration file, not a security boundary. Treat a persistent goal as
work performed under your own account with your own permissions.

The accounting helpers make no network requests. They read local transcripts to extract
token counters and model labels, skipping lines without usage counters so that prompts,
responses, and file contents are not parsed into the ledger. Evidence strings, lesson text,
project tags, and local logs can still contain sensitive information if the coordinator
writes it there. See local data and accounting for
[Codex](codex/docs/accounting.md) and [Claude Code](claude-code/docs/accounting.md).

Only the current release is intended to receive fixes; no response-time commitment
or security support SLA is offered.
