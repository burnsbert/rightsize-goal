# Contributing

Rightsize Goal is licensed under [MIT](LICENSE). Contributions are welcome under
the same license. Include only material you have the right to contribute; retain
required third-party attribution if introducing outside code or assets.

Keep host implementations separate: `codex/` owns Codex runtime integration;
the planned `claude-code/` implementation must document its own tools, models,
installation, and limitations. Do not assume one host exposes the other's APIs.

Use Python 3.11+; the Codex helpers use only the standard library. From the root:

```text
python -m unittest discover -s codex/tests -p "test_*.py"
```

Use temporary destination directories for installer development. Do not test
failure/rollback logic against your real Codex configuration. For deliberate local
workflow development, see the [symlink instructions](codex/docs/install.md).

Changes to routing must preserve explicit model/effort choices, evidence-backed
escalation, acceptance checks, and honest unavailable usage. Add regression tests
for consequential behavior changes. Document user-visible flags and compatibility
changes in the same pull request. Never commit session transcripts, credentials,
usage databases, project scratch files, or private configuration backups.

PRs should explain the problem, resulting behavior, checks run, and limitations.
See the [release checklist](codex/docs/release.md) before tagging a release.
